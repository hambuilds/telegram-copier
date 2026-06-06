# Plan: XAUUSD Trader Desktop — Complete GUI + Distribution

## Problem
`trader_app.py` is **completely empty** (2 bytes). The test suite (`tests/test_trader_app.py`) expects a full Tkinter GUI with SetupWizard, Dashboard, Manual Entry, Log tabs, queue polling, and MT5/Telegram integration. The `build_exe.py` already targets this file. Without the GUI, the app is un-runnable and the distributable `.exe` is useless.

## Goal
Implement `trader_app.py` so that:
1. All existing tests pass (`python -m unittest discover tests -v`)
2. The app is a runnable desktop GUI with setup wizard + dashboard + manual entry + log
3. PyInstaller builds a working standalone executable
4. Friends can receive the `.exe`, double-click it, configure everything through the GUI, and trade

## Chunk Breakdown

### Chunk 1 — trader_app.py GUI Implementation
**File:** `xauusd-trader-desktop/trader_app.py`

Implement the following, each matching the test interface exactly:

1. **`SetupWizard(Toplevel)`** — modal setup dialog
   - Fields: mt5_path, mt5_account, mt5_password, mt5_server, symbol, base_lot, martingale_multiplier, max_martingale_levels, position_a_ratio, telegram_bot_token, magic_number, sl_pips, tp1_pips, tp2_pips
   - `_pos_a_ratio_var` (StringVar) — typing updates `_b_ratio_label` via `_update_b_ratio()`
   - Save button → `_on_save()` validates, writes `config.json`, stores `self._result` dict, calls `destroy()`
   - Cancel button → `_on_cancel()` sets `self._result = None`
   - `get_result()` returns the dict or None

2. **`_DashboardTab(ttk.Frame)`**
   - Constructor args: `parent_notebook, mt5_engine, bot_ref_dict, logger`
   - MT5 Connect/Disconnect button: `_on_mt5_connect()` toggles engine.connect() / disconnect()
   - Bot Start/Stop button: `_on_bot_toggle()` creates/starts `SignalBot` or stops it
   - `update_latest_signal(signal)` updates a label showing latest signal info
   - Martingale level & lot display labels

3. **`_ManualEntryTab(ttk.Frame)`**
   - Constructor args: `parent_notebook, mt5_engine, signal_callback, logger`
   - Fields: action (BUY/SELL), symbol, entry, sl, tp1, tp2, lot
   - Execute button → `_on_execute()` builds `Signal` dataclass, calls `signal_callback(sig)` AND `mt5_engine.process_signal(sig)`

4. **`_QueueLoggingHandler(logging.Handler)`**
   - Constructor takes a `ScrolledText` widget
   - `emit(record)` schedules `_append(record)` via `widget.after(0, ...)`
   - `_append()` inserts formatted log line into the scrolled text widget

5. **`TraderApp(tk.Tk)`**
   - `__init__()`: loads config (shows SetupWizard if missing), creates MT5Engine, creates Notebook with Dashboard, ManualEntry, Log tabs, starts `_poll_queue()` loop
   - `_poll_queue()`: polls `self._signal_queue` every 1000ms, calls `self._engine.process_signal()` and `self._dashboard.update_latest_signal()`
   - `_on_close()`: stops bot, disconnects MT5, cancels polling, destroys window
   - `protocol("WM_DELETE_WINDOW", self._on_close)`

6. **`main()`** entry point
   - `if __name__ == "__main__": main()`
   - Creates TraderApp and calls mainloop()

**Acceptance criteria:**
- `python -m unittest tests.test_trader_app` passes all tests
- `python trader_app.py` opens a GUI window

### Chunk 2 — Build & Distribution Polish
**File:** `xauusd-trader-desktop/build_exe.py`

Improve the build script:
- Keep `--onefile` for single-file distribution
- Keep `--windowed` for no console
- Add `--noconfirm` to auto-clean dist
- Add `--clean` for reproducible builds
- Ensure `config_store.py`, `signal_parser.py`, `mt5_engine.py`, `telegram_bot.py` are picked up as PyInstaller hidden imports (or let PyInstaller auto-detect from imports in trader_app.py)
- Add a check that `trader_app.py` is non-empty before building

**Acceptance criteria:**
- `python build_exe.py` completes without errors
- The resulting `dist/XAUUSDTrader` runs on Linux (or `.exe` on Windows)

### Chunk 3 — Integration Testing
- Run ALL tests: `python -m unittest discover tests -v`
- Verify `trader_app.py` can be imported and instantiated
- Run `python build_exe.py` and confirm build succeeds

## Implementation Notes
- Use **standard `tkinter`** (already in the test stub, no extra deps needed)
- `sys.path` manipulation: `tests/test_trader_app.py` inserts `__file__.parent.parent` into `sys.path`, so trader_app.py must be at the module root and import sibling modules as `from config_store import TraderConfig` etc.
- The tests stub out tkinter, MT5Engine, SignalBot, so the implementation must match the exact attribute names the tests reference.
- The wizard should compute `position_b_ratio = 1.0 - a_ratio` automatically.
- `_poll_queue` must use `self.after()` to re-schedule itself.
