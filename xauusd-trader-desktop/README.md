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

## For Friends — Just Double-Click

No Python. No command line. No editing files.

1. Get the single executable file from the developer:
   - **Windows:** `XAUUSDTrader.exe`
   - **Linux:** `XAUUSDTrader`
2. Double-click it.
3. The **Setup Wizard** appears. Fill in your MT5 details and Telegram bot token.
4. Click **Save** — the dashboard opens.
5. Click **Connect** → **Start Bot** — you're live.

📖 See [`SETUP.md`](SETUP.md) for a detailed step-by-step guide with screenshots and troubleshooting.

---

## For Developers — Build from Source

### Prerequisites

| Requirement | Details |
|---|---|
| Python | 3.10 or later |
| MetaTrader 5 | Must be installed and the terminal path known |
| Telegram bot | A bot token obtained via [@BotFather](https://t.me/BotFather) |

### Install & Run

```bash
pip install -r requirements.txt
python trader_app.py
```

### Build the Standalone Executable

```bash
python build_exe.py
```

PyInstaller produces a self-contained binary — no Python needed on the target machine.

| Platform | Output |
|---|---|
| Windows | `dist/XAUUSDTrader.exe` |
| Linux / macOS | `dist/XAUUSDTrader` |

---

## App Overview

### Dashboard Tab

- **MT5 Connect / Disconnect** — link to your MT5 terminal
- **Bot Start / Stop** — listen for Telegram signals
- **Martingale Level & Lot** — current position size and level
- **Latest Signal** — last received action, symbol, entry, SL, TP1, TP2

### Manual Entry Tab

Place a trade without waiting for a Telegram signal:

1. Select **BUY** or **SELL**.
2. Enter symbol, entry price, SL, TP1, TP2, and lot.
3. Click **Execute**.

### Log Tab

Real-time scrollable log of all trading events, errors, and Telegram messages.

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
  SETUP.md             # User-friendly setup guide
  tests/               # Unit tests for all modules
```

---

## Signal Formats

The bot understands three message formats. Just forward signals to your bot:

**Multi-line:**
```
BUY XAUUSD @ 2350.00
SL: 2345.00
TP1: 2355.00
TP2: 2360.00
```

**Compact:**
```
BUY XAUUSD 2350.00 | SL 2345.00 | TP1 2355.00 | TP2 2360.00
```

**Simple:**
```
BUY XAUUSD @ 2350.00
SL: 2345.00
TP1: 2355.00
TP2: 2360.00
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| MT5 connection fails immediately | Verify the `terminal64.exe` path is correct |
| Telegram bot never receives messages | Check the bot token and ensure the bot is added to the channel/group |
| Orders not placed | Ensure MT5 is logged in and auto-trading is enabled |

---

## License

For educational purposes. Trading financial instruments involves risk.
Use with a demo account first.
