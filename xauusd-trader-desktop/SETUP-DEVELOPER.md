# Developer Setup Guide

> How to set up the XAUUSD Trader Desktop app from source on your PC.

---

## What You Need First

| Item | Minimum Version | How to Check |
|------|----------------|--------------|
| Python | 3.10+ | Open CMD / Terminal and run: `python --version` |
| Git | Any | `git --version` |
| MetaTrader 5 | Latest | Must be installed and you know the path to `terminal64.exe` |

---

## Step 1 — Download the Code

Open a terminal (CMD or PowerShell on Windows; Terminal on Linux/Mac) and run:

```bash
git clone https://github.com/hambuilds/telegram-copier.git
cd telegram-copier/xauusd-trader-desktop
```

---

## Step 2 — Create a Virtual Environment

Keeping the project in its own environment avoids package conflicts.

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You will see `(venv)` at the start of your prompt when it is active.

---

## Step 3 — Install Dependencies

All required packages are listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

This installs:
- `python-telegram-bot` (receives signals from Telegram)
- `MetaTrader5` (talks to MT5)
- `pyinstaller` (builds the `.exe` for your friend)

---

## Step 4 — Run the App

```bash
python trader_app.py
```

The first time you run it, the **Setup Wizard** opens automatically.

1. **MT5 Settings** — paste the full path to `terminal64.exe` (or the Linux/Mac equivalent), plus your account number, password and server.
2. **Trading Settings** — double-check the symbol is `XAUUSD`, set your base lot and martingale preferences.
3. **Telegram Bot** — paste the token you got from [@BotFather](https://t.me/BotFather).
4. Click **Save**.

The dashboard opens. Click **Connect** → **Start Bot** to go live.

---

## Step 5 — Run the Tests

```bash
python -m unittest discover tests -v
```

All tests should pass before you build the `.exe`.

---

## Step 6 — Build the .exe for Your Friend

```bash
python build_exe.py
```

When PyInstaller finishes, the ready-to-share file is inside the `dist` folder:

- **Windows:** `dist/XAUUSDTrader.exe`
- **Linux / macOS:** `dist/XAUUSDTrader`

Copy that single file and send it to your friend. They do not need Python.

---

## Troubleshooting

| Problem | Quick Fix |
|---------|-----------|
| `pip` not found | Re-install Python and tick **"Add to PATH"** during install |
| `MetaTrader5` install fails | Make sure MT5 is already installed on this PC |
| App opens then closes instantly | Check the `Log` tab — a missing MT5 path is the most common cause |
| Setup wizard keeps re-appearing | Ensure `config.json` was created next to `trader_app.py` |
| Tests fail | Make sure you activated the virtual environment before running tests |

---

## Folder Cheat-Sheet

```
xauusd-trader-desktop/
  trader_app.py        # Launch this to run the app
  config_store.py      # Where settings are saved
  signal_parser.py     # How Telegram text becomes a trade
  format_manager.py    # (new) Choose or build signal formats
  mt5_engine.py        # Sends orders to MetaTrader 5
  telegram_bot.py      # Listens for Telegram messages
  build_exe.py         # Run this to create the .exe
  tests/               # Unit tests
```
