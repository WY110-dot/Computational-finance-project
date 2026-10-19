import unittest

import numpy as np
import pandas as pd

from src import tsmom as ts


def config(**overrides):
    cfg = {
        'assets': ['A', 'B', 'C'],
        'vol_target': 0.40,
        'max_gross_exposure': 6.0,
        'min_assets': 1,
        'portfolio_rescale': False,
        'portfolio_vol_target': 0.12,
    }
    cfg.update(overrides)
    return cfg


class TestWeights(unittest.TestCase):
    def setUp(self):
        self.idx = pd.DatetimeIndex(['2020-01-31'])
        self.signal = pd.DataFrame([[1.0, -1.0, 0.0]], index=self.idx, columns=['A', 'B', 'C'])
        self.vol = pd.DataFrame([[0.2, 0.4, 0.2]], index=self.idx, columns=['A', 'B', 'C'])

    def test_formula(self):
        w, d = ts.build_weights(self.signal, self.vol, config())
        self.assertAlmostEqual(w.loc[self.idx[0], 'A'], 0.40 / 0.20 / 3, places=12)
        self.assertAlmostEqual(w.loc[self.idx[0], 'B'], -0.40 / 0.40 / 3, places=12)
        self.assertEqual(w.loc[self.idx[0], 'C'], 0.0)
        self.assertAlmostEqual(d.loc[self.idx[0], 'gross_exposure'], 1.0, places=12)
        self.assertAlmostEqual(d.loc[self.idx[0], 'net_exposure'], 1.0 / 3, places=12)
        self.assertEqual(int(d.loc[self.idx[0], 'n_assets']), 3)

    def test_gross_cap(self):
        vol = pd.DataFrame([[0.01, 0.01, 0.01]], index=self.idx, columns=['A', 'B', 'C'])
        w, d = ts.build_weights(self.signal, vol, config())
        self.assertAlmostEqual(d.loc[self.idx[0], 'gross_exposure'], 6.0, places=10)
        self.assertTrue(bool(d.loc[self.idx[0], 'gross_capped']))
        self.assertAlmostEqual(w.loc[self.idx[0], 'A'], 3.0, places=10)
        self.assertAlmostEqual(w.loc[self.idx[0], 'B'], -3.0, places=10)

    def test_min_assets(self):
        vol = pd.DataFrame([[0.2, np.nan, np.nan]], index=self.idx, columns=['A', 'B', 'C'])
        w, d = ts.build_weights(self.signal, vol, config(min_assets=2))
        self.assertTrue((w.loc[self.idx[0]] == 0).all())
        self.assertEqual(int(d.loc[self.idx[0], 'n_assets']), 1)

    def test_ex_ante_vol_and_rescale(self):
        cov = pd.DataFrame(
            np.diag([0.04, 0.16, 0.04]),
            index=pd.MultiIndex.from_product([self.idx, ['A', 'B', 'C']]),
            columns=['A', 'B', 'C'],
        )
        w, d = ts.build_weights(self.signal, self.vol, config(), cov=cov)
        expected = 0.4 / 0.2 / 3
        short = 0.4 / 0.4 / 3
        var = expected ** 2 * 0.04 + short ** 2 * 0.16
        self.assertAlmostEqual(d.loc[self.idx[0], 'ex_ante_portfolio_vol'], np.sqrt(var), places=12)
        self.assertAlmostEqual(w.loc[self.idx[0], 'A'], expected, places=12)

        w2, d2 = ts.build_weights(
            self.signal, self.vol, config(portfolio_rescale=True), cov=cov)
        scale = 0.12 / np.sqrt(var)
        self.assertAlmostEqual(d2.loc[self.idx[0], 'scale'], scale, places=12)
        self.assertAlmostEqual(w2.loc[self.idx[0], 'A'], expected * scale, places=12)

    def test_no_lookahead(self):
        later = self.signal.copy()
        later.loc[pd.Timestamp('2020-02-29')] = [1.0, 1.0, 1.0]
        vol = pd.concat([self.vol, self.vol.rename(index={self.idx[0]: pd.Timestamp('2020-02-29')})])
        w1, _ = ts.build_weights(self.signal, self.vol, config())
        w2, _ = ts.build_weights(later, vol, config())
        pd.testing.assert_series_equal(w1.loc[self.idx[0]], w2.loc[self.idx[0]])


if __name__ == '__main__':
    unittest.main()
