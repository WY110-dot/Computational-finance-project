import json
d = json.load(open("f:/金融数学/计算金融/Project/project 3 第一版/verification.json", encoding="utf-8"))
print("Reproducibility:", d["reproducibility"]["performed"], d["reproducibility"]["tables_compared"], d["reproducibility"]["max_absolute_difference"])
