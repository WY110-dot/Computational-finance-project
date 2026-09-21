uv sync --locked
uv run --locked python -m pytest
uv run --locked python run.py --config config/default.json --out outputs
uv run --locked python verify.py --config config/default.json --out outputs --rerun
#复跑
notepad config\default.json
"end": "2026-09-21",
"adjustment_reference_date": "2026-09-21"
#更新
uv run --locked python download_data.py `
  --config config/default.json `
  --snapshot-dir data/raw_20260921 `
  --manifest data/manifests/source_manifest_20260921.json
#下载新快照
"prices_snapshot": "data/raw_20260921/prices_raw.parquet",
"adjustment_snapshot": "data/raw_20260921/adjustment_raw.parquet",
"manifest": "data/manifests/source_manifest_20260921.json"
#让项目使用新数据
uv run --locked python run.py --config config/default.json --out outputs
uv run --locked python verify.py --config config/default.json --out outputs --rerun
#复跑