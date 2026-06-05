"""
main.py — Telegram-to-MT5 signal copier bot.

Listens to configured Telegram channels for trading signals, parses them,
and executes XAUUSD orders on MetaTrader 5 with TP-split and martingale
recovery.

Usage (normal run):
    python main.py

Usage (unit-test the signal parser):
    python main.py --test
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import config

# Lazy-import heavy/optional deps so parser tests can run without them.
_newmessage = None
_telegramclient = None

def _lazy_telethon():
    global _newmessage, _telegramclient
    if _newmessage is None:
        from telethon import TelegramClient as TC
        from telethon.events import NewMessage as NM
        _telegramclient = TC
        _newmessage = NM
    return _telegramclient, _newmessage

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class Signal:
    action: str      # "BUY" or "SELL"
    symbol: str      # canonical symbol, e.g. "XAUUSD"
    entry: float
    sl: float
    tp1: float
    tp2: float


@dataclass
class MartingaleState:
    level: int       # current martingale level (0 = base lot)
    lot: float       # current base lot for this level


# ── State persistence ─────────────────────────────────────────────────────────


def load_state() -> MartingaleState:
    """Load martingale state from state.json. Returns default state on failure."""
    path = Path(config.STATE_FILE)
    if not path.exists():
        return MartingaleState(level=0, lot=config.BASE_LOT)
    try:
        data = json.loads(path.read_text())
        return MartingaleState(
            level=int(data.get("level", 0)),
            lot=float(data.get("lot", config.BASE_LOT)),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("Failed to load state file: %s — resetting.", exc)
        return MartingaleState(level=0, lot=config.BASE_LOT)


def save_state(state: MartingaleState) -> None:
    """Persist martingale state to state.json."""
    path = Path(config.STATE_FILE)
    try:
        path.write_text(json.dumps(asdict(state), indent=2))
    except OSError as exc:
        log.error("Failed to write state file: %s", exc)


# ── Lazy MT5 import ───────────────────────────────────────────────────────────

_mt5 = None

def _lazy_mt5():
    global _mt5
    if _mt5 is None:
        import MetaTrader5 as mt5_mod
        _mt5 = mt5_mod
    return _mt5


# ── MT5 helpers ───────────────────────────────────────────────────────────────


def mt5_connect() -> bool:
    """Initialise MT5 connection. Returns True on success."""
    mt5 = _lazy_mt5()
    if not mt5.initialize(path=config.MT5_PATH):
        log.error("MT5 initialise() failed: %s", mt5.last_error())
        return False
    if config.MT5_ACCOUNT:
        if not mt5.login(config.MT5_ACCOUNT, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
            log.error("MT5 login failed: %s", mt5.last_error())
            return False
    log.info("MT5 connected.")
    return True


def mt5_wait_connect() -> bool:
    """Retry MT5 connection every config.MT5_CONNECT_RETRY_DELAY seconds."""
    for attempt in range(1, config.MT5_CONNECT_RETRIES + 1):
        if mt5_connect():
            return True
        log.warning(
            "MT5 connection attempt %s/%s failed — retrying in %ss…",
            attempt, config.MT5_CONNECT_RETRIES, config.MT5_CONNECT_RETRY_DELAY,
        )
        time.sleep(config.MT5_CONNECT_RETRY_DELAY)
    log.error("Could not establish MT5 connection after %s attempts.", config.MT5_CONNECT_RETRIES)
    return False


def mt5_normalise_lot(lot: float) -> float:
    """Round lot to the symbol's volume_step using MT5 symbol_info."""
    mt5 = _lazy_mt5()
    info = mt5.symbol_info(config.SYMBOL)
    if info is None:
        log.warning("symbol_info(%s) returned None — using unrounded lot.", config.SYMBOL)
        return round(lot, 2)
    step = info.volume_step
    rounded = round(lot / step) * step
    # MT5 minimum volume check
    if info and rounded < info.volume_min:
        rounded = info.volume_min
    return rounded


def mt5_send_order(
    action: str,
    symbol: str,
    lot: float,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    magic: int,
) -> bool:
    """
    Send a market order (BUY / SELL) on `symbol` with given lot, entry,
    stop-loss, and take-profit prices. Returns True on success.
    """
    mt5 = _lazy_mt5()
    action_type = mt5.TRADE_ACTION_DEAL
    type_trade = mt5.ORDER_TYPE_BUY if action.upper() == "BUY" else mt5.ORDER_TYPE_SELL

    request = {
        "action": action_type,
        "symbol": symbol,
        "volume": lot,
        "type": type_trade,
        "price": entry_price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 10,
        "magic": magic,
        "comment": f"sig_{action.lower()}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    if result is None:
        log.error("order_send returned None for %s %s @ %s", action, symbol, entry_price)
        return False
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        log.error(
            "order_send failed — retcode=%s (%s) comment=%s",
            result.retcode, result.comment, result.comment,
        )
        return False

    log.info(
        "Order sent: %s %s %.2f @ %s | SL=%s TP=%s | ticket=%s",
        action, symbol, lot, entry_price, sl_price, tp_price, result.order,
    )
    return True


def mt5_close_position(ticket: int) -> bool:
    """Close an open position by ticket."""
    mt5 = _lazy_mt5()
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        log.warning("Position %s not found for closing.", ticket)
        return False
    pos = positions[0]
    action_type = mt5.TRADE_ACTION_DEAL
    type_trade = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY

    request = {
        "action": action_type,
        "position": ticket,
        "symbol": pos.symbol,
        "volume": pos.volume,
        "type": type_trade,
        "price": mt5.symbol_info_tick(pos.symbol).bid,
        "deviation": 10,
        "magic": config.MAGIC_NUMBER,
        "comment": "close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        log.error("Close position %s failed: retcode=%s", ticket, result.retcode)
        return False
    log.info("Closed position %s.", ticket)
    return True


# ── Signal parser ─────────────────────────────────────────────────────────────

# Regex patterns for common Telegram signal formats.
#
# Format A — multi-line:
#   BUY XAUUSD @ 2350.00
#   SL: 2345.00
#   TP1: 2352.50
#   TP2: 2355.00
#
# Format B — compact:
#   Gold Buy 2350.00 | SL 2345.00 | TP1 2352.50 | TP2 2355.00
#   XAUUSD BUY 2350.00 SL 2345.00 TP1 2352.50 TP2 2355.00
#   BUY GOLD 2350.00 SL 2345.00 TP1 2352.50 TP2 2355.00

ACTION_RE = re.compile(
    r"\b(BUY|SELL)\b", re.IGNORECASE
)

SYMBOL_RE = re.compile(
    r"\b(XAUUSD|GOLD|XAU/USD)\b", re.IGNORECASE
)

FLOAT_RE = re.compile(r"-?\d+\.?\d*")

# Multi-line: each field on its own line
MULTI_LINE_RE = re.compile(
    r"(?i)\b(BUY|SELL)\s+(XAUUSD|GOLD|XAU/USD)\s*[@\s]\s*(\d+\.?\d*)"
    r".*?SL[:\s]+(\d+\.?\d*)"
    r".*?TP1[:\s]+(\d+\.?\d*)"
    r".*?TP2[:\s]+(\d+\.?\d*)",
    re.IGNORECASE | re.DOTALL,
)

# Compact single-line variants
COMPACT_RE = re.compile(
    r"(?:[-\s]*(?:GOLD|XAUUSD|XAU/USD)\s+)?\b(BUY|SELL)\s+(?:GOLD|XAUUSD|XAU/USD)?\s*(\d+\.?\d*)"
    r"(?:\s*[@\|\/])?\s*SL\s+(\d+\.?\d*)"
    r"(?:\s*[@\|\/])?\s*TP1\s+(\d+\.?\d*)"
    r"(?:\s*[@\|\/])?\s*TP2\s+(\d+\.?\d*)",
    re.IGNORECASE | re.DOTALL,
)

# Simple "BUY XAUUSD @ price" with SL/TP lines following
SIMPLE_RE = re.compile(
    r"^(BUY|SELL)\s+(XAUUSD|GOLD|XAU/USD)\s*[@\s]\s*(\d+\.?\d*)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_signal(text: str) -> Signal | None:
    """
    Parse a Telegram message into a Signal dataclass.

    Tries three patterns in order:
      1. Multi-line  (SL/TP on separate lines)
      2. Compact     (single-line with separators)
      3. Simple      (action + symbol + price, SL/TP lines follow)

    Returns None if no pattern matches.
    """
    text = text.strip()

    # ── Pattern 1: multi-line ───────────────────────────────────────────────
    # Case-fold the whole text once so individual patterns don't need inline flags
    text_lower = text.lower()
    text_upper = text.upper()

    m = MULTI_LINE_RE.search(text)
    if m:
        action, symbol, entry, sl, tp1, tp2 = m.groups()
        return Signal(
            action=action.upper(),
            symbol=config.SYMBOL_ALIASES.get(symbol.upper(), symbol.upper()),
            entry=float(entry),
            sl=float(sl),
            tp1=float(tp1),
            tp2=float(tp2),
        )

    # ── Pattern 2: compact single-line ──────────────────────────────────────
    m = COMPACT_RE.search(text)
    if m:
        action, entry, sl, tp1, tp2 = m.groups()
        # symbol not captured in this pattern — scan for it
        sym_match = SYMBOL_RE.search(text)
        raw_symbol = sym_match.group(1) if sym_match else "XAUUSD"
        return Signal(
            action=action.upper(),
            symbol=config.SYMBOL_ALIASES.get(raw_symbol.upper(), raw_symbol.upper()),
            entry=float(entry),
            sl=float(sl),
            tp1=float(tp1),
            tp2=float(tp2),
        )

    # ── Pattern 3: simple "BUY XAUUSD @ 2350.00" + separate SL/TP lines ────
    m = SIMPLE_RE.search(text)
    if m:
        action, raw_symbol, entry = m.groups()
        sym_canonical = config.SYMBOL_ALIASES.get(raw_symbol.upper(), raw_symbol.upper())
        # look for SL and TP in remaining lines
        sl_match = re.search(r"SL[:\s]+(\d+\.?\d*)", text, re.IGNORECASE)
        tp1_match = re.search(r"TP1[:\s]+(\d+\.?\d*)", text, re.IGNORECASE)
        tp2_match = re.search(r"TP2[:\s]+(\d+\.?\d*)", text, re.IGNORECASE)
        if sl_match and tp1_match and tp2_match:
            return Signal(
                action=action.upper(),
                symbol=sym_canonical,
                entry=float(entry),
                sl=float(sl_match.group(1)),
                tp1=float(tp1_match.group(1)),
                tp2=float(tp2_match.group(1)),
            )

    log.debug("No signal pattern matched for: %s", text[:120])
    return None


def test_signal_parser() -> None:
    """
    Assert that parse_signal() works on at least 3 sample message formats.
    Run with: python main.py --test
    """
    test_cases = [
        # Case 1 — multi-line
        (
            "BUY XAUUSD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n",
            "BUY", "XAUUSD", 2350.00, 2345.00, 2352.50, 2355.00,
        ),
        # Case 2 — compact (Gold alias)
        (
            "Gold Buy 2350.00 | SL 2345.00 | TP1 2352.50 | TP2 2355.00",
            "BUY", "XAUUSD", 2350.00, 2345.00, 2352.50, 2355.00,
        ),
        # Case 3 — compact (XAUUSD uppercase, / separator)
        (
            "SELL XAU/USD 2350.00 / SL 2345.00 / TP1 2352.50 / TP2 2355.00",
            "SELL", "XAUUSD", 2350.00, 2345.00, 2352.50, 2355.00,
        ),
    ]

    for raw, exp_action, exp_symbol, exp_entry, exp_sl, exp_tp1, exp_tp2 in test_cases:
        sig = parse_signal(raw)
        assert sig is not None, f"parse_signal returned None for: {raw!r}"
        assert sig.action == exp_action, f"action: {sig.action!r} != {exp_action!r}"
        assert sig.symbol == exp_symbol, f"symbol: {sig.symbol!r} != {exp_symbol!r}"
        assert abs(sig.entry - exp_entry) < 1e-6, f"entry: {sig.entry} != {exp_entry}"
        assert abs(sig.sl - exp_sl) < 1e-6, f"sl: {sig.sl} != {exp_sl}"
        assert abs(sig.tp1 - exp_tp1) < 1e-6, f"tp1: {sig.tp1} != {exp_tp1}"
        assert abs(sig.tp2 - exp_tp2) < 1e-6, f"tp2: {sig.tp2} != {exp_tp2}"
        print(f"  PASS: {exp_action} {exp_symbol} {exp_entry}")

    print("test_signal_parser: all assertions passed.")


# ── Trading logic ─────────────────────────────────────────────────────────────


def process_signal(signal: Signal) -> None:
    """Execute a parsed signal: validate, apply martingale lot, open two TP positions."""
    if signal.symbol != config.SYMBOL:
        log.info("Ignoring signal for %s (only %s is supported).", signal.symbol, config.SYMBOL)
        return

    state = load_state()

    # Determine lot sizes
    lot_a = mt5_normalise_lot(state.lot * config.POSITION_A_RATIO)
    lot_b = mt5_normalise_lot(state.lot * config.POSITION_B_RATIO)

    # Fallback if rounding collapses both to minimum
    if lot_a <= 0:
        lot_a = mt5.symbol_info(config.SYMBOL).volume_min
    if lot_b <= 0:
        lot_b = mt5.symbol_info(config.SYMBOL).volume_min

    log.info(
        "Executing signal: %s %s @ %s | SL=%s | TP1=%s TP2=%s | lot=%.2f (level=%s)",
        signal.action, signal.symbol, signal.entry,
        signal.sl, signal.tp1, signal.tp2,
        state.lot, state.level,
    )

    ok_a = mt5_send_order(
        action=signal.action,
        symbol=config.SYMBOL,
        lot=lot_a,
        entry_price=signal.entry,
        sl_price=signal.sl,
        tp_price=signal.tp1,
        magic=config.MAGIC_NUMBER,
    )
    ok_b = mt5_send_order(
        action=signal.action,
        symbol=config.SYMBOL,
        lot=lot_b,
        entry_price=signal.entry,
        sl_price=signal.sl,
        tp_price=signal.tp2,
        magic=config.MAGIC_NUMBER,
    )

    if not (ok_a and ok_b):
        log.error("One or both orders failed — see above for retcode details.")
    else:
        log.info("Both positions opened successfully.")


def advance_martingale(win: bool) -> None:
    """
    Update martingale state after a trade result is known.
    - On win: reset to base lot and level 0.
    - On loss: increase level; if max reached, reset to base.
    """
    state = load_state()
    if win:
        state.level = 0
        state.lot = config.BASE_LOT
        log.info("Trade won — martingale reset to level 0, lot=%.2f.", config.BASE_LOT)
    else:
        if state.level < config.MAX_MARTINGALE_LEVELS:
            state.level += 1
            state.lot = round(state.lot * config.MARTINGALE_MULTIPLIER, 4)
            log.info(
                "Trade lost — martingale advanced to level %s, lot=%.4f.",
                state.level, state.lot,
            )
        else:
            # Max level reached — reset
            state.level = 0
            state.lot = config.BASE_LOT
            log.info(
                "Max martingale level (%s) reached — resetting to level 0, lot=%.2f.",
                config.MAX_MARTINGALE_LEVELS, config.BASE_LOT,
            )
    save_state(state)


# ── Telegram event handler ─────────────────────────────────────────────────────


async def on_new_message(event) -> None:
    """Fired by Telethon for every new message in watched channels."""
    message_text = event.message.text or ""
    if not message_text.strip():
        return

    log.debug("Raw message: %s", message_text[:200])

    signal = parse_signal(message_text)
    if signal is None:
        log.debug("Could not parse signal, skipping.")
        return

    process_signal(signal)


# ── Entry point ───────────────────────────────────────────────────────────────


async def main() -> None:
    """Boot the bot: connect MT5, start Telegram listener."""
    if not mt5_wait_connect():
        sys.exit(1)

    if not config.TELEGRAM_API_ID or not config.TELEGRAM_API_HASH:
        log.error("TG_API_ID and TG_API_HASH must be set.")
        sys.exit(1)

    TelegramClient, NewMessageCls = _lazy_telethon()
    client = TelegramClient(
        config.TELEGRAM_SESSION_NAME,
        config.TELEGRAM_API_ID,
        config.TELEGRAM_API_HASH,
    )

    for channel in config.TELEGRAM_CHANNELS:
        client.add_event_handler(on_new_message, NewMessageCls(chats=channel))
        log.info("Listening on Telegram channel: %s", channel)

    log.info("Bot started. Press Ctrl+C to stop.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    if "--test" in sys.argv:
        test_signal_parser()
    else:
        import asyncio
        asyncio.run(main())