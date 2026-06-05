"""
trader_app.py — XAUUSD Trader Desktop App
Chunk 5 — Desktop GUI

Spec: .kimchi/docs/plan.md

A single-file tkinter application with:
  - SetupWizard (modal) on first run (no config.json)
  - Dashboard, Manual Entry, Log tabs via ttk.Notebook
  - MT5Engine + SignalBot integration via a threading.Queue
  - Graceful shutdown on WM_DELETE_WINDOW
"""

from __future__ import annotations

import functools
import logging
import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import TYPE_CHECKING, Any

from config_store import TraderConfig
from mt5_engine import MT5Engine
from signal_parser import Signal

from telegram_bot import SignalBot

# ── Logging handler that schedules widget updates on the main thread ─────────


class _QueueLoggingHandler(logging.Handler):
    """
    Custom logging handler that stores LogRecords in a tkinter widget.

    Because ``handle()`` is called from arbitrary threads (MT5, Telegram),
    it uses ``widget.after(0, ...)`` to safely schedule the text insertion
    on the main GUI thread.
    """

    def __init__(self, widget: scrolledtext.ScrolledText) -> None:
        super().__init__()
        self._widget = widget
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # Schedule GUI update on the main thread (must wrap in lambda/partial — after() doesn't accept extra args)
            self._widget.after(0, functools.partial(self._append, msg))
        except Exception:
            self.handleError(record)

    def _append(self, msg: str) -> None:
        self._widget.configure(state="normal")
        self._widget.insert(tk.END, msg + "\n")
        self._widget.see(tk.END)
        self._widget.configure(state="disabled")


# ── Setup Wizard ─────────────────────────────────────────────────────────────


class SetupWizard(tk.Toplevel):
    """
    Modal configuration dialog shown on first run (no config.json).

    Collects all fields required by ``TraderConfig`` and writes the file
    on "Save".  "Cancel" closes the application.
    """

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("XAUUSD Trader — First Run Setup")
        self.resizable(False, False)
        self._result: dict[str, Any] | None = None
        self._cancelled = False

        # Make this dialog modal (steal focus and block the parent)
        self.transient(parent)
        self.grab_set()

        self._build_ui()

        # Centre over parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        # Bind Enter key to Save
        self.bind("<Return>", lambda _: self._on_save())
        # Escape to Cancel
        self.bind("<Escape>", lambda _: self._on_cancel())

    # ── UI construction ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        # ── Section: MT5 ──────────────────────────────────────────────────
        ttk.Label(frame, text="MetaTrader 5", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 4)
        )

        self._mt5_path_var = tk.StringVar(value="C:\\Program Files\\MetaTrader 5\\terminal64.exe")
        self._mt5_account_var = tk.StringVar(value="0")
        self._mt5_password_var = tk.StringVar(value="")
        self._mt5_server_var = tk.StringVar(value="")

        self._add_field(frame, "Terminal Path:", self._mt5_path_var, row=1)
        self._add_field(frame, "Account ID:", self._mt5_account_var, row=2)
        self._add_field(frame, "Password:", self._mt5_password_var, row=3, show="*")
        self._add_field(frame, "Server:", self._mt5_server_var, row=4)

        # ── Section: Trading ─────────────────────────────────────────────
        row_offset = 5
        ttk.Label(frame, text="Trading", font=("TkDefaultFont", 10, "bold")).grid(
            row=row_offset, column=0, columnspan=3, sticky=tk.W, pady=(10, 4)
        )

        self._symbol_var = tk.StringVar(value="XAUUSD")
        self._base_lot_var = tk.StringVar(value="0.01")
        self._mart_mult_var = tk.StringVar(value="2.0")
        self._max_levels_var = tk.StringVar(value="3")
        self._pos_a_ratio_var = tk.StringVar(value="60")

        self._add_field(frame, "Symbol:", self._symbol_var, row=row_offset + 1)
        self._add_field(frame, "Base Lot:", self._base_lot_var, row=row_offset + 2)
        self._add_field(frame, "Martingale Multiplier:", self._mart_mult_var, row=row_offset + 3)
        self._add_field(frame, "Max Martingale Levels:", self._max_levels_var, row=row_offset + 4)
        self._add_field(frame, "Position Split A (%):", self._pos_a_ratio_var, row=row_offset + 5)

        # B ratio label (auto-computed)
        self._b_ratio_label = ttk.Label(frame, text="Position Split B (%): 40 (auto)")
        self._b_ratio_label.grid(
            row=row_offset + 6, column=1, sticky=tk.W, padx=(0, 4)
        )
        self._pos_a_ratio_var.trace_add("write", lambda *_: self._update_b_ratio())

        # ── Section: Telegram ────────────────────────────────────────────
        tg_row = row_offset + 7
        ttk.Label(frame, text="Telegram", font=("TkDefaultFont", 10, "bold")).grid(
            row=tg_row, column=0, columnspan=3, sticky=tk.W, pady=(10, 4)
        )

        self._bot_token_var = tk.StringVar(value="")
        self._add_field(frame, "Bot Token:", self._bot_token_var, row=tg_row + 1)

        # ── Section: EA ──────────────────────────────────────────────────
        ea_row = tg_row + 2
        ttk.Label(frame, text="Expert Advisor", font=("TkDefaultFont", 10, "bold")).grid(
            row=ea_row, column=0, columnspan=3, sticky=tk.W, pady=(10, 4)
        )

        self._magic_var = tk.StringVar(value="20250605")
        self._sl_pips_var = tk.StringVar(value="50")
        self._tp1_pips_var = tk.StringVar(value="25")
        self._tp2_pips_var = tk.StringVar(value="50")

        self._add_field(frame, "Magic Number:", self._magic_var, row=ea_row + 1)
        self._add_field(frame, "SL (pips):", self._sl_pips_var, row=ea_row + 2)
        self._add_field(frame, "TP1 (pips):", self._tp1_pips_var, row=ea_row + 3)
        self._add_field(frame, "TP2 (pips):", self._tp2_pips_var, row=ea_row + 4)

        # ── Buttons ─────────────────────────────────────────────────────
        btn_row = ea_row + 5
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=btn_row, column=0, columnspan=3, pady=(16, 0))

        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=12).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(btn_frame, text="Save", command=self._on_save, width=12).pack(
            side=tk.LEFT, padx=4
        )

    def _add_field(
        self,
        parent: ttk.Frame,
        label: str,
        var: tk.StringVar,
        row: int,
        show: str = "",
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=(0, 8), pady=2)
        entry = ttk.Entry(parent, textvariable=var, width=40, show=show)
        entry.grid(row=row, column=1, columnspan=2, sticky=tk.EW, pady=2)

    def _update_b_ratio(self) -> None:
        try:
            a = float(self._pos_a_ratio_var.get())
            b = 100.0 - a
            self._b_ratio_label.config(text=f"Position Split B (%): {b:.1f} (auto)")
        except ValueError:
            self._b_ratio_label.config(text="Position Split B (%): — (invalid)")

    # ── Callbacks ───────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        try:
            a = float(self._pos_a_ratio_var.get())
            b = 100.0 - a
            from config_store import TraderConfig
            cfg = TraderConfig(
                mt5_path=self._mt5_path_var.get(),
                mt5_account=int(self._mt5_account_var.get()),
                mt5_password=self._mt5_password_var.get(),
                mt5_server=self._mt5_server_var.get(),
                symbol=self._symbol_var.get(),
                base_lot=float(self._base_lot_var.get()),
                martingale_multiplier=float(self._mart_mult_var.get()),
                max_martingale_levels=int(self._max_levels_var.get()),
                position_a_ratio=a / 100.0,
                position_b_ratio=b / 100.0,
                telegram_bot_token=self._bot_token_var.get(),
                magic_number=int(self._magic_var.get()),
                sl_pips=int(self._sl_pips_var.get()),
                tp1_pips=int(self._tp1_pips_var.get()),
                tp2_pips=int(self._tp2_pips_var.get()),
            )
            cfg.save()
            self._result = {
                "mt5_path": self._mt5_path_var.get(),
                "mt5_account": int(self._mt5_account_var.get()),
                "mt5_password": self._mt5_password_var.get(),
                "mt5_server": self._mt5_server_var.get(),
                "symbol": self._symbol_var.get(),
                "base_lot": float(self._base_lot_var.get()),
                "martingale_multiplier": float(self._mart_mult_var.get()),
                "max_martingale_levels": int(self._max_levels_var.get()),
                "position_a_ratio": a / 100.0,
                "position_b_ratio": b / 100.0,
                "telegram_bot_token": self._bot_token_var.get(),
                "magic_number": int(self._magic_var.get()),
                "sl_pips": int(self._sl_pips_var.get()),
                "tp1_pips": int(self._tp1_pips_var.get()),
                "tp2_pips": int(self._tp2_pips_var.get()),
            }
            self.destroy()
        except ValueError as exc:
            tk.messagebox.showerror("Validation Error", f"Invalid input: {exc}", parent=self)

    def _on_cancel(self) -> None:
        self._cancelled = True
        self.destroy()

    # ── Public API ──────────────────────────────────────────────────────────

    def get_result(self) -> dict[str, Any] | None:
        """Return the collected config dict, or None if cancelled."""
        return None if self._cancelled else self._result


# ── Dashboard Tab ─────────────────────────────────────────────────────────────


class _DashboardTab(ttk.Frame):
    """Dashboard tab showing connection status, martingale state, and latest signal."""

    def __init__(
        self,
        parent: ttk.Notebook,
        engine: MT5Engine,
        bot_ref: "dict[str, SignalBot | None]",
        log: logging.Logger,
    ) -> None:
        super().__init__(parent, padding=12)
        self._engine = engine
        self._bot_ref = bot_ref
        self._log = log

        self._mt5_status_var = tk.StringVar(value="Disconnected")
        self._bot_status_var = tk.StringVar(value="Stopped")
        self._level_var = tk.StringVar(value="Level: 0")
        self._lot_var = tk.StringVar(value="Lot: —")
        self._signal_var = tk.StringVar(value="No signal received yet")

        self._build_ui()

    def _build_ui(self) -> None:
        ttk.Label(self, text="MT5 Connection", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 4)
        )
        ttk.Label(self, textvariable=self._mt5_status_var, foreground="red").grid(
            row=1, column=0, sticky=tk.W
        )
        self._connect_btn = ttk.Button(
            self, text="Connect", command=self._on_mt5_connect
        )
        self._connect_btn.grid(row=2, column=0, sticky=tk.W, pady=(4, 16))

        ttk.Label(self, text="Telegram Bot", font=("TkDefaultFont", 10, "bold")).grid(
            row=3, column=0, sticky=tk.W, pady=(0, 4)
        )
        ttk.Label(self, textvariable=self._bot_status_var, foreground="red").grid(
            row=4, column=0, sticky=tk.W
        )
        self._bot_btn = ttk.Button(
            self, text="Start Bot", command=self._on_bot_toggle
        )
        self._bot_btn.grid(row=5, column=0, sticky=tk.W, pady=(4, 16))

        ttk.Separator(self, orient=tk.HORIZONTAL).grid(
            row=6, column=0, columnspan=2, sticky=tk.EW, pady=8
        )

        ttk.Label(self, text="Martingale State", font=("TkDefaultFont", 10, "bold")).grid(
            row=7, column=0, sticky=tk.W, pady=(0, 4)
        )
        ttk.Label(self, textvariable=self._level_var).grid(row=8, column=0, sticky=tk.W)
        ttk.Label(self, textvariable=self._lot_var).grid(row=9, column=0, sticky=tk.W, pady=(0, 16))

        ttk.Label(self, text="Latest Signal", font=("TkDefaultFont", 10, "bold")).grid(
            row=10, column=0, sticky=tk.W, pady=(0, 4)
        )
        self._signal_label = ttk.Label(self, textvariable=self._signal_var, wraplength=400)
        self._signal_label.grid(row=11, column=0, sticky=tk.W)

        # Configure grid weights so the frame expands properly
        self.columnconfigure(0, weight=1)

    def _on_mt5_connect(self) -> None:
        if self._engine.is_connected():
            self._engine.disconnect()
            self._mt5_status_var.set("Disconnected")
            self._connect_btn.config(text="Connect")
            self._log.info("MT5 disconnected via dashboard.")
        else:
            ok = self._engine.connect()
            if ok:
                self._mt5_status_var.set("Connected")
                self._connect_btn.config(text="Disconnect")
                self._log.info("MT5 connected via dashboard.")
            else:
                self._mt5_status_var.set("Connection Failed")
                self._log.error("MT5 connection failed via dashboard.")

    def _on_bot_toggle(self) -> None:
        bot = self._bot_ref.get("bot")
        if bot is None or not bot.is_running():
            if bot is None:
                token = self._engine.config.telegram_bot_token
                if not token:
                    self._log.warning("Cannot start bot: no token in config.")
                    return
                q: queue.Queue[Signal] = queue.Queue()
                bot = SignalBot(token, q, self._engine.config.symbol_aliases)
                self._bot_ref["bot"] = bot
            bot.start()
            self._bot_status_var.set("Running")
            self._bot_btn.config(text="Stop Bot")
            self._log.info("Telegram bot started via dashboard.")
        else:
            bot.stop()
            self._bot_status_var.set("Stopped")
            self._bot_btn.config(text="Start Bot")
            self._log.info("Telegram bot stopped via dashboard.")

    def update_martingale_state(self, level: int, lot: float) -> None:
        self._level_var.set(f"Level: {level}")
        self._lot_var.set(f"Lot: {lot:.4f}")

    def update_latest_signal(self, sig: Signal | None) -> None:
        if sig is None:
            self._signal_var.set("No signal received yet")
        else:
            self._signal_var.set(
                f"{sig.action} {sig.symbol} @ {sig.entry}  "
                f"SL={sig.sl}  TP1={sig.tp1}  TP2={sig.tp2}"
            )


# ── Manual Entry Tab ──────────────────────────────────────────────────────────


class _ManualEntryTab(ttk.Frame):
    """Manual signal entry tab with form fields and an Execute button."""

    def __init__(
        self,
        parent: ttk.Notebook,
        engine: MT5Engine,
        on_executed: Any,
        log: logging.Logger,
    ) -> None:
        super().__init__(parent, padding=12)
        self._engine = engine
        self._on_executed = on_executed
        self._log = log

        self._action_var = tk.StringVar(value="BUY")
        self._symbol_var = tk.StringVar(value=engine.config.symbol)
        self._entry_var = tk.StringVar(value="")
        self._sl_var = tk.StringVar(value="")
        self._tp1_var = tk.StringVar(value="")
        self._tp2_var = tk.StringVar(value="")
        self._lot_var = tk.StringVar(value=str(engine.config.base_lot))

        self._build_ui()

    def _build_ui(self) -> None:
        row = 0

        ttk.Label(self, text="Action:").grid(row=row, column=0, sticky=tk.W, pady=3)
        action_combo = ttk.Combobox(
            self, textvariable=self._action_var, values=["BUY", "SELL"], state="readonly", width=10
        )
        action_combo.grid(row=row, column=1, sticky=tk.W, pady=3)

        row += 1
        ttk.Label(self, text="Symbol:").grid(row=row, column=0, sticky=tk.W, pady=3)
        ttk.Entry(self, textvariable=self._symbol_var, width=20).grid(row=row, column=1, sticky=tk.W, pady=3)

        row += 1
        ttk.Label(self, text="Entry Price:").grid(row=row, column=0, sticky=tk.W, pady=3)
        ttk.Entry(self, textvariable=self._entry_var, width=20).grid(row=row, column=1, sticky=tk.W, pady=3)

        row += 1
        ttk.Label(self, text="SL Price:").grid(row=row, column=0, sticky=tk.W, pady=3)
        ttk.Entry(self, textvariable=self._sl_var, width=20).grid(row=row, column=1, sticky=tk.W, pady=3)

        row += 1
        ttk.Label(self, text="TP1 Price:").grid(row=row, column=0, sticky=tk.W, pady=3)
        ttk.Entry(self, textvariable=self._tp1_var, width=20).grid(row=row, column=1, sticky=tk.W, pady=3)

        row += 1
        ttk.Label(self, text="TP2 Price:").grid(row=row, column=0, sticky=tk.W, pady=3)
        ttk.Entry(self, textvariable=self._tp2_var, width=20).grid(row=row, column=1, sticky=tk.W, pady=3)

        row += 1
        ttk.Label(self, text="Lot:").grid(row=row, column=0, sticky=tk.W, pady=3)
        ttk.Entry(self, textvariable=self._lot_var, width=20).grid(row=row, column=1, sticky=tk.W, pady=3)

        row += 1
        self._execute_btn = ttk.Button(self, text="Execute Signal", command=self._on_execute)
        self._execute_btn.grid(row=row, column=0, columnspan=2, pady=(16, 0))

        self.columnconfigure(1, weight=1)

    def _on_execute(self) -> None:
        try:
            sig = Signal(
                action=self._action_var.get().upper(),
                symbol=self._symbol_var.get().upper(),
                entry=float(self._entry_var.get()),
                sl=float(self._sl_var.get()),
                tp1=float(self._tp1_var.get()),
                tp2=float(self._tp2_var.get()),
            )
        except ValueError as exc:
            self._log.warning("Manual entry form has invalid data: %s", exc)
            tk.messagebox.showerror("Validation Error", f"Invalid input: {exc}", parent=self)
            return

        self._engine.config.base_lot = float(self._lot_var.get())
        ok = self._engine.process_signal(sig)
        status = "SUCCESS" if ok else "FAILED"
        self._log.info("Manual signal %s: %s %s @ %s", status, sig.action, sig.symbol, sig.entry)
        self._on_executed(sig)


# ── Main Application ──────────────────────────────────────────────────────────


class TraderApp(tk.Tk):
    """
    Root window of the XAUUSD Trader desktop application.

    On construction:
      1. Checks for ``config.json``; if missing, blocks on the modal SetupWizard.
      2. Initialises ``MT5Engine`` (not yet connected).
      3. Builds the three-tab notebook.
      4. Attaches a ``_QueueLoggingHandler`` to the log ScrolledText.
      5. Starts the queue-polling loop (``after(100, ...)``).

    Parameters
    ----------
    config_path: str | None
        Optional path to the config file.  Defaults to ``config.json`` in
        the current working directory.
    """

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__()
        self.title("XAUUSD Trader")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── 1. Load or create configuration ──────────────────────────────
        self._config_path = config_path or "config.json"
        self._engine: MT5Engine | None = None
        self._bot_ref: dict[str, SignalBot | None] = {"bot": None}
        self._signal_queue: queue.Queue[Signal] = queue.Queue()
        self._latest_signal: Signal | None = None
        self._log = logging.getLogger("trader_app")

        # Block on modal wizard until config exists
        self._ensure_config()

        # ── 2. Build MT5 engine ──────────────────────────────────────────
        config = TraderConfig.load(self._config_path)
        self._engine = MT5Engine(config)

        # ── 3. Build UI ──────────────────────────────────────────────────
        self._build_ui()

        # ── 4. Start queue polling ───────────────────────────────────────
        self._polling_active = True
        self._poll_queue()

    def _ensure_config(self) -> None:
        """Show the setup wizard if config.json is absent."""
        import os

        if not os.path.exists(self._config_path):
            self.withdraw()  # hide main window while wizard is open
            wizard = SetupWizard(self)
            self.wait_window(wizard)  # block until wizard closes
            result = wizard.get_result()

            if result is None:
                # User cancelled — exit immediately
                self.destroy()
                return

            cfg = TraderConfig(mt5_path=result["mt5_path"], **result)
            cfg.save(self._config_path)
            self._log.info("Config saved to %s.", self._config_path)
            self.deiconify()  # restore main window

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ── Tab 1: Dashboard ──────────────────────────────────────────────
        self._dashboard = _DashboardTab(
            notebook, self._engine, self._bot_ref, self._log
        )
        notebook.add(self._dashboard, text="Dashboard")

        # ── Tab 2: Manual Entry ───────────────────────────────────────────
        self._manual_tab = _ManualEntryTab(
            notebook, self._engine, self._on_signal_executed, self._log
        )
        notebook.add(self._manual_tab, text="Manual Entry")

        # ── Tab 3: Log ───────────────────────────────────────────────────
        log_frame = ttk.Frame(notebook, padding=4)
        notebook.add(log_frame, text="Log")

        self._log_text = scrolledtext.ScrolledText(
            log_frame, state="disabled", height=20, font=("Courier New", 9)
        )
        self._log_text.pack(fill=tk.BOTH, expand=True)

        handler = _QueueLoggingHandler(self._log_text)
        handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)
        # Ensure the root logger propagates so the handler sees messages
        logging.getLogger().setLevel(logging.INFO)

        self._log.info("XAUUSD Trader started.")

    # ── Queue polling ────────────────────────────────────────────────────────

    def _poll_queue(self) -> None:
        """
        Poll ``self._signal_queue`` and dispatch any received ``Signal`` objects.

        Runs on the main thread via ``after(100, ...)`` so it never blocks
        the GUI.  The flag ``self._polling_active`` is cleared on shutdown.
        """
        if not self._polling_active:
            return

        try:
            while True:
                sig = self._signal_queue.get_nowait()
                if self._engine is not None:
                    ok = self._engine.process_signal(sig)
                    self._log.info(
                        "Queue signal %s: %s %s @ %s",
                        "SUCCESS" if ok else "FAILED",
                        sig.action, sig.symbol, sig.entry,
                    )
                self._latest_signal = sig
                self._dashboard.update_latest_signal(sig)
        except queue.Empty:
            pass

        self.after(100, self._poll_queue)

    # ── Callbacks ────────────────────────────────────────────────────────────

    def _on_signal_executed(self, sig: Signal | None = None) -> None:
        """Called by the manual-entry tab after a signal is executed."""
        self._latest_signal = sig
        self._dashboard.update_latest_signal(sig)

    # ── Shutdown ─────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        """Graceful shutdown: stop bot, disconnect MT5, destroy window."""
        self._log.info("Shutdown requested.")
        self._polling_active = False

        # Stop Telegram bot
        bot = self._bot_ref.get("bot")
        if bot is not None and bot.is_running():
            bot.stop()
            self._log.info("Telegram bot stopped.")

        # Disconnect MT5
        if self._engine is not None and self._engine.is_connected():
            self._engine.disconnect()
            self._log.info("MT5 disconnected.")

        self.destroy()

    def run(self) -> None:
        """Alias for ``self.mainloop()`` as specified in the spec."""
        self.mainloop()