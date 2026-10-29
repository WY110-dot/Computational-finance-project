"""Generate the final 6-10 page Chinese research report from run outputs.

No performance number is embedded in this module.  Tables, charts and summary
sentences are populated from ``ReportInputs`` at build time.  Inputs may be
in-memory mappings/DataFrames or paths to CSV, Parquet or JSON files.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import date, datetime
import html
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


@dataclass
class ReportInputs:
    """Flexible collection of audited outputs consumed by the report."""

    title: str = "CF2026 计算金融课程项目"
    subtitle: str = "基于 Tushare 的可复现多因子研究与下一交易日开盘回测"
    config: Any = None
    manifest: Any = None
    data_quality: Any = None
    factor_summary: Any = None
    ic_summary: Any = None
    ic_timeseries: Any = None
    group_summary: Any = None
    spread_summary: Any = None
    rank_dynamics: Any = None
    strategy_summary: Any = None
    equity_curves: Any = None
    experiment_summary: Any = None
    liquidity_summary: Any = None
    audit_summary: Any = None
    limitations: Sequence[str] | None = None
    source_notes: Sequence[str] | None = None

    @classmethod
    def from_directory(cls, directory: str | Path, **overrides: Any) -> "ReportInputs":
        """Discover conventional result filenames without requiring all of them."""

        root = Path(directory)
        candidates = {
            "config": ("config.json", "default.json"),
            "manifest": ("run_manifest.json", "manifest.json"),
            "data_quality": ("data_quality.json", "quality_report.json", "data_quality.csv"),
            "factor_summary": ("distribution.csv", "factor_summary.csv"),
            "ic_summary": ("ic_summary.csv",),
            "ic_timeseries": ("ic_timeseries.csv",),
            "group_summary": ("group_summary.csv", "group_returns_summary.csv"),
            "spread_summary": ("spread_summary.csv",),
            "rank_dynamics": ("rank_dynamics.csv",),
            "strategy_summary": ("strategy_summary.csv", "performance.csv"),
            "equity_curves": ("equity_curves.csv", "nav.csv"),
            "experiment_summary": ("experiment_summary.csv", "frequency_experiment.csv"),
            "liquidity_summary": ("liquidity_summary.csv",),
            "audit_summary": ("audit_summary.json", "audit.json", "audit_summary.csv"),
        }
        values: dict[str, Any] = {}
        for field_name, names in candidates.items():
            for name in names:
                path = root / name
                if path.exists():
                    values[field_name] = path
                    break
        values.update(overrides)
        return cls(**values)


def _read_path(path: str | Path) -> Any:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(source)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(source)
    if suffix == ".json":
        return json.loads(source.read_text(encoding="utf-8"))
    raise ValueError(f"unsupported report input format: {source}")


def _load_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, (str, Path)):
        value = _read_path(value)
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, pd.DataFrame):
        return value.iloc[0].to_dict() if not value.empty else {}
    raise TypeError(f"expected mapping-like report input, got {type(value).__name__}")


def _load_table(value: Any) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    if isinstance(value, (str, Path)):
        value = _read_path(value)
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, pd.Series):
        return value.rename("value").reset_index()
    if isinstance(value, Mapping):
        for key in ("records", "rows", "data", "by_asset"):
            if key in value and isinstance(value[key], (list, tuple)):
                return pd.DataFrame(value[key])
        try:
            return pd.DataFrame(value)
        except ValueError:
            return pd.DataFrame([value])
    if isinstance(value, (list, tuple)):
        return pd.DataFrame(value)
    raise TypeError(f"expected table-like report input, got {type(value).__name__}")


def _coerce_inputs(inputs: ReportInputs | Mapping[str, Any] | None, overrides: Mapping[str, Any]) -> ReportInputs:
    if inputs is None:
        result = ReportInputs()
    elif isinstance(inputs, ReportInputs):
        result = inputs
    elif isinstance(inputs, Mapping):
        values = dict(inputs)
        diagnostic = values.pop("diagnostics", None)
        if diagnostic is not None:
            for name in (
                "distribution",
                "ic_summary",
                "ic_timeseries",
                "group_summary",
                "spread_summary",
                "rank_dynamics",
            ):
                if hasattr(diagnostic, name):
                    target = "factor_summary" if name == "distribution" else name
                    values.setdefault(target, getattr(diagnostic, name))
        allowed = {field.name for field in fields(ReportInputs)}
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise TypeError(f"unknown ReportInputs fields: {unknown}")
        result = ReportInputs(**values)
    else:
        raise TypeError("inputs must be ReportInputs, a mapping or None")
    if overrides:
        allowed = {field.name for field in fields(ReportInputs)}
        unknown = sorted(set(overrides) - allowed)
        if unknown:
            raise TypeError(f"unknown report overrides: {unknown}")
        result = replace(result, **dict(overrides))
    return result


def _nested(mapping: Mapping[str, Any], path: str, default: Any = None) -> Any:
    value: Any = mapping
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return default
        value = value[part]
    return value


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fmt(value: Any, digits: int = 3) -> str:
    number = _finite(value)
    return "—" if number is None else f"{number:,.{digits}f}"


def _pct(value: Any, digits: int = 2) -> str:
    number = _finite(value)
    return "—" if number is None else f"{number * 100:.{digits}f}%"


def _integer(value: Any) -> str:
    number = _finite(value)
    return "—" if number is None else f"{int(round(number)):,}"


def _first_column(frame: pd.DataFrame, names: Iterable[str]) -> str | None:
    lower = {str(column).lower(): str(column) for column in frame.columns}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _strategy_table(value: Any) -> pd.DataFrame:
    frame = _load_table(value)
    if frame.empty:
        return frame
    if "strategy" not in frame.columns:
        if frame.index.name is not None or not isinstance(frame.index, pd.RangeIndex):
            frame = frame.reset_index().rename(columns={frame.index.name or "index": "strategy"})
        else:
            first = frame.columns[0]
            if not pd.api.types.is_numeric_dtype(frame[first]):
                frame = frame.rename(columns={first: "strategy"})
            else:
                frame.insert(0, "strategy", [f"strategy_{index + 1}" for index in range(len(frame))])
    frame["strategy"] = frame["strategy"].astype(str)
    return frame


def _metric(frame: pd.DataFrame, row: pd.Series, aliases: Sequence[str]) -> Any:
    column = _first_column(frame, aliases)
    return row[column] if column is not None else None


def _strategy_label(value: Any) -> str:
    name = str(value)
    labels = {
        "momentum_monthly": "MOM20 Monthly",
        "momentum_weekly": "MOM20 Weekly",
        "reversal_weekly": "REV5 Weekly",
        "low_volatility_weekly": "LOWVOL20 Weekly",
        "momentum_weekly_liquidity": "MOM20 Weekly + Capacity",
        "equal_weight_monthly": "Equal-weight Monthly",
    }
    return labels.get(name.lower(), name)


def _select_primary_strategy(frame: pd.DataFrame, config: Mapping[str, Any]) -> pd.Series | None:
    if frame.empty:
        return None
    factor = str(_nested(config, "strategy.primary_factor", "momentum")).lower()
    frequency = str(_nested(config, "strategy.baseline_frequency", "monthly")).lower()
    names = frame["strategy"].str.lower()
    match = frame.loc[names.str.contains(factor, regex=False) & names.str.contains(frequency, regex=False)]
    if match.empty:
        match = frame.loc[names.str.contains(factor, regex=False)]
    return (match.iloc[0] if not match.empty else frame.iloc[0]).copy()


def _equity_wide(value: Any) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    if isinstance(value, Mapping) and not isinstance(value, pd.DataFrame):
        series: list[pd.Series] = []
        for name, item in value.items():
            if isinstance(item, pd.Series):
                current = item.copy()
            else:
                table = _load_table(item)
                date_column = _first_column(table, ("date", "trade_date", "datetime"))
                value_column = _first_column(table, ("wealth", "equity", "nav", "portfolio_value", "value"))
                if date_column is None or value_column is None:
                    continue
                current = pd.Series(table[value_column].to_numpy(), index=pd.to_datetime(table[date_column]))
            current.name = str(name)
            series.append(current)
        return pd.concat(series, axis=1).sort_index() if series else pd.DataFrame()
    frame = _load_table(value)
    if frame.empty:
        return frame
    date_column = _first_column(frame, ("date", "trade_date", "datetime"))
    strategy_column = _first_column(frame, ("strategy", "name", "portfolio"))
    value_column = _first_column(frame, ("wealth", "equity", "nav", "portfolio_value", "value"))
    if date_column and strategy_column and value_column:
        result = frame.pivot(index=date_column, columns=strategy_column, values=value_column)
    else:
        result = frame.set_index(date_column) if date_column else frame.copy()
    result.index = pd.to_datetime(result.index, errors="coerce")
    result = result.loc[result.index.notna()].sort_index()
    return result.apply(pd.to_numeric, errors="coerce")


def _font_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get("QUANTCF_CJK_FONT")
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(
        Path(path)
        for path in (
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyh.ttf",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        )
    )
    return candidates


def _register_cjk_font() -> tuple[str, Path | None]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    for candidate in _font_candidates():
        if not candidate.is_file():
            continue
        try:
            name = "QuantCFCJK"
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(candidate)))
            return name, candidate
        except Exception:
            continue
    fallback = "STSong-Light"
    if fallback not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(fallback))
    return fallback, None


def _chart_font(path: Path | None) -> Any:
    if path is None:
        return None
    try:
        from matplotlib.font_manager import FontProperties

        return FontProperties(fname=str(path))
    except Exception:
        return None


def _make_charts(inputs: ReportInputs, directory: Path, font_path: Path | None) -> dict[str, Path]:
    try:
        import matplotlib
    except ImportError:
        # Charts are helpful but not allowed to make the evidence-bearing PDF
        # fail.  The report will insert an explicit missing-chart notice while
        # retaining all numerical tables.
        return {}

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    chart_font = _chart_font(font_path)
    colours = ["#126477", "#E07A5F", "#3D8D7A", "#7A6FAC", "#D6A84B", "#506784"]
    paths: dict[str, Path] = {}

    def finish(name: str, figure: Any) -> None:
        path = directory / f"{name}.png"
        figure.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(figure)
        paths[name] = path

    equity = _equity_wide(inputs.equity_curves)
    if not equity.empty:
        normalised = equity.divide(equity.apply(lambda column: column.dropna().iloc[0] if column.notna().any() else np.nan))
        figure, axis = plt.subplots(figsize=(8.4, 3.25))
        for index, column in enumerate(normalised.columns[:8]):
            axis.plot(normalised.index, normalised[column], label=_strategy_label(column), linewidth=1.4, color=colours[index % len(colours)])
        axis.axhline(1.0, color="#8B98A1", linewidth=0.7, linestyle="--")
        axis.set_ylabel("Normalized NAV")
        axis.grid(alpha=0.18)
        axis.legend(frameon=False, fontsize=7, ncol=2)
        figure.tight_layout()
        finish("equity", figure)

    ic = _load_table(inputs.ic_timeseries)
    date_column = _first_column(ic, ("date", "trade_date"))
    factor_column = _first_column(ic, ("factor", "name"))
    rank_column = _first_column(ic, ("rank_ic", "rankic", "spearman"))
    horizon_column = _first_column(ic, ("horizon", "period"))
    if date_column and factor_column and rank_column and not ic.empty:
        work = ic.copy()
        work[date_column] = pd.to_datetime(work[date_column], errors="coerce")
        work[rank_column] = pd.to_numeric(work[rank_column], errors="coerce")
        if horizon_column:
            numeric_horizon = pd.to_numeric(work[horizon_column], errors="coerce")
            if numeric_horizon.notna().any():
                work = work.loc[numeric_horizon == numeric_horizon.max()]
        figure, axis = plt.subplots(figsize=(8.4, 3.1))
        for index, (name, group) in enumerate(work.groupby(factor_column, sort=True)):
            group = group.sort_values(date_column)
            smooth = group.set_index(date_column)[rank_column].rolling(20, min_periods=5).mean()
            axis.plot(smooth.index, smooth, label=str(name), linewidth=1.35, color=colours[index % len(colours)])
        axis.axhline(0.0, color="#8B98A1", linewidth=0.7)
        axis.set_ylabel("20D rolling Rank IC")
        axis.grid(alpha=0.18)
        axis.legend(frameon=False, fontsize=7, ncol=3)
        figure.tight_layout()
        finish("rank_ic", figure)

    groups = _load_table(inputs.group_summary)
    required = {
        "factor": _first_column(groups, ("factor", "name")),
        "group": _first_column(groups, ("group", "quantile")),
        "return": _first_column(groups, ("mean_return", "return", "group_return")),
    }
    if all(required.values()) and not groups.empty:
        horizon = _first_column(groups, ("horizon", "period"))
        work = groups.copy()
        if horizon:
            numeric_horizon = pd.to_numeric(work[horizon], errors="coerce")
            if numeric_horizon.notna().any():
                work = work.loc[numeric_horizon == numeric_horizon.max()]
        figure, axis = plt.subplots(figsize=(8.4, 3.1))
        for index, (name, group) in enumerate(work.groupby(required["factor"], sort=True)):
            group = group.sort_values(required["group"])
            axis.plot(
                pd.to_numeric(group[required["group"]], errors="coerce"),
                pd.to_numeric(group[required["return"]], errors="coerce") * 100,
                marker="o",
                label=str(name),
                color=colours[index % len(colours)],
            )
        axis.axhline(0.0, color="#8B98A1", linewidth=0.7)
        axis.set_xlabel("Formation-time quantile (low to high)")
        axis.set_ylabel("Mean forward return (%)")
        axis.grid(alpha=0.18)
        axis.legend(frameon=False, fontsize=7, ncol=3)
        figure.tight_layout()
        finish("groups", figure)
    return paths


def _architecture_drawing(font_name: str) -> Any:
    from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
    from reportlab.lib import colors

    drawing = Drawing(505, 165)
    labels = [
        "Tushare 快照",
        "清洗与复权",
        "因子注册器",
        "Alphalens 式诊断",
        "目标权重",
        "下一日开盘成交",
        "现金持仓账本",
        "报告与运行记录",
    ]
    positions = [(4, 105), (130, 105), (256, 105), (382, 105), (4, 20), (130, 20), (256, 20), (382, 20)]
    for (x, y), label in zip(positions, labels):
        drawing.add(Rect(x, y, 116, 40, rx=7, ry=7, fillColor=colors.HexColor("#E9F2F3"), strokeColor=colors.HexColor("#126477"), strokeWidth=0.8))
        drawing.add(String(x + 58, y + 20, label, fontName=font_name, fontSize=8.2, textAnchor="middle", fillColor=colors.HexColor("#173847")))

    def arrow(x1: float, y1: float, x2: float, y2: float) -> None:
        drawing.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#70939C"), strokeWidth=1.2))
        drawing.add(Polygon([x2, y2, x2 - 5, y2 + 3, x2 - 5, y2 - 3], fillColor=colors.HexColor("#70939C"), strokeColor=None))

    for x in (120, 246, 372):
        arrow(x, 125, x + 10, 125)
        arrow(x, 40, x + 10, 40)
    drawing.add(Line(440, 105, 440, 82, strokeColor=colors.HexColor("#70939C"), strokeWidth=1.2))
    drawing.add(Line(440, 82, 62, 82, strokeColor=colors.HexColor("#70939C"), strokeWidth=1.2))
    drawing.add(Line(62, 82, 62, 60, strokeColor=colors.HexColor("#70939C"), strokeWidth=1.2))
    drawing.add(Polygon([62, 60, 59, 65, 65, 65], fillColor=colors.HexColor("#70939C"), strokeColor=None))
    return drawing


def _page_count_story(
    output_path: Path,
    inputs: ReportInputs,
    font_name: str,
    charts: Mapping[str, Path],
) -> tuple[list[Any], Any]:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    page_width, _ = A4
    content_width = page_width - 32 * mm
    navy = colors.HexColor("#143A4A")
    teal = colors.HexColor("#126477")
    pale = colors.HexColor("#E9F2F3")
    orange = colors.HexColor("#D86F45")
    grey = colors.HexColor("#536773")

    styles = {
        "title": ParagraphStyle("title", fontName=font_name, fontSize=24, leading=34, textColor=navy, spaceAfter=12, alignment=TA_CENTER, wordWrap="CJK"),
        "subtitle": ParagraphStyle("subtitle", fontName=font_name, fontSize=12, leading=20, textColor=teal, spaceAfter=18, alignment=TA_CENTER, wordWrap="CJK"),
        "h1": ParagraphStyle("h1", fontName=font_name, fontSize=17, leading=24, textColor=navy, spaceAfter=10, wordWrap="CJK"),
        "h2": ParagraphStyle("h2", fontName=font_name, fontSize=11.5, leading=18, textColor=teal, spaceBefore=5, spaceAfter=5, wordWrap="CJK"),
        "body": ParagraphStyle("body", fontName=font_name, fontSize=9.2, leading=15, textColor=colors.HexColor("#273B46"), spaceAfter=7, wordWrap="CJK"),
        "small": ParagraphStyle("small", fontName=font_name, fontSize=7.7, leading=11.4, textColor=grey, spaceAfter=5, wordWrap="CJK"),
        "callout": ParagraphStyle("callout", fontName=font_name, fontSize=10, leading=16, textColor=navy, backColor=pale, borderColor=teal, borderWidth=0.6, borderPadding=9, spaceAfter=10, wordWrap="CJK"),
        "warning": ParagraphStyle("warning", fontName=font_name, fontSize=9, leading=14, textColor=colors.HexColor("#72361E"), backColor=colors.HexColor("#FFF2EA"), borderColor=orange, borderWidth=0.5, borderPadding=7, spaceAfter=7, wordWrap="CJK"),
        "cell": ParagraphStyle("cell", fontName=font_name, fontSize=7.5, leading=10.5, textColor=colors.HexColor("#273B46"), wordWrap="CJK"),
    }

    def paragraph(text: Any, style: str = "body") -> Paragraph:
        safe = html.escape(str(text)).replace("\n", "<br/>")
        return Paragraph(safe, styles[style])

    def table(rows: Sequence[Sequence[Any]], widths: Sequence[float] | None = None) -> Table:
        if not rows:
            rows = [["无可用记录"]]
        converted = [[paragraph(cell, "cell") for cell in row] for row in rows]
        object_ = Table(converted, colWidths=widths or [content_width / len(rows[0])] * len(rows[0]), repeatRows=1, hAlign="LEFT")
        object_.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), pale),
                    ("TEXTCOLOR", (0, 0), (-1, 0), navy),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.8, teal),
                    ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#B8CACF")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFA")]),
                ]
            )
        )
        return object_

    def image(name: str, height_mm: float) -> Any:
        if name not in charts:
            return paragraph("该图所需的实际输出尚未提供；报告没有用示例数据替代。", "warning")
        return Image(str(charts[name]), width=content_width, height=height_mm * mm, kind="proportional", hAlign="CENTER")

    config = _load_mapping(inputs.config)
    manifest = _load_mapping(inputs.manifest)
    quality_mapping = _load_mapping(inputs.data_quality) if isinstance(inputs.data_quality, (Mapping, str, Path)) else {}
    quality = _load_table(inputs.data_quality)
    factor_summary = _load_table(inputs.factor_summary)
    ic_summary = _load_table(inputs.ic_summary)
    group_summary = _load_table(inputs.group_summary)
    spread_summary = _load_table(inputs.spread_summary)
    ranks = _load_table(inputs.rank_dynamics)
    strategies = _strategy_table(inputs.strategy_summary)
    experiment = _load_table(inputs.experiment_summary)
    liquidity = _load_table(inputs.liquidity_summary)
    audit_mapping = _load_mapping(inputs.audit_summary) if isinstance(inputs.audit_summary, (Mapping, str, Path)) else {}
    audit = _load_table(inputs.audit_summary)
    primary = _select_primary_strategy(strategies, config)

    assets = _nested(config, "data.assets", []) or []
    start = _nested(config, "data.start", manifest.get("research_start", "—"))
    end = _nested(config, "data.end", manifest.get("research_end", "—"))
    horizons = _nested(config, "factors.label_horizons", []) or []
    top_n = _nested(config, "strategy.top_n", "—")
    buy_fee = _nested(config, "execution.buy_fee", None)
    sell_fee = _nested(config, "execution.sell_fee", None)
    participation = _nested(config, "execution.participation_rate", None)

    if primary is None:
        executive = "策略汇总尚未提供，因此本报告不生成任何收益结论。"
    else:
        total_return = _metric(strategies, primary, ("total_return", "cumulative_return", "net_total_return"))
        sharpe = _metric(strategies, primary, ("sharpe", "sharpe_ratio", "annualized_sharpe"))
        drawdown = _metric(strategies, primary, ("max_drawdown", "maximum_drawdown"))
        executive = (
            f"预先指定主策略“{_strategy_label(primary['strategy'])}”的净累计收益为 {_pct(total_return)}，"
            f"年化 Sharpe 为 {_fmt(sharpe)}，最大回撤为 {_pct(drawdown)}。"
            "这些数字是历史描述结果，不代表未来收益承诺。"
        )

    story: list[Any] = []

    # Page 1: cover and executive summary.
    story.extend(
        [
            Spacer(1, 18 * mm),
            paragraph(inputs.title, "title"),
            paragraph(inputs.subtitle, "subtitle"),
            Spacer(1, 5 * mm),
            paragraph("研究目标", "h2"),
            paragraph(
                "建立一套从不可变数据快照、因子诊断、目标组合、订单成交、现金持仓账本到实验记录和自动报告的完整流程。项目首先追求时序正确、可审计和可复现，其次才讨论策略表现。",
                "callout",
            ),
            table(
                [
                    ["研究维度", "预先固定的设计"],
                    ["市场与样本", f"Tushare A 股 ETF；{start} 至 {end}；配置资产 {len(assets) if assets else '—'} 只"],
                    ["因子", "20 日动量、5 日反转、20 日低波动；统一为分数越高越优"],
                    ["执行", "形成日收盘后产生信号，下一交易日开盘成交；不借款、不卖空"],
                    ["对照实验", "主因子的月度与周度调仓；除频率外保持其他参数一致"],
                    ["自主拓展", "基于滞后成交金额的参与率限制、部分成交、未成交不收费"],
                ],
                [42 * mm, content_width - 42 * mm],
            ),
            Spacer(1, 7 * mm),
            paragraph("结果摘要", "h2"),
            paragraph(executive),
            paragraph("报告中的表格、图形和数值均在生成时读取本次运行输出；缺失证据会被明确标记，不以手工示例补齐。", "small"),
            PageBreak(),
        ]
    )

    # Page 2: data and architecture.
    quality_rows: list[list[Any]] = [["数据质量字段", "本次输出"]]
    if quality_mapping:
        for key in ("raw_rows", "clean_rows", "calendar_days", "missing_grid_cells", "duplicate_rows", "invalid_rows"):
            if key in quality_mapping:
                quality_rows.append([key, quality_mapping[key]])
    if len(quality_rows) == 1 and not quality.empty:
        for column in quality.columns[:6]:
            if len(quality) == 1:
                quality_rows.append([column, quality.iloc[0][column]])
    if len(quality_rows) == 1:
        quality_rows.append(["状态", "未提供结构化数据质量摘要"])
    story.extend(
        [
            paragraph("1  数据契约与系统架构", "h1"),
            paragraph("数据范围与不可变快照", "h2"),
            paragraph(
                "原始日线与复权因子分别保存，并以 SHA-256 校验。清洗层只执行显式规则：日期和代码唯一、价格为正、成交量和成交额非负、复权参考日固定。原始价格、复权因子与复权价格同时保留，避免无法追溯的二次调整。"
            ),
            table(quality_rows[:8], [55 * mm, content_width - 55 * mm]),
            Spacer(1, 4 * mm),
            paragraph("模块边界", "h2"),
            _architecture_drawing(font_name),
            paragraph(
                "架构借鉴 Qlib 的配置与记录器分离、Alphalens 的因子诊断契约，以及 Backtrader 的策略/订单/成交/经纪商账本边界；本项目保留轻量自研实现，便于逐笔核验课程要求。",
                "small",
            ),
            PageBreak(),
        ]
    )

    # Page 3: factors and diagnostic protocol.
    story.extend(
        [
            paragraph("2  因子、标签与诊断协议", "h1"),
            table(
                [
                    ["因子", "定义（形成日 t 收盘可得）", "方向与主要失效情形"],
                    ["20 日动量", "C(t) / C(t-20) - 1", "越大越优；反转、拥挤和制度切换时可能失效"],
                    ["5 日反转", "-[C(t) / C(t-5) - 1]", "越大越优；持续趋势中可能长期逆势"],
                    ["20 日低波动", "-std[r(t-19), …, r(t)]", "越大越优；风险偏好快速上升时可能落后"],
                ],
                [28 * mm, 58 * mm, content_width - 86 * mm],
            ),
            Spacer(1, 5 * mm),
            paragraph("可交易的前向标签", "h2"),
            paragraph(
                "对持有期 h，标签定义为 y(t,h) = O(t+1+h) / O(t+1) - 1。因子在 t 日收盘后形成，最早只能在 t+1 日开盘进入；标签只进入诊断模块，绝不进入权重或成交模块。"
            ),
            paragraph(f"本次配置的诊断持有期为：{', '.join(map(str, horizons)) if horizons else '以诊断输出为准'} 个交易日。多日标签可能重叠，因此 IC 与分组收益只作排序诊断，不拼接成策略净值。", "small"),
            paragraph("截面相关与形成时分组", "h2"),
            paragraph(
                "每天跨资产计算 Pearson IC 与使用平均并列秩的 Spearman Rank IC。有效样本少于配置阈值，或因子/标签任一为常数时，相关系数保留为缺失。分位组先按因子值、再按资产代码稳定排序并一次性形成；随后标签缺失只减少原组有效人数，绝不重新分组。"
            ),
            paragraph("稳定性与交易含义", "h2"),
            paragraph(
                "除覆盖率和分布外，还记录相邻形成日的因子秩自相关、平均绝对百分位变化，以及各分位组成员换手。较低秩自相关通常意味着信号变化快，可能在真实执行中对应更高换手和更敏感的交易成本。"
            ),
            paragraph("IC 不是收益率，Rank IC 也不是预测正确率。任何统计显著性结论都需要进一步处理重叠标签、自相关和多重检验。", "warning"),
            PageBreak(),
        ]
    )

    # Page 4: actual diagnostics.
    factor_rows = [["因子", "覆盖率", "均值", "标准差", "1%", "中位数", "99%"]]
    if not factor_summary.empty:
        factor_col = _first_column(factor_summary, ("factor", "name"))
        for _, row in factor_summary.head(6).iterrows():
            factor_rows.append(
                [
                    row[factor_col] if factor_col else "—",
                    _pct(row.get("coverage")),
                    _fmt(row.get("mean"), 4),
                    _fmt(row.get("std"), 4),
                    _fmt(row.get("p01"), 4),
                    _fmt(row.get("p50"), 4),
                    _fmt(row.get("p99"), 4),
                ]
            )
    else:
        factor_rows.append(["未提供", "—", "—", "—", "—", "—", "—"])
    ic_rows = [["因子", "持有期", "平均 IC", "平均 Rank IC", "有效日", "平均有效资产"]]
    if not ic_summary.empty:
        factor_col = _first_column(ic_summary, ("factor", "name"))
        for _, row in ic_summary.head(8).iterrows():
            ic_rows.append(
                [
                    row[factor_col] if factor_col else "—",
                    _integer(row.get("horizon")),
                    _fmt(row.get("mean_ic", row.get("ic_mean")), 4),
                    _fmt(row.get("mean_rank_ic", row.get("rank_ic_mean")), 4),
                    _integer(row.get("ic_days", row.get("valid_days"))),
                    _fmt(row.get("mean_effective_assets"), 1),
                ]
            )
    else:
        ic_rows.append(["未提供", "—", "—", "—", "—", "—"])
    story.extend(
        [
            paragraph("3  因子诊断结果", "h1"),
            paragraph("覆盖率与原始分布", "h2"),
            table(factor_rows),
            Spacer(1, 3 * mm),
            paragraph("逐日 IC 与 Rank IC", "h2"),
            table(ic_rows),
            Spacer(1, 3 * mm),
            image("rank_ic", 47),
            image("groups", 47),
            paragraph(
                "分组图使用形成时成员，并对每个形成日先做组内等权平均、再跨日平均。High-Low 为最高分组减最低分组；单调性同时报告严格标签和组号-平均收益秩相关。",
                "small",
            ),
            PageBreak(),
        ]
    )

    # Page 5: execution correctness.
    story.extend(
        [
            paragraph("4  回测设计与正确性控制", "h1"),
            paragraph("事件时序与职责分离", "h2"),
            paragraph(
                "策略层只输出目标权重；执行层把目标与交易前持仓转换为订单；成交层应用下一交易日开盘价、费用、滑点和容量限制；账本层独立维护现金、份额和收盘估值。该边界防止因子代码直接改写资金，便于逐项审计。"
            ),
            table(
                [
                    ["控制项", "实现约束"],
                    ["信息可得性", "t 日收盘因子只能影响 t+1 日及之后的订单"],
                    ["价格缺失", "缺少当日开盘价则不成交、不收费；已有持仓按受限的最近收盘价估值"],
                    ["现金与卖空", "先卖后买；买入按可用现金同比缩放；现金不得透支、份额不得为负"],
                    ["费用", f"买入 {_pct(buy_fee)}、卖出 {_pct(sell_fee)}；只按实际成交金额收取"],
                    ["毛/净收益", "相同信号与配置进行零费率独立重跑，不用净收益机械加回手续费"],
                    ["容量", f"过去完整窗口的滞后成交额 × 参与率 {_pct(participation)}；允许部分成交"],
                ],
                [42 * mm, content_width - 42 * mm],
            ),
            Spacer(1, 5 * mm),
            paragraph("账本恒等式", "h2"),
            paragraph(
                "Fee(t) = cb × Buy(t) + cs × Sell(t)\n"
                "Cash(t) = Cash(t-1) + Sell(t) - Buy(t) - Fee(t)\n"
                "Units_i(t) = Units_i(t-1) + Executed_i(t) / Open_i(t)\n"
                "Equity(t) = Cash(t) + Σ Units_i(t) × Close_i(t)"
            ),
            paragraph("最大回撤把初始资金作为第一个峰值，因而不会遗漏首日交易成本造成的回撤。换手使用实际双边成交额除以交易前权益；未成交订单既不改变份额，也不产生费用。", "callout"),
            paragraph("关键自动测试", "h2"),
            paragraph(
                "测试覆盖前向标签手算、未来数据扰动不改变历史、常数截面 IC 为缺失、形成时分组不受标签缺失影响、先卖后买现金恒等式、缺价冻结、部分成交、未成交零费用、容量使用滞后窗口、无限容量退化为基础回测，以及相同输入重复运行完全一致。",
                "small",
            ),
            PageBreak(),
        ]
    )

    # Page 6: performance.
    performance_rows = [["策略", "累计收益", "年化收益", "年化波动", "Sharpe", "最大回撤", "累计成本"]]
    if not strategies.empty:
        for _, row in strategies.head(9).iterrows():
            performance_rows.append(
                [
                    _strategy_label(row["strategy"]),
                    _pct(_metric(strategies, row, ("total_return", "cumulative_return", "net_total_return"))),
                    _pct(_metric(strategies, row, ("annualized_return", "annual_return", "cagr"))),
                    _pct(_metric(strategies, row, ("annualized_volatility", "annual_vol", "volatility"))),
                    _fmt(_metric(strategies, row, ("sharpe", "sharpe_ratio", "annualized_sharpe"))),
                    _pct(_metric(strategies, row, ("max_drawdown", "maximum_drawdown"))),
                    _fmt(_metric(strategies, row, ("total_cost", "cumulative_cost", "fees")), 2),
                ]
            )
    else:
        performance_rows.append(["未提供", "—", "—", "—", "—", "—", "—"])
    story.extend(
        [
            paragraph("5  策略绩效、风险与成本", "h1"),
            table(performance_rows),
            Spacer(1, 5 * mm),
            image("equity", 78),
            paragraph(executive, "callout"),
            paragraph(
                "累计收益、年化收益、年化波动、Sharpe 和最大回撤均以扣费后净值为主。交易次数、平均持仓数、最大单资产权重、双边换手和累计现金费用应与收益指标一起解释；高收益而现金或持仓恒等式不成立的结果无效。",
                "small",
            ),
            PageBreak(),
        ]
    )

    # Page 7: controlled experiment and liquidity extension.
    if experiment.empty and not strategies.empty:
        primary_factor = str(_nested(config, "strategy.primary_factor", "momentum")).lower()
        mask = strategies["strategy"].str.lower().str.contains(primary_factor, regex=False)
        frequency_rows = strategies.loc[mask & strategies["strategy"].str.lower().str.contains("weekly|monthly", regex=True)]
        experiment = frequency_rows.copy()
    experiment_rows = [["方案", "累计净收益", "Sharpe", "换手", "累计成本"]]
    if not experiment.empty:
        exp_strategy = _strategy_table(experiment)
        for _, row in exp_strategy.head(6).iterrows():
            experiment_rows.append(
                [
                    _strategy_label(row["strategy"]),
                    _pct(_metric(exp_strategy, row, ("total_return", "cumulative_return", "net_total_return"))),
                    _fmt(_metric(exp_strategy, row, ("sharpe", "sharpe_ratio", "annualized_sharpe"))),
                    _fmt(_metric(exp_strategy, row, ("annual_turnover", "turnover", "annualized_turnover"))),
                    _fmt(_metric(exp_strategy, row, ("total_cost", "cumulative_cost", "fees")), 2),
                ]
            )
    else:
        experiment_rows.append(["频率对照证据尚未提供", "—", "—", "—", "—"])
    liquidity_rows = [["流动性拓展指标", "本次输出"]]
    if not liquidity.empty:
        if len(liquidity) == 1:
            for column in liquidity.columns[:8]:
                value = liquidity.iloc[0][column]
                key = str(column).lower()
                if _finite(value) is not None and ("return" in key or "ratio" in key):
                    value = _pct(value)
                elif _finite(value) is not None and ("notional" in key or "cost" in key):
                    value = f"{float(value):,.2f}"
                elif column in {"unlimited_strategy", "limited_strategy"}:
                    value = _strategy_label(value)
                liquidity_rows.append([column, value])
        else:
            name_column = _first_column(liquidity, ("strategy", "metric", "name")) or liquidity.columns[0]
            value_column = _first_column(liquidity, ("value", "result"))
            for _, row in liquidity.head(7).iterrows():
                liquidity_rows.append([row[name_column], row[value_column] if value_column else str(row.to_dict())])
    else:
        liquidity_rows.append(["状态", "可选流动性实验未提供；本报告不推断成交比例或容量影响"])
    story.extend(
        [
            paragraph("6  控制实验与流动性拓展", "h1"),
            paragraph("只改变调仓频率", "h2"),
            paragraph(
                f"主因子保持为 {_nested(config, 'strategy.primary_factor', '配置值')}，持仓数量保持为 {top_n}，资产池、样本区间、费率、执行时点和权重规则不变；唯一主要差异是月度与周度调仓。事前只预期较低频率减少交易负担，不预设收益或 Sharpe 必然改善。"
            ),
            table(experiment_rows),
            paragraph("频率改变也会改变持仓暴露路径，因此净收益差不能全部归因于费用；零费率重跑有助于拆分但仍是两条独立路径。", "small"),
            paragraph("自主拓展：滞后流动性预算", "h2"),
            table(liquidity_rows[:9], [62 * mm, content_width - 62 * mm]),
            paragraph(
                "容量上限只使用成交日前已经完成的历史成交额窗口。卖单和买单分别受限，执行后留下的旧持仓真实保留；未成交部分当日取消且不收费。复权价格乘成交量只是容量代理，因此拓展的主要价值是检验执行约束接入是否正确，而非证明真实市场容量。",
                "small",
            ),
            PageBreak(),
        ]
    )

    # Page 8: audit, reproducibility and limitations.
    hash_rows = [["可复现对象", "SHA-256 / 状态"]]
    hashes = manifest.get("hashes", {}) if isinstance(manifest.get("hashes", {}), Mapping) else {}
    for key in ("config_sha256", "data_sha256", "source_sha256", "environment_sha256"):
        if key in hashes:
            hash_rows.append([key, str(hashes[key])])
    if len(hash_rows) == 1:
        hash_rows.append(["运行清单", "未提供哈希清单"])
    audit_rows = [["审计字段", "本次输出"]]
    if audit_mapping:
        for key, value in list(audit_mapping.items())[:8]:
            if isinstance(value, Mapping):
                boolean_values = [item for item in value.values() if isinstance(item, (bool, np.bool_))]
                if boolean_values and len(boolean_values) == len(value):
                    shown = f"{sum(map(bool, boolean_values))}/{len(boolean_values)} passed"
                else:
                    finite_values = [_finite(item) for item in value.values()]
                    finite_values = [item for item in finite_values if item is not None]
                    shown = max(finite_values) if finite_values else str(value)
            else:
                shown = value
            audit_rows.append([key, shown])
    elif not audit.empty:
        for column in audit.columns[:7]:
            audit_rows.append([column, audit.iloc[0][column]])
    else:
        audit_rows.append(["状态", "未提供独立账本审计摘要"])
    limitations = list(inputs.limitations or [
        "固定 ETF 资产池不能消除幸存者偏差，历史结果只代表该池和该区间。",
        "日频开盘成交忽略盘口深度、集合竞价提交限制和日内冲击。",
        "参与率模型使用历史成交金额代理，不能替代真实可成交容量。",
        "已观察过部分历史结果，时间分段只能称为稳健性分析，不能包装为完全未见样本外检验。",
        "重叠标签和多次研究选择会影响统计推断，本报告的 IC 与分组结果以描述性解释为主。",
    ])
    source_notes = list(inputs.source_notes or [
        "数据接口：Tushare Pro（fund_daily 与 fund_adj）；本地快照和哈希是复现基准。",
        "设计参考：Quantopian Alphalens、Microsoft Qlib、mementum Backtrader 的公开架构思想；未复制其研究结论。",
        "课程要求：CF2026 Project 1 任务说明。",
    ])
    limitation_text = "\n".join(f"{index + 1}. {text}" for index, text in enumerate(limitations))
    source_text = "\n".join(f"[{index + 1}] {text}" for index, text in enumerate(source_notes))
    story.extend(
        [
            paragraph("7  审计、复现、局限与下一步", "h1"),
            paragraph("实验记录与独立审计", "h2"),
            table(hash_rows, [53 * mm, content_width - 53 * mm]),
            Spacer(1, 3 * mm),
            table(audit_rows[:9], [53 * mm, content_width - 53 * mm]),
            paragraph(
                f"运行编号：{manifest.get('run_id', '—')}；稳定实验指纹：{manifest.get('experiment_fingerprint', '—')}。JSON 使用严格标准格式，缺失数值写为 null，不写入 NaN 或 Infinity。工件清单逐文件记录大小与 SHA-256。",
                "small",
            ),
            paragraph("局限与解释边界", "h2"),
            paragraph(limitation_text),
            paragraph("下一步", "h2"),
            paragraph(
                "优先引入动态资产池和退市/上市历史、真实停牌涨跌停与最小交易单位、可校准的成交容量和冲击模型，并在预先冻结且未查看的验证期上复核。只有在账本审计、数据版本和研究协议全部固定后，才考虑更复杂的组合优化或机器学习。"
            ),
            paragraph("资料来源与设计借鉴", "h2"),
            paragraph(source_text, "small"),
        ]
    )
    return story, styles


def generate_report(
    output_path: str | Path,
    inputs: ReportInputs | Mapping[str, Any] | None = None,
    **overrides: Any,
) -> Path:
    """Build the polished eight-page evidence-backed Chinese report."""
    report_inputs = _coerce_inputs(inputs, overrides)
    destination = Path(output_path)
    from .polished_report import generate_polished_report

    return generate_polished_report(destination, report_inputs)


build_report = generate_report


__all__ = ["ReportInputs", "build_report", "generate_report"]
