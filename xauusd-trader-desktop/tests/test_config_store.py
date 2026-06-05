# XAUUSD Trader Desktop App
# Tests for Chunk 1 — Config Store

import json
import os
import tempfile
import unittest
from pathlib import Path

from config_store import TraderConfig


class TestTraderConfigDefaults(unittest.TestCase):
    def test_defaults_produce_valid_object(self):
        cfg = TraderConfig(mt5_path="/some/path")
        self.assertEqual(cfg.mt5_path, "/some/path")
        self.assertEqual(cfg.symbol, "XAUUSD")
        self.assertEqual(cfg.base_lot, 0.01)
        self.assertEqual(cfg.martingale_multiplier, 2.0)
        self.assertEqual(cfg.position_a_ratio, 0.60)
        self.assertEqual(cfg.position_b_ratio, 0.40)

    def test_default_symbol_aliases(self):
        cfg = TraderConfig(mt5_path="")
        self.assertEqual(cfg.symbol_aliases["GOLD"], "XAUUSD")
        self.assertEqual(cfg.symbol_aliases["XAU/USD"], "XAUUSD")


class TestTraderConfigSaveLoad(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = Path(self.tmpdir) / "config.json"

    def tearDown(self):
        for f in Path(self.tmpdir).iterdir():
            f.unlink()
        os.rmdir(self.tmpdir)

    def test_load_returns_defaults_when_file_missing(self):
        cfg = TraderConfig.load(str(self.config_path))
        self.assertEqual(cfg.mt5_path, "")
        self.assertEqual(cfg.base_lot, 0.01)

    def test_roundtrip_preserves_data(self):
        original = TraderConfig(
            mt5_path="/home/user/mt5/terminal64.exe",
            mt5_account=123456,
            mt5_password="secret",
            mt5_server="MetaQuotes-Demo",
            symbol="XAUUSD",
            base_lot=0.05,
            martingale_multiplier=2.5,
            max_martingale_levels=5,
            position_a_ratio=0.70,
            position_b_ratio=0.30,
            telegram_bot_token="123456:ABC-DEF",
        )
        original.save(str(self.config_path))

        loaded = TraderConfig.load(str(self.config_path))
        self.assertEqual(loaded.mt5_path, original.mt5_path)
        self.assertEqual(loaded.mt5_account, original.mt5_account)
        self.assertEqual(loaded.mt5_password, original.mt5_password)
        self.assertEqual(loaded.mt5_server, original.mt5_server)
        self.assertEqual(loaded.symbol, original.symbol)
        self.assertEqual(loaded.base_lot, original.base_lot)
        self.assertEqual(loaded.martingale_multiplier, original.martingale_multiplier)
        self.assertEqual(loaded.max_martingale_levels, original.max_martingale_levels)
        self.assertEqual(loaded.position_a_ratio, original.position_a_ratio)
        self.assertEqual(loaded.position_b_ratio, original.position_b_ratio)
        self.assertEqual(loaded.telegram_bot_token, original.telegram_bot_token)

    def test_load_applies_defaults_for_missing_keys(self):
        # Write a minimal config file missing some fields
        minimal = {"mt5_path": "/minimal/path"}
        with open(self.config_path, "w") as f:
            json.dump(minimal, f)

        loaded = TraderConfig.load(str(self.config_path))
        self.assertEqual(loaded.mt5_path, "/minimal/path")
        self.assertEqual(loaded.base_lot, 0.01)  # default
        self.assertEqual(loaded.magic_number, 20250605)  # default

    def test_save_writes_valid_json(self):
        cfg = TraderConfig(mt5_path="/write/test")
        cfg.save(str(self.config_path))
        with open(self.config_path) as f:
            data = json.load(f)
        self.assertEqual(data["mt5_path"], "/write/test")
        self.assertIn("base_lot", data)


class TestTraderConfigValidate(unittest.TestCase):
    def test_valid_config_passes(self):
        cfg = TraderConfig(mt5_path="/path", base_lot=0.01, position_a_ratio=0.6, position_b_ratio=0.4)
        cfg.validate()  # should not raise

    def test_empty_mt5_path_raises(self):
        cfg = TraderConfig(mt5_path="", base_lot=0.01)
        with self.assertRaises(ValueError) as ctx:
            cfg.validate()
        self.assertIn("mt5_path", str(ctx.exception))

    def test_zero_lot_raises(self):
        cfg = TraderConfig(mt5_path="/path", base_lot=0.0)
        with self.assertRaises(ValueError) as ctx:
            cfg.validate()
        self.assertIn("base_lot", str(ctx.exception))

    def test_negative_lot_raises(self):
        cfg = TraderConfig(mt5_path="/path", base_lot=-0.01)
        with self.assertRaises(ValueError):
            cfg.validate()

    def test_ratios_not_sum_to_one_raises(self):
        cfg = TraderConfig(
            mt5_path="/path",
            base_lot=0.01,
            position_a_ratio=0.50,
            position_b_ratio=0.30,
        )
        with self.assertRaises(ValueError) as ctx:
            cfg.validate()
        self.assertIn("position_a_ratio", str(ctx.exception))

    def test_ratios_within_tolerance_pass(self):
        cfg = TraderConfig(
            mt5_path="/path",
            base_lot=0.01,
            position_a_ratio=0.595,
            position_b_ratio=0.405,
        )
        # 0.595 + 0.405 = 1.0 exactly, should pass
        cfg.validate()


if __name__ == "__main__":
    unittest.main()