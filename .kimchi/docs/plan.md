# Plan: 24/7 Headless Mode + PnL Auto-Close for XAUUSD Trader

## Goal
1. Add a **headless/CLI mode** so the trader can run 24/7 on a VPS without a GUI or display.
2. Add a **PnL target auto-close** feature: monitor floating PnL and close ALL open positions (including martingales) when total profit reaches a user-configured threshold.

## Chunks

### Chunk 1 — PnL Target Core (config_store.py, mt5_engine.py)
**Files:** `config_store.py`, `mt5_engine.py`

**Changes:**
- `TraderConfig`: add `pnl_target: float = 0.0` (0 = disabled). Add `pnl_check_interval_seconds: int = 10`.
- `MT5Engine`:
  - `get_account_info() -> dict | None` — wraps `mt5.account_info()`, returns balance/equity/margin.
  - `get_total_floating_pnl(magic: int | None = None) -> float` — sums profit of all open positions. If `magic` is provided, filters by magic number.
  - `close_all_positions(magic: int | None = None) -> list[int]` — closes every open position, returns list of successfully closed tickets. If `magic` provided, only closes positions with that magic.
  - `advance_martingale_after_close()` — helper to reset martingale state after a bulk close.

**Acceptance:**
- `test_mt5_engine.py` passes existing tests.
- New tests: `test_get_total_floating_pnl`, `test_close_all_positions`, `test_close_all_positions_filters_magic`, `test_pnl_target_config_roundtrip`.

---

### Chunk 2 — Headless CLI Entry Point (headless_trader.py)
**File:** `headless_trader.py` (new)

**Behavior:**
- Reads `config.json` from cwd (or path via `--config` arg).
- Connects to MT5, starts Telegram bot.
- Logs to stdout and rotating file (`trader.log`).
- Runs a main loop that:
  1. Polls signal queue (non-blocking).
  2. Processes signals via `MT5Engine.process_signal()`.
  3. Checks floating PnL every `pnl_check_interval_seconds`. If `pnl_target > 0` and `total_pnl >= pnl_target`, logs the event, closes all positions, resets martingale state, and sends a Telegram notification (if bot token present).
  4. Sleeps 1s between iterations.
- Handles SIGINT/SIGTERM gracefully: stop bot, disconnect MT5, exit.
- CLI args via `argparse`:
  - `--config PATH` — config file location
  - `--daemon` — daemonize (background)
  - `--log-level {DEBUG,INFO,WARNING,ERROR}`

**Key design:** Reuses `MT5Engine`, `SignalBot`, `TraderConfig`, `FormatManager`. No Tkinter.

**Acceptance:**
- `python headless_trader.py --help` works.
- With mock MT5, main loop processes signals and respects PnL target.
- Covered by `test_headless_trader.py`.

---

### Chunk 3 — GUI Updates (trader_app.py)
**File:** `trader_app.py`

**Changes:**
- `SetupWizard`: add fields for **PnL Target** ($ amount) and **PnL Check Interval** (seconds).
- `_DashboardTab`: display current floating PnL, PnL target, and an auto-close status indicator. Add a **"Close All Now"** manual button that calls `close_all_positions()` and resets martingale.
- Update `_poll_queue` to also check PnL target every N seconds (using a timestamp counter so it doesn't spam).
- When auto-close triggers from GUI, show a messagebox and log it.

**Acceptance:**
- Setup wizard includes PnL target and interval fields.
- Dashboard shows live PnL and target.
- Manual "Close All" button works.
- Existing tests pass; new test for dashboard PnL display.

---

### Chunk 4 — Tests & Validation
**Files:** `tests/test_headless_trader.py`, `tests/test_mt5_engine.py` (append)

**Test coverage:**
- `test_headless_trader.py`:
  - CLI arg parsing
  - Main loop with mock signal queue
  - PnL target triggers close_all + martingale reset
  - Graceful shutdown on SIGINT
- `test_mt5_engine.py` append:
  - `get_total_floating_pnl` with/without magic filter
  - `close_all_positions` with/without magic filter
  - `pnl_target` config persistence

**Run:**
```bash
cd xauusd-trader-desktop
python -m unittest discover tests -v
```

All tests must pass.
