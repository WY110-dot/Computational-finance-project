# Raw data snapshot

`prices_raw.parquet` and `adjustment_raw.parquet` are immutable Tushare snapshots inherited from the validated project1 draft. Their original legacy manifest is preserved under `data/manifests/source_manifest_legacy.json`; the final pipeline calculates and records fresh SHA-256 hashes without rewriting the source files.

Do not manually edit these Parquet files. A refreshed download must be written as a new snapshot and recorded with its retrieval time, requested universe, date range, API names and checksums.

