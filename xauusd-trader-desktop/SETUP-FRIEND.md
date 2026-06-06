# Friend Setup Guide — XAUUSD Trader Desktop

> A simple, no-code guide to get the trading bot running on Windows.

---

## What You Need

1. A **Windows PC** with MetaTrader 5 installed.
2. The `XAUUSDTrader.exe` file your friend sent you.
3. A **Telegram bot token** from your friend (they will give you this).

---

## Step 1 — Download the File

Your friend will send you a single file called `XAUUSDTrader.exe`.

- Save it to your **Desktop** or any folder you will remember.
- **Do not rename it.**

---

## Step 2 — Double-Click to Open

Find the file and double-click it.

> **Windows SmartScreen warning**
> If Windows shows a blue screen saying *"Windows protected your PC"*, click **More info** then **Run anyway**. This happens because the app was built locally, not by a big software company.

The **Setup Wizard** appears.

---

## Step 3 — Fill in the Setup Wizard

### MT5 Settings

| Field | What to type |
|-------|-------------|
| **MT5 Path** | Ask your friend for this. It usually looks like: `C:\Program Files\MetaTrader 5\terminal64.exe` |
| **Account** | Your MT5 account number (only numbers) |
| **Password** | Your MT5 password |
| **Server** | Your broker's server name, e.g. `Pepperstone-Demo` |

### Trading Settings

Your friend will tell you the best numbers for these, or you can leave the defaults.

| Field | Default | Meaning |
|-------|---------|---------|
| **Symbol** | XAUUSD | The gold pair we trade |
| **Base Lot** | 0.01 | How much gold each trade starts with |
| **Martingale Multiplier** | 2.0 | Doubles the trade size after a loss |
| **Max Levels** | 3 | How many times the bot can double before resetting |
| **Position A Ratio** | 60% | How much of the trade goes to the first take-profit |
| **Position B Ratio** | 40% | How much of the trade goes to the second take-profit |

### Order Parameters

Leave these as they are unless your friend tells you otherwise:

- **Magic Number:** `20250605`
- **SL Pips:** `50`
- **TP1 Pips:** `25`
- **TP2 Pips:** `50`

### Telegram Bot

Paste the **Bot Token** your friend gave you. It looks like:

```
123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

---

## Step 4 — Save and Start

Click **Save**. The dashboard opens.

1. Click **Connect** (links the app to MetaTrader 5).
2. Click **Start Bot** (starts listening for Telegram signals).

You are live! The bot will now automatically place trades when signals arrive.

---

## What You See on the Dashboard

- **MT5 Status:** Should say **Connected**.
- **Bot Status:** Should say **Running**.
- **Martingale Level:** Starts at `0`.
- **Current Lot:** Starts at `0.01`.
- **Latest Signal:** Shows the last trade the bot received.

---

## The Other Tabs

- **Manual Entry:** Place a trade yourself without waiting for Telegram.
- **Log:** A live scroll of everything the bot is doing. If something goes wrong, check here first.
- **Signal Formats:** (advanced) If your Telegram channel uses a different message style, ask your friend how to add it.

---

## Troubleshooting

| Problem | What to do |
|---------|-----------|
| "MT5 Error — Failed to connect" | Double-check the **MT5 Path**. Open File Explorer, find `terminal64.exe`, right-click it, choose **Copy as path**, and paste it into the app. |
| "No Token" warning when starting bot | You missed the **Bot Token** field in the Setup Wizard. Close the app and re-open it — the wizard will appear again because no config was saved. |
| Bot running but no trades | Make sure the bot is added to the Telegram channel that sends signals. Copy the bot's name from [@BotFather](https://t.me/BotFather) and ask the channel admin to add it. |
| "Both orders failed" in Log | Check that MT5 is logged in and the green **AutoTrading** button in MT5 is pressed. |
| App won't open at all | Make sure you downloaded the `.exe` file fully (not paused or corrupted). Ask your friend to re-send it. |
| Windows says it is a virus | It is not a virus. Click **More info → Run anyway**. The app is safe — it was built by your friend on their own PC, which is why Windows is cautious. |

---

## How to Close the App

Click the **X** on the window, or right-click the app icon in the taskbar and choose **Close window**.

The app will safely disconnect MT5 and stop the Telegram bot before closing.

---

## Need Help?

If you get stuck, send your friend a screenshot of the **Log** tab. That tells them exactly what is happening.
