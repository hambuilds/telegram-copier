"""
mt5_engine.py — XAUUSD Trader Desktop App
Chunk 3 — MetaTrader 5 Engine

Wraps MT5 connection, lot normalization, order execution, and martingale
state management.  Lazy-imports MetaTrader5 so tests can run without it.

References:
  - Spec:            .kimchi/docs/plan.md  (Chunk 3)
  - Original source: telegram-mt5-bot/main.py  (mt5_* helpers + martingale logic)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path

from config_store import TraderConfig
from signal_parser import Signal

log = logging.getLogger(__name__)

# ── Lazy MT5 import ───────────────────────────────────────────────────────────

_mt5: object = None  # type: ignore[assignment]


def _lazy_mt5():
    global _mt5
    if _mt5 is None:
        import MetaTrader5 as mt5_mod
        _mt5 = mt5_mod
    return _mt5


# ── Martingale state ──────────────────────────────────────────────────────────


@dataclass
class MartingaleState:
    level: int   # current martingale level (0 = base lot)
    lot: float   # current base lot for this level


# ── MT5Engine ─────────────────────────────────────────────────────────────────


class MT5Engine:
    """
    High-level MT5 wrapper for the XAUUSD Trader Desktop app.

    Parameters
    ----------
    config: TraderConfig
        Application configuration (path, account, lot rules, state file, …).
    """

    def __init__(self, config: TraderConfig) -> None:
        self.config = config
        self._connected = False

    # ── Connection ───────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """
        Initialise the MT5 terminal and (optionally) log in to the account.

        Returns
        -------
        bool
            ``True`` when the terminal is ready; ``False`` on failure.
        """
        mt5 = _lazy_mt5()
        if not mt5.initialize(path=self.config.mt5_path):
            log.error("MT5 initialize() failed: %s", mt5.last_error())
            return False

        if self.config.mt5_account:
            if not mt5.login(
                self.config.mt5_account,
                password=self.config.mt5_password,
                server=self.config.mt5_server,
            ):
                log.error("MT5 login failed: %s", mt5.last_error())
                return False

        self._connected = True
        log.info("MT5 connected.")
        return True

    def disconnect(self) -> None:
        """Shut down the MT5 terminal."""
        mt5 = _lazy_mt5()
        mt5.shutdown()
        self._connected = False
        log.info("MT5 disconnected.")

    def is_connected(self) -> bool:
        return self._connected

    # ── Helpers ──────────────────────────────────────────────────────────────

    def normalize_lot(self, lot: float) -> float:
        """
        Round ``lot`` to the symbol's ``volume_step`` using MT5 symbol_info.

        If the rounded value falls below ``volume_min`` the minimum is returned
        instead.

        Parameters
        ----------
        lot: float
            Raw (pre-rounding) lot size.

        Returns
        -------
        float
            Lot rounded to the nearest valid step.
        """
        mt5 = _lazy_mt5()
        info = mt5.symbol_info(self.config.symbol)
        if info is None:
            log.warning(
                "symbol_info(%s) returned None — returning unrounded lot.",
                self.config.symbol,
            )
            return round(lot, 2)

        step = info.volume_step
        rounded = round(lot / step) * step
        if rounded < info.volume_min:
            rounded = info.volume_min
        return rounded

    # ── Order execution ───────────────────────────────────────────────────────

    def send_market_order(
        self,
        action: str,
        symbol: str,
        lot: float,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        magic: int,
    ) -> int | None:
        """
        Send a market order (BUY or SELL) with SL and TP.

        Parameters
        ----------
        action:      "BUY" or "SELL"
        symbol:      MT5 symbol name (e.g. "XAUUSD")
        lot:         Volume to trade
        entry_price: Market entry price
        sl_price:    Stop-loss price
        tp_price:    Take-profit price
        magic:       Magic number for this EA

        Returns
        -------
        int | None
            Order ticket on success; ``None`` on failure.
        """
        mt5 = _lazy_mt5()
        action_type = mt5.TRADE_ACTION_DEAL
        type_trade = (
            mt5.ORDER_TYPE_BUY if action.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        )

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
            log.error(
                "order_send returned None for %s %s @ %s",
                action, symbol, entry_price,
            )
            return None
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(
                "order_send failed — retcode=%s comment=%s",
                result.retcode, result.comment,
            )
            return None

        log.info(
            "Order sent: %s %s %.2f @ %s | SL=%s TP=%s | ticket=%s",
            action, symbol, lot, entry_price, sl_price, tp_price, result.order,
        )
        return result.order

    def close_position(self, ticket: int) -> bool:
        """
        Close an open position by ticket number.

        Returns
        -------
        bool
            ``True`` on success; ``False`` if the position was not found or
            the close request failed.
        """
        mt5 = _lazy_mt5()
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            log.warning("Position %s not found for closing.", ticket)
            return False

        pos = positions[0]
        action_type = mt5.TRADE_ACTION_DEAL
        type_trade = (
            mt5.ORDER_TYPE_SELL
            if pos.type == mt5.ORDER_TYPE_BUY
            else mt5.ORDER_TYPE_BUY
        )

        request = {
            "action": action_type,
            "position": ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": type_trade,
            "price": mt5.symbol_info_tick(pos.symbol).bid,
            "deviation": 10,
            "magic": self.config.magic_number,
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

    # ── Martingale state persistence ──────────────────────────────────────────

    def _load_state(self) -> MartingaleState:
        """Load martingale state from the configured state file."""
        path = Path(self.config.state_file)
        if not path.exists():
            return MartingaleState(level=0, lot=self.config.base_lot)

        try:
            data = json.loads(path.read_text())
            return MartingaleState(
                level=int(data.get("level", 0)),
                lot=float(data.get("lot", self.config.base_lot)),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            log.warning("Failed to load state file: %s — resetting.", exc)
            return MartingaleState(level=0, lot=self.config.base_lot)

    def _save_state(self, state: MartingaleState) -> None:
        """Persist martingale state to the configured state file."""
        path = Path(self.config.state_file)
        try:
            path.write_text(json.dumps(asdict(state), indent=2))
        except OSError as exc:
            log.error("Failed to write state file: %s", exc)

    # ── Signal processing ─────────────────────────────────────────────────────

    def process_signal(self, signal: Signal) -> bool:
        """
        Execute a parsed trading signal by opening two positions
        (one for each TP level).

        Lot sizing follows the martingale state machine:
        - ``lot_a = normalize_lot(state.lot * position_a_ratio)``
        - ``lot_b = normalize_lot(state.lot * position_b_ratio)``

        If rounding collapses a lot to zero, the symbol's ``volume_min`` is
        used as a fallback.

        Parameters
        ----------
        signal: Signal
            Parsed signal containing action, symbol, entry, SL, TP1, TP2.

        Returns
        -------
        bool
            ``True`` only when **both** orders succeed.
        """
        if signal.symbol != self.config.symbol:
            log.info(
                "Ignoring signal for %s (only %s is supported).",
                signal.symbol, self.config.symbol,
            )
            return False

        state = self._load_state()

        # Compute per-position lots
        lot_a = self.normalize_lot(state.lot * self.config.position_a_ratio)
        lot_b = self.normalize_lot(state.lot * self.config.position_b_ratio)

        # Fallback if rounding collapses lot to zero
        mt5 = _lazy_mt5()
        vol_min = mt5.symbol_info(self.config.symbol).volume_min
        if lot_a <= 0:
            lot_a = vol_min
        if lot_b <= 0:
            lot_b = vol_min

        log.info(
            "Executing signal: %s %s @ %s | SL=%s | TP1=%s TP2=%s "
            "| lot=%.2f (level=%s)",
            signal.action, signal.symbol, signal.entry,
            signal.sl, signal.tp1, signal.tp2,
            state.lot, state.level,
        )

        ticket_a = self.send_market_order(
            action=signal.action,
            symbol=self.config.symbol,
            lot=lot_a,
            entry_price=signal.entry,
            sl_price=signal.sl,
            tp_price=signal.tp1,
            magic=self.config.magic_number,
        )

        ticket_b = self.send_market_order(
            action=signal.action,
            symbol=self.config.symbol,
            lot=lot_b,
            entry_price=signal.entry,
            sl_price=signal.sl,
            tp_price=signal.tp2,
            magic=self.config.magic_number,
        )

        if ticket_a is None or ticket_b is None:
            log.error("One or both orders failed — see above for retcode details.")
            return False

        log.info("Both positions opened successfully (tickets %s, %s).", ticket_a, ticket_b)
        return True

    # ── Martingale advance ────────────────────────────────────────────────────

    def advance_martingale(self, win: bool) -> None:
        """
        Update the martingale state machine after a trade result is known.

        - **Win**  → reset to level 0 and ``base_lot``.
        - **Loss** → increment level; if ``max_martingale_levels`` is reached,
                     reset to level 0 and ``base_lot`` instead of compounding.

        The updated state is immediately persisted to ``config.state_file``.

        Parameters
        ----------
        win: bool
            ``True`` when the trade closed profitably.
        """
        state = self._load_state()

        if win:
            state.level = 0
            state.lot = self.config.base_lot
            log.info(
                "Trade won — martingale reset to level 0, lot=%.2f.",
                self.config.base_lot,
            )
        else:
            if state.level < self.config.max_martingale_levels:
                state.level += 1
                state.lot = round(state.lot * self.config.martingale_multiplier, 4)
                log.info(
                    "Trade lost — martingale advanced to level %s, lot=%.4f.",
                    state.level, state.lot,
                )
            else:
                state.level = 0
                state.lot = self.config.base_lot
                log.info(
                    "Max martingale level (%s) reached — resetting to level 0, lot=%.2f.",
                    self.config.max_martingale_levels, self.config.base_lot,
                )

        self._save_state(state)