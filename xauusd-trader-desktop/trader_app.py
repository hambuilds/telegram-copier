"""
trader_app.py — XAUUSD Trader Desktop App
Chunk 5 — Desktop GUI

Spec: .kimchi/docs/plan.md

Tkinter GUI application for XAUUSD trading with MT5 integration,
Telegram signal bot, and manual order entry.
"""

import logging
import os
import queue
import sys

import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from tkinter import messagebox

from config_store import TraderConfig
from format_manager import get_manager
from format_editor import _SignalFormatsTab
from mt5_engine import MT5Engine
from signal_parser import Signal
from telegram_bot import SignalBot

# Module-level logger
_log = logging.getLogger(__name__)


# ── Setup Wizard ──────────────────────────────────────────────────────────────


class SetupWizard(tk.Toplevel):
    """
    Modal dialog for first-run configuration of the trading app.

    Collects MT5 path/account/credentials, trading parameters, and
    Telegram bot token, then saves a ``TraderConfig`` to disk.
    """

    def __init__(self, master: tk.Tk | tk.Toplevel) -> None:
        super().__init__(master)
        self.title("XAUUSD Trader — Setup")
        self.geometry("600x700")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._result: dict | None = None

        # StringVar for all form fields
        self._mt5_path_var = tk.StringVar(value="C:\\MT5\\terminal.exe")
        self._mt5_account_var = tk.StringVar(value="")
        self._mt5_password_var = tk.StringVar(value="")
        self._mt5_server_var = tk.StringVar(value="")
        self._symbol_var = tk.StringVar(value="XAUUSD")
        self._base_lot_var = tk.StringVar(value="0.01")
        self._mart_mult_var = tk.StringVar(value="2.0")
        self._max_levels_var = tk.StringVar(value="3")
        self._pos_a_ratio_var = tk.StringVar(value="60")
        self._bot_token_var = tk.StringVar(value="")
        self._magic_var = tk.StringVar(value="20250605")
        self._sl_pips_var = tk.StringVar(value="50")
        self._tp1_pips_var = tk.StringVar(value="25")
        self._tp2_pips_var = tk.StringVar(value="50")

        # Build UI
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        row = 0

        # ── MT5 Settings ────────────────────────────────────────────────────
        ttk.Label(container, text="MT5 Settings", font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        row += 1

        _add_field(container, row, "MT5 Path:", self._mt5_path_var)
        row += 1
        _add_field(container, row, "Account:", self._mt5_account_var)
        row += 1
        _add_field(container, row, "Password:", self._mt5_password_var)
        row += 1
        _add_field(container, row, "Server:", self._mt5_server_var)
        row += 1

        ttk.Separator(container).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        # ── Trading Settings ────────────────────────────────────────────────
        ttk.Label(container, text="Trading Settings", font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        row += 1

        _add_field(container, row, "Symbol:", self._symbol_var)
        row += 1
        _add_field(container, row, "Base Lot:", self._base_lot_var)
        row += 1
        _add_field(container, row, "Martingale Multiplier:", self._mart_mult_var)
        row += 1
        _add_field(container, row, "Max Martingale Levels:", self._max_levels_var)
        row += 1

        ttk.Separator(container).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        # ── Position Ratio ──────────────────────────────────────────────────
        ttk.Label(container, text="Position Ratios", font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        row += 1

        ttk.Label(container, text="Position A Ratio (%):").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=4
        )
        a_entry = ttk.Entry(container, textvariable=self._pos_a_ratio_var, width=15)
        a_entry.grid(row=row, column=1, sticky="w", pady=4)
        a_entry.bind("<KeyRelease>", lambda e: self._update_b_ratio())
        row += 1

        ttk.Label(container, text="Position B Ratio (%):").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self._b_ratio_label = ttk.Label(container, text="40.0%")
        self._b_ratio_label.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Separator(container).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        # ── Magic Number & Pips ─────────────────────────────────────────────
        ttk.Label(container, text="Order Parameters", font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        row += 1

        _add_field(container, row, "Magic Number:", self._magic_var)
        row += 1
        _add_field(container, row, "SL Pips:", self._sl_pips_var)
        row += 1
        _add_field(container, row, "TP1 Pips:", self._tp1_pips_var)
        row += 1
        _add_field(container, row, "TP2 Pips:", self._tp2_pips_var)
        row += 1

        ttk.Separator(container).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        # ── Telegram Bot ────────────────────────────────────────────────────
        ttk.Label(container, text="Telegram Bot", font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        row += 1

        _add_field(container, row, "Bot Token:", self._bot_token_var)
        row += 1

        # ── Buttons ─────────────────────────────────────────────────────────
        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=16)
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="left", padx=8)

    def run(self) -> None:
        """Show, lift, focus, and block until the wizard is closed."""
        self.transient(self.master)
        self.grab_set()
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.wait_window()

    def _update_b_ratio(self) -> None:
        """Compute position_b_ratio = 1.0 - a_ratio and update the label."""
        try:
            a_ratio = float(self._pos_a_ratio_var.get()) / 100.0
        except ValueError:
            a_ratio = 0.0
        b_ratio = 1.0 - a_ratio
        self._b_ratio_label.config(text=f"{b_ratio * 100:.1f}%")

    def _on_save(self) -> None:
        """Validate inputs, create and save config, store result and close."""
        try:
            mt5_path = self._mt5_path_var.get()
            mt5_account = int(self._mt5_account_var.get()) if self._mt5_account_var.get() else 0
            mt5_password = self._mt5_password_var.get()
            mt5_server = self._mt5_server_var.get()
            symbol = self._symbol_var.get()
            base_lot = float(self._base_lot_var.get())
            mart_mult = float(self._mart_mult_var.get())
            max_levels = int(self._max_levels_var.get())
            pos_a_ratio = float(self._pos_a_ratio_var.get()) / 100.0
            pos_b_ratio = 1.0 - pos_a_ratio
            bot_token = self._bot_token_var.get()
            magic = int(self._magic_var.get())
            sl_pips = int(self._sl_pips_var.get())
            tp1_pips = int(self._tp1_pips_var.get())
            tp2_pips = int(self._tp2_pips_var.get())

            config = TraderConfig(
                mt5_path=mt5_path,
                mt5_account=mt5_account,
                mt5_password=mt5_password,
                mt5_server=mt5_server,
                symbol=symbol,
                symbol_aliases={"GOLD": "XAUUSD", "XAU/USD": "XAUUSD"},
                base_lot=base_lot,
                martingale_multiplier=mart_mult,
                max_martingale_levels=max_levels,
                position_a_ratio=pos_a_ratio,
                position_b_ratio=pos_b_ratio,
                magic_number=magic,
                telegram_bot_token=bot_token,
                sl_pips=sl_pips,
                tp1_pips=tp1_pips,
                tp2_pips=tp2_pips,
            )
            config.validate()
            config.save()

            self._result = {
                "mt5_path": mt5_path,
                "mt5_account": mt5_account,
                "mt5_password": mt5_password,
                "mt5_server": mt5_server,
                "symbol": symbol,
                "symbol_aliases": {"GOLD": "XAUUSD", "XAU/USD": "XAUUSD"},
                "base_lot": base_lot,
                "martingale_multiplier": mart_mult,
                "max_martingale_levels": max_levels,
                "position_a_ratio": pos_a_ratio,
                "position_b_ratio": pos_b_ratio,
                "magic_number": magic,
                "telegram_bot_token": bot_token,
                "sl_pips": sl_pips,
                "tp1_pips": tp1_pips,
                "tp2_pips": tp2_pips,
                "pip_value": 0.10,
                "mt5_connect_retries": 5,
                "mt5_connect_retry_delay": 10,
                "state_file": "state.json",
                "config_file": "config.json",
            }
        except Exception as exc:
            messagebox.showerror("Validation Error", str(exc))
            return

        self.destroy()

    def _on_cancel(self) -> None:
        """Cancel and close without saving."""
        self._result = None
        self.destroy()

    def get_result(self) -> dict | None:
        """Return the saved configuration dict or None if cancelled."""
        return self._result


# ── Dashboard Tab ─────────────────────────────────────────────────────────────


class _DashboardTab(ttk.Frame):
    """
    Main dashboard tab showing connection status, bot status,
    martingale state, and the latest signal.
    """

    def __init__(
        self,
        parent: ttk.Notebook,
        engine: MT5Engine,
        bot_ref: dict,
        logger: logging.Logger,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._bot_ref = bot_ref
        self._log = logger

        # State display vars
        self._mt5_status_var = tk.StringVar(value="Disconnected")
        self._bot_status_var = tk.StringVar(value="Stopped")
        self._level_var = tk.StringVar(value="0")
        self._lot_var = tk.StringVar(value="0.01")
        self._latest_signal_var = tk.StringVar(value="No signal received")

        content = ttk.Frame(self, padding=16)
        content.pack(fill="both", expand=True)

        # ── MT5 Section ─────────────────────────────────────────────────────
        ttk.Label(content, text="MT5 Connection", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Label(content, text="Status:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Label(content, textvariable=self._mt5_status_var).grid(
            row=1, column=1, sticky="w", pady=4
        )
        self._mt5_btn = ttk.Button(
            content, text="Connect", command=self._on_mt5_connect
        )
        self._mt5_btn.grid(row=2, column=0, columnspan=2, pady=8)

        ttk.Separator(content).grid(row=3, column=0, columnspan=2, sticky="ew", pady=8)

        # ── Bot Section ─────────────────────────────────────────────────────
        ttk.Label(content, text="Telegram Bot", font=("Segoe UI", 10, "bold")).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Label(content, text="Status:").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Label(content, textvariable=self._bot_status_var).grid(
            row=5, column=1, sticky="w", pady=4
        )
        self._bot_btn = ttk.Button(
            content, text="Start Bot", command=self._on_bot_toggle
        )
        self._bot_btn.grid(row=6, column=0, columnspan=2, pady=8)

        ttk.Separator(content).grid(row=7, column=0, columnspan=2, sticky="ew", pady=8)

        # ── Martingale State ────────────────────────────────────────────────
        ttk.Label(content, text="Martingale State", font=("Segoe UI", 10, "bold")).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Label(content, text="Level:").grid(row=9, column=0, sticky="w", pady=4)
        ttk.Label(content, textvariable=self._level_var).grid(
            row=9, column=1, sticky="w", pady=4
        )
        ttk.Label(content, text="Current Lot:").grid(row=10, column=0, sticky="w", pady=4)
        ttk.Label(content, textvariable=self._lot_var).grid(
            row=10, column=1, sticky="w", pady=4
        )

        ttk.Separator(content).grid(row=11, column=0, columnspan=2, sticky="ew", pady=8)

        # ── Latest Signal ───────────────────────────────────────────────────
        ttk.Label(content, text="Latest Signal", font=("Segoe UI", 10, "bold")).grid(
            row=12, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Label(content, textvariable=self._latest_signal_var).grid(
            row=13, column=0, columnspan=2, sticky="w", pady=4
        )

    def _on_mt5_connect(self) -> None:
        """Toggle MT5 connection state."""
        if not self._engine.is_connected():
            success = self._engine.connect()
            if success:
                self._mt5_status_var.set("Connected")
                self._mt5_btn.config(text="Disconnect")
            else:
                messagebox.showerror("MT5 Error", "Failed to connect to MT5 terminal.")
        else:
            self._engine.disconnect()
            self._mt5_status_var.set("Disconnected")
            self._mt5_btn.config(text="Connect")

    def _on_bot_toggle(self) -> None:
        """Toggle Telegram bot start/stop."""
        bot = self._bot_ref.get("bot")
        if bot is None or not bot.is_running():
            # Start bot
            token = self._engine.config.telegram_bot_token
            if not token:
                messagebox.showwarning("No Token", "Telegram bot token not configured.")
                return
            signal_queue = self._bot_ref.get("queue", queue.Queue())
            bot = SignalBot(
                token,
                signal_queue,
                aliases=self._engine.config.symbol_aliases,
            )
            bot.start()
            self._bot_ref["bot"] = bot
            self._bot_status_var.set("Running")
            self._bot_btn.config(text="Stop Bot")
        else:
            # Stop bot
            bot.stop()
            self._bot_ref["bot"] = None
            self._bot_status_var.set("Stopped")
            self._bot_btn.config(text="Start Bot")

    def update_latest_signal(self, signal: Signal) -> None:
        """Update the label showing the latest received signal."""
        self._latest_signal_var.set(
            f"{signal.action} {signal.symbol} @ {signal.entry} "
            f"| SL={signal.sl} TP1={signal.tp1} TP2={signal.tp2}"
        )


# ── Manual Entry Tab ──────────────────────────────────────────────────────────


class _ManualEntryTab(ttk.Frame):
    """
    Tab for manually entering trading signals without Telegram.
    """

    def __init__(
        self,
        parent: ttk.Notebook,
        engine: MT5Engine,
        signal_callback,
        logger: logging.Logger,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._signal_callback = signal_callback
        self._log = logger

        # Form StringVars
        self._action_var = tk.StringVar(value="BUY")
        self._symbol_var = tk.StringVar(value=engine.config.symbol)
        self._entry_var = tk.StringVar(value="")
        self._sl_var = tk.StringVar(value="")
        self._tp1_var = tk.StringVar(value="")
        self._tp2_var = tk.StringVar(value="")
        self._lot_var = tk.StringVar(value=str(engine.config.base_lot))

        content = ttk.Frame(self, padding=16)
        content.pack(fill="both", expand=True)

        row = 0

        ttk.Label(content, text="Manual Signal Entry", font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        row += 1

        # Action
        ttk.Label(content, text="Action:").grid(row=row, column=0, sticky="w", pady=4)
        action_combo = ttk.Combobox(
            content, textvariable=self._action_var, values=["BUY", "SELL"], state="readonly", width=15
        )
        action_combo.grid(row=row, column=1, sticky="w", pady=4)
        action_combo.current(0)
        row += 1

        _add_field(content, row, "Symbol:", self._symbol_var)
        row += 1
        _add_field(content, row, "Entry Price:", self._entry_var)
        row += 1
        _add_field(content, row, "Stop Loss:", self._sl_var)
        row += 1
        _add_field(content, row, "TP1 Price:", self._tp1_var)
        row += 1
        _add_field(content, row, "TP2 Price:", self._tp2_var)
        row += 1
        _add_field(content, row, "Lot:", self._lot_var)
        row += 1

        ttk.Button(content, text="Execute Signal", command=self._on_execute).grid(
            row=row, column=0, columnspan=2, pady=16
        )

    def _on_execute(self) -> None:
        """Read form fields, create Signal, call callback and engine."""
        try:
            sig = Signal(
                action=self._action_var.get(),
                symbol=self._symbol_var.get(),
                entry=float(self._entry_var.get()),
                sl=float(self._sl_var.get()),
                tp1=float(self._tp1_var.get()),
                tp2=float(self._tp2_var.get()),
            )
        except ValueError as exc:
            messagebox.showerror("Invalid Input", f"Check numeric fields: {exc}")
            return

        self._signal_callback(sig)
        self._engine.process_signal(sig)


# ── Queue Logging Handler ─────────────────────────────────────────────────────


class _QueueLoggingHandler(logging.Handler):
    """
    Custom logging handler that schedules GUI widget updates on the main thread.

    Must use ``widget.after(0, ...)`` to safely update the ScrolledText widget
    from the logging thread.
    """

    def __init__(self, widget: tk.scrolledtext.ScrolledText) -> None:
        super().__init__()
        self._widget = widget

    def emit(self, record: logging.LogRecord) -> None:
        """Schedule ``_append`` to run on the main GUI thread."""
        # Pass record as default arg to capture it at call time
        self._widget.after(0, lambda: self._append(record))

    def _append(self, record: logging.LogRecord) -> None:
        """Append a formatted log record to the ScrolledText widget."""
        self._widget.configure(state="normal")
        self._widget.insert("end", f"{record.getMessage()}\n")
        self._widget.see("end")
        self._widget.configure(state="disabled")


# ── Main Application ──────────────────────────────────────────────────────────


class TraderApp(tk.Tk):
    """
    Main application window for the XAUUSD Trader Desktop app.

    Orchestrates the MT5 engine, Telegram bot, and manual signal entry
    through a tabbed GUI.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("XAUUSD Trader Desktop")
        self.geometry("800x600")

        # Load config; show setup wizard if path is missing
        self.trader_config = TraderConfig.load()
        if not self.trader_config.mt5_path:
            # Show wizard as a topmost modal dialog while the main window stays
            # behind it.  Do NOT withdraw() the main window on Windows; it
            # can prevent the transient child from mapping at all.
            wizard = SetupWizard(self)
            wizard.run()
            result = wizard.get_result()
            if result is None:
                self.destroy()
                return
            # Reload config from wizard result
            self.trader_config = TraderConfig(**result)

        # Core components
        self._engine = MT5Engine(self.trader_config)
        self._format_manager = get_manager()
        self._signal_queue: queue.Queue[Signal] = queue.Queue()
        self._bot_ref: dict = {"bot": None, "queue": self._signal_queue}
        self._polling_active = True
        self._latest_signal: Signal | None = None

        # Notebook tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # Dashboard tab
        self._dashboard = _DashboardTab(
            notebook, self._engine, self._bot_ref, _log
        )
        notebook.add(self._dashboard, text="Dashboard")

        # Manual Entry tab
        manual_tab = _ManualEntryTab(
            notebook, self._engine, self._on_manual_signal, _log
        )
        notebook.add(manual_tab, text="Manual Entry")

        # Log tab
        self._log_widget = tk.scrolledtext.ScrolledText(
            notebook, state="disabled", height=15
        )
        self._log_widget.pack(fill="both", expand=True)
        notebook.add(self._log_widget, text="Log")

        # Signal Formats tab
        formats_tab = _SignalFormatsTab(notebook, self._format_manager, _log)
        notebook.add(formats_tab, text="Signal Formats")

        # Attach logging handler
        handler = _QueueLoggingHandler(self._log_widget)
        handler.setLevel(logging.INFO)
        _log.addHandler(handler)
        _log.setLevel(logging.INFO)
        _log.info("XAUUSD Trader Desktop started.")

        # Start polling loop
        self.after(1000, self._poll_queue)

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _poll_queue(self) -> None:
        """Poll signal queue and process signals; reschedule self."""
        if not self._polling_active:
            return

        try:
            signal = self._signal_queue.get_nowait()
            self._engine.process_signal(signal)
            self._latest_signal = signal
            self._dashboard.update_latest_signal(signal)
        except queue.Empty:
            pass

        if self._polling_active:
            self.after(1000, self._poll_queue)

    def _on_manual_signal(self, signal: Signal) -> None:
        """Callback for signals entered via Manual Entry tab."""
        _log.info(
            "Manual signal: %s %s @ %s SL=%s TP1=%s TP2=%s",
            signal.action, signal.symbol, signal.entry,
            signal.sl, signal.tp1, signal.tp2,
        )

    def _on_close(self) -> None:
        """Clean shutdown: stop polling, stop bot, disconnect MT5."""
        self._polling_active = False
        bot = self._bot_ref.get("bot")
        if bot is not None:
            bot.stop()
        self._engine.disconnect()
        self.destroy()


# ── Helper ────────────────────────────────────────────────────────────────────


def _add_field(
    parent: ttk.Frame,
    row: int,
    label_text: str,
    var: tk.StringVar,
) -> None:
    """Add a label + entry row to a parent frame."""
    ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(parent, textvariable=var, width=30).grid(row=row, column=1, sticky="w", pady=4)


# ── Entry Point ───────────────────────────────────────────────────────────────


def _ensure_exe_dir() -> None:
    """When running as a PyInstaller bundled executable, change cwd to the
    directory containing the .exe so that config.json and state.json are
    created next to the executable, not in the user's Downloads/Desktop folder.
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        if exe_dir:
            os.chdir(exe_dir)


def main() -> None:
    """Create and run the main application window."""
    _ensure_exe_dir()
    app = TraderApp()
    app.mainloop()


if __name__ == "__main__":
    main()