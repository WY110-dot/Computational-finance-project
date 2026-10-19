import unittest

import numpy as np
import pandas as pd

from src import tsmom as ts


class TestSignal(unittest.TestCase):
    def setUp(self):
        self.px = pd.DataFrame(
            {'A': [100.0, 110.0, 121.0, 108.9, 100.0, 120.0, 118.8]},
            index=pd.date_range('2020-01-31', periods=7, freq='ME'),
        )

    def test_trailing_return(self):
        r1 = ts.trailing_return(self.px, 1)
        self.assertAlmostEqual(r1['A'].iloc[1], 0.10, places=12)
        self.assertAlmostEqual(r1['A'].iloc[2], 0.10, places=12)
        r3 = ts.trailing_return(self.px, 3)
        self.assertAlmostEqual(r3['A'].iloc[4], 100.0 / 110.0 - 1, places=12)
        self.assertTrue(np.isnan(r3['A'].iloc[0]))

    def test_sign_and_multihorizon(self):
        s1 = ts.sign_signal(self.px, 1)
        self.assertEqual(s1['A'].iloc[1], 1.0)
        self.assertEqual(s1['A'].iloc[3], -1.0)
        m = ts.multihorizon_signal(self.px, [1, 3])
        # Row 5: 1-month +1 (120/100), 3-month -1 (120/121), average 0.
        self.assertEqual(m['A'].iloc[5], 0.0)
        self.assertTrue(np.isnan(m['A'].iloc[1]))

    def test_skip_month(self):
        # 12-1 at row 3 uses P[2] / P[0] - 1, not P[3] / P[1] - 1.
        r = ts.trailing_return(self.px, 1, skip=0)
        r_skip = ts.trailing_return(self.px, 1, skip=1)
        self.assertAlmostEqual(r['A'].iloc[3], -0.10, places=12)
        self.assertAlmostEqual(r_skip['A'].iloc[3], 0.10, places=12)

    def test_month_end_dates(self):
        daily = pd.bdate_range('2020-01-01', '2020-03-31')
        me = ts.month_end_dates(daily)
        self.assertEqual(str(me[0].date()), '2020-01-31')
        self.assertEqual(str(me[1].date()), '2020-02-28')
        self.assertEqual(str(me[2].date()), '2020-03-31')

    def test_execution_map(self):
        daily = pd.bdate_range('2020-01-01', '2020-01-31')
        sig = pd.DatetimeIndex([pd.Timestamp('2020-01-03'), pd.Timestamp('2020-01-31')])
        m = ts.execution_map(sig, daily, '2020-01-01', '2020-01-31')
        self.assertEqual(m[pd.Timestamp('2020-01-06')], pd.Timestamp('2020-01-03'))
        self.assertNotIn(pd.Timestamp('2020-02-03'), m)  # outside end
        for exec_date, signal_date in m.items():
            self.assertLess(signal_date, exec_date)


if __name__ == '__main__':
    unittest.main()
