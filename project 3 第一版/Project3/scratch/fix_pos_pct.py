from pathlib import Path

content = Path("src/quantcf/project3_report.py").read_text(encoding="utf-8")
content = content.replace("r['delta_ann_pos_ratio']", "r['delta_ann_pos_pct']")
Path("src/quantcf/project3_report.py").write_text(content, encoding="utf-8")
print("Fixed delta_ann_pos_pct in report.py!")
