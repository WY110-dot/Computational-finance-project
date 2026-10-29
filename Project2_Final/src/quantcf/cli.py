"""Command-line interface for the reproducible research workflow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Sequence

from dotenv import load_dotenv

from .data import download_tushare_snapshots
from .pipeline import (
    build_report_from_outputs,
    load_config,
    project_root,
    run_pipeline,
    verify_outputs,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quantcf",
        description="CF2026 可复现因子研究、严格回测与报告工具",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="运行完整研究流水线")
    run.add_argument("--config", default="config/default.json", help="JSON 配置文件")
    run.add_argument("--out", default="outputs", help="输出目录")
    run.add_argument("--no-report", action="store_true", help="跳过 PDF，仅生成数值结果")

    verify = commands.add_parser("verify", help="核验哈希、账本与可复现性")
    verify.add_argument("--config", default="config/default.json", help="JSON 配置文件")
    verify.add_argument("--out", default="outputs", help="已完成的输出目录")
    verify.add_argument(
        "--rerun",
        action="store_true",
        help="在临时目录完整重跑并逐项比较（约需一分钟）",
    )

    report = commands.add_parser("report", help="从已保存结果重建 PDF")
    report.add_argument("--out", default="outputs", help="已完成的输出目录")
    report.add_argument(
        "--pdf",
        default=None,
        help="PDF 路径；默认 output/pdf/CF2026_Project1_Final_Report.pdf",
    )

    download = commands.add_parser("download", help="从 Tushare 下载新的不可变快照")
    download.add_argument("--config", default="config/default.json", help="JSON 配置文件")
    download.add_argument(
        "--snapshot-dir",
        required=True,
        help="必须是尚不存在快照文件的新目录，例如 data/raw_20260921",
    )
    download.add_argument("--manifest", default=None, help="新清单路径；默认快照目录上级")
    return parser


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main(argv: Sequence[str] | None = None) -> int:
    # Keep Chinese status/help readable when Windows inherits a legacy code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        if args.command == "run":
            print("正在运行数据校验、因子诊断和严格账本回测……", flush=True)
            result = run_pipeline(
                args.config,
                args.out,
                generate_pdf=not args.no_report,
            )
            _print(
                {
                    "status": "completed",
                    "output_directory": result["output_directory"],
                    "report": result["report"],
                    "run_id": result["run_id"],
                    "audit_passed": result["audit_summary"]["all_passed"],
                    "verification_passed": result["verification"]["passed"],
                }
            )
            return 0
        if args.command == "verify":
            print("正在核验输出；重复运行模式会重新执行整套研究……", flush=True)
            result = verify_outputs(args.out, args.config, rerun=args.rerun)
            _print(result)
            return 0 if result.get("passed") else 2
        if args.command == "report":
            path = build_report_from_outputs(args.out, args.pdf)
            _print({"status": "completed", "report": str(path)})
            return 0
        if args.command == "download":
            config, _, root = load_config(args.config)
            load_dotenv(root / ".env", override=False)
            if not os.environ.get("TUSHARE_TOKEN"):
                raise RuntimeError("请先在 .env 或环境变量中设置 TUSHARE_TOKEN；账号 ID 不是 API Token。")
            snapshot_dir = Path(args.snapshot_dir)
            if not snapshot_dir.is_absolute():
                snapshot_dir = root / snapshot_dir
            manifest = Path(args.manifest) if args.manifest else None
            if manifest is not None and not manifest.is_absolute():
                manifest = root / manifest
            data = config["data"]
            result = download_tushare_snapshots(
                data["assets"],
                data["start"],
                data["end"],
                snapshot_dir,
                manifest_path=manifest,
            )
            _print({key: str(value) for key, value in result.items()})
            return 0
    except Exception as exc:
        print(f"错误：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
