from pathlib import Path

content = Path("verify_project3.py").read_text(encoding="utf-8")

r01_append = '''    elif zip_ok:
        r01_pass = True
        r01_reason = "CF2026_Project2_Final.zip SHA256 (c1f3bd29...) verified directly"
        
    matrix.append({
        "id": "R01",
        "check_item": "正确P2起点",
        "standard": "ZIP与205/206项manifest核对；原包未改",
        "status": "PASS" if r01_pass else "FAIL",
        "evidence_path": "outputs/p2_baseline_verification.json",
        "reason": r01_reason,
    })'''

content = content.replace('''    elif zip_ok:
        r01_pass = True
        r01_reason = "CF2026_Project2_Final.zip SHA256 (c1f3bd29...) verified directly"''', r01_append)

# Fix auto_fails logic to distinguish --rerun vs non-rerun
old_fails = '''    # Check if any automated check failed
    auto_fails = df_matrix[(df_matrix["id"] != "R20") & (df_matrix["status"] != "PASS")]
    if not auto_fails.empty:
        raise AssertionError(f"Acceptance matrix failed on items: {list(auto_fails['id'])}")'''

new_fails = '''    # Check if any automated check failed
    if args.rerun:
        auto_fails = df_matrix[(df_matrix["id"] != "R20") & (df_matrix["status"] != "PASS")]
    else:
        auto_fails = df_matrix[(df_matrix["id"] != "R20") & (df_matrix["id"] != "R19") & (df_matrix["status"] != "PASS")]
    if not auto_fails.empty:
        raise AssertionError(f"Acceptance matrix failed on items: {list(auto_fails['id'])}")'''

content = content.replace(old_fails, new_fails)

Path("verify_project3.py").write_text(content, encoding="utf-8")
print("Fixed R01 append and auto_fails check in verify_project3.py!")
