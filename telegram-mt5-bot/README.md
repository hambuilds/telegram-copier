# Telegram-to-MT5 Signal Copier Bot

Copies trading signals from one or more Telegram channels and automatically
executes **XAUUSD only** trades on MetaTrader 5, with a TP-split (60 % TP1 /
40 % TP2) and martingale recovery on losing trades.

---

## Table of Contents

1. [Features](#features)
2. [Prerequisites](#prerequisites)
3. [Environment Variables](#environment-variables)
4. [MT5 Terminal Setup](#mt5-terminal-setup)
5. [Telegram API Setup](#telegram-api-setup)
6. [Installing Dependencies](#installing-dependencies)
7. [Running the Bot](#running-the-bot)
8. [Signal Format Examples](#signal-format-examples)
9. [How Martingale Works](#how-martingale-works)
10. [State Persistence](#state-persistence)
11. [Testing the Parser](#testing-the-parser)
12. [Project Structure](#project-structure)

---

## Features

- **XAUUSD only** — all other symbols are ignored.
- **TP split**: 60 % of lot → TP1 (25 pips), 40 % → TP2 (50 pips). Both positions share the same SL (50 pips).
- **Martingale recovery**: on a losing trade, lot is multiplied by a configurable factor (default 2.0) up to 3 consecutive levels before resetting.
- **State persistence** via `state.json` — martingale level survives bot restarts.
- **MT5 retry logic**: retries connection every 10 s up to 5 times before exiting.
- Signal parser handles three common Telegram formats (multi-line, compact with `|`, compact with `/`).

---

## Prerequisites

| Requirement | Version / Notes |
|-------------|-----------------|
| Python      | 3.10+           |
| MetaTrader5 | MT5 build 2260+ |
| Telegram app| Any modern release |

---

## Environment Variables

Create a `.env` file in the bot directory or export variables before running.
All keys are optional except `TG_API_ID` and `TG_API_HASH`.

| Variable | Default | Description |
|---|---|---|
| `TG_API_ID` | *(required)* | Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `TG_API_HASH` | *(required)* | Telegram API hash |
| `TG_CHANNELS` | `""` | Comma-separated list of channel usernames or numeric IDs, e.g. `sig_channel,@my_group,-100123456` |
| `TG_SESSION_NAME` | `telegram_mt5_bot` | Session file name (no extension) |
| `MT5_ACCOUNT` | `0` | MT5 account number (0 = shared terminal) |
| `MT5_PASSWORD` | `""` | MT5 account password |
| `MT5_SERVER` | `""` | MT5 broker server |
| `MT5_PATH` | `C:/Program Files/MetaTrader 5/terminal64.exe` | Path to MT5 terminal executable |
| `SYMBOL` | `XAUUSD` | Traded symbol (only XAUUSD is supported) |
| `BASE_LOT` | `0.01` | Base lot size for level-0 trades |
| `MARTINGALE_MULTIPLIER` | `2.0` | Lot multiplier after each losing trade |
| `MAX_MARTINGALE_LEVELS` | `3` | Maximum consecutive martingale levels before forced reset |
| `STATE_FILE` | `state.json` | Path to the JSON file storing martingale state |

### Example `.env`

```env
TG_API_ID=1234567
TG_API_HASH=abcdef1234567890abcdef1234567890
TG_CHANNELS=gold_signals,@my_trading_group
MT5_ACCOUNT=12345678
MT5_PASSWORD=MySecretPass
MT5_SERVER=MetaQuotes-Demo
MT5_PATH=C:/Program Files/MetaTrader 5/terminal64.exe
BASE_LOT=0.02
MARTINGALE_MULTIPLIER=2.0
MAX_MARTINGALE_LEVELS=3
```

---

## MT5 Terminal Setup

1. **Enable DLL imports** in MT5:
   - Open MT5 → *Tools* → *Options* → *Expert Advisors*
   - Check **"Allow DLL imports"**
   - Check **"Allow import of external experts"**
2. **Enable automated trading**:
   - In the same dialog, set *Allow automated trading* to **ON**
3. **Note the terminal path** (default: `C:/Program Files/MetaTrader 5/terminal64.exe`)
4. If using a **demo account**, leave `MT5_ACCOUNT` / `MT5_PASSWORD` / `MT5_SERVER` empty and the bot will connect to the shared terminal.

---

## Telegram API Setup

1. Go to [my.telegram.org](https://my.telegram.org) and log in.
2. Click **API development tools** → fill in the form (any name/description).
3. Copy the `api_id` and `api_hash`.
4. **Add the bot to your signal channels** and give it **read-message permission**.
5. For private channels the bot needs to be an **admin or member** — it cannot read messages in channels where it is not a member.

---

## Installing Dependencies

```bash
cd projects/telegram-mt5-bot
pip install -r requirements.txt
```

Or directly:

```bash
pip install MetaTrader5 Telethon
```

---

## Running the Bot

```bash
# Normal run
python main.py

# Run in background (Linux/macOS)
nohup python main.py >> bot.log 2>&1 &

# Docker (optional)
docker run -d --env-file .env python:3.10-slim \
  pip install MetaTrader5 Telethon && \
  python main.py
```

The bot connects to MT5 first (retries up to 5 times, 10 s apart), then starts
the Telegram listener. Press **Ctrl+C** to stop gracefully.

---

## Signal Format Examples

The parser recognises these three formats. Other formats that match the same
field structure will also work.

### Format A — Multi-line (most common in free signal channels)

```
BUY XAUUSD @ 2350.00
SL: 2345.00
TP1: 2352.50
TP2: 2355.00
```

### Format B — Compact with pipe separator

```
Gold Buy 2350.00 | SL 2345.00 | TP1 2352.50 | TP2 2355.00
```

### Format C — Compact with slash separator

```
SELL XAU/USD 2350.00 / SL 2345.00 / TP1 2352.50 / TP2 2355.00
```

**Aliases**: `GOLD` and `XAU/USD` are automatically normalised to `XAUUSD`.
Action is case-insensitive.

---

## How Martingale Works

| Event | Level | Lot (default BASE_LOT=0.01, multiplier=2.0) |
|---|---|---|
| Win | 0 | 0.01 |
| Loss | 1 | 0.02 |
| Loss | 2 | 0.04 |
| Loss | 3 | 0.08 |
| Loss (max reached) → reset | 0 | 0.01 |

- Martingale advances **only on a confirmed losing trade** (checked externally by the user via MT5 terminal or an external monitor).
- The bot's `advance_martingale()` function is a helper; the current version is **triggered manually** or can be wired to MT5's `OnTrade` event callback if needed.
- State is written to `state.json` after every update, so the bot resumes at the correct level after a restart.

---

## State Persistence

`state.json` (created automatically in the bot's working directory):

```json
{
  "level": 2,
  "lot": 0.04
}
```

- **Do not edit this file manually** while the bot is running.
- On startup the bot reads this file and resumes from the saved level and lot.

---

## Testing the Parser

No MT5 or Telegram connection needed.

```bash
python main.py --test
```

Expected output:

```
PASS: BUY XAUUSD 2350.0
PASS: BUY XAUUSD 2350.0
PASS: SELL XAUUSD 2350.0
test_signal_parser: all assertions passed.
```

---

## Project Structure

```
telegram-mt5-bot/
├── main.py           # Bot entrypoint: event loop, parser, MT5 sender, martingale
├── config.py         # All settings with env-var fallbacks
├── requirements.txt  # Python dependencies
├── README.md         # This file
└── state.json        # Created at runtime — do not commit
```

---

## Disclaimer

This bot executes real trades on a live or demo MT5 account.
Use at your own risk. Always test on a demo account first.