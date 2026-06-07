"""
headless_trader.py — XAUUSD Trader Desktop App
Chunk 2 — Headless CLI Entry Point

Runs 24/7 on a VPS/cloud server without a GUI.
Receives signals via Telegram and executes them via MT5.
Monitors floating PnL and closes all positions when target is reached.

References:
  - Spec: .kimchi/docs/plan.md  (Chunk 2)
  - Dependencies: mt5_engine.MT5Engine, telegram_bot.SignalBot,
                  config_store.TraderConfig, format_manager.FormatManager
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import queue
import signal
import sys
import threading
import time
from pathlib import Path

# Bring TraderConfig into scope for type hints used by this module.
from config_store import TraderConfig
from format_manager import FormatManager
from mt5_engine import MT5Engine
from signal_parser import Signal

# Lazy import for optional Telegram bot
_telegram_bot_module: object = None  # type: ignore[assignment]


def _lazy_telegram_bot():
    global _telegram_bot_module
    if _telegram_bot_module is None:
        from telegram_bot import SignalBot

        _telegram_bot_module = SignalBot
    return _telegram_bot_module


# ── Logging setup ─────────────────────────────────────────────────────────────

_log_handler_file: logging.Handler | None = None
_log_handler_stream: logging.Handler | None = None


def _configure_logging(log_level: str) -> logging.Logger:
    """
    Configure module-level logging with a RotatingFileHandler and a
    StreamHandler (stdout).  Returns the 'headless_trader' logger.
    """
    global _log_handler_file, _log_handler_stream

    logger = logging.getLogger("headless_trader")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Prevent duplicate handlers on repeated calls (e.g. during tests).
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Rotating file handler: trader.log, 5 MB max, 3 backups.
    _log_handler_file = logging.handlers.RotatingFileHandler(
        "trader.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    _log_handler_file.setFormatter(fmt)
    logger.addHandler(_log_handler_file)

    # Stream handler for stdout.
    _log_handler_stream = logging.StreamHandler(sys.stdout)
    _log_handler_stream.setFormatter(fmt)
    logger.addHandler(_log_handler_stream)

    return logger


# ── Signal handler for graceful shutdown ─────────────────────────────────────

_running = False  # module-level flag set by signal handlers
_log: logging.Logger | None = None


def _on_signal(signum: int, frame) -> None:
    global _running
    if _log is not None:
        _log.info("Received signal %d — initiating graceful shutdown.", signum)
    _running = False


# ── HeadlessTrader ─────────────────────────────────────────────────────────────


class HeadlessTrader:
    """
    Headless 24/7 trading daemon.

    Connects to MT5, optionally starts a Telegram bot for signal ingestion,
    and runs a main loop that:
      1. Processes incoming signals from the Telegram bot queue.
      2. Checks floating PnL against ``pnl_target`` and closes all positions
         when the target is reached.

    Parameters
    ----------
    config_path: str
        Path to the JSON configuration file.
    log_level: str
        Logging level (``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``).
    enable_telegram: bool
        If ``False``, the Telegram bot is never started even when a token
        is present in the config.
    """

    def __init__(
        self,
        config_path: str,
        log_level: str,
        enable_telegram: bool,
    ) -> None:
        self._config_path = config_path
        self._log_level = log_level
        self._enable_telegram = enable_telegram

        self._config: TraderConfig = TraderConfig.load(config_path)
        self._engine: MT5Engine = MT5Engine(self._config)
        self._signal_queue: queue.Queue[Signal] = queue.Queue()
        self._format_manager: FormatManager = FormatManager.load_from_config()

        self._running = False
        self._bot = None  # type: ignore[attr-defined]

        global _log
        _log = _configure_logging(log_level)
        self._log = _log

    # ── Public API ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """
        Connect to MT5, optionally start the Telegram bot, and enter
        the main processing loop.
        """
        global _running

        # Connect to MT5.
        if not self._engine.connect():
            self._log.error("Failed to connect to MT5. Exiting.")
            return

        # Log account info if available.
        account_info = self._engine.get_account_info()
        if account_info is not None:
            self._log.info(
                "MT5 Account — balance=%.2f equity=%.2f profit=%.2f",
                account_info["balance"],
                account_info["equity"],
                account_info["profit"],
            )
        else:
            self._log.warning("Could not retrieve MT5 account info.")

        # Start Telegram bot if token is present and not disabled.
        if self._enable_telegram and self._config.telegram_bot_token:
            SignalBot = _lazy_telegram_bot()
            self._bot = SignalBot(
                token=self._config.telegram_bot_token,
                signal_queue=self._signal_queue,
                aliases=self._config.symbol_aliases,
            )
            self._bot.start()
            self._log.info("Telegram bot started.")
        else:
            self._log.info("Telegram bot disabled — no token or --no-telegram set.")

        self._running = True
        _running = True
        self._run_loop()

    # ── Main loop ─────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        """
        Process signals and check PnL target in a tight loop until
        ``_running`` is set to ``False`` by a signal handler.
        """
        global _running

        pnl_target = self._config.pnl_target
        pnl_interval = self._config.pnl_check_interval_seconds
        last_pnl_check = time.monotonic()
        magic = self._config.magic_number

        while _running:
            now = time.monotonic()

            # 1. Poll signal queue (non-blocking).
            try:
                signal_obj = self._signal_queue.get_nowait()
                self._log.info("Processing signal: %s %s @ %s", signal_obj.action, signal_obj.symbol, signal_obj.entry)
                self._engine.process_signal(signal_obj)
            except queue.Empty:
                pass

            # 2. Check PnL target.
            if pnl_target > 0 and (now - last_pnl_check) >= pnl_interval:
                pnl = self._engine.get_total_floating_pnl(magic=magic)
                self._log.debug("Floating PnL: %.2f / %.2f", pnl, pnl_target)
                if pnl >= pnl_target:
                    self._log.info(
                        "PnL target reached: %.2f / %.2f — closing all positions.",
                        pnl,
                        pnl_target,
                    )
                    closed = self._engine.close_all_positions(magic=magic)
                    self._log.info("Closed %d positions: %s", len(closed), closed)
                    self._engine.reset_martingale_state()
                    self._notify_telegram(
                        f"✅ PnL target reached! Closed {len(closed)} positions. Floating PnL: ${pnl:.2f}"
                    )
                last_pnl_check = now

            time.sleep(1)

        # Cleanup after loop exits.
        self._shutdown()

    # ── Telegram notification ──────────────────────────────────────────────

    def _notify_telegram(self, message: str) -> None:
        """
        Send a message via the Telegram bot if it is running.
        Silently logs errors — we never crash on notification failures.
        """
        if self._bot is None or not hasattr(self._bot, "_app") or self._bot._app is None:
            return
        try:
            import asyncio

            app = self._bot._app
            # run_sync schedules the coroutine in the bot's event loop and
            # blocks until completion, which is safe here inside the main loop.
            asyncio.get_event_loop().run_until_complete(
                app.bot.send_message(
                    chat_id=app._update_queue._bot._user_id,  # type: ignore[attr-defined]
                    text=message,
                )
            )
        except Exception as exc:
            self._log.warning("Telegram notification failed: %s", exc)

    # ── Shutdown ──────────────────────────────────────────────────────────

    def _shutdown(self) -> None:
        """Stop the bot and disconnect from MT5."""
        self._log.info("Shutting down HeadlessTrader.")

        # Stop Telegram bot.
        if self._bot is not None:
            try:
                self._bot.stop()
                self._log.info("Telegram bot stopped.")
            except Exception as exc:
                self._log.warning("Error stopping Telegram bot: %s", exc)

        # Disconnect MT5.
        try:
            self._engine.disconnect()
        except Exception as exc:
            self._log.warning("Error disconnecting MT5: %s", exc)

        self._log.info("HeadlessTrader shutdown complete.")


# ── CLI entry point ────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="XAUUSD Headless Trader — runs 24/7 without a GUI."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to config file (default: config.json in cwd)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Disable Telegram bot even if token is configured",
    )
    args = parser.parse_args()

    # Register signal handlers before entering the main loop.
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    trader = HeadlessTrader(
        config_path=args.config,
        log_level=args.log_level,
        enable_telegram=not args.no_telegram,
    )
    trader.start()


if __name__ == "__main__":
    main()