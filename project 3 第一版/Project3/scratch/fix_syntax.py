with open("src/quantcf/project3_report.py", "r", encoding="utf-8") as f:
    text = f.read()

# Replace the broken newline
old_str = 'md_content += f"| **{r[\'universe\']}** | {r[\'candidate_id\']} | {r[\'candidate_id\']} | {r[\'candidate_id\']} | {r[\'n_dates\']} | {fmt_pct(r[\'ann_return\'])} | {cagr_s} | {fmt_pct(r[\'ann_vol\'])} | {fmt_float(r[\'sharpe\'])} | {fmt_pct(r[\'max_drawdown\'])} | {fmt_pct(r[\'max_drawdown_daily\'])} | {fmt_float(r[\'turnover\'], 1)} | {fmt_fees(r[\'fees\'])} | PASS |\n"'
new_str = 'md_content += f"| **{r[\'universe\']}** | {r[\'candidate_id\']} | {r[\'candidate_id\']} | {r[\'candidate_id\']} | {r[\'n_dates\']} | {fmt_pct(r[\'ann_return\'])} | {cagr_s} | {fmt_pct(r[\'ann_vol\'])} | {fmt_float(r[\'sharpe\'])} | {fmt_pct(r[\'max_drawdown\'])} | {fmt_pct(r[\'max_drawdown_daily\'])} | {fmt_float(r[\'turnover\'], 1)} | {fmt_fees(r[\'fees\'])} | PASS |\\n"'

if old_str in text:
    text = text.replace(old_str, new_str)
    print("Replaced old_str in src/quantcf/project3_report.py")
else:
    print("old_str not found, trying regex...")
    import re
    text = re.sub(r'md_content \+= f"\| \*\*\{r\[\'universe\'\]\}\*\* \| (.*?)\| PASS \|\n"', r'md_content += f"| **{r[\'universe\']}** | \1| PASS |\\n"', text)

with open("src/quantcf/project3_report.py", "w", encoding="utf-8") as f:
    f.write(text)

import py_compile
try:
    py_compile.compile("src/quantcf/project3_report.py", doraise=True)
    print("Compilation SUCCESS!")
except Exception as e:
    print("Compilation error:", e)
