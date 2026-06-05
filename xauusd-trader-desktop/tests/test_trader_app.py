"""
test_trader_app.py — XAUUSD Trader Desktop App
Chunk 5 — Desktop GUI Tests

Spec: .kimchi/docs/plan.md

Tests behaviour and method-call interaction; does NOT test pixel-perfect
GUI rendering.

Strategy:
  - Inject tk_stub via sys.modules BEFORE any tkinter import so the
    real module classes (Tk, Toplevel, etc.) are the stub versions.
  - Mock MT5Engine and SignalBot so no real MT5 / Telegram is needed.
  - Use a temporary working directory for config file isolation.
"""

# ── Headless tkinter stub (must be before any tkinter import) ─────────────────
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import tk_stub as _tk_stub

sys.modules["tkinter"] = _tk_stub
sys.modules["tkinter.scrolledtext"] = _tk_stub
sys.modules["tkinter.ttk"] = _tk_stub
sys.modules["tkinter.messagebox"] = _tk_stub.messagebox

import json
import logging
import queue
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# Now import from the local source — tkinter will resolve to the stub
import tkinter as tk  # noqa: E402  (module replaced above)


# ── Temp-dir fixture ──────────────────────────────────────────────────────────


class _TempDirFixture(unittest.TestCase):
    """Creates a temporary working directory that is restored after each test."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self._orig_cwd = Path.cwd()
        os.chdir(self._tmp)
        # Ensure trader_app resolves from the source directory, not an installed package
        src = Path(__file__).parent.parent
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))

    def tearDown(self) -> None:
        os.chdir(self._orig_cwd)
        src = Path(__file__).parent.parent
        if str(src) in sys.path:
            sys.path.remove(str(src))
        shutil.rmtree(self._tmp, ignore_errors=True)


def _make_fake_config(path: str | Path = "config.json", **overrides: Any) -> None:
    base = {
        "mt5_path": "C:\\MT5\\terminal.exe",
        "mt5_account": 12345,
        "mt5_password": "secret",
        "mt5_server": "Demo-Server",
        "symbol": "XAUUSD",
        "symbol_aliases": {"GOLD": "XAUUSD", "XAU/USD": "XAUUSD"},
        "base_lot": 0.01,
        "martingale_multiplier": 2.0,
        "max_martingale_levels": 3,
        "position_a_ratio": 0.6,
        "position_b_ratio": 0.4,
        "magic_number": 20250605,
        "telegram_bot_token": "123456:ABC-DEF",
        "sl_pips": 50,
        "tp1_pips": 25,
        "tp2_pips": 50,
        "pip_value": 0.10,
        "mt5_connect_retries": 5,
        "mt5_connect_retry_delay": 10,
        "state_file": "state.json",
        "config_file": "config.json",
    }
    base.update(overrides)
    Path(path).write_text(json.dumps(base, indent=2))


# ── SetupWizard tests ─────────────────────────────────────────────────────────


class TestSetupWizard(_TempDirFixture):
    def test_save_writes_config_json(self) -> None:
        import trader_app

        root = tk.Tk()
        root.withdraw()

        wizard = trader_app.SetupWizard(root)
        wizard._mt5_path_var.set("D:\\MT5\\terminal.exe")
        wizard._mt5_account_var.set("99999")
        wizard._mt5_password_var.set("pw")
        wizard._mt5_server_var.set("Live")
        wizard._symbol_var.set("XAUUSD")
        wizard._base_lot_var.set("0.02")
        wizard._mart_mult_var.set("1.5")
        wizard._max_levels_var.set("5")
        wizard._pos_a_ratio_var.set("70")
        wizard._bot_token_var.set("tok")
        wizard._magic_var.set("111111")
        wizard._sl_pips_var.set("40")
        wizard._tp1_pips_var.set("20")
        wizard._tp2_pips_var.set("30")
        wizard._on_save()

        result = wizard.get_result()
        self.assertIsNotNone(result)
        self.assertEqual(result["mt5_path"], "D:\\MT5\\terminal.exe")
        self.assertEqual(result["mt5_account"], 99999)
        self.assertEqual(result["base_lot"], 0.02)
        self.assertAlmostEqual(result["position_a_ratio"], 0.70)
        self.assertAlmostEqual(result["position_b_ratio"], 0.30)
        self.assertTrue(Path("config.json").exists())
        root.destroy()

    def test_cancel_does_not_write_config(self) -> None:
        import trader_app

        root = tk.Tk()
        root.withdraw()
        wizard = trader_app.SetupWizard(root)
        # Prevent real destroy from closing the test process
        wizard.destroy = MagicMock()
        wizard._on_cancel()

        self.assertIsNone(wizard.get_result())
        self.assertFalse(Path("config.json").exists())
        root.destroy()

    def test_b_ratio_auto_computed(self) -> None:
        import trader_app

        root = tk.Tk()
        root.withdraw()
        wizard = trader_app.SetupWizard(root)
        wizard.destroy = MagicMock()
        wizard._pos_a_ratio_var.set("75")
        wizard._update_b_ratio()
        # The label text is updated via config(); check it contains 25
        self.assertIn("25.0", wizard._b_ratio_label.cget("text"))
        wizard._on_cancel()
        root.destroy()


# ── DashboardTab tests ────────────────────────────────────────────────────────


class TestDashboardTab(_TempDirFixture):
    def setUp(self) -> None:
        super().setUp()
        _make_fake_config("config.json")
        Path("state.json").write_text(json.dumps({"level": 1, "lot": 0.02}))

    @patch("mt5_engine.MT5Engine")
    @patch("telegram_bot.SignalBot")
    def test_connect_btn_toggles_state(
        self, mock_bot_cls: MagicMock, mock_engine_cls: MagicMock
    ) -> None:
        import trader_app

        mock_engine = MagicMock()
        mock_engine.is_connected.return_value = False
        mock_engine.connect.return_value = True
        mock_engine.config.symbol = "XAUUSD"
        mock_engine.config.symbol_aliases = {"GOLD": "XAUUSD"}
        mock_engine_cls.return_value = mock_engine

        root = tk.Tk()
        root.withdraw()
        bot_ref: dict[str, Any] = {"bot": None}

        tab = trader_app._DashboardTab(
            tk.ttk.Notebook(root),
            mock_engine,
            bot_ref,
            logging.getLogger("test"),
        )

        # Connect
        tab._on_mt5_connect()
        mock_engine.connect.assert_called_once()

        # Disconnect
        mock_engine.is_connected.return_value = True
        tab._on_mt5_connect()
        mock_engine.disconnect.assert_called_once()

        root.destroy()

    @patch("mt5_engine.MT5Engine")
    @patch("telegram_bot.SignalBot")
    def test_bot_toggle_starts_bot(
        self, mock_bot_cls: MagicMock, mock_engine_cls: MagicMock
    ) -> None:
        import trader_app

        mock_engine = MagicMock()
        mock_engine.is_connected.return_value = False
        mock_engine.config.symbol = "XAUUSD"
        mock_engine.config.symbol_aliases = {"GOLD": "XAUUSD"}
        mock_engine.config.telegram_bot_token = "123:abc"
        mock_engine_cls.return_value = mock_engine

        mock_bot = MagicMock()
        mock_bot.is_running.return_value = False
        mock_bot_cls.return_value = mock_bot

        root = tk.Tk()
        root.withdraw()
        bot_ref: dict[str, Any] = {"bot": None}

        tab = trader_app._DashboardTab(
            tk.ttk.Notebook(root),
            mock_engine,
            bot_ref,
            logging.getLogger("test"),
        )

        tab._on_bot_toggle()
        mock_bot.start.assert_called_once()
        self.assertIs(bot_ref["bot"], mock_bot)

        root.destroy()


# ── ManualEntryTab tests ──────────────────────────────────────────────────────


class TestManualEntryTab(_TempDirFixture):
    def setUp(self) -> None:
        super().setUp()
        _make_fake_config("config.json")

    @patch("mt5_engine.MT5Engine")
    @patch("telegram_bot.SignalBot")
    def test_execute_creates_signal_and_calls_process(
        self, _: MagicMock, mock_engine_cls: MagicMock
    ) -> None:
        import trader_app

        mock_engine = MagicMock()
        mock_engine.is_connected.return_value = False
        mock_engine.process_signal.return_value = True
        mock_engine.config.symbol = "XAUUSD"
        mock_engine.config.symbol_aliases = {"GOLD": "XAUUSD"}
        mock_engine.config.base_lot = 0.01
        mock_engine_cls.return_value = mock_engine

        root = tk.Tk()
        root.withdraw()

        executed_signals: list = []

        def capture(sig):
            executed_signals.append(sig)

        tab = trader_app._ManualEntryTab(
            tk.ttk.Notebook(root),
            mock_engine,
            capture,
            logging.getLogger("test"),
        )

        tab._action_var.set("BUY")
        tab._symbol_var.set("XAUUSD")
        tab._entry_var.set("2350.00")
        tab._sl_var.set("2345.00")
        tab._tp1_var.set("2352.50")
        tab._tp2_var.set("2355.00")
        tab._lot_var.set("0.01")

        tab._on_execute()

        self.assertEqual(len(executed_signals), 1)
        sig = executed_signals[0]
        self.assertEqual(sig.action, "BUY")
        self.assertEqual(sig.symbol, "XAUUSD")
        self.assertAlmostEqual(sig.entry, 2350.00)
        self.assertAlmostEqual(sig.sl, 2345.00)
        self.assertAlmostEqual(sig.tp1, 2352.50)
        self.assertAlmostEqual(sig.tp2, 2355.00)
        mock_engine.process_signal.assert_called_once_with(sig)

        root.destroy()


# ── Queue polling tests ───────────────────────────────────────────────────────


class TestQueuePolling(_TempDirFixture):
    def setUp(self) -> None:
        super().setUp()
        _make_fake_config("config.json")

    @patch("mt5_engine.MT5Engine")
    @patch("telegram_bot.SignalBot")
    def test_poll_queue_dispatches_signal(
        self, _: MagicMock, mock_engine_cls: MagicMock
    ) -> None:
        import trader_app
        from signal_parser import Signal

        mock_engine = MagicMock()
        mock_engine.is_connected.return_value = False
        mock_engine.process_signal.return_value = True
        mock_engine.config.symbol = "XAUUSD"
        mock_engine.config.symbol_aliases = {"GOLD": "XAUUSD"}
        mock_engine_cls.return_value = mock_engine

        # Build a signal queue and enqueue one signal
        sq: queue.Queue[Signal] = queue.Queue()
        sig = Signal(
            action="SELL", symbol="XAUUSD", entry=2340.0,
            sl=2335.0, tp1=2342.5, tp2=2345.0,
        )
        sq.put(sig)

        # Manually construct a minimal app object (bypass __init__)
        app = trader_app.TraderApp.__new__(trader_app.TraderApp)
        app._engine = mock_engine
        app._signal_queue = sq
        app._polling_active = True
        app._latest_signal = None
        app._dashboard = MagicMock()
        app._log = logging.getLogger("test")
        # _poll_queue schedules itself via self.after() — mock it out
        app.after = MagicMock()

        app._poll_queue()

        mock_engine.process_signal.assert_called_once_with(sig)
        self.assertEqual(app._latest_signal, sig)
        app._dashboard.update_latest_signal.assert_called_once_with(sig)


# ── QueueLoggingHandler tests ─────────────────────────────────────────────────


class TestQueueLoggingHandler(_TempDirFixture):
    def test_handler_queues_message(self) -> None:
        import trader_app

        root = tk.Tk()
        root.withdraw()

        widget = tk.scrolledtext.ScrolledText(root)
        widget.configure(state="disabled")

        handler = trader_app._QueueLoggingHandler(widget)

        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0,
            msg="Test log message", args=(), exc_info=None,
        )

        # The handler should schedule a call via widget.after(0, ...)
        calls: list = []
        widget.after = lambda ms, fn, *args: calls.append((ms, fn)) or 0

        handler.emit(record)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 0)  # ms == 0

        # Execute the scheduled _append function
        fn = calls[0][1]
        fn()

        self.assertEqual(widget.get("1.0", tk.END).strip(), "Test log message")

        root.destroy()


# ── Shutdown sequence tests ───────────────────────────────────────────────────


class TestShutdownSequence(_TempDirFixture):
    def setUp(self) -> None:
        super().setUp()
        _make_fake_config("config.json")

    @patch("mt5_engine.MT5Engine")
    @patch("telegram_bot.SignalBot")
    def test_close_stops_bot_and_disconnects(
        self, mock_bot_cls: MagicMock, mock_engine_cls: MagicMock
    ) -> None:
        import trader_app

        mock_engine = MagicMock()
        mock_engine.is_connected.return_value = True
        mock_engine.config.symbol = "XAUUSD"
        mock_engine.config.symbol_aliases = {"GOLD": "XAUUSD"}
        mock_engine_cls.return_value = mock_engine

        mock_bot = MagicMock()
        mock_bot.is_running.return_value = True
        mock_bot_cls.return_value = mock_bot

        bot_ref: dict[str, Any] = {"bot": mock_bot}

        # Build minimal app via __new__ (bypass __init__)
        app = trader_app.TraderApp.__new__(trader_app.TraderApp)
        app._engine = mock_engine
        app._bot_ref = bot_ref
        app._polling_active = True
        app._log = logging.getLogger("test")
        app._log.addHandler(logging.NullHandler())
        # _on_close calls self.destroy() — mock it so the test doesn't exit
        app.destroy = MagicMock()

        app._on_close()

        mock_bot.stop.assert_called_once()
        mock_engine.disconnect.assert_called_once()
        self.assertFalse(app._polling_active)


# ── Import sanity test ────────────────────────────────────────────────────────


class TestImport(_TempDirFixture):
    def test_import_succeeds(self) -> None:
        _make_fake_config("config.json")
        import trader_app

        self.assertTrue(hasattr(trader_app, "TraderApp"))
        self.assertTrue(hasattr(trader_app, "SetupWizard"))
        self.assertTrue(hasattr(trader_app, "_DashboardTab"))
        self.assertTrue(hasattr(trader_app, "_ManualEntryTab"))
        self.assertTrue(hasattr(trader_app, "_QueueLoggingHandler"))


if __name__ == "__main__":
    unittest.main()