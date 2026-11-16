with open("BUGFIX_CHANGELOG.md", "r", encoding="utf-8") as f:
    text = f.read()

print("Length of BUGFIX_CHANGELOG.md:", len(text))
idx = text.rfind("## ")
print("Last section header:", text[idx:idx+100])
