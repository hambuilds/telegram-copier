"""
telegram_bot.py — XAUUSD Trader Desktop App
Chunk 4 — Telegram Listener

Spec: .kimchi/docs/plan.md
Reference: telegram-mt5-bot/main.py (original Telethon handler)
"""

from __future__ import annotations

import queue
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import Application, ContextTypes, MessageHandler

from signal_parser import Signal, parse_signal

# Lazy telegram import so tests can run without the package installed
_telegram: object = None  # type: ignore[assignment]

# Module-level aliases for runtime patching by tests
Application: Any = None
MessageHandler: Any = None
ContextTypes: Any = None
filters: Any = None


def _lazy_telegram():
    global _telegram, Application, MessageHandler, ContextTypes, filters
    if _telegram is None:
        from telegram import Update
        from telegram.ext import Application as _App, ContextTypes as _CT, MessageHandler as _MH, filters as _filt
        _telegram = type(
            "TelegramLib",
            (),
            {
                "Update": Update,
                "Application": _App,
                "ContextTypes": _CT,
                "MessageHandler": _MH,
                "filters": _filt,
            },
        )()
        # Expose at module level so tests can patch these names directly.
        # Use hasattr trick: if Application is already a Mock (set by
        # unittest.mock.patch), do NOT overwrite it — the patch target
        # (telegram_bot.Application) has replaced the name already.
        if not hasattr(Application, "builder"):
            Application = _telegram.Application
        if not hasattr(MessageHandler, "__name__"):
            MessageHandler = _telegram.MessageHandler
        if not hasattr(ContextTypes, "__name__"):
            ContextTypes = _telegram.ContextTypes
        if not hasattr(filters, "TEXT"):
            filters = _telegram.filters
    return _telegram


class SignalBot:
    """
    Lightweight Telegram bot that listens for trading signals.

    Incoming plain-text messages are parsed via ``parse_signal``.
    Valid ``Signal`` objects are put onto ``signal_queue`` for consumption
    by the desktop GUI (or any other caller).

    Parameters
    ----------
    token:
        Telegram bot token obtained via @BotFather.
    signal_queue:
        A ``queue.Queue`` that will receive ``Signal`` objects.
    aliases:
        Symbol alias mapping passed through to ``parse_signal``.
    """

    def __init__(
        self,
        token: str,
        signal_queue: queue.Queue[Signal],
        aliases: dict[str, str],
    ) -> None:
        self._token = token
        self._queue = signal_queue
        self._aliases = aliases
        self._app: Any = None
        self._thread: threading.Thread | None = None
        self._running = False

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def start(self) -> None:
        """Start the Telegram polling loop in a background daemon thread."""
        if self._running:
            return

        lib = _lazy_telegram()
        # Use module-level names so tests can patch telegram_bot.Application, etc.
        # _lazy_telegram() populates the module-level aliases on first call.
        self._app = Application.builder().token(self._token).build()

        # Register plain-text message handler
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message)
        )

        self._thread = threading.Thread(
            target=self._run_polling,
            name="SignalBot-polling",
            daemon=True,
        )
        self._thread.start()
        self._running = True

    def stop(self) -> None:
        """Stop the polling loop and join the background thread."""
        if not self._running or self._app is None:
            return

        # Run stop() and shutdown() on the thread's event loop.
        # shutdown() posts a shutdown signal and await_shutdown() blocks
        # until the application is fully stopped.
        self._app._process_updates = False  # type: ignore[attr-defined]
        self._app._closing = True  # type: ignore[attr-defined]
        try:
            self._app.stop()
            self._app.shutdown()
        except Exception:
            # If the app wasn't fully initialised yet, swallow the error.
            pass

        if self._thread is not None:
            self._thread.join(timeout=5.0)

        self._running = False

    def is_running(self) -> bool:
        """Return True if the bot thread is active."""
        return self._running

    # -------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------

    async def _on_message(self, update: Any, context: Any) -> None:
        """
        Handler invoked by python-telegram-bot for every non-command text message.

        Parses the message text and, on success, enqueues the resulting
        ``Signal`` object.
        """
        text = update.message.text if update.message else ""
        if not text or not text.strip():
            return

        signal = parse_signal(text, self._aliases)
        if signal is not None:
            self._queue.put(signal)

    def _run_polling(self) -> None:
        """
        Target for the background thread.  ``stop_signals=()`` prevents
        the thread from intercepting Ctrl+C (that belongs to the GUI).
        """
        if self._app is None:
            return
        import asyncio
        asyncio.run(self._app.run_polling(stop_signals=()))