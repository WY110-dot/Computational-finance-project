import os
import zipfile

source_dir = r"F:\金融数学资料\计算金融\Project\CF2026_Quant_System"
output_zip = r"F:\金融数学资料\计算金融\CF2026_project1.zip"

# 严格剔除禁止提交的文件和目录
exclude_dirs = {'.venv', '.git', '__pycache__', '.pytest_cache', '.mypy_cache', 'temp_matplotlib'}
exclude_files = {'.env', '.DS_Store'}

print(f"开始打包项目，源目录: {source_dir}")
print(f"目标文件: {output_zip}")
print(f"正在过滤以下敏感/冗余文件: {exclude_dirs | exclude_files}")

with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(source_dir):
        # 原地修改 dirs 以跳过不需要遍历的目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file in exclude_files:
                continue
            
            file_path = os.path.join(root, file)
            # 让压缩包内的相对路径直接以项目目录内容开始
            arcname = os.path.relpath(file_path, source_dir)
            zipf.write(file_path, arcname)

print(f"打包完成！文件已保存至: {output_zip}")

