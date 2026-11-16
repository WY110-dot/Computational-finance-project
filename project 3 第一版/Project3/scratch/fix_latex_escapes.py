with open("src/quantcf/project3_report.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix LaTeX in f-strings so that \frac becomes \\frac, \times becomes \\times, \cdot becomes \\cdot, \sum becomes \\sum
# In raw string representation:
text = text.replace(r"\frac", r"\\frac")
text = text.replace(r"\times", r"\\times")
text = text.replace(r"\cdot", r"\\cdot")
text = text.replace(r"\sum", r"\\sum")
text = text.replace(r"\ln", r"\\ln")
text = text.replace(r"\Delta", r"\\Delta")

with open("src/quantcf/project3_report.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated LaTeX backslashes in src/quantcf/project3_report.py")
