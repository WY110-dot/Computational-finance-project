from pathlib import Path

content = Path("tests/test_project3_counterexamples.py").read_text(encoding="utf-8")

# Fix ret_total in panel_rows of test_a0_long_cash_six_assets
old_test_a0 = '''        for a in assets:
            panel_rows.append({
                "date": d,
                "asset": a,
                "open_adj": 100.0,
                "close_adj": 100.0,
                "ret_total": 0.001,
                "amount": 1e8,
            })'''

new_test_a0 = '''        ret_val = 0.01 if (d.day % 2 == 0) else -0.01
        for a in assets:
            panel_rows.append({
                "date": d,
                "asset": a,
                "open_adj": 100.0,
                "close_adj": 100.0,
                "ret_total": ret_val,
                "amount": 1e8,
            })'''

content = content.replace(old_test_a0, new_test_a0)
content = content.replace('res_a["metrics"]["max_drawdown_daily"]', 'res_a["summary"]["max_drawdown_daily"]')
content = content.replace('res_b["metrics"]["max_drawdown_daily"]', 'res_b["summary"]["max_drawdown_daily"]')

Path("tests/test_project3_counterexamples.py").write_text(content, encoding="utf-8")
print("Fixed counterexamples tests!")
