import unittest

import numpy as np
import pandas as pd

from src import tsmom as ts


class TestNoLookahead(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(11)
        dates = pd.date_range('2019-01-31', periods=36, freq='ME')
        self.px = pd.DataFrame(
            {'A': 100 * np.cumprod(1 + rng.normal(0.005, 0.04, len(dates))),
             'B': 100 * np.cumprod(1 + rng.normal(0.002, 0.03, len(dates)))},
            index=dates,
        )
        self.vol = pd.DataFrame(0.2, index=dates, columns=['A', 'B'])
        self.cfg = {'assets': ['A', 'B'], 'vol_target': 0.4, 'min_assets': 1,
                    'max_gross_exposure': 6.0, 'portfolio_rescale': False}

    def test_future_prices_do_not_change_past_signal(self):
        cut = 24
        changed = self.px.copy()
        changed.iloc[cut + 1:] *= 10.0
        for h in (1, 3, 12):
            s_old = ts.sign_signal(self.px, h)
            s_new = ts.sign_signal(changed, h)
            pd.testing.assert_frame_equal(s_old.iloc[:cut + 1], s_new.iloc[:cut + 1])

    def test_future_prices_do_not_change_past_weights(self):
        cut = 24
        changed = self.px.copy()
        changed.iloc[cut + 1:] *= 10.0
        w_old, _ = ts.build_weights(ts.sign_signal(self.px, 12), self.vol, self.cfg)
        w_new, _ = ts.build_weights(ts.sign_signal(changed, 12), self.vol, self.cfg)
        pd.testing.assert_frame_equal(w_old.iloc[:cut + 1], w_new.iloc[:cut + 1])

    def test_vol_uses_only_past_returns(self):
        dates = pd.bdate_range('2020-01-01', periods=300)
        rng = np.random.default_rng(3)
        px = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, len(dates))), index=dates)
        changed = px.copy()
        changed.iloc[200:] *= 5.0
        v1 = ts.ewma_vol(px.pct_change(fill_method=None).to_frame('A'), 60, 40, 252)
        v2 = ts.ewma_vol(changed.pct_change(fill_method=None).to_frame('A'), 60, 40, 252)
        pd.testing.assert_frame_equal(v1.iloc[:200], v2.iloc[:200])


if __name__ == '__main__':
    unittest.main()
