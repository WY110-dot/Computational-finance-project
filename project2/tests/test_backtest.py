import unittest

import numpy as np
import pandas as pd

from src import backtest as bt


def cfg(**overrides):
    c = {
        'start': '2020-02-03',
        'end': '2020-02-06',
        'initial_cash': 100.0,
        'annualization': 252,
        'daily_risk_free': 0.0,
        'buy_fee': 0.0,
        'sell_fee': 0.0,
        'max_stale_days': 5,
        'max_gross_exposure': 6.0,
    }
    c.update(overrides)
    return c


def pivots(opens, closes):
    dates = pd.bdate_range('2020-02-03', periods=len(opens))
    return {
        'open': pd.DataFrame({'A': opens}, index=dates),
        'close': pd.DataFrame({'A': closes}, index=dates),
    }


def weights(value):
    return pd.DataFrame({'A': [value]}, index=[pd.Timestamp('2020-01-31')])


class TestBacktest(unittest.TestCase):
    def test_long_ledger(self):
        p = pivots([10.0, 11.0, 12.0, 13.0], [11.0, 12.0, 13.0, 14.0])
        daily, trades = bt.simulate(p, weights(1.0), cfg())
        self.assertEqual(len(daily), 4)
        self.assertAlmostEqual(daily.nav.iloc[0], 1.10, places=12)
        self.assertAlmostEqual(daily.nav.iloc[-1], 1.40, places=12)
        self.assertAlmostEqual(daily.daily_return.iloc[0], 0.10, places=12)
        self.assertEqual(int(daily.n_long.iloc[0]), 1)
        self.assertEqual(int(daily.n_short.iloc[0]), 0)
        self.assertGreater(len(trades), 0)
        self.assertLess(pd.Timestamp(trades.signal_date.iloc[0]), pd.Timestamp(trades.date.iloc[0]))
        bt.audit(daily, trades, cfg())

    def test_short_ledger(self):
        p = pivots([10.0, 10.0, 10.0, 10.0], [9.0, 8.0, 8.0, 8.0])
        daily, trades = bt.simulate(p, weights(-1.0), cfg())
        # Sell 10 units at 10: cash 200, holding -10 units worth 90 -> 110.
        self.assertAlmostEqual(daily.cash.iloc[0], 200.0, places=12)
        self.assertAlmostEqual(daily.nav.iloc[0], 1.10, places=12)
        self.assertAlmostEqual(daily.nav.iloc[1], 1.20, places=12)
        self.assertEqual(int(daily.n_short.iloc[0]), 1)
        self.assertLess(trades.trade_dollars.iloc[0], 0)
        bt.audit(daily, trades, cfg())

    def test_fees_and_cash(self):
        p = pivots([10.0], [9.0])
        c = cfg(start='2020-02-03', end='2020-02-03', sell_fee=0.01)
        daily, trades = bt.simulate(p, weights(-1.0), c)
        self.assertAlmostEqual(trades.fee.iloc[0], 1.0, places=12)
        self.assertAlmostEqual(daily.cash.iloc[0], 199.0, places=12)
        self.assertAlmostEqual(daily.nav.iloc[0], 1.09, places=12)
        bt.audit(daily, trades, c)

    def test_monthly_compounding(self):
        p = pivots([10.0, 11.0], [11.0, 9.9])
        c = cfg(start='2020-02-03', end='2020-02-04')
        daily, _ = bt.simulate(p, weights(1.0), c)
        m = bt.monthly_returns(daily)
        self.assertEqual(len(m), 1)
        self.assertAlmostEqual(m.iloc[0], -0.01, places=12)  # +10% then -10%
        self.assertAlmostEqual(daily.nav.iloc[-1], 0.99, places=12)

    def test_audit_detects_tampering(self):
        p = pivots([10.0, 10.0], [11.0, 12.0])
        daily, trades = bt.simulate(p, weights(1.0), cfg(start='2020-02-03', end='2020-02-04'))
        bad = daily.copy()
        bad.loc[1, 'nav'] = bad.loc[1, 'nav'] + 0.01
        with self.assertRaises(AssertionError):
            bt.audit(bad, trades, cfg(start='2020-02-03', end='2020-02-04'))

    def test_subperiod_rebase(self):
        p = pivots([10.0, 11.0, 12.0, 13.0], [11.0, 12.0, 13.0, 14.0])
        c = cfg()
        daily, _ = bt.simulate(p, weights(1.0), c)
        sub = bt.subperiod_metrics(daily, '2020-02-04', '2020-02-06', c)
        self.assertAlmostEqual(sub['terminal_nav'], 14.0 / 11.0, places=10)
        self.assertAlmostEqual(sub['days'], 3, places=12)


if __name__ == '__main__':
    unittest.main()
