import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.data import sha

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'


@unittest.skipUnless((OUT / 'strategy_summary.csv').exists(),
                     'run.py has not produced outputs/ yet')
class TestOutputs(unittest.TestCase):
    def test_summary_invariants(self):
        s = pd.read_csv(OUT / 'strategy_summary.csv').set_index('strategy')
        expected = {
            'tsmom_12m', 'tsmom_diversified', 'tsmom_diversified_gross',
            'benchmark_ew', 'tsmom_diversified_longonly',
            'tsmom_diversified_shortonly', 'tsmom_multihorizon',
            'tsmom_12_1', 'tsmom_diversified_volscale12',
        }
        self.assertEqual(set(s.index), expected)
        self.assertTrue((s['days'] == 6289).all())
        self.assertTrue((s['terminal_nav'] > 0).all())
        self.assertTrue(((s['max_drawdown'] >= 0) & (s['max_drawdown'] <= 1)).all())
        self.assertTrue((s['avg_gross_exposure'] >= s['avg_net_exposure'].abs()).all())

    def test_audit(self):
        audits = json.loads((OUT / 'audit.json').read_text(encoding='utf-8'))
        for name, errors in audits.items():
            with self.subTest(strategy=name):
                self.assertLess(max(errors.values()), 1e-5)

    def test_quality(self):
        q = json.loads((OUT / 'quality_report.json').read_text(encoding='utf-8'))
        self.assertEqual(q['assets'], 9)
        self.assertEqual(q['raw_rows'], 61407)
        self.assertEqual(q['clean_rows'], 58932)
        self.assertEqual(q['calendar_days'], 6548)
        self.assertEqual(q['missing_grid_cells'], 0)
        self.assertEqual(sum(a['duplicate_keys'] for a in q['by_asset']), 0)

    def test_predictive_sample_alignment(self):
        p = pd.read_csv(OUT / 'predictive_regressions.csv')
        pooled = p[p.scope == 'pooled'].set_index('horizon_months')
        for h in (1, 3, 6, 12):
            self.assertEqual(int(pooled.loc[h, 'n']), 2700)
        self.assertEqual(int(pooled.loc[24, 'n']), 2592)

    def test_hand_check_weight_and_fee(self):
        w = pd.read_csv(OUT / 'weights.csv')
        row = w[(w.portfolio == 'tsmom_12m') & (w.asset == 'XLB')
                & (w.date == '2019-12-31')].weight.iloc[0]
        self.assertAlmostEqual(float(row), 0.3398793652, places=6)
        t = pd.read_csv(OUT / 'tsmom_diversified_trades.csv')
        first = t.iloc[0]
        self.assertEqual(first.asset, 'XLB')
        self.assertAlmostEqual(float(first.fee), float(first.trade_dollars) * 0.001, places=6)
        self.assertLess(pd.Timestamp(first.signal_date), pd.Timestamp(first.date))

    def test_provenance_hashes(self):
        manifest = json.loads((OUT / 'run_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['research_days'], 6289)
        self.assertEqual(manifest['research_start'], '2000-01-03')
        self.assertEqual(manifest['research_end'], '2024-12-31')
        for rel, digest in manifest['code_sha256'].items():
            path = ROOT / rel
            if path.exists():
                with self.subTest(file=rel):
                    self.assertEqual(sha(path), digest)
        self.assertEqual(sha(ROOT / 'data/source_manifest.json'),
                         manifest['source_manifest_sha256'])

    def test_diagnostics(self):
        d = json.loads((OUT / 'diagnostics.json').read_text(encoding='utf-8'))
        self.assertGreater(d['average_pairwise_correlation_daily'], 0)
        self.assertLess(d['average_pairwise_correlation_daily'], 1)
        self.assertGreater(d['ex_ante_portfolio_vol']['mean'], 0)
        self.assertAlmostEqual(d['signal_long_bias']['12'], 0.739259, places=4)


if __name__ == '__main__':
    unittest.main()
