# XAUUSD Trader Desktop Project Exploration

## 1. Overall Project Structure and Files

```
xauusd-trader-desktop/
├── trader_app.py          # GUI entry point (currently empty/placeholder)
├── config_store.py        # Configuration persistence (TraderConfig dataclass)
├── signal_parser.py       # Signal text parsing (BUY/SELL with entry, SL, TP1, TP2)
├── mt5_engine.py          # MetaTrader 5 order engine and martingale state
├── telegram_bot.py        # Telegram signal listener (python-telegram-bot wrapper)
├── build_exe.py           # PyInstaller build script for standalone executable
├── requirements.txt       # Python dependencies
├── README.md              # Project overview and usage instructions
├── SETUP.md               # Detailed beginner setup guide
└── tests/                 # Unit tests directory (empty __init__.py expected)
```

Note: `trader_app.py` was found to be empty (2 bytes) during exploration, suggesting the actual GUI implementation might be elsewhere or the file is a placeholder.

## 2. Technology Stack

The project uses:
- **Python 3.10+** as the core language
- **Desktop GUI** - Based on the documentation mentioning tabs (Dashboard, Manual Entry, Log) and the use of `python-telegram-bot` and `MetaTrader5`, the GUI is likely built with a Python GUI framework (possibly Tkinter, PyQt, or CustomTkinter) though the exact framework isn't visible in the explored files.
- **Telegram Integration** - `python-telegram-bot>=20.0` for bot functionality
- **MetaTrader 5 Integration** - `MetaTrader5` Python package for MT5 terminal communication
- **Build/Packaging** - `pyinstaller` for creating standalone executables
- **Configuration** - JSON-based config file (`config.json`) and state file (`state.json`)

## 3. Telegram Authentication/Bot Token Handling

- Telegram bot token is collected during the Setup Wizard and stored in `config.json`
- The token is accessed via `TraderConfig.telegram_bot_token`
- In `telegram_bot.py`, the `SignalBot` class takes the token as a constructor parameter
- The token is used to build the Telegram application: `Application.builder().token(self._token).build()`
- The bot runs in a background daemon thread via `_run_polling()` which calls `asyncio.run(self._app.run_polling(stop_signals=()))`
- Message handling: `_on_message` callback parses incoming text messages and puts valid `Signal` objects onto a `signal_queue`

## 4. MT5 Connection Handling

- MT5 connection parameters (path, account, password, server) are stored in `TraderConfig`
- The `MT5Engine` class in `mt5_engine.py` handles all MT5 interactions
- Connection process:
  1. `MT5Engine.connect()` calls `mt5.initialize(path=self.config.mt5_path)`
  2. If account credentials are provided, it calls `mt5.login()` with account, password, and server
  3. Connection status tracked via `self._connected` flag
  4. Disconnection via `mt5.shutdown()`
- The MT5 package is lazily imported via `_lazy_mt5()` to allow testing without MT5 installed
- Order execution: `send_market_order()` constructs and sends trade requests via `mt5.order_send()`
- Position closing: `close_position()` sends opposing trades to close positions

## 5. Build/Packaging Setup

- Handled by `build_exe.py` which uses PyInstaller
- Build command: `python build_exe.py`
- PyInstaller arguments:
  - `--onefile`: Bundle everything into a single executable
  - `--windowed`: No console window (GUI app)
  - `--name`: "XAUUSDTrader"
  - Entry point: `trader_app.py`
- Output: `dist/XAUUSDTrader.exe` (Windows) or `dist/XAUUSDTrader` (Linux/macOS)
- The standalone app includes Python interpreter and all dependencies
- First run of the standalone app triggers the Setup Wizard if `config.json` is missing

## 6. Dependencies

From `requirements.txt`:
- `python-telegram-bot>=20.0`: Telegram Bot API wrapper
- `MetaTrader5`: Python package for MetaTrader 5 terminal integration
- `pyinstaller`: For building standalone executables

Additional implicit dependencies (likely installed as sub-dependencies):
- `asyncio` (standard library)
- `queue` (standard library)
- `threading` (standard library)
- `json` (standard library)
- `dataclasses` (standard library for Python 3.7+)

## 7. Entry Points and Key Modules

### Entry Points
1. **Primary**: `trader_app.py` - Main application launcher (GUI entry point)
2. **Build Script**: `build_exe.py` - Creates standalone executable
3. **Potential**: Could be run as `python -m` if structured as a package (but currently flat structure)

### Key Modules
1. **config_store.py** - Manages application configuration (`TraderConfig` dataclass with validation, loading/saving to JSON)
2. **signal_parser.py** - Parses trading signals from Telegram messages using regex patterns (multi-line, compact, simple formats)
3. **mt5_engine.py** - Core MT5 integration:
   - Connection management (`connect`, `disconnect`, `is_connected`)
   - Order execution (`send_market_order`, `close_position`)
   - Lot normalization and validation
   - Martingale state management (persistence to `state.json`)
   - Signal processing (`process_signal` opens dual positions)
4. **telegram_bot.py** - Telegram signal listener:
   - Background polling thread
   - Message handling and signal parsing
   - Queue-based signal delivery to main application
5. **trader_app.py** - (Currently empty) Expected to contain:
   - GUI framework initialization
   - Setup Wizard implementation
   - Main window with tabs (Dashboard, Manual Entry, Log)
   - Integration of MT5Engine and SignalBot
   - Event handling for UI buttons (connect, start/stop bot, manual trades)

## Additional Observations

### Configuration Files
- `config.json`: User configuration (MT5 credentials, Telegram token, trading parameters)
- `state.json`: Martingale state persistence (level and lot size)

### Martingale System
- Implemented in `MT5Engine.advance_martingale()`
- On win: reset to level 0 and base lot
- On loss: increase level and multiply lot by martingale_multiplier
- If max_martingale_levels reached: reset to level 0 and base lot
- State persisted to `state.json`

### Signal Processing Flow
1. Telegram bot receives message → `telegram_bot.py:_on_message`
2. Message parsed via `signal_parser.py:parse_signal` → `Signal` object
3. Signal placed on `queue.Queue` for main thread consumption
4. Main GUI (in `trader_app.py`) retrieves signal and calls `mt5_engine.py:process_signal`
5. `process_signal` loads martingale state, calculates position sizes, sends two orders via `send_market_order`

### Security Considerations
- Sensitive data (MT5 password, Telegram token) stored in plaintext `config.json`
- Documentation warns: "Never share this file — it contains your MT5 password and Telegram token!"
- No encryption or secure credential storage implemented

### Limitations / Placeholders
- `trader_app.py` is currently empty (2 bytes), suggesting the actual GUI code may be missing or this is a stub
- The project appears to be functional based on the detailed documentation, but the GUI implementation is not visible in the explored source files
- Test directory exists but appears empty (no test files visible)

This exploration reveals a well-documented Python desktop application that bridges Telegram trading signals to MetaTrader 5 with automated position sizing and risk management via a martingale strategy.
