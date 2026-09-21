"""
重新下载最新完整数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.data.tushare_connector import TushareConnector
from src.data.data_downloader import DataDownloader
from src.data.data_quality import DataQualityChecker

print("\n" + "="*80)
print("重新下载最新完整数据 (2020-2026)")
print("="*80)

# 下载数据
downloader = DataDownloader()
df = downloader.download_etf_data(
    ts_code="510050.SH",
    start_date="20200101",
    end_date="",  # 不指定结束日期，获取所有可用数据
    save_csv=True
)

if not df.empty:
    print(f"\n[OK] 成功下载 {len(df)} 条记录")
    print(f"日期范围: {df['trade_date'].min()} 至 {df['trade_date'].max()}")
    
    # 质量检查
    print("\n" + "="*80)
    print("运行质量检查...")
    print("="*80)
    
    checker = DataQualityChecker()
    results = checker.check_all(df, ts_code="510050.SH")
    
    report_dir = Path(__file__).parent / "data" / "processed"
    checker.save_report(results, report_dir)
    
    print("\n" + "="*80)
    print("数据更新完成！")
    print("="*80)
    print(f"总记录数: {len(df)}")
    print(f"时间跨度: {df['trade_date'].min()} - {df['trade_date'].max()}")
    print(f"质量状态: {results['status']}")
    print("="*80)
else:
    print("[ERROR] 下载失败")
