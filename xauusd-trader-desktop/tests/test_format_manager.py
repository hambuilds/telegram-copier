"""
test_format_manager.py — Unit tests for format_manager.py.
Run with: python -m unittest xauusd-trader-desktop.tests.test_format_manager -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from format_manager import (
    FormatManager,
    SignalFormatProfile,
    TaggedToken,
    build_regex_from_tokens,
    tokenize_sample,
    tokens_to_tagged,
    parse_signal,
    _builtin_profiles,
)
from signal_parser import Signal

DEFAULT_ALIASES = {"GOLD": "XAUUSD", "XAU/USD": "XAUUSD"}


# -------------------------------------------------------------------
# Tokenisation & regex builder
# -------------------------------------------------------------------

class TestTokenize(unittest.TestCase):
    def test_simple_tokens(self):
        text = "BUY XAUUSD @ 2350.00"
        self.assertEqual(
            tokenize_sample(text),
            ["BUY", "XAUUSD", "@", "2350.00"],
        )

    def test_punctuation_separated(self):
        text = "SL: 2345.00 | TP1 2352.50"
        self.assertEqual(
            tokenize_sample(text),
            ["SL:", "2345.00", "|", "TP1", "2352.50"],
        )

    def test_slash_in_symbol(self):
        text = "XAU/USD"
        self.assertEqual(tokenize_sample(text), ["XAU/USD"])


class TestRegexBuilder(unittest.TestCase):
    def test_literal_and_field(self):
        tokens = [
            TaggedToken("BUY", "action"),
            TaggedToken("XAUUSD", "symbol"),
            TaggedToken("@", "literal"),
            TaggedToken("2350.00", "entry"),
        ]
        rx = build_regex_from_tokens(tokens)
        self.assertIn("(?is)", rx)
        self.assertIn("(?P<action>BUY|SELL)", rx)
        self.assertIn("(?P<symbol>", rx)
        self.assertIn(r"@", rx)
        self.assertIn("(?P<entry>", rx)
        # Should have \s+ between non-ignore fragments
        self.assertIn(r"\s+", rx)

    def test_ignore_collapses(self):
        tokens = [
            TaggedToken("BUY", "action"),
            TaggedToken("XAUUSD", "ignore"),
            TaggedToken("@", "ignore"),
            TaggedToken("2350.00", "entry"),
        ]
        rx = build_regex_from_tokens(tokens)
        # Only one .*? even though there are two consecutive ignores
        self.assertEqual(rx.count(".*?"), 1)

    def test_generated_regex_matches(self):
        tokens = [
            TaggedToken("BUY", "action"),
            TaggedToken("XAUUSD", "symbol"),
            TaggedToken("@", "literal"),
            TaggedToken("2350.00", "entry"),
            TaggedToken("SL:", "literal"),
            TaggedToken("2345.00", "sl"),
            TaggedToken("TP1:", "literal"),
            TaggedToken("2352.50", "tp1"),
            TaggedToken("TP2:", "literal"),
            TaggedToken("2355.00", "tp2"),
        ]
        rx = build_regex_from_tokens(tokens)
        compiled = __import__("re").compile(rx, __import__("re").IGNORECASE | __import__("re").DOTALL)
        text = "BUY XAUUSD @ 2350.00 SL: 2345.00 TP1: 2352.50 TP2: 2355.00"
        m = compiled.search(text)
        self.assertIsNotNone(m)
        self.assertEqual(m.group("action").upper(), "BUY")
        self.assertEqual(m.group("symbol").upper(), "XAUUSD")
        self.assertAlmostEqual(float(m.group("entry")), 2350.0)


# -------------------------------------------------------------------
# Built-in presets
# -------------------------------------------------------------------

class TestBuiltinPresets(unittest.TestCase):
    def setUp(self):
        self.fm = FormatManager()

    def test_standard_multiline_buy(self):
        text = (
            "BUY XAUUSD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n"
        )
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")
        self.assertEqual(sig.symbol, "XAUUSD")
        self.assertAlmostEqual(sig.entry, 2350.00)
        self.assertAlmostEqual(sig.sl, 2345.00)
        self.assertAlmostEqual(sig.tp1, 2352.50)
        self.assertAlmostEqual(sig.tp2, 2355.00)

    def test_standard_multiline_sell_gold_alias(self):
        text = (
            "SELL GOLD @ 2340.00\n"
            "SL: 2345.00\n"
            "TP1: 2337.50\n"
            "TP2: 2335.00\n"
        )
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "SELL")
        self.assertEqual(sig.symbol, "XAUUSD")
        self.assertAlmostEqual(sig.entry, 2340.00)

    def test_standard_multiline_xau_usd_alias(self):
        text = (
            "BUY XAU/USD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n"
        )
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.symbol, "XAUUSD")

    def test_compact_pipe_separator_buy_gold(self):
        text = "Gold Buy 2350.00 | SL 2345.00 | TP1 2352.50 | TP2 2355.00"
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")
        self.assertEqual(sig.symbol, "XAUUSD")
        self.assertAlmostEqual(sig.entry, 2350.00)
        self.assertAlmostEqual(sig.sl, 2345.00)
        self.assertAlmostEqual(sig.tp1, 2352.50)
        self.assertAlmostEqual(sig.tp2, 2355.00)

    def test_compact_slash_separator_sell(self):
        text = "SELL XAU/USD 2350.00 / SL 2345.00 / TP1 2352.50 / TP2 2355.00"
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "SELL")
        self.assertEqual(sig.symbol, "XAUUSD")

    def test_compact_no_symbol_buy(self):
        text = "BUY 2350.00 | SL 2345.00 | TP1 2352.50 | TP2 2355.00"
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")
        self.assertEqual(sig.symbol, "XAUUSD")

    def test_compact_uppercase_xauusd(self):
        text = "XAUUSD BUY 2350.00 SL 2345.00 TP1 2352.50 TP2 2355.00"
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")
        self.assertEqual(sig.symbol, "XAUUSD")

    def test_simple_buy_with_follow_lines(self):
        text = (
            "BUY XAUUSD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n"
        )
        sig = self.fm.match(text, DEFAULT_ALIASES)
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
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "SELL")
        self.assertEqual(sig.symbol, "XAUUSD")

    def test_tradingview_preset(self):
        text = "BUY XAUUSD @ 2350.00 SL=2345.00 TP1=2352.50 TP2=2355.00"
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")
        self.assertEqual(sig.symbol, "XAUUSD")
        self.assertAlmostEqual(sig.entry, 2350.00)

    def test_no_match(self):
        self.assertIsNone(self.fm.match("Hello world", DEFAULT_ALIASES))

    def test_empty_string(self):
        self.assertIsNone(self.fm.match("", DEFAULT_ALIASES))

    def test_incomplete_signal(self):
        text = (
            "BUY XAUUSD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
        )
        self.assertIsNone(self.fm.match(text, DEFAULT_ALIASES))

    def test_action_case_insensitive(self):
        text = (
            "buy xauusd @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n"
        )
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")

    def test_action_normalised_to_uppercase(self):
        text = (
            "SeLl XAUUSD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00\n"
        )
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "SELL")


# -------------------------------------------------------------------
# Custom profiles
# -------------------------------------------------------------------

class TestCustomProfiles(unittest.TestCase):
    def setUp(self):
        self.fm = FormatManager()

    def test_add_custom_profile(self):
        profile = self.fm.add_custom_profile(
            name="My Format",
            pattern=r"(?is)(?P<action>BUY|SELL)[^\d]+(?P<entry>\d+\.?\d*).*?SL[^\d]+(?P<sl>\d+\.?\d*).*?TP1[^\d]+(?P<tp1>\d+\.?\d*).*?TP2[^\d]+(?P<tp2>\d+\.?\d*)",
        )
        self.assertEqual(profile.name, "My Format")
        self.assertFalse(profile.is_builtin)
        self.assertTrue(any(p.id == profile.id for p in self.fm.all_profiles()))

    def test_add_custom_profile_invalid_regex(self):
        with self.assertRaises(ValueError) as ctx:
            self.fm.add_custom_profile(name="Bad", pattern=r"(?P<action>(BUY)")
        self.assertIn("Invalid regex pattern", str(ctx.exception))

    def test_delete_custom_profile(self):
        profile = self.fm.add_custom_profile(
            name="ToDelete",
            pattern=r"(?is)(?P<action>BUY|SELL)",
        )
        self.assertTrue(self.fm.delete_custom_profile(profile.id))
        self.assertFalse(any(p.id == profile.id for p in self.fm.all_profiles()))

    def test_delete_builtin_fails(self):
        self.assertFalse(self.fm.delete_custom_profile("builtin-standard"))

    def test_custom_profile_matches(self):
        self.fm.add_custom_profile(
            name="Custom",
            pattern=(
                r"(?is)(?P<action>BUY|SELL)\s+(?P<symbol>XAUUSD|GOLD|XAU/USD)\s*@\s*(?P<entry>\d+\.?\d*)"
                r"\s*STOP\s+(?P<sl>\d+\.?\d*)"
                r"\s*TARGET1\s+(?P<tp1>\d+\.?\d*)"
                r"\s*TARGET2\s+(?P<tp2>\d+\.?\d*)"
            ),
        )
        text = "BUY XAUUSD @ 2350.00 STOP 2345.00 TARGET1 2352.50 TARGET2 2355.00"
        sig = self.fm.match(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")
        self.assertAlmostEqual(sig.sl, 2345.00)

    def test_builtins_tried_before_customs(self):
        # Add a custom profile that would also match the standard text
        # but is placed after builtins; standard format should win first.
        text = "BUY XAUUSD @ 2350.00 SL: 2345.00 TP1: 2352.50 TP2: 2355.00"
        sig1 = self.fm.match(text, DEFAULT_ALIASES)
        # Now add a custom with a deliberately different action mapping
        # (same pattern, just proves ordering)
        self.fm.add_custom_profile(
            name="CustomSame",
            pattern=r"(?is)(?P<action>BUY|SELL)\s+(?P<symbol>XAUUSD|GOLD|XAU/USD)\s*[@\s]\s*(?P<entry>\d+\.?\d*)"  # incomplete
        )
        sig2 = self.fm.match(text, DEFAULT_ALIASES)
        # Both should succeed because builtin matches first
        self.assertIsNotNone(sig2)
        self.assertEqual(sig1, sig2)


# -------------------------------------------------------------------
# Persistence
# -------------------------------------------------------------------

class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmpdir.name, "formats.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_and_load(self):
        fm = FormatManager()
        profile = fm.add_custom_profile(
            name="Persisted",
            pattern=r"(?is)(?P<action>BUY|SELL)\s+now",
        )
        fm.save_to_config(self.path)

        fm2 = FormatManager.load_from_config(self.path)
        self.assertEqual(len(fm2.custom_profiles()), 1)
        self.assertEqual(fm2.custom_profiles()[0].name, "Persisted")
        self.assertEqual(fm2.custom_profiles()[0].pattern, profile.pattern)

    def test_load_missing_file(self):
        fm = FormatManager.load_from_config(self.path)
        self.assertEqual(len(fm.custom_profiles()), 0)

    def test_load_corrupt_file(self):
        with open(self.path, "w") as f:
            f.write("not json")
        fm = FormatManager.load_from_config(self.path)
        self.assertEqual(len(fm.custom_profiles()), 0)


# -------------------------------------------------------------------
# Backward-compatible parse_signal()
# -------------------------------------------------------------------

class TestBackwardCompat(unittest.TestCase):
    def test_parse_signal_wraps_manager(self):
        text = (
            "BUY XAUUSD @ 2350.00\n"
            "SL: 2345.00\n"
            "TP1: 2352.50\n"
            "TP2: 2355.00"
        )
        sig = parse_signal(text, DEFAULT_ALIASES)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "BUY")


# -------------------------------------------------------------------
# test_pattern helper
# -------------------------------------------------------------------

class TestTestPattern(unittest.TestCase):
    def test_valid_pattern(self):
        fm = FormatManager()
        pattern = (
            r"(?is)(?P<action>BUY|SELL)\s+(?P<symbol>XAUUSD|GOLD|XAU/USD)\s*@\s*(?P<entry>\d+\.?\d*)"
            r"\s*SL:\s*(?P<sl>\d+\.?\d*)\s*TP1:\s*(?P<tp1>\d+\.?\d*)\s*TP2:\s*(?P<tp2>\d+\.?\d*)"
        )
        samples = ["BUY XAUUSD @ 2350.00 SL: 2345.00 TP1: 2352.50 TP2: 2355.00"]
        results = fm.test_pattern(pattern, samples)
        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0].action, "BUY")

    def test_invalid_pattern_raises(self):
        fm = FormatManager()
        with self.assertRaises(ValueError):
            fm.test_pattern(r"(?P<bad", ["text"])

    def test_no_match_returns_none(self):
        fm = FormatManager()
        pattern = r"(?is)(?P<action>BUY|SELL)\s+(?P<symbol>XAUUSD|GOLD|XAU/USD)\s*@\s*(?P<entry>\d+\.?\d*)"
        samples = ["Hello world"]
        results = fm.test_pattern(pattern, samples)
        self.assertIsNone(results[0])


# -------------------------------------------------------------------
# tokens_to_tagged
# -------------------------------------------------------------------

class TestTokensToTagged(unittest.TestCase):
    def test_basic(self):
        text = "BUY XAUUSD"
        tags = ["action", "symbol"]
        result = tokens_to_tagged(text, tags)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].text, "BUY")
        self.assertEqual(result[0].tag, "action")
        self.assertEqual(result[1].text, "XAUUSD")
        self.assertEqual(result[1].tag, "symbol")

    def test_mismatch_raises(self):
        text = "BUY XAUUSD"
        tags = ["action"]
        with self.assertRaises(ValueError):
            tokens_to_tagged(text, tags)


if __name__ == "__main__":
    unittest.main(verbosity=2)
