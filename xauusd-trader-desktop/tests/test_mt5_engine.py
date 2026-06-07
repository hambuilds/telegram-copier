"""
test_mt5_engine.py — XAUUSD Trader Desktop App
Chunk 3 — MT5Engine unit tests

Uses unittest.mock to mock MetaTrader5 so tests run without the package
installed.  The mock is stored in mt5_engine._mt5 so it can be reset
between tests.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config_store  # noqa: E402
import signal_parser  # noqa: E402
import mt5_engine  # noqa: E402
from config_store import TraderConfig  # noqa: E402
from signal_parser import Signal  # noqa: E402
from mt5_engine import MT5Engine, MartingaleState  # noqa: E402


# ── Mock MT5 factory ──────────────────────────────────────────────────────────


def make_mock_mt5(volume_step: float = 0.01, volume_min: float = 0.01):
    mock = MagicMock()
    mock.TRADE_ACTION_DEAL = 1
    mock.ORDER_TYPE_BUY = 0
    mock.ORDER_TYPE_SELL = 1
    mock.ORDER_TIME_GTC = 0
    mock.ORDER_FILLING_RETURN = 1
    mock.TRADE_RETCODE_DONE = 1

    sym_info = MagicMock()
    sym_info.volume_step = volume_step
    sym_info.volume_min = volume_min
    mock.symbol_info.return_value = sym_info
    mock.symbol_info_tick.return_value = MagicMock(bid=2350.0)

    return mock


def install_mock(mock):
    """Install a fresh mock into mt5_engine and reset its internal cache."""
    mt5_engine._mt5 = mock


# ── Config helper ─────────────────────────────────────────────────────────────


def make_config(state_file: str = "state.json") -> TraderConfig:
    return TraderConfig(
        mt5_path="C:\\MT5\\terminal64.exe",
        mt5_account=123456,
        mt5_password="test",
        mt5_server="MetaQuotes-Demo",
        symbol="XAUUSD",
        base_lot=0.01,
        martingale_multiplier=2.0,
        max_martingale_levels=3,
        position_a_ratio=0.60,
        position_b_ratio=0.40,
        magic_number=20250605,
        state_file=state_file,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestNormalizeLot(unittest.TestCase):
    """Acceptance Criterion 2 — normalize_lot() rounds to the symbol's volume_step."""

    def test_rounds_to_volume_step(self):
        mock = make_mock_mt5(volume_step=0.01, volume_min=0.01)
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertAlmostEqual(engine.normalize_lot(0.016), 0.02)
        self.assertAlmostEqual(engine.normalize_lot(0.333), 0.33)
        self.assertAlmostEqual(engine.normalize_lot(0.014), 0.01)

    def test_enforces_volume_min(self):
        mock = make_mock_mt5(volume_step=0.01, volume_min=0.01)
        install_mock(mock)

        engine = MT5Engine(make_config())
        # 0.001 rounds to 0 — should be clamped to volume_min
        self.assertEqual(engine.normalize_lot(0.001), 0.01)


class TestConnect(unittest.TestCase):
    """Acceptance Criterion 1 — connect() returns True when MT5 initialises."""

    def test_connect_success(self):
        mock = make_mock_mt5()
        mock.initialize.return_value = True
        mock.login.return_value = True
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertTrue(engine.connect())
        self.assertTrue(engine.is_connected())

    def test_connect_initialize_fails(self):
        mock = make_mock_mt5()
        mock.initialize.return_value = False
        mock.last_error.return_value = "init failed"
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertFalse(engine.connect())
        self.assertFalse(engine.is_connected())

    def test_connect_login_fails(self):
        mock = make_mock_mt5()
        mock.initialize.return_value = True
        mock.login.return_value = False
        mock.last_error.return_value = "bad credentials"
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertFalse(engine.connect())
        self.assertFalse(engine.is_connected())


class TestSendMarketOrder(unittest.TestCase):
    """send_market_order() returns ticket on success, None on failure."""

    def _ok_result(self, order=987654):
        r = MagicMock()
        r.retcode = mt5_engine._mt5.TRADE_RETCODE_DONE
        r.order = order
        r.comment = "done"
        return r

    def test_returns_ticket_on_success(self):
        mock = make_mock_mt5()
        mock.order_send.return_value = self._ok_result()
        install_mock(mock)

        engine = MT5Engine(make_config())
        ticket = engine.send_market_order(
            action="BUY", symbol="XAUUSD", lot=0.01,
            entry_price=2350.0, sl_price=2345.0, tp_price=2352.5,
            magic=20250605,
        )
        self.assertEqual(ticket, 987654)

    def test_returns_none_when_result_is_none(self):
        mock = make_mock_mt5()
        mock.order_send.return_value = None
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertIsNone(engine.send_market_order(
            action="BUY", symbol="XAUUSD", lot=0.01,
            entry_price=2350.0, sl_price=2345.0, tp_price=2352.5,
            magic=20250605,
        ))

    def test_returns_none_on_bad_retcode(self):
        mock = make_mock_mt5()
        bad = MagicMock()
        bad.retcode = 10014
        bad.comment = "market closed"
        mock.order_send.return_value = bad
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertIsNone(engine.send_market_order(
            action="BUY", symbol="XAUUSD", lot=0.01,
            entry_price=2350.0, sl_price=2345.0, tp_price=2352.5,
            magic=20250605,
        ))


class TestClosePosition(unittest.TestCase):
    """close_position() returns True on success, False when position missing."""

    def test_close_success(self):
        mock = make_mock_mt5()
        pos = MagicMock()
        pos.symbol = "XAUUSD"
        pos.type = mock.ORDER_TYPE_BUY
        pos.volume = 0.01
        mock.positions_get.return_value = [pos]

        ok = MagicMock()
        ok.retcode = mock.TRADE_RETCODE_DONE
        mock.order_send.return_value = ok
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertTrue(engine.close_position(123456))

    def test_close_position_not_found(self):
        mock = make_mock_mt5()
        mock.positions_get.return_value = []
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertFalse(engine.close_position(999999))


class TestProcessSignal(unittest.TestCase):
    """
    Acceptance Criterion 3:
      process_signal() sends two order_send calls with correct TPs.
    """

    def setUp(self):
        self.work_dir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.work_dir, "state.json")
        with open(self.state_path, "w") as f:
            json.dump({"level": 0, "lot": 0.01}, f)

        self.mock = make_mock_mt5(volume_step=0.01, volume_min=0.01)
        ok = MagicMock()
        ok.retcode = self.mock.TRADE_RETCODE_DONE
        ok.order = 1
        ok.comment = "done"
        self.mock.order_send.return_value = ok
        install_mock(self.mock)

        self.config = make_config(state_file=self.state_path)
        self.engine = MT5Engine(self.config)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.work_dir, ignore_errors=True)

    def test_sends_two_orders(self):
        sig = Signal(action="BUY", symbol="XAUUSD",
                     entry=2350.0, sl=2345.0, tp1=2352.5, tp2=2355.0)
        ok = self.engine.process_signal(sig)
        self.assertTrue(ok)
        self.assertEqual(self.mock.order_send.call_count, 2)

    def test_tp_prices_correct(self):
        """First call uses TP1, second uses TP2."""
        sig = Signal(action="SELL", symbol="XAUUSD",
                     entry=2350.0, sl=2355.0, tp1=2347.5, tp2=2345.0)
        self.engine.process_signal(sig)

        calls = self.mock.order_send.call_args_list
        self.assertEqual(len(calls), 2)

        req_a = calls[0][0][0]
        self.assertAlmostEqual(req_a["tp"], 2347.5)

        req_b = calls[1][0][0]
        self.assertAlmostEqual(req_b["tp"], 2345.0)

    def test_wrong_symbol_returns_false(self):
        sig = Signal(action="BUY", symbol="EURUSD",
                     entry=1.1000, sl=1.0950, tp1=1.1020, tp2=1.1050)
        self.assertFalse(self.engine.process_signal(sig))
        self.mock.order_send.assert_not_called()

    def test_partial_order_failure_returns_false(self):
        success = MagicMock()
        success.retcode = self.mock.TRADE_RETCODE_DONE
        success.order = 1
        failure = MagicMock()
        failure.retcode = 10014
        failure.comment = "no money"
        self.mock.order_send.side_effect = [success, failure]

        sig = Signal(action="BUY", symbol="XAUUSD",
                     entry=2350.0, sl=2345.0, tp1=2352.5, tp2=2355.0)
        self.assertFalse(self.engine.process_signal(sig))


class TestGetAccountInfo(unittest.TestCase):
    """get_account_info() returns a dict with balance/equity/margin/profit or None."""

    def test_returns_dict_on_success(self):
        mock = make_mock_mt5()
        acc = MagicMock()
        acc.balance = 10000.0
        acc.equity = 10500.0
        acc.margin = 500.0
        acc.margin_free = 10000.0
        acc.profit = 500.0
        mock.account_info.return_value = acc
        install_mock(mock)

        engine = MT5Engine(make_config())
        info = engine.get_account_info()
        self.assertIsInstance(info, dict)
        self.assertEqual(info["balance"], 10000.0)
        self.assertEqual(info["equity"], 10500.0)
        self.assertEqual(info["margin"], 500.0)
        self.assertEqual(info["margin_free"], 10000.0)
        self.assertEqual(info["profit"], 500.0)

    def test_returns_none_when_account_info_is_none(self):
        mock = make_mock_mt5()
        mock.account_info.return_value = None
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertIsNone(engine.get_account_info())


class TestGetTotalFloatingPnl(unittest.TestCase):
    """get_total_floating_pnl() sums position.profit, optionally filtering by magic."""

    def test_sums_all_positions(self):
        mock = make_mock_mt5()
        pos1 = MagicMock(profit=10.5, magic=20250605)
        pos2 = MagicMock(profit=-3.2, magic=20250605)
        mock.positions_get.return_value = [pos1, pos2]
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertAlmostEqual(engine.get_total_floating_pnl(), 7.3)

    def test_filters_by_magic(self):
        mock = make_mock_mt5()
        pos1 = MagicMock(profit=10.0, magic=20250605)
        pos2 = MagicMock(profit=-5.0, magic=999999)
        mock.positions_get.return_value = [pos1, pos2]
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertAlmostEqual(engine.get_total_floating_pnl(magic=20250605), 10.0)
        self.assertAlmostEqual(engine.get_total_floating_pnl(magic=999999), -5.0)

    def test_returns_zero_when_no_positions(self):
        mock = make_mock_mt5()
        mock.positions_get.return_value = []
        install_mock(mock)

        engine = MT5Engine(make_config())
        self.assertEqual(engine.get_total_floating_pnl(), 0.0)


class TestCloseAllPositions(unittest.TestCase):
    """close_all_positions() closes every open position, returning successful tickets."""

    def test_closes_all_positions(self):
        mock = make_mock_mt5()
        pos1 = MagicMock(ticket=100, symbol="XAUUSD", type=mock.ORDER_TYPE_BUY, volume=0.01, magic=20250605)
        pos2 = MagicMock(ticket=200, symbol="XAUUSD", type=mock.ORDER_TYPE_SELL, volume=0.01, magic=20250605)
        mock.positions_get.return_value = [pos1, pos2]

        ok = MagicMock()
        ok.retcode = mock.TRADE_RETCODE_DONE
        mock.order_send.return_value = ok
        install_mock(mock)

        engine = MT5Engine(make_config())
        closed = engine.close_all_positions()
        self.assertEqual(sorted(closed), [100, 200])

    def test_filters_by_magic(self):
        mock = make_mock_mt5()
        pos1 = MagicMock(ticket=100, symbol="XAUUSD", type=mock.ORDER_TYPE_BUY, volume=0.01, magic=20250605)
        pos2 = MagicMock(ticket=200, symbol="XAUUSD", type=mock.ORDER_TYPE_SELL, volume=0.01, magic=999999)
        mock.positions_get.return_value = [pos1, pos2]

        ok = MagicMock()
        ok.retcode = mock.TRADE_RETCODE_DONE
        mock.order_send.return_value = ok
        install_mock(mock)

        engine = MT5Engine(make_config())
        closed = engine.close_all_positions(magic=20250605)
        self.assertEqual(closed, [100])

    def test_partial_failure_returns_only_successes(self):
        mock = make_mock_mt5()
        pos1 = MagicMock(ticket=100, symbol="XAUUSD", type=mock.ORDER_TYPE_BUY, volume=0.01, magic=20250605)
        pos2 = MagicMock(ticket=200, symbol="XAUUSD", type=mock.ORDER_TYPE_SELL, volume=0.01, magic=20250605)
        mock.positions_get.return_value = [pos1, pos2]

        success = MagicMock()
        success.retcode = mock.TRADE_RETCODE_DONE
        failure = MagicMock()
        failure.retcode = 10014
        failure.comment = "no money"
        mock.order_send.side_effect = [success, failure]
        install_mock(mock)

        engine = MT5Engine(make_config())
        closed = engine.close_all_positions()
        self.assertEqual(closed, [100])


class TestResetMartingaleState(unittest.TestCase):
    """reset_martingale_state() writes level=0 and lot=base_lot to the state file."""

    def test_resets_to_base_values(self):
        work_dir = tempfile.mkdtemp()
        state_path = os.path.join(work_dir, "state.json")

        with open(state_path, "w") as f:
            json.dump({"level": 3, "lot": 0.08}, f)

        install_mock(make_mock_mt5())
        engine = MT5Engine(make_config(state_file=state_path))
        engine.reset_martingale_state()

        with open(state_path) as f:
            state = json.load(f)
        self.assertEqual(state["level"], 0)
        self.assertAlmostEqual(state["lot"], 0.01)

        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)


class TestConfigPnlFieldsRoundtrip(unittest.TestCase):
    """TraderConfig save/load preserves pnl_target and pnl_check_interval_seconds."""

    def test_pnl_fields_roundtrip(self):
        work_dir = tempfile.mkdtemp()
        cfg_path = os.path.join(work_dir, "config.json")

        config = TraderConfig(
            mt5_path="C:\\MT5\\terminal64.exe",
            pnl_target=500.0,
            pnl_check_interval_seconds=30,
        )
        config.save(cfg_path)

        loaded = TraderConfig.load(cfg_path)
        self.assertEqual(loaded.pnl_target, 500.0)
        self.assertEqual(loaded.pnl_check_interval_seconds, 30)

        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)


class TestAdvanceMartingale(unittest.TestCase):
    """
    Acceptance Criteria 4 & 5:
      4. advance_martingale(False) doubles lot up to max level, then resets.
      5. State JSON is created/updated after every martingale advance.
    """

    def setUp(self):
        self.work_dir = tempfile.mkdtemp()

    def state_path(self):
        return os.path.join(self.work_dir, "state.json")

    def write_state(self, level, lot):
        with open(self.state_path(), "w") as f:
            json.dump({"level": level, "lot": lot}, f)

    def read_state(self):
        with open(self.state_path()) as f:
            return json.load(f)

    def test_win_resets_level_and_lot(self):
        self.write_state(2, 0.04)
        install_mock(make_mock_mt5())
        engine = MT5Engine(make_config(state_file=self.state_path()))
        engine.advance_martingale(win=True)

        s = self.read_state()
        self.assertEqual(s["level"], 0)
        self.assertAlmostEqual(s["lot"], 0.01)

    def test_loss_increments_level_and_doubles_lot(self):
        self.write_state(0, 0.01)
        install_mock(make_mock_mt5())
        engine = MT5Engine(make_config(state_file=self.state_path()))
        engine.advance_martingale(win=False)

        s = self.read_state()
        self.assertEqual(s["level"], 1)
        self.assertAlmostEqual(s["lot"], 0.02)

    def test_loss_caps_at_max_level_then_resets(self):
        self.write_state(3, 0.08)
        install_mock(make_mock_mt5())
        engine = MT5Engine(make_config(state_file=self.state_path()))
        engine.advance_martingale(win=False)

        s = self.read_state()
        self.assertEqual(s["level"], 0)
        self.assertAlmostEqual(s["lot"], 0.01)

    def test_state_file_created_if_missing(self):
        path = self.state_path()
        self.assertFalse(os.path.exists(path))
        install_mock(make_mock_mt5())
        engine = MT5Engine(make_config(state_file=path))
        engine.advance_martingale(win=False)

        self.assertTrue(os.path.exists(path))
        s = self.read_state()
        self.assertEqual(s["level"], 1)


if __name__ == "__main__":
    unittest.main()