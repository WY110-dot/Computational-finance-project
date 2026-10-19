import unittest

import numpy as np
import pandas as pd

from src import stats


class TestStats(unittest.TestCase):
    def test_nw_regression(self):
        x = np.linspace(-1, 1, 80)
        y = 1.0 + 2.0 * x + 1e-4 * np.sin(np.arange(80))
        r = stats.nw_regression(y, x, lags=12)
        self.assertAlmostEqual(r['alpha'], 1.0, delta=1e-4)
        self.assertAlmostEqual(r['beta'], 2.0, delta=1e-4)
        self.assertEqual(r['n'], 80)
        self.assertGreater(r['r2'], 0.999)

    def test_cluster_regression(self):
        rng = np.random.default_rng(7)
        x = rng.normal(size=120)
        y = 0.5 + 1.5 * x + rng.normal(scale=0.1, size=120)
        groups = np.repeat(np.arange(12), 10)
        r = stats.cluster_regression(y, x, groups, lags=12)
        self.assertAlmostEqual(r['alpha'], 0.5, delta=0.1)
        self.assertAlmostEqual(r['beta'], 1.5, delta=0.1)
        self.assertEqual(r['n'], 120)

    def test_alpha_regression(self):
        benchmark = np.linspace(-0.05, 0.05, 120)
        strategy = 0.01 + 0.5 * benchmark
        r = stats.alpha_regression(strategy, benchmark, lags=12)
        self.assertAlmostEqual(r['alpha_annual'], 0.12, places=10)
        self.assertAlmostEqual(r['beta'], 0.5, places=10)
        self.assertEqual(r['n'], 120)

    def test_mean_tstat_and_sharpe(self):
        m = np.array([0.01, -0.005, 0.02, 0.0, 0.015] * 12)
        mt = stats.mean_tstat(m, lags=12)
        self.assertAlmostEqual(mt['mean'], m.mean(), places=12)
        self.assertEqual(mt['n'], len(m))
        s = stats.sharpe(m, rf_annual=0.0, periods=12)
        expected = m.mean() / m.std(ddof=1) * np.sqrt(12)
        self.assertAlmostEqual(s['sharpe'], expected, places=12)
        self.assertAlmostEqual(s['ann_return'], m.mean() * 12, places=12)

    def test_extreme_bins(self):
        market = pd.Series(np.linspace(-0.10, 0.098, 100))
        strategy = -2.0 * market + 0.001
        out = stats.extreme_table(strategy, market, lags=12).set_index('bin')
        self.assertEqual(int(out.loc['bottom_10pct', 'months']), 10)
        self.assertEqual(int(out.loc['middle_80pct', 'months']), 80)
        self.assertEqual(int(out.loc['top_10pct', 'months']), 10)
        self.assertEqual(int(out.loc['bottom_20pct', 'months']), 20)
        self.assertEqual(int(out.loc['top_20pct', 'months']), 20)
        # The strategy is short the market, so bottom-market months do best.
        self.assertGreater(out.loc['bottom_10pct', 'mean_tsmom'],
                           out.loc['top_10pct', 'mean_tsmom'])


if __name__ == '__main__':
    unittest.main()
