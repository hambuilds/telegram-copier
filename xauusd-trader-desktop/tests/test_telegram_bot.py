"""
test_telegram_bot.py — XAUUSD Trader Desktop App
Chunk 4 — Telegram Listener Tests

Spec: .kimchi/docs/plan.md
"""

from __future__ import annotations

import queue
import unittest
from unittest.mock import (
    ANY,
    AsyncMock,
    MagicMock,
    patch,
)

from signal_parser import Signal

# Import the class under test
from telegram_bot import SignalBot


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_fake_update(text: str) -> MagicMock:
    """Return a fake ``telegram.Update`` with a plain-text message."""
    msg = MagicMock()
    msg.text = text
    update = MagicMock()
    update.message = msg
    return update


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSignalBotInit(unittest.TestCase):
    """SignalBot initialises with correct defaults."""

    def test_token_stored(self):
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-token", q, {"GOLD": "XAUUSD"})
        self.assertEqual(bot._token, "my-token")

    def test_queue_stored(self):
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-token", q, {})
        self.assertIs(bot._queue, q)

    def test_aliases_stored(self):
        q: queue.Queue[Signal] = queue.Queue()
        aliases = {"XAU/USD": "XAUUSD"}
        bot = SignalBot("my-token", q, aliases)
        self.assertEqual(bot._aliases, aliases)

    def test_not_running_initially(self):
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-token", q, {})
        self.assertFalse(bot.is_running())


class TestSignalBotStartStop(unittest.TestCase):
    """``start()`` and ``stop()`` manage the background thread correctly."""

    @patch("telegram_bot.Application")
    def test_start_creates_thread(self, mock_app_cls):
        """start() must spawn a daemon thread and mark the bot as running."""
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-token", q, {})

        bot.start()

        try:
            self.assertTrue(bot.is_running())
            self.assertIsNotNone(bot._thread)
            self.assertTrue(bot._thread.daemon)
        finally:
            bot.stop()

    @patch("telegram_bot.Application")
    def test_start_idempotent(self, mock_app_cls):
        """Calling start() twice must not create multiple threads."""
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-token", q, {})

        bot.start()
        first_thread = bot._thread

        bot.start()  # second call — must be no-op
        try:
            self.assertIs(bot._thread, first_thread)
        finally:
            bot.stop()

    @patch("telegram_bot.Application")
    def test_stop_joins_thread(self, mock_app_cls):
        """stop() must join the background thread and mark bot as not running."""
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-token", q, {})

        bot.start()
        self.assertTrue(bot.is_running())

        bot.stop()

        self.assertFalse(bot.is_running())

    @patch("telegram_bot.Application")
    def test_stop_idempotent(self, mock_app_cls):
        """Calling stop() on an already-stopped bot must not raise."""
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-token", q, {})
        # stop when not running must be safe
        bot.stop()
        self.assertFalse(bot.is_running())


class TestSignalBotMessageParsing(unittest.TestCase):
    """Text messages are parsed and enqueued as Signal objects."""

    @patch("telegram_bot.Application")
    def test_valid_multiline_signal_enqueue(self, mock_app_cls):
        """A valid multi-line BUY signal must be put on the queue."""
        q: queue.Queue[Signal] = queue.Queue()
        aliases = {"GOLD": "XAUUSD", "XAU/USD": "XAUUSD"}
        bot = SignalBot("my-token", q, aliases)

        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app

        bot.start()
        try:
            # Simulate a message being processed by the handler
            raw = (
                "BUY XAUUSD @ 2350.00\n"
                "SL: 2345.00\n"
                "TP1: 2352.50\n"
                "TP2: 2355.00"
            )
            update = _make_fake_update(raw)

            # Manually invoke _on_message since the thread is mocked
            import asyncio
            asyncio.run(bot._on_message(update, MagicMock()))

            self.assertFalse(q.empty())
            sig = q.get_nowait()
            self.assertEqual(sig.action, "BUY")
            self.assertEqual(sig.symbol, "XAUUSD")
            self.assertAlmostEqual(sig.entry, 2350.00)
            self.assertAlmostEqual(sig.sl, 2345.00)
            self.assertAlmostEqual(sig.tp1, 2352.50)
            self.assertAlmostEqual(sig.tp2, 2355.00)
        finally:
            bot.stop()

    @patch("telegram_bot.Application")
    def test_valid_compact_signal_enqueue(self, mock_app_cls):
        """A compact single-line signal must be parsed and enqueued."""
        q: queue.Queue[Signal] = queue.Queue()
        aliases = {"GOLD": "XAUUSD", "XAU/USD": "XAUUSD"}
        bot = SignalBot("my-token", q, aliases)

        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app

        bot.start()
        try:
            raw = "Gold Buy 2350.00 | SL 2345.00 | TP1 2352.50 | TP2 2355.00"
            update = _make_fake_update(raw)

            import asyncio
            asyncio.run(bot._on_message(update, MagicMock()))

            self.assertFalse(q.empty())
            sig = q.get_nowait()
            self.assertEqual(sig.action, "BUY")
            self.assertEqual(sig.symbol, "XAUUSD")
        finally:
            bot.stop()

    @patch("telegram_bot.Application")
    def test_valid_single_line_signal(self, mock_app_cls):
        """A '/'-separated single-line signal must be parsed."""
        q: queue.Queue[Signal] = queue.Queue()
        aliases = {"XAU/USD": "XAUUSD"}
        bot = SignalBot("my-token", q, aliases)

        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app

        bot.start()
        try:
            raw = "SELL XAU/USD 2350.00 / SL 2345.00 / TP1 2352.50 / TP2 2355.00"
            update = _make_fake_update(raw)

            import asyncio
            asyncio.run(bot._on_message(update, MagicMock()))

            self.assertFalse(q.empty())
            sig = q.get_nowait()
            self.assertEqual(sig.action, "SELL")
        finally:
            bot.stop()

    @patch("telegram_bot.Application")
    def test_non_signal_message_not_enqueued(self, mock_app_cls):
        """A plain text message that is not a signal must not enqueue anything."""
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-token", q, {})

        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app

        bot.start()
        try:
            update = _make_fake_update("Hello, how are you?")
            import asyncio
            asyncio.run(bot._on_message(update, MagicMock()))
            self.assertTrue(q.empty())
        finally:
            bot.stop()

    @patch("telegram_bot.Application")
    def test_empty_message_not_enqueued(self, mock_app_cls):
        """A blank message must not cause enqueue."""
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-token", q, {})

        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app

        bot.start()
        try:
            update = _make_fake_update("")
            import asyncio
            asyncio.run(bot._on_message(update, MagicMock()))
            self.assertTrue(q.empty())
        finally:
            bot.stop()

    @patch("telegram_bot.Application")
    def test_none_message_handled(self, mock_app_cls):
        """A message with no text attribute must be handled gracefully."""
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-token", q, {})

        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app

        bot.start()
        try:
            update = MagicMock()
            update.message = None
            import asyncio
            asyncio.run(bot._on_message(update, MagicMock()))
            self.assertTrue(q.empty())
        finally:
            bot.stop()

    @patch("telegram_bot.Application")
    def test_app_builder_called_with_token(self, mock_app_cls):
        """start() must call Application.builder().token(token).build() and run."""
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-secret-token", q, {})

        mock_builder = MagicMock()
        mock_app = MagicMock()
        mock_app_cls.builder.return_value = mock_builder
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_app

        bot.start()
        try:
            mock_app_cls.builder.assert_called_once_with()
            mock_builder.token.assert_called_once_with("my-secret-token")
            mock_builder.build.assert_called_once_with()
            self.assertTrue(bot.is_running())
        finally:
            bot.stop()

    @patch("telegram_bot.Application")
    def test_message_handler_registered(self, mock_app_cls):
        """start() must register a MessageHandler with the application."""
        q: queue.Queue[Signal] = queue.Queue()
        bot = SignalBot("my-token", q, {})

        mock_app = MagicMock()
        mock_builder = MagicMock()
        mock_app_cls.builder.return_value = mock_builder
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_app

        bot.start()
        try:
            mock_app.add_handler.assert_called_once()
            handler_arg = mock_app.add_handler.call_args[0][0]
            # Verify the handler is a MessageHandler with the bot's callback
            from telegram.ext import MessageHandler
            self.assertIsInstance(handler_arg, MessageHandler)
            # Callback is stored on MessageHandler's callback attribute
            self.assertEqual(handler_arg.callback, bot._on_message)
        finally:
            bot.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)