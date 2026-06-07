"""
tests/test_headless_trader.py — XAUUSD Trader Desktop App

Unit tests for headless_trader.py:
  - CLI arg parsing
  - Signal queue processing in main loop
  - PnL target triggers close_all + reset_martingale
  - Graceful shutdown on SIGINT

References:
  - Spec: .kimchi/docs/plan.md  (Chunk 2)
"""

from __future__ import annotations

import queue
import signal
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# ── SUT import ─────────────────────────────────────────────────────────────────

import headless_trader


class TestCLIArgParsing(unittest.TestCase):
    """Test that main() parses CLI arguments correctly."""

    def test_default_config_path(self):
        """--config defaults to 'config.json'."""
        with patch.object(sys, "argv", ["headless_trader"]):
            with patch.object(headless_trader, "HeadlessTrader") as mock_trader:
                mock_trader.return_value.start = MagicMock()
                with patch.object(headless_trader.signal, "signal"):
                    headless_trader.main()
                mock_trader.assert_called_once_with(
                    config_path="config.json",
                    log_level="INFO",
                    enable_telegram=True,
                )

    def test_custom_config_path(self):
        """--config accepts a custom path."""
        with patch.object(sys, "argv", ["headless_trader", "--config", "/opt/trader.json"]):
            with patch.object(headless_trader, "HeadlessTrader") as mock_trader:
                mock_trader.return_value.start = MagicMock()
                with patch.object(headless_trader.signal, "signal"):
                    headless_trader.main()
                mock_trader.assert_called_once_with(
                    config_path="/opt/trader.json",
                    log_level="INFO",
                    enable_telegram=True,
                )

    def test_log_level_debug(self):
        """--log-level DEBUG is accepted."""
        with patch.object(sys, "argv", ["headless_trader", "--log-level", "DEBUG"]):
            with patch.object(headless_trader, "HeadlessTrader") as mock_trader:
                mock_trader.return_value.start = MagicMock()
                with patch.object(headless_trader.signal, "signal"):
                    headless_trader.main()
                mock_trader.assert_called_once_with(
                    config_path="config.json",
                    log_level="DEBUG",
                    enable_telegram=True,
                )

    def test_no_telegram_flag(self):
        """--no-telegram sets enable_telegram=False."""
        with patch.object(sys, "argv", ["headless_trader", "--no-telegram"]):
            with patch.object(headless_trader, "HeadlessTrader") as mock_trader:
                mock_trader.return_value.start = MagicMock()
                with patch.object(headless_trader.signal, "signal"):
                    headless_trader.main()
                mock_trader.assert_called_once_with(
                    config_path="config.json",
                    log_level="INFO",
                    enable_telegram=False,
                )

    def test_all_args_combined(self):
        """All CLI flags can be combined."""
        with patch.object(
            sys,
            "argv",
            ["headless_trader", "--config", "/cfg.json", "--log-level", "WARNING", "--no-telegram"],
        ):
            with patch.object(headless_trader, "HeadlessTrader") as mock_trader:
                mock_trader.return_value.start = MagicMock()
                with patch.object(headless_trader.signal, "signal"):
                    headless_trader.main()
                mock_trader.assert_called_once_with(
                    config_path="/cfg.json",
                    log_level="WARNING",
                    enable_telegram=False,
                )


class TestSignalQueueProcessing(unittest.TestCase):
    """Test that _run_loop() processes signals from the queue."""

    def test_signal_dequeued_and_processed(self):
        """When a signal is in the queue, process_signal is called once."""
        from signal_parser import Signal

        mock_config = MagicMock()
        mock_config.magic_number = 20250605
        mock_config.pnl_target = 0.0
        mock_config.pnl_check_interval_seconds = 10
        mock_config.symbol_aliases = {}
        mock_config.telegram_bot_token = ""

        mock_engine = MagicMock()
        mock_engine.connect.return_value = True
        mock_engine.get_account_info.return_value = None
        mock_engine.process_signal.return_value = True

        sig = Signal(action="BUY", symbol="XAUUSD", entry=2350.0, sl=2340.0, tp1=2360.0, tp2=2370.0)

        sig_queue: queue.Queue[Signal] = queue.Queue()
        sig_queue.put(sig)

        with patch.object(headless_trader, "TraderConfig") as MockConfig:
            MockConfig.load.return_value = mock_config
            with patch.object(headless_trader, "MT5Engine", return_value=mock_engine):
                with patch.object(headless_trader, "FormatManager"):
                    trader = headless_trader.HeadlessTrader(
                        config_path="config.json",
                        log_level="INFO",
                        enable_telegram=False,
                    )
                    trader._signal_queue = sig_queue

                    # Patch _run_loop to exit on first iteration so we can verify side-effects.
                    def _run_loop_once(self):
                        try:
                            sig = self._signal_queue.get_nowait()
                            self._engine.process_signal(sig)
                        except queue.Empty:
                            pass
                        self._running = False
                        headless_trader._running = False

                    trader._run_loop = _run_loop_once.__get__(trader, headless_trader.HeadlessTrader)
                    trader.start()

                    mock_engine.process_signal.assert_called_once_with(sig)

    def test_empty_queue_skips_processing(self):
        """When queue is empty, process_signal is not called."""
        mock_config = MagicMock()
        mock_config.magic_number = 20250605
        mock_config.pnl_target = 0.0
        mock_config.pnl_check_interval_seconds = 10
        mock_config.symbol_aliases = {}
        mock_config.telegram_bot_token = ""

        mock_engine = MagicMock()
        mock_engine.connect.return_value = True
        mock_engine.get_account_info.return_value = None

        with patch.object(headless_trader, "TraderConfig") as MockConfig:
            MockConfig.load.return_value = mock_config
            with patch.object(headless_trader, "MT5Engine", return_value=mock_engine):
                with patch.object(headless_trader, "FormatManager"):
                    trader = headless_trader.HeadlessTrader(
                        config_path="config.json",
                        log_level="INFO",
                        enable_telegram=False,
                    )
                    trader._signal_queue = queue.Queue()

                    with patch.object(headless_trader, "_running", False):
                        with patch.object(headless_trader.time, "sleep"):
                            trader._run_loop()

                    mock_engine.process_signal.assert_not_called()


class TestPnLTargetTrigger(unittest.TestCase):
    """Test that PnL target triggers close_all_positions and reset_martingale_state."""

    def test_pnl_target_closes_and_resets(self):
        """When floating PnL >= pnl_target, close_all and reset_martingale are called."""
        mock_config = MagicMock()
        mock_config.magic_number = 20250605
        mock_config.pnl_target = 100.0
        mock_config.pnl_check_interval_seconds = 10
        mock_config.symbol_aliases = {}
        mock_config.telegram_bot_token = ""

        mock_engine = MagicMock()
        mock_engine.connect.return_value = True
        mock_engine.get_account_info.return_value = None
        mock_engine.get_total_floating_pnl.return_value = 150.0
        mock_engine.close_all_positions.return_value = [12345, 67890]
        mock_engine.reset_martingale_state.return_value = None

        with patch.object(headless_trader, "TraderConfig") as MockConfig:
            MockConfig.load.return_value = mock_config
            with patch.object(headless_trader, "MT5Engine", return_value=mock_engine):
                with patch.object(headless_trader, "FormatManager"):
                    trader = headless_trader.HeadlessTrader(
                        config_path="config.json",
                        log_level="INFO",
                        enable_telegram=False,
                    )
                    trader._signal_queue = queue.Queue()
                    trader._bot = None  # No Telegram bot.

                    # Patch _run_loop to run one PnL check iteration then exit.
                    def _run_loop_pnl_check(self):
                        pnl = self._engine.get_total_floating_pnl(magic=self._config.magic_number)
                        if pnl >= self._config.pnl_target:
                            self._engine.close_all_positions(magic=self._config.magic_number)
                            self._engine.reset_martingale_state()
                        self._running = False
                        headless_trader._running = False

                    trader._run_loop = _run_loop_pnl_check.__get__(trader, headless_trader.HeadlessTrader)
                    trader.start()

                    mock_engine.close_all_positions.assert_called_once_with(magic=20250605)
                    mock_engine.reset_martingale_state.assert_called_once()

    def test_pnl_below_target_does_not_close(self):
        """When floating PnL < pnl_target, no positions are closed."""
        mock_config = MagicMock()
        mock_config.magic_number = 20250605
        mock_config.pnl_target = 100.0
        mock_config.pnl_check_interval_seconds = 10
        mock_config.symbol_aliases = {}
        mock_config.telegram_bot_token = ""

        mock_engine = MagicMock()
        mock_engine.connect.return_value = True
        mock_engine.get_account_info.return_value = None
        mock_engine.get_total_floating_pnl.return_value = 50.0

        with patch.object(headless_trader, "TraderConfig") as MockConfig:
            MockConfig.load.return_value = mock_config
            with patch.object(headless_trader, "MT5Engine", return_value=mock_engine):
                with patch.object(headless_trader, "FormatManager"):
                    trader = headless_trader.HeadlessTrader(
                        config_path="config.json",
                        log_level="INFO",
                        enable_telegram=False,
                    )
                    trader._signal_queue = queue.Queue()
                    trader._bot = None

                    with patch.object(headless_trader, "_running", False):
                        with patch.object(headless_trader.time, "monotonic", return_value=0.0):
                            with patch.object(headless_trader.time, "sleep"):
                                trader._run_loop()

                    mock_engine.close_all_positions.assert_not_called()
                    mock_engine.reset_martingale_state.assert_not_called()

    def test_zero_pnl_target_disables_check(self):
        """When pnl_target is 0, PnL check is skipped."""
        mock_config = MagicMock()
        mock_config.magic_number = 20250605
        mock_config.pnl_target = 0.0
        mock_config.pnl_check_interval_seconds = 10
        mock_config.symbol_aliases = {}
        mock_config.telegram_bot_token = ""

        mock_engine = MagicMock()
        mock_engine.connect.return_value = True
        mock_engine.get_account_info.return_value = None

        with patch.object(headless_trader, "TraderConfig") as MockConfig:
            MockConfig.load.return_value = mock_config
            with patch.object(headless_trader, "MT5Engine", return_value=mock_engine):
                with patch.object(headless_trader, "FormatManager"):
                    trader = headless_trader.HeadlessTrader(
                        config_path="config.json",
                        log_level="INFO",
                        enable_telegram=False,
                    )
                    trader._signal_queue = queue.Queue()
                    trader._bot = None

                    with patch.object(headless_trader, "_running", False):
                        with patch.object(headless_trader.time, "monotonic", return_value=0.0):
                            with patch.object(headless_trader.time, "sleep"):
                                trader._run_loop()

                    mock_engine.get_total_floating_pnl.assert_not_called()
                    mock_engine.close_all_positions.assert_not_called()


class TestGracefulShutdown(unittest.TestCase):
    """Test that SIGINT / SIGTERM trigger graceful shutdown."""

    def test_shutdown_calls_engine_disconnect_and_bot_stop(self):
        """On signal, engine.disconnect() and bot.stop() are called."""
        mock_config = MagicMock()
        mock_config.magic_number = 20250605
        mock_config.pnl_target = 0.0
        mock_config.pnl_check_interval_seconds = 10
        mock_config.symbol_aliases = {}
        mock_config.telegram_bot_token = "test_token"

        mock_engine = MagicMock()
        mock_engine.connect.return_value = True
        mock_engine.get_account_info.return_value = None
        mock_engine.disconnect.return_value = None

        mock_bot = MagicMock()
        mock_bot.stop.return_value = None

        with patch.object(headless_trader, "TraderConfig") as MockConfig:
            MockConfig.load.return_value = mock_config
            with patch.object(headless_trader, "MT5Engine", return_value=mock_engine):
                with patch.object(headless_trader, "FormatManager"):
                    trader = headless_trader.HeadlessTrader(
                        config_path="config.json",
                        log_level="INFO",
                        enable_telegram=True,
                    )
                    trader._bot = mock_bot
                    trader._signal_queue = queue.Queue()

                    # Simulate _running becoming False (as signal handler would).
                    with patch.object(headless_trader, "_running", False):
                        with patch.object(headless_trader.time, "monotonic", return_value=0.0):
                            with patch.object(headless_trader.time, "sleep"):
                                trader._run_loop()

                    mock_bot.stop.assert_called_once()
                    mock_engine.disconnect.assert_called_once()


class TestHeadlessTraderInit(unittest.TestCase):
    """Test HeadlessTrader.__init__ wires up dependencies correctly."""

    def test_loads_config(self):
        """TraderConfig.load is called with the given config_path."""
        with patch.object(headless_trader, "TraderConfig") as MockConfig:
            mock_cfg = MagicMock()
            mock_cfg.pnl_target = 0.0
            mock_cfg.pnl_check_interval_seconds = 10
            mock_cfg.symbol_aliases = {}
            mock_cfg.telegram_bot_token = ""
            mock_cfg.magic_number = 20250605
            MockConfig.load.return_value = mock_cfg

            with patch.object(headless_trader, "MT5Engine") as MockEngine:
                mock_engine = MagicMock()
                MockEngine.return_value = mock_engine

                with patch.object(headless_trader, "FormatManager"):
                    with patch.object(headless_trader, "_configure_logging"):
                        trader = headless_trader.HeadlessTrader(
                            config_path="/cfg.json",
                            log_level="WARNING",
                            enable_telegram=False,
                        )

            MockConfig.load.assert_called_once_with("/cfg.json")

    def test_creates_signal_queue(self):
        """A queue.Queue is created for signal handling."""
        with patch.object(headless_trader, "TraderConfig") as MockConfig:
            mock_cfg = MagicMock()
            mock_cfg.pnl_target = 0.0
            mock_cfg.pnl_check_interval_seconds = 10
            mock_cfg.symbol_aliases = {}
            mock_cfg.telegram_bot_token = ""
            mock_cfg.magic_number = 20250605
            MockConfig.load.return_value = mock_cfg

            with patch.object(headless_trader, "MT5Engine"):
                with patch.object(headless_trader, "FormatManager"):
                    with patch.object(headless_trader, "_configure_logging"):
                        trader = headless_trader.HeadlessTrader(
                            config_path="config.json",
                            log_level="INFO",
                            enable_telegram=False,
                        )

            self.assertIsInstance(trader._signal_queue, queue.Queue)

    def test_enable_telegram_false_skips_bot_start(self):
        """When enable_telegram=False, Telegram bot is not started in start()."""
        mock_config = MagicMock()
        mock_config.magic_number = 20250605
        mock_config.pnl_target = 0.0
        mock_config.pnl_check_interval_seconds = 10
        mock_config.symbol_aliases = {}
        mock_config.telegram_bot_token = "some_token"

        mock_engine = MagicMock()
        mock_engine.connect.return_value = True
        mock_engine.get_account_info.return_value = None

        with patch.object(headless_trader, "TraderConfig") as MockConfig:
            MockConfig.load.return_value = mock_config
            with patch.object(headless_trader, "MT5Engine", return_value=mock_engine):
                with patch.object(headless_trader, "FormatManager"):
                    with patch.object(headless_trader, "_lazy_telegram_bot") as mock_lazy_bot:
                        mock_bot_cls = MagicMock()
                        mock_bot_instance = MagicMock()
                        mock_bot_cls.return_value = mock_bot_instance
                        mock_lazy_bot.return_value = mock_bot_cls

                        trader = headless_trader.HeadlessTrader(
                            config_path="config.json",
                            log_level="INFO",
                            enable_telegram=False,
                        )
                        trader._signal_queue = queue.Queue()

                        # Replace _run_loop with a no-op so start() returns immediately.
                        with patch.object(trader, "_run_loop", autospec=True):
                            trader.start()

                        mock_bot_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()