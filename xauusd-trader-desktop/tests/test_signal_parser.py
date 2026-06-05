"""
test_signal_parser.py — Unit tests for signal_parser.py.
Run with: python -m unittest xauusd-trader-desktop.tests.test_signal_parser -v
"""

import unittest
import sys
from pathlib import Path

# Allow 'xauusd-trader-desktop' to be resolved as a package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_parser import Signal, parse_signal


DEFAULT_ALIASES = {"GOLD": "XAUUSD", "XAU/USD": "XAUUSD"}


class TestSignalParser(unittest.TestCase):
    """Tests for parse_signal() using the three recognised formats."""

    # -----------------------------------------------------------------
    # Multi-line format
    # -----------------------------------------------------------------
    def test_multiline_buy_xauusd(self):
        text = (
            "BUY XAUUSD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n"
        )
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")
        self.assertEqual(sig.symbol, "XAUUSD")
        self.assertAlmostEqual(sig.entry, 2350.00)
        self.assertAlmostEqual(sig.sl, 2345.00)
        self.assertAlmostEqual(sig.tp1, 2352.50)
        self.assertAlmostEqual(sig.tp2, 2355.00)

    def test_multiline_sell_gold_alias(self):
        """'GOLD' alias resolves to canonical 'XAUUSD'."""
        text = (
            "SELL GOLD @ 2340.00\n"
            "SL: 2345.00\n"
            "TP1: 2337.50\n"
            "TP2: 2335.00\n"
        )
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "SELL")
        self.assertEqual(sig.symbol, "XAUUSD")
        self.assertAlmostEqual(sig.entry, 2340.00)

    def test_multiline_xau_usd_alias(self):
        """'XAU/USD' alias resolves to canonical 'XAUUSD'."""
        text = (
            "BUY XAU/USD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n"
        )
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.symbol, "XAUUSD")

    # -----------------------------------------------------------------
    # Compact single-line format (| or / separators)
    # -----------------------------------------------------------------
    def test_compact_pipe_separator_buy_gold(self):
        text = "Gold Buy 2350.00 | SL 2345.00 | TP1 2352.50 | TP2 2355.00"
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")
        self.assertEqual(sig.symbol, "XAUUSD")
        self.assertAlmostEqual(sig.entry, 2350.00)
        self.assertAlmostEqual(sig.sl, 2345.00)
        self.assertAlmostEqual(sig.tp1, 2352.50)
        self.assertAlmostEqual(sig.tp2, 2355.00)

    def test_compact_slash_separator_sell(self):
        text = "SELL XAU/USD 2350.00 / SL 2345.00 / TP1 2352.50 / TP2 2355.00"
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "SELL")
        self.assertEqual(sig.symbol, "XAUUSD")
        self.assertAlmostEqual(sig.entry, 2350.00)
        self.assertAlmostEqual(sig.sl, 2345.00)
        self.assertAlmostEqual(sig.tp1, 2352.50)
        self.assertAlmostEqual(sig.tp2, 2355.00)

    def test_compact_no_symbol_buy(self):
        """Symbol may be omitted in compact form; defaults to XAUUSD."""
        text = "BUY 2350.00 | SL 2345.00 | TP1 2352.50 | TP2 2355.00"
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")
        self.assertEqual(sig.symbol, "XAUUSD")

    def test_compact_uppercase_xauusd(self):
        text = "XAUUSD BUY 2350.00 SL 2345.00 TP1 2352.50 TP2 2355.00"
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")
        self.assertEqual(sig.symbol, "XAUUSD")

    # -----------------------------------------------------------------
    # Simple format (action + symbol + entry only; SL/TP follow)
    # -----------------------------------------------------------------
    def test_simple_buy_with_follow_lines(self):
        text = (
            "BUY XAUUSD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n"
        )
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")
        self.assertEqual(sig.symbol, "XAUUSD")
        self.assertAlmostEqual(sig.entry, 2350.00)

    def test_simple_gold_alias_with_follow_lines(self):
        text = (
            "SELL GOLD @ 2340.00\n"
            "SL: 2345.00\n"
            "TP1: 2337.50\n"
            "TP2: 2335.00\n"
        )
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "SELL")
        self.assertEqual(sig.symbol, "XAUUSD")

    # -----------------------------------------------------------------
    # Edge cases — invalid / non-signal input
    # -----------------------------------------------------------------
    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_signal("", DEFAULT_ALIASES))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(parse_signal("   \n  ", DEFAULT_ALIASES))

    def test_non_signal_text_returns_none(self):
        self.assertIsNone(parse_signal("Hello world, how are you?", DEFAULT_ALIASES))

    def test_incomplete_signal_returns_none(self):
        """Missing TP2 means no pattern should match."""
        text = (
            "BUY XAUUSD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
        )
        self.assertIsNone(parse_signal(text, DEFAULT_ALIASES))

    def test_unknown_symbol_not_in_aliases(self):
        """Symbols not in aliases are returned as-is (uppercased)."""
        text = (
            "BUY FOOBAR @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n"
        )
        sig = parse_signal(text, DEFAULT_ALIASES)
        # FOOBAR is not matched by any of the three patterns, so returns None
        self.assertIsNone(sig)

    # -----------------------------------------------------------------
    # Alias parameter behaviour
    # -----------------------------------------------------------------
    def test_custom_alias_map(self):
        """Custom aliases dict is respected."""
        aliases = {"XAUUSD": "XAUUSD", "GOLD": "XAUUSD", "CRAP": "WTF"}
        text = "BUY GOLD @ 2350.00 | SL 2345.00 | TP1 2352.50 | TP2 2355.00"
        sig = parse_signal(text, aliases)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.symbol, "XAUUSD")

    def test_action_case_insensitive(self):
        """Action matching is case-insensitive."""
        text = (
            "buy xauusd @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n"
        )
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")

    def test_action_normalised_to_uppercase(self):
        """Action is always returned as uppercase."""
        text = (
            "SeLl XAUUSD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n"
        )
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "SELL")


if __name__ == "__main__":
    unittest.main(verbosity=2)