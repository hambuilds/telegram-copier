"""
config.py — All tunable settings for the Telegram-to-MT5 signal copier bot.
All values fall back to sensible defaults when the matching env var is unset.
"""

import os

# ── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_API_ID: int = int(os.getenv("TG_API_ID", 0))
TELEGRAM_API_HASH: str = os.getenv("TG_API_HASH", "")
TELEGRAM_CHANNELS: list[str] = [
    ch.strip()
    for ch in os.getenv("TG_CHANNELS", "").split(",")
    if ch.strip()
]
TELEGRAM_SESSION_NAME: str = os.getenv("TG_SESSION_NAME", "telegram_mt5_bot")

# ── MetaTrader 5 ─────────────────────────────────────────────────────────────
MT5_ACCOUNT: int = int(os.getenv("MT5_ACCOUNT", 0))
MT5_PASSWORD: str = os.getenv("MT5_PASSWORD", "")
MT5_SERVER: str = os.getenv("MT5_SERVER", "")
MT5_PATH: str = os.getenv(
    "MT5_PATH",
    "C:/Program Files/MetaTrader 5/terminal64.exe",
)

# ── Trading ──────────────────────────────────────────────────────────────────
SYMBOL: str = os.getenv("SYMBOL", "XAUUSD")

# Allowed aliases that map to the canonical XAUUSD symbol
SYMBOL_ALIASES: dict[str, str] = {
    "GOLD": "XAUUSD",
    "XAU/USD": "XAUUSD",
    "XAUUSD": "XAUUSD",
}

BASE_LOT: float = float(os.getenv("BASE_LOT", 0.01))
MARTINGALE_MULTIPLIER: float = float(os.getenv("MARTINGALE_MULTIPLIER", 2.0))
MAX_MARTINGALE_LEVELS: int = int(os.getenv("MAX_MARTINGALE_LEVELS", 3))

# Pip values (XAUUSD: 1 pip = 0.10 in price terms)
SL_PIPS: int = 50
TP1_PIPS: int = 25
TP2_PIPS: int = 50
PIP_VALUE_XAUUSD: float = 0.10  # 1 decimal place = 1 pip for gold

# Position split ratios
POSITION_A_RATIO: float = 0.60  # 60 % → TP1
POSITION_B_RATIO: float = 0.40  # 40 % → TP2

# ── Retry / Error Handling ───────────────────────────────────────────────────
MT5_CONNECT_RETRIES: int = 5
MT5_CONNECT_RETRY_DELAY: int = 10  # seconds

# ── State ────────────────────────────────────────────────────────────────────
STATE_FILE: str = os.getenv("STATE_FILE", "state.json")

# ── Magic numbers (MT5) ───────────────────────────────────────────────────────
MAGIC_NUMBER: int = 20250605  # identifying our orders in MT5