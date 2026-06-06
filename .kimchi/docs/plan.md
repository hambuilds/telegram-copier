# XAUUSD Trader Desktop App — Build Plan

## Overview
Convert the existing `telegram-mt5-bot` (Telethon + hardcoded `.env` config) into a standalone **tkinter desktop GUI** application.

**New app directory:** `xauusd-trader-desktop/` (top-level project folder).  
**Entry point:** `xauusd-trader-desktop/trader_app.py`  
**Target artifact:** single `.exe` via PyInstaller (`xauusd-trader-desktop/build_exe.py`).

---

## Existing-code reference (read-only)
- `telegram-mt5-bot/main.py` — `Signal` dataclass, 3-regex parser, MT5 helpers, martingale state machine, Telethon handler.
- `telegram-mt5-bot/config.py` — env-based constants (BASE_LOT, POSITION_A_RATIO, MAGIC_NUMBER, etc.).

---

## Chunk 1 — Config Store (`config_store.py` + tests)

### Files
- `xauusd-trader-desktop/config_store.py`
- `xauusd-trader-desktop/tests/test_config_store.py`

### Interface
```python
from dataclasses import dataclass, field, asdict
from typing import Dict

@dataclass
class TraderConfig:
    mt5_path: str
    mt5_account: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    symbol: str = "XAUUSD"
    symbol_aliases: Dict[str, str] = field(default_factory=lambda: {
        "GOLD": "XAUUSD",
        "XAU/USD": "XAUUSD",
    })
    base_lot: float = 0.01
    martingale_multiplier: float = 2.0
    max_martingale_levels: int = 3
    position_a_ratio: float = 0.60
    position_b_ratio: float = 0.40
    magic_number: int = 20250605
    telegram_bot_token: str = ""
    sl_pips: int = 50
    tp1_pips: int = 25
    tp2_pips: int = 50
    pip_value: float = 0.10
    mt5_connect_retries: int = 5
    mt5_connect_retry_delay: int = 10
    state_file: str = "state.json"
    config_file: str = "config.json"

    def save(self, path: str | None = None) -> None: ...
    @staticmethod
    def load(path: str | None = None) -> "TraderConfig": ...
    def validate(self) -> None: ...   # raises ValueError on bad data
```

### Behaviour
- `save()` serialises to JSON (indent 2).  `load()` deserialises, applies defaults for missing keys.
- `validate()` ensures:
  - `mt5_path` is non-empty.
  - `base_lot` > 0.
  - `position_a_ratio + position_b_ratio` ≈ 1.0 (±0.01).
  - `telegram_bot_token` is non-empty when checked by caller (optional here but required by bot start).
- File paths are resolved relative to the script directory (`Path(__file__).with_name(...)` is **not** used; use `Path.cwd()` / passed path only).

### Acceptance Criteria
1. `TraderConfig.load()` returns a valid object with defaults when file is missing.
2. Round-trip `save()` then `load()` restores identical data.
3. `validate()` raises `ValueError` for bad ratios or zero/negative lot.

---

## Chunk 2 — Signal Parser (`signal_parser.py` + tests)

### Files
- `xauusd-trader-desktop/signal_parser.py`
- `xauusd-trader-desktop/tests/test_signal_parser.py`

### Interface
```python
from dataclasses import dataclass

@dataclass
class Signal:
    action: str      # "BUY" or "SELL"
    symbol: str      # canonical symbol, e.g. "XAUUSD"
    entry: float
    sl: float
    tp1: float
    tp2: float

def parse_signal(text: str, aliases: dict[str, str]) -> Signal | None: ...
```

### Behaviour
- Port the three regex patterns from `main.py` (`MULTI_LINE_RE`, `COMPACT_RE`, `SIMPLE_RE`) with minor cleanup.
- Accept `aliases` mapping (e.g. `"GOLD" → "XAUUSD"`) instead of a hardcoded module constant.
- Return `None` when no pattern matches.
- Strip text and upper-case action.

### Acceptance Criteria
1. Parses existing test cases:
   - Multi-line: `BUY XAUUSD @ 2350.00\nSL: 2345.00\nTP1: 2352.50\nTP2: 2355.00`
   - Compact: `Gold Buy 2350.00 | SL 2345.00 | TP1 2352.50 | TP2 2355.00`
   - Single-line: `SELL XAU/USD 2350.00 / SL 2345.00 / TP1 2352.50 / TP2 2355.00`
2. Aliases correctly map `GOLD` → `XAUUSD`.
3. Returns `None` for empty / non-signal strings.

---

## Chunk 3 — MT5 Engine (`mt5_engine.py` + tests)

### Files
- `xauusd-trader-desktop/mt5_engine.py`
- `xauusd-trader-desktop/tests/test_mt5_engine.py`

### Interface
```python
from config_store import TraderConfig
from signal_parser import Signal

class MT5Engine:
    def __init__(self, config: TraderConfig) -> None: ...
    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...
    def normalize_lot(self, lot: float) -> float: ...
    def send_market_order(self, action: str, symbol: str, lot: float,
                          entry_price: float, sl_price: float, tp_price: float,
                          magic: int) -> int | None: ...   # returns ticket or None
    def close_position(self, ticket: int) -> bool: ...
    def process_signal(self, signal: Signal) -> bool: ...
    def advance_martingale(self, win: bool) -> None: ...
```

### Behaviour
- Lazy-import `MetaTrader5` so tests can run without the package installed.
- `connect()` calls `mt5.initialize(path=...)` and optionally `mt5.login()`.
- `process_signal(signal)`:
  1. Load martingale state from JSON (`state_file`).
  2. Compute `lot_a = normalize_lot(state.lot * config.position_a_ratio)`  
     `lot_b = normalize_lot(state.lot * config.position_b_ratio)`.
  3. Fallback to `volume_min` if rounding collapses lot to 0.
  4. Send two market orders with TP1 and TP2 respectively.
  5. Return `True` only if **both** orders succeed.
- `advance_martingale(win)`:
  - Win → reset level 0, base lot.
  - Loss → increment level, lot *= multiplier (capped at `max_martingale_levels`).
  - Persist state to JSON.

### Acceptance Criteria
1. `connect()` returns `True` when mocked MT5 returns success.
2. `normalize_lot()` rounds to the mocked symbol’s `volume_step`.
3. `process_signal()` sends two `order_send` calls with correct volumes and TPs.
4. `advance_martingale(False)` doubles lot up to max level, then resets.
5. State JSON is created/updated after every martingale advance.

---

## Chunk 4 — Telegram Listener (`telegram_bot.py` + tests)

### Files
- `xauusd-trader-desktop/telegram_bot.py`
- `xauusd-trader-desktop/tests/test_telegram_bot.py`

### Interface
```python
import queue
from config_store import TraderConfig
from signal_parser import Signal

class SignalBot:
    def __init__(self, token: str, signal_queue: queue.Queue[Signal],
                 aliases: dict[str, str]) -> None: ...
    def start(self) -> None: ...   # non-blocking; starts background thread
    def stop(self) -> None: ...
    def is_running(self) -> bool: ...
```

### Behaviour
- Uses `python-telegram-bot` (v20+ / `Application.builder().token(...).build()`).
- Handler for plain text messages:
  1. Extract `update.message.text`.
  2. Call `parse_signal(text, self.aliases)`.
  3. If valid, put into `signal_queue`.
- `start()` creates an `internal` thread that calls `application.run_polling()` with `stop_signals=()` so it doesn't steal Ctrl+C from the GUI.
- `stop()` calls `application.stop()` / `shutdown()` and joins the background thread.

### Acceptance Criteria
1. `start()` creates a thread and marks `is_running() == True`.
2. Mocked text update is parsed and enqueued.
3. `stop()` cleanly shuts down the thread (joins within 5 s).

---

## Chunk 5 — Desktop GUI (`trader_app.py` + tests)

### Files
- `xauusd-trader-desktop/trader_app.py`
- `xauusd-trader-desktop/tests/test_trader_app.py`

### Interface
```python
import tkinter as tk
from config_store import TraderConfig
from mt5_engine import MT5Engine
from telegram_bot import SignalBot

class TraderApp(tk.Tk):
    def __init__(self) -> None: ...
    def run(self) -> None: ...   # alias for self.mainloop()
```

### Behaviour
- On start-up, checks for `config.json`.  If missing, shows a **modal SetupWizard** (`tk.Toplevel`) with entry fields for:
  - MT5 terminal path, account, password, server.
  - Symbol (default `XAUUSD`).
  - Base lot, martingale multiplier, max levels.
  - Position split ratios (A %, auto-compute B % = 100 - A).
  - Telegram bot token.
  - Magic number.
  - Save / Cancel buttons.
- Main window contains a `ttk.Notebook` with three tabs:
  1. **Dashboard** — Labels showing:
     - MT5 connection status (connect button + status label).
     - Telegram bot status (start/stop button + status label).
     - Current martingale level & lot.
     - Latest received signal (action, symbol, entry, SL, TP1, TP2).
  2. **Manual Entry** — Entry widgets for:
     - Action (`BUY` / `SELL` `ttk.Combobox`).
     - Symbol (default from config, editable).
     - Entry Price, SL, TP1, TP2, Lot.
     - Execute button → calls `engine.process_signal(...)`.
  3. **Log** — `ScrolledText` widget (read-only) fed by a custom `logging.Handler` that calls `widget.after(0, ...)` to keep thread-safe.
- Background integration:
  - `MT5Engine` created on startup (not connected yet).
  - `SignalBot` created when user presses "Start Bot".
  - `self.after(100, self._poll_queue)` drains `signal_queue` and passes Signals to `engine.process_signal()`.
- Graceful shutdown (`WM_DELETE_WINDOW`) stops bot, disconnects MT5, destroys window.

### Acceptance Criteria
1. `python trader_app.py` launches without exception.
2. Setup wizard appears on first run; saving writes `config.json`.
3. Dashboard shows status labels and buttons work.
4. Manual Entry sends a mocked `process_signal` with correct values.
5. Log tab displays at least one test log line.
6. Window close does not leave dangling threads.

---

## Chunk 6 — Packaging & Documentation

### Files
- `xauusd-trader-desktop/build_exe.py`
- `xauusd-trader-desktop/requirements.txt`
- `xauusd-trader-desktop/README.md`
- `xauusd-trader-desktop/tests/__init__.py` (if needed)

### Interface
```python
# build_exe.py
import PyInstaller.__main__

def build() -> None: ...

if __name__ == "__main__":
    build()
```

### Behaviour
- `build_exe.py` invokes PyInstaller with at least these arguments:
  ```python
  PyInstaller.__main__.run([
      "--onefile",
      "--windowed",
      "--name", "XAUUSDTrader",
      "trader_app.py",
  ])
  ```
- `requirements.txt` lists exact PyPI packages:
  ```
  python-telegram-bot>=20.0
  MetaTrader5
  pyinstaller
  ```
- `README.md` contains:
  - What the app does.
  - Prerequisites (Python 3.10+, MetaTrader 5 installed, Telegram bot token).
  - Installation (`pip install -r requirements.txt`).
  - First-run setup wizard walkthrough.
  - Running the app (`python trader_app.py`).
  - Building the `.exe` (`python build_exe.py`).

### Acceptance Criteria
1. `pip install -r requirements.txt` succeeds (or at least the file is syntactically valid).
2. `python build_exe.py` runs `PyInstaller` without crashing.
3. `README.md` is complete and accurate.

---

## Execution Order
1. **Chunk 1** (config) and **Chunk 2** (parser) are independent → **may run in parallel.**
2. **Chunk 3** (engine) depends on Chunk 1.
3. **Chunk 4** (bot) depends on Chunk 2.
4. **Chunk 5** (GUI) depends on Chunks 1–4.
5. **Chunk 6** (packaging) depends on Chunk 5.

## Test Strategy
- Each chunk ships its own `unittest` file.
- For `mt5_engine` and `telegram_bot`, use `unittest.mock` to mock the external libraries (`MetaTrader5`, `telegram.ext.Application`) so tests run in CI.
- `test_trader_app.py` uses `unittest.mock` to replace `MT5Engine` and `SignalBot` with dummy implementations, verifying GUI behaviour without launching MT5 or Telegram.
- Run all tests with `python -m unittest discover xauusd-trader-desktop/tests -v`.
