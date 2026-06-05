# XAUUSD Trader Desktop App

> Automated XAUUSD signal trading via MetaTrader 5, powered by Telegram signals
> and a martingale position-scaling engine.

## What It Does

- **Listens** for BUY / SELL signals forwarded from a Telegram bot.
- **Parses** multi-line, compact, and single-line signal formats (e.g. `BUY XAUUSD @ 2350.00`).
- **Splits** each signal into two sized positions (A and B) with separate take-profit targets.
- **Executes** orders directly through MetaTrader 5 with configurable SL/TP.
- **Manages** martingale position sizing: double lot after a loss, reset after a win.
- **Provides** a desktop GUI with a dashboard, manual-entry tab, and live log viewer.

---

## Prerequisites

| Requirement | Details |
|---|---|
| Python | 3.10 or later |
| MetaTrader 5 | Must be installed and the terminal path known (e.g. `C:\Program Files\MetaTrader 5\terminal64.exe`) |
| Telegram bot | A bot token obtained via [@BotFather](https://t.me/BotFather). Forward trading signals to the bot. |

---

## Installation

### 1 — Clone or copy the project

```bash
cd xauusd-trader-desktop
```

### 2 — Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate      # Linux / macOS
# venv\Scripts\activate       # Windows
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

> `python-telegram-bot>=20.0` — Telegram bot framework  
> `MetaTrader5` — Python bridge to MetaTrader 5 terminal  
> `pyinstaller` — Bundles the app into a standalone `.exe`

### 4 — Verify MT5 path

The first time the app launches it will ask for the full path to your MT5
`terminal64.exe` (or `terminal.exe` on 32-bit). Keep this path handy.

---

## First-Run Setup Wizard

On the very first launch (`python trader_app.py`) a modal **Setup Wizard**
appears. Fill in every field:

| Field | Description |
|---|---|
| MT5 Terminal Path | Full path to `terminal64.exe` |
| MT5 Account | Trading account number |
| MT5 Password | Account password |
| MT5 Server | Broker server (e.g. `Exness-MT5Real`) |
| Symbol | Trading symbol, default `XAUUSD` |
| Base Lot | Starting lot size, default `0.01` |
| Martingale Multiplier | Lot multiplier after a loss, default `2.0` |
| Max Martingale Levels | Maximum consecutive doublings, default `3` |
| Position A Ratio % | Size of the first position, default `60` |
| Telegram Bot Token | Token from `@BotFather` |
| Magic Number | Unique ID for EA-synced orders, default `20250605` |

Click **Save** to write `config.json` and close the wizard. The app will then
show the main dashboard. Click **Cancel** to exit without saving.

---

## Running the App

```bash
python trader_app.py
```

### Dashboard Tab

- **MT5 Connect / Disconnect** — connect to the MT5 terminal.
- **Bot Start / Stop** — start listening for Telegram signals.
- **Martingale Level & Lot** — current position size and level.
- **Latest Signal** — last received action, symbol, entry, SL, TP1, TP2.

### Manual Entry Tab

Use this tab to send a trade without a Telegram signal:

1. Select **BUY** or **SELL**.
2. Enter symbol, entry price, SL, TP1, TP2, and lot.
3. Click **Execute**.

### Log Tab

A read-only scrollable log shows all trading events, errors, and Telegram
messages in real time.

---

## Building the Standalone `.exe`

```bash
python build_exe.py
```

PyInstaller will produce `dist/XAUUSDTrader.exe` (Windows) or
`dist/XAUUSDTrader` (Linux/macOS). The binary is self-contained and can be
run without a Python installation.

### Output location

```
xauusd-trader-desktop/
  dist/
    XAUUSDTrader.exe    # Windows
    XAUUSDTrader        # Linux / macOS
```

---

## Distributing to Friends

1. **Share the `.exe` from the `dist/` folder.**
2. Tell them the MT5 path, account credentials, and Telegram bot token.
3. On first run they will see the Setup Wizard — no config file needs to be
   pre-shared.
4. The `config.json` is stored next to the `.exe` so each user can have their
   own settings.

> **Tip:** You can rename the `.exe` freely — the app discovers `config.json`
> relative to its own location.

---

## File Structure

```
xauusd-trader-desktop/
  trader_app.py        # GUI entry point
  config_store.py      # Configuration persistence
  signal_parser.py     # Signal text parsing
  mt5_engine.py        # MetaTrader 5 order engine
  telegram_bot.py      # Telegram signal listener
  build_exe.py         # PyInstaller build script
  requirements.txt     # Python dependencies
  README.md            # This file
  tests/               # Unit tests for all modules
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'MetaTrader5'` | Run `pip install -r requirements.txt` |
| MT5 connection fails immediately | Verify the `terminal64.exe` path is correct |
| Telegram bot never receives messages | Check the bot token and ensure the bot is added to the channel/group |
| Orders not placed | Ensure MT5 is logged in and auto-trading is enabled |
| `pyinstaller: command not found` | Install PyInstaller: `pip install pyinstaller` |

---

## License

For educational purposes. Trading financial instruments involves risk.
Use with a demo account first.