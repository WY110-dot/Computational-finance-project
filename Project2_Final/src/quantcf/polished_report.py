"""Polished eight-page PDF renderer with audited mathematical notation."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .report import (
    _equity_wide,
    _finite,
    _fmt,
    _load_mapping,
    _load_table,
    _metric,
    _nested,
    _pct,
    _register_cjk_font,
    _select_primary_strategy,
    _strategy_label,
    _strategy_table,
)


NAVY = "#102F44"
NAVY_2 = "#173F55"
TEAL = "#087E8B"
CYAN = "#DDF2F3"
CORAL = "#F26B4F"
GOLD = "#D9A441"
INK = "#213442"
MUTED = "#607783"
PALE = "#F3F7F8"
LINE = "#CBD9DE"
WHITE = "#FFFFFF"


def _bold_font(regular: str) -> str:
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        candidate = Path("C:/Windows/Fonts/msyhbd.ttc")
        if candidate.is_file():
            name = "QuantCFCJKBold"
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(candidate)))
            return name
    except Exception:
        pass
    return regular


def _safe_num(value: Any, default: float = 0.0) -> float:
    result = _finite(value)
    return default if result is None else float(result)


def _make_math_panel(
    path: Path,
    lines: Sequence[str],
    *,
    width: float = 9.6,
    line_height: float = 0.48,
    font_size: float = 16.0,
) -> Path:
    """Render equations with fractions, sums and subscripts as vector-like PNG."""

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    height = max(0.8, 0.30 + line_height * len(lines))
    figure = plt.figure(figsize=(width, height), facecolor=PALE)
    for index, expression in enumerate(lines):
        y = 1.0 - (index + 0.68) / len(lines)
        figure.text(0.035, y, expression, fontsize=font_size, color=NAVY, va="center")
    figure.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.16, facecolor=PALE)
    plt.close(figure)
    return path


def _make_charts(inputs: Any, directory: Path) -> dict[str, Path]:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.edgecolor": "#9FB1B9",
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "grid.color": "#DCE5E8",
            "grid.linewidth": 0.55,
        }
    )
    colours = [TEAL, CORAL, "#4E6FAE", GOLD, "#7A5BA7", "#3C6376"]
    paths: dict[str, Path] = {}

    equity = _equity_wide(inputs.equity_curves)
    if not equity.empty:
        normalised = equity.divide(
            equity.apply(lambda column: column.dropna().iloc[0] if column.notna().any() else np.nan)
        )
        figure, (top, bottom) = plt.subplots(
            2, 1, figsize=(10.4, 5.2), sharex=True,
            gridspec_kw={"height_ratios": [2.35, 1.0], "hspace": 0.08},
        )
        for index, column in enumerate(normalised.columns):
            series = normalised[column]
            colour = colours[index % len(colours)]
            width = 2.0 if str(column).lower() == "momentum_monthly" else 1.25
            top.plot(series.index, series, label=_strategy_label(column), color=colour, linewidth=width)
            drawdown = series / series.cummax() - 1.0
            if str(column).lower() in {"momentum_monthly", "equal_weight_monthly"}:
                bottom.plot(drawdown.index, drawdown * 100.0, label=_strategy_label(column), color=colour, linewidth=1.25)
        top.axhline(1.0, color="#8397A0", linestyle="--", linewidth=0.65)
        top.set_ylabel("Net asset value")
        top.grid(True, alpha=0.8)
        top.legend(frameon=False, fontsize=7.2, ncol=3, loc="upper left")
        bottom.axhline(0.0, color="#8397A0", linewidth=0.6)
        bottom.set_ylabel("Drawdown (%)")
        bottom.grid(True, alpha=0.8)
        bottom.xaxis.set_major_locator(mdates.YearLocator())
        bottom.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        figure.align_ylabels()
        path = directory / "performance.png"
        figure.savefig(path, dpi=210, bbox_inches="tight", facecolor="white")
        plt.close(figure)
        paths["performance"] = path

    ic = _load_table(inputs.ic_timeseries)
    groups = _load_table(inputs.group_summary)
    if not ic.empty or not groups.empty:
        figure, axes = plt.subplots(1, 2, figsize=(10.4, 3.75), gridspec_kw={"wspace": 0.27})
        if not ic.empty:
            work = ic.copy()
            work["date"] = pd.to_datetime(work["date"], errors="coerce")
            if "horizon" in work:
                work = work.loc[pd.to_numeric(work["horizon"], errors="coerce") == 5]
            for index, (name, group) in enumerate(work.groupby("factor", sort=True)):
                smooth = group.sort_values("date").set_index("date")["rank_ic"].rolling(20, min_periods=5).mean()
                axes[0].plot(smooth.index, smooth, label=str(name), color=colours[index], linewidth=1.1)
            axes[0].axhline(0, color="#8397A0", linewidth=0.6)
            axes[0].set_title("20-session rolling Rank IC (h = 5)", color=NAVY, fontsize=9.5, weight="bold")
            axes[0].set_ylabel("Rank IC")
            axes[0].grid(True)
            axes[0].legend(frameon=False, fontsize=7, ncol=3)
            axes[0].xaxis.set_major_locator(mdates.YearLocator(2))
            axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        if not groups.empty:
            work = groups.copy()
            if "horizon" in work:
                work = work.loc[pd.to_numeric(work["horizon"], errors="coerce") == 5]
            for index, (name, group) in enumerate(work.groupby("factor", sort=True)):
                group = group.sort_values("group")
                axes[1].plot(
                    group["group"], pd.to_numeric(group["mean_return"], errors="coerce") * 100,
                    marker="o", markersize=4, label=str(name), color=colours[index], linewidth=1.35,
                )
            axes[1].axhline(0, color="#8397A0", linewidth=0.6)
            axes[1].set_title("Formation-time group return (h = 5)", color=NAVY, fontsize=9.5, weight="bold")
            axes[1].set_xlabel("Quantile: low score  →  high score")
            axes[1].set_ylabel("Mean forward return (%)")
            axes[1].set_xticks([1, 2, 3, 4, 5])
            axes[1].grid(True)
            axes[1].legend(frameon=False, fontsize=7)
        path = directory / "diagnostics.png"
        figure.savefig(path, dpi=210, bbox_inches="tight", facecolor="white")
        plt.close(figure)
        paths["diagnostics"] = path

    strategies = _strategy_table(inputs.strategy_summary)
    if not strategies.empty:
        names = ["momentum_monthly", "momentum_weekly", "momentum_weekly_liquidity"]
        work = strategies.set_index("strategy").reindex(names).dropna(how="all")
        if not work.empty:
            returns = pd.to_numeric(work["cumulative_return"], errors="coerce") * 100
            costs = pd.to_numeric(work["total_transaction_cost"], errors="coerce") / 1000
            labels = [_strategy_label(name) for name in work.index]
            figure, axes = plt.subplots(1, 2, figsize=(10.2, 3.0), gridspec_kw={"wspace": 0.35})
            bars = axes[0].bar(labels, returns, color=[TEAL, "#4E6FAE", GOLD], width=0.62)
            axes[0].set_title("Cumulative net return", color=NAVY, fontsize=9.5, weight="bold")
            axes[0].set_ylabel("Percent")
            axes[0].grid(axis="y")
            axes[0].tick_params(axis="x", rotation=12, labelsize=7)
            for bar, value in zip(bars, returns):
                axes[0].text(bar.get_x() + bar.get_width() / 2, value + 3, f"{value:.1f}%", ha="center", fontsize=7)
            bars = axes[1].bar(labels, costs, color=[TEAL, "#4E6FAE", GOLD], width=0.62)
            axes[1].set_title("Cash transaction cost", color=NAVY, fontsize=9.5, weight="bold")
            axes[1].set_ylabel("CNY thousand")
            axes[1].grid(axis="y")
            axes[1].tick_params(axis="x", rotation=12, labelsize=7)
            for bar, value in zip(bars, costs):
                axes[1].text(bar.get_x() + bar.get_width() / 2, value + 3, f"{value:.1f}", ha="center", fontsize=7)
            path = directory / "experiments.png"
            figure.savefig(path, dpi=210, bbox_inches="tight", facecolor="white")
            plt.close(figure)
            paths["experiments"] = path
    return paths


def _pipeline_drawing(font: str) -> Any:
    from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    drawing = Drawing(178 * mm, 33 * mm)
    labels = ["Tushare\n快照", "清洗与\n固定复权", "因子与\n标签", "目标权重", "次日开盘\nBroker", "审计与\n报告"]
    box_w, box_h, gap = 25.5 * mm, 17 * mm, 4.6 * mm
    y = 8 * mm
    for index, label in enumerate(labels):
        x = index * (box_w + gap)
        fill = colors.HexColor(CYAN if index not in {4, 5} else "#E9EEF6")
        drawing.add(Rect(x, y, box_w, box_h, rx=4, ry=4, fillColor=fill, strokeColor=colors.HexColor(TEAL), strokeWidth=0.8))
        for offset, line in enumerate(label.split("\n")):
            drawing.add(String(x + box_w / 2, y + box_h / 2 + (2.5 - offset * 5) * mm, line, fontName=font, fontSize=7.4, fillColor=colors.HexColor(NAVY), textAnchor="middle"))
        if index < len(labels) - 1:
            start = x + box_w
            end = x + box_w + gap - 1 * mm
            mid = y + box_h / 2
            drawing.add(Line(start, mid, end, mid, strokeColor=colors.HexColor(TEAL), strokeWidth=1.0))
            drawing.add(Polygon([end, mid, end - 2.2 * mm, mid + 1.4 * mm, end - 2.2 * mm, mid - 1.4 * mm], fillColor=colors.HexColor(TEAL), strokeColor=None))
    return drawing


def _timeline_drawing(font: str) -> Any:
    from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    drawing = Drawing(178 * mm, 29 * mm)
    items = [("t 日收盘", "计算因子 / 冻结信号"), ("t+1 日开盘", "先卖后买 / 真实费用"), ("t+1 日收盘", "标记持仓 / 计算净值")]
    for index, ((title, subtitle), x_mm) in enumerate(zip(items, [2, 62, 122])):
        x = x_mm * mm
        drawing.add(Rect(x, 5 * mm, 52 * mm, 18 * mm, rx=5, ry=5, fillColor=colors.HexColor(PALE), strokeColor=colors.HexColor(TEAL if index < 2 else GOLD), strokeWidth=1.0))
        drawing.add(String(x + 26 * mm, 16.5 * mm, title, fontName=font, fontSize=8.2, fillColor=colors.HexColor(NAVY), textAnchor="middle"))
        drawing.add(String(x + 26 * mm, 10 * mm, subtitle, fontName=font, fontSize=6.9, fillColor=colors.HexColor(MUTED), textAnchor="middle"))
        if index < 2:
            drawing.add(Line(x + 52 * mm, 14 * mm, x + 59 * mm, 14 * mm, strokeColor=colors.HexColor(TEAL), strokeWidth=1.1))
            drawing.add(Polygon([x + 59 * mm, 14 * mm, x + 56 * mm, 16 * mm, x + 56 * mm, 12 * mm], fillColor=colors.HexColor(TEAL), strokeColor=None))
    return drawing


def generate_polished_report(output_path: str | Path, inputs: Any) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    regular, _ = _register_cjk_font()
    bold = _bold_font(regular)
    page_w, page_h = A4
    content_w = page_w - 30 * mm

    styles = {
        "cover_tag": ParagraphStyle("cover_tag", fontName=bold, fontSize=8.5, leading=11, textColor=colors.HexColor("#8DDBE2"), alignment=TA_LEFT, spaceAfter=5 * mm),
        "cover_title": ParagraphStyle("cover_title", fontName=bold, fontSize=28, leading=35, textColor=colors.white, alignment=TA_LEFT, spaceAfter=4 * mm),
        "cover_sub": ParagraphStyle("cover_sub", fontName=regular, fontSize=12.2, leading=18, textColor=colors.HexColor("#D7E6EC"), alignment=TA_LEFT),
        "cover_note": ParagraphStyle("cover_note", fontName=regular, fontSize=8.8, leading=14, textColor=colors.HexColor("#D7E6EC")),
        "section_no": ParagraphStyle("section_no", fontName=bold, fontSize=8, leading=10, textColor=colors.HexColor(TEAL), spaceAfter=1 * mm),
        "title": ParagraphStyle("title", fontName=bold, fontSize=20, leading=25, textColor=colors.HexColor(NAVY), spaceAfter=4 * mm),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=11.2, leading=14, textColor=colors.HexColor(TEAL), spaceBefore=3 * mm, spaceAfter=2 * mm),
        "body": ParagraphStyle("body", fontName=regular, fontSize=8.8, leading=14, textColor=colors.HexColor(INK), spaceAfter=2.2 * mm),
        "small": ParagraphStyle("small", fontName=regular, fontSize=7.3, leading=11, textColor=colors.HexColor(MUTED)),
        "table": ParagraphStyle("table", fontName=regular, fontSize=7.3, leading=9.4, textColor=colors.HexColor(INK)),
        "table_head": ParagraphStyle("table_head", fontName=bold, fontSize=7.2, leading=9.2, textColor=colors.white),
        "kpi_value": ParagraphStyle("kpi_value", fontName=bold, fontSize=15, leading=18, textColor=colors.HexColor(NAVY), alignment=TA_CENTER),
        "kpi_label": ParagraphStyle("kpi_label", fontName=regular, fontSize=6.8, leading=9, textColor=colors.HexColor(MUTED), alignment=TA_CENTER),
        "cover_kpi_value": ParagraphStyle("cover_kpi_value", fontName=bold, fontSize=18, leading=21, textColor=colors.white, alignment=TA_CENTER),
        "cover_kpi_label": ParagraphStyle("cover_kpi_label", fontName=regular, fontSize=7.1, leading=9, textColor=colors.HexColor("#BFD8DF"), alignment=TA_CENTER),
        "callout": ParagraphStyle("callout", fontName=regular, fontSize=8.3, leading=13, textColor=colors.HexColor(NAVY)),
    }

    def p(text: Any, style: str = "body") -> Paragraph:
        return Paragraph(str(text).replace("\n", "<br/>"), styles[style])

    def section(number: str, title: str, kicker: str) -> list[Any]:
        return [p(kicker.upper(), "section_no"), p(f"{number}  {title}", "title")]

    def table(rows: Sequence[Sequence[Any]], widths: Sequence[float] | None = None, *, header: bool = True, compact: bool = False) -> Table:
        rendered = [[cell if hasattr(cell, "wrap") else p(cell, "table_head" if header and r_index == 0 else "table") for cell in row] for r_index, row in enumerate(rows)]
        result = Table(rendered, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        commands: list[tuple[Any, ...]] = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3 if compact else 4.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3 if compact else 4.2),
            ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor(LINE)),
        ]
        start = 0
        if header:
            commands.extend([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)), ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(TEAL))])
            start = 1
        for index in range(start, len(rows)):
            commands.append(("BACKGROUND", (0, index), (-1, index), colors.HexColor(WHITE if index % 2 else PALE)))
        result.setStyle(TableStyle(commands))
        return result

    def kpis(items: Sequence[tuple[str, str]], *, cover: bool = False) -> Table:
        cells = [[[p(value, "cover_kpi_value" if cover else "kpi_value"), p(label, "cover_kpi_label" if cover else "kpi_label")]] for value, label in items]
        row = [cell[0] for cell in cells]
        grid = Table([row], colWidths=[content_w / len(items)] * len(items), hAlign="LEFT")
        grid.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(NAVY_2 if cover else PALE)),
            ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#35677B" if cover else LINE)),
            ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#35677B" if cover else LINE)),
            ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]))
        return grid

    def callout(text: str, *, warning: bool = False) -> Table:
        result = Table([[p(text, "callout")]], colWidths=[content_w])
        result.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF1EC" if warning else CYAN)),
            ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor(CORAL if warning else TEAL)),
            ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return result

    config = _load_mapping(inputs.config)
    manifest = _load_mapping(inputs.manifest)
    quality = _load_mapping(inputs.data_quality)
    factors = _load_table(inputs.factor_summary)
    ic_summary = _load_table(inputs.ic_summary)
    strategies = _strategy_table(inputs.strategy_summary)
    experiment = _strategy_table(inputs.experiment_summary)
    liquidity = _load_table(inputs.liquidity_summary)
    audit = _load_mapping(inputs.audit_summary)
    primary = _select_primary_strategy(strategies, config)
    start, end = _nested(config, "data.start", "—"), _nested(config, "data.end", "—")
    assets = _nested(config, "data.assets", []) or []
    buy_fee = _safe_num(_nested(config, "execution.buy_fee", 0.0))
    sell_fee = _safe_num(_nested(config, "execution.sell_fee", 0.0))
    participation = _safe_num(_nested(config, "execution.participation_rate", 0.0))
    primary_return = _metric(strategies, primary, ("cumulative_return", "total_return")) if primary is not None else None
    primary_sharpe = _metric(strategies, primary, ("sharpe_ratio", "sharpe")) if primary is not None else None
    primary_drawdown = _metric(strategies, primary, ("maximum_drawdown", "max_drawdown")) if primary is not None else None

    with tempfile.TemporaryDirectory(prefix=".quantcf-polished-", dir=destination.parent) as temporary:
        temp = Path(temporary)
        charts = _make_charts(inputs, temp)
        equations = {
            "adjustment": _make_math_panel(temp / "eq_adjustment.png", [r"$P^{\mathrm{adj}}_{i,t}=P^{\mathrm{raw}}_{i,t}\,\frac{a_{i,t}}{a_{i,\tau}}$"], line_height=0.62, font_size=20),
            "factors": _make_math_panel(temp / "eq_factors.png", [
                r"$f^{\mathrm{MOM20}}_{i,t}=\frac{C^{\mathrm{adj}}_{i,t}}{C^{\mathrm{adj}}_{i,t-20}}-1$",
                r"$f^{\mathrm{REV5}}_{i,t}=-\left(\frac{C^{\mathrm{adj}}_{i,t}}{C^{\mathrm{adj}}_{i,t-5}}-1\right)$",
                r"$f^{\mathrm{LOWVOL20}}_{i,t}=-\sqrt{\frac{1}{19}\sum_{j=0}^{19}\left(r_{i,t-j}-\bar r_{i,t}\right)^2}$",
                r"$y^{(h)}_{i,t}=\frac{O^{\mathrm{adj}}_{i,t+h+1}}{O^{\mathrm{adj}}_{i,t+1}}-1$",
            ], line_height=0.44, font_size=15.3),
            "diagnostics": _make_math_panel(temp / "eq_diagnostics.png", [
                r"$\mathrm{IC}^{(h)}_t=\mathrm{Corr}_{i\in S_t^{(h)}}\!\left(f_{i,t},y^{(h)}_{i,t}\right)$",
                r"$R^{(h)}_{k,t}=\frac{1}{\left|G_{k,t}\right|}\sum_{i\in G_{k,t}}y^{(h)}_{i,t},\qquad \mathrm{Spread}^{(h)}_t=R^{(h)}_{K,t}-R^{(h)}_{1,t}$",
            ], line_height=0.50, font_size=14.5),
            "ledger": _make_math_panel(temp / "eq_ledger.png", [
                r"$B_t=\sum_{\Delta q_{i,t}>0}\Delta q_{i,t}\,\widetilde O_{i,t},\qquad S_t=\sum_{\Delta q_{i,t}<0}(-\Delta q_{i,t})\,\widetilde O_{i,t}$",
                r"$\mathrm{Fee}_t=c_bB_t+c_sS_t,\qquad \mathrm{Cash}_t=\mathrm{Cash}_{t-1}+S_t-B_t-\mathrm{Fee}_t$",
                r"$q_{i,t}=q_{i,t-1}+\Delta q_{i,t},\qquad W_t=\mathrm{Cash}_t+\sum_i q_{i,t}M_{i,t}$",
                r"$R_t=\frac{W_t}{W_{t-1}}-1$",
            ], line_height=0.46, font_size=13.2),
            "metrics": _make_math_panel(temp / "eq_metrics.png", [
                r"$R_{\mathrm{cum}}=\frac{W_T}{W_0}-1,\qquad R_{\mathrm{ann}}=\left(\frac{W_T}{W_0}\right)^{252/T}-1$",
                r"$\sigma_{\mathrm{ann}}=\sqrt{252}\,\mathrm{Std}(R_t),\qquad \mathrm{Sharpe}=\sqrt{252}\,\frac{\mathrm{Mean}(R_t-r_{f,t})}{\mathrm{Std}(R_t-r_{f,t})}$",
                r"$H_t=\max_{0\leq s\leq t}W_s,\qquad \mathrm{MDD}=\max_t\left(1-\frac{W_t}{H_t}\right)$",
            ], line_height=0.47, font_size=13.2),
            "turnover": _make_math_panel(temp / "eq_turnover.png", [r"$\mathrm{Turnover}_t=\frac{B_t+S_t}{W_t^{-}},\qquad \mathrm{CashCost}=\sum_t\mathrm{Fee}_t$"], line_height=0.60, font_size=17),
        }

        story: list[Any] = []
        story.extend([
            Spacer(1, 20 * mm), p("CF2026 · PROJECT 1 · FINAL RESEARCH REPORT", "cover_tag"),
            p("可复现多因子研究<br/>与下一交易日开盘回测", "cover_title"),
            p("Tushare 中国上市 ETF · 因子诊断 · 严格现金账本 · 执行容量扩展", "cover_sub"), Spacer(1, 13 * mm),
            kpis([(_pct(primary_return), "主策略累计净收益"), (_fmt(primary_sharpe, 3), "主策略年化 Sharpe"), (_pct(primary_drawdown), "主策略最大回撤")], cover=True),
            Spacer(1, 11 * mm), p("研究结论", "cover_tag"),
            p("本项目首先验证信息时序、成交现金流与可复现性，再讨论收益表现。形成日 t 的收盘信息只能影响 t+1 开盘订单；毛收益来自相同信号的零费率独立重跑，而不是机械加回手续费。", "cover_note"),
            Spacer(1, 8 * mm),
            table([["研究区间", f"{start} — {end}"], ["资产与策略", f"{len(assets)} 只 ETF；MOM20 Top 5 月度为预设主策略"], ["验证状态", f"{audit.get('strategies_audited', '—')} 套账本；全部通过：{audit.get('all_passed', '—')}"], ["解释边界", "历史描述结果，不构成投资建议，不宣称独立样本外有效"]], [38 * mm, content_w - 38 * mm], header=False), PageBreak(),
        ])

        story.extend(section("01", "数据契约与研究架构", "Data lineage & system boundary"))
        story.extend([
            kpis([(str(quality.get("clean_rows", quality.get("rows", "—"))), "清洗记录"), (str(len(assets) or quality.get("assets", "—")), "配置资产"), (str(quality.get("calendar_days", "—")), "交易日"), (str(quality.get("missing_grid_cells", "—")), "未填补网格缺口")]),
            p("固定参考日复权", "h2"), p("原始行情与复权因子分开保存。参考日 τ 必须对全部资产存在，缺失时直接失败，不从可变文件末端猜测。"),
            Image(str(equations["adjustment"]), width=content_w, height=23 * mm),
            p("其中 a 为 Tushare 复权因子。相邻总收益由 close_raw × adj_factor 计算；参考日归一化常数会在收益比值中抵消，因此不会把未来值注入历史收益。", "small"),
            p("松耦合流水线", "h2"), _pipeline_drawing(regular),
            table([["数据约束", "本次实现"], ["来源与版本", "Tushare fund_daily + fund_adj；Parquet 快照与 SHA-256 清单"], ["字段单位", "价格：元/份；vol：手（100份）；amount：千元，规范化为人民币元"], ["缺失策略", "不插值、不前填、不补零；缺少开盘价则不成交、不收费"], ["设计借鉴", "Alphalens 诊断、Qlib Recorder、Backtrader Broker/Analyzer 边界"]], [38 * mm, content_w - 38 * mm]), PageBreak(),
        ])

        story.extend(section("02", "因子、可交易标签与统计口径", "Signal definition & information timing"))
        story.extend([
            callout("统一方向：三个因子都定义为“数值越大越优”。全部滚动窗口只读取 t 日收盘及以前数据。"), Spacer(1, 3 * mm),
            Image(str(equations["factors"]), width=content_w, height=72 * mm),
            table([["符号", "严格含义", "实现细节"], ["C_adj / O_adj", "固定参考日复权收盘价 / 开盘价", "因子形成于 t 日收盘"], ["r", "复权收盘的一期收益", "LOWVOL20 使用20个收益、样本标准差 ddof=1"], ["y(h)", "t+1 开盘进入、t+h+1 开盘退出", "仅用于诊断，不进入权重或 Broker"]], [30 * mm, 70 * mm, content_w - 100 * mm]),
            p("IC、Rank IC 与形成时分组", "h2"), Image(str(equations["diagnostics"]), width=content_w, height=35 * mm),
            p("S 是因子和标签同时有效的资产集合；Rank IC 对横截面平均并列秩计算 Pearson 相关，即 Spearman 相关。分组成员 G 在查看未来收益前一次性固定，标签缺失只减少 n_valid，绝不重新分组。", "small"), PageBreak(),
        ])

        story.extend(section("03", "因子诊断：覆盖、IC 与分组收益", "Alphalens-style evidence"))
        coverage_rows = [["因子", "覆盖率", "均值", "标准差", "1%", "中位数", "99%"]]
        for _, row in factors.head(6).iterrows():
            coverage_rows.append([row.get("factor", "—"), _pct(row.get("coverage")), _fmt(row.get("mean"), 4), _fmt(row.get("std"), 4), _fmt(row.get("p01"), 4), _fmt(row.get("p50"), 4), _fmt(row.get("p99"), 4)])
        ic_rows = [["因子", "h", "平均 IC", "平均 Rank IC", "IC IR", "有效日", "平均资产"]]
        for _, row in ic_summary.head(8).iterrows():
            ic_rows.append([row.get("factor", "—"), _fmt(row.get("horizon"), 0), _fmt(row.get("mean_ic"), 4), _fmt(row.get("mean_rank_ic"), 4), _fmt(row.get("ic_ir"), 3), _fmt(row.get("ic_days"), 0), _fmt(row.get("mean_effective_assets"), 1)])
        story.extend([table(coverage_rows, compact=True), Spacer(1, 3 * mm), table(ic_rows, compact=True), Spacer(1, 4 * mm), Image(str(charts["diagnostics"]), width=content_w, height=67 * mm) if "diagnostics" in charts else p("诊断图未生成。", "small"), callout("读取方式：IC 是横截面相关，不是收益率；Rank IC 也不是预测正确率。五日标签重叠，因此结果用于排序诊断，不直接拼成策略净值。", warning=True), PageBreak()])

        story.extend(section("04", "下一开盘执行与现金账本", "Backtest correctness before performance"))
        story.extend([
            _timeline_drawing(regular), p("账本变量与恒等式", "h2"),
            p("Δq 是实际成交的带符号份额；Õ 是应用滑点后的实际成交价；B、S 分别为买入和卖出成交额；M 是当日允许使用的收盘标记价。"),
            Image(str(equations["ledger"]), width=content_w, height=60 * mm),
            table([["风险点", "强制规则"], ["前视偏差", "signal_date=t，execution_date 必须是日历中的下一交易日"], ["缺失开盘", "订单拒绝；成交份额、成交金额和手续费全部为0"], ["现金与卖空", "先卖后买；买单按可用现金同比缩放；现金和份额均不得为负"], ["估值缺失", "新仓当日可用成交开盘价；之后只允许有限天数的最近收盘价"], ["容量", f"仅用成交日前已完成的 {int(_nested(config, 'execution.adv_window', 20))} 日平均成交额 × {_pct(participation)}"], ["费用", f"买入 {_pct(buy_fee)}、卖出 {_pct(sell_fee)}；只对实际成交额收费"]], [34 * mm, content_w - 34 * mm], compact=True),
            Spacer(1, 3 * mm), callout(f"独立审计：{audit.get('strategies_audited', '—')} 套净/毛账本，全部通过={audit.get('all_passed', '—')}；最大账本误差={audit.get('maximum_accounting_error', '—')}；时序违规={audit.get('timing_violations', '—')}。"), PageBreak(),
        ])

        story.extend(section("05", "绩效、风险与成本", "Audited net performance"))
        perf_rows = [["策略", "累计净收益", "年化收益", "年化波动", "Sharpe", "最大回撤", "现金费用"]]
        for _, row in strategies.head(8).iterrows():
            perf_rows.append([_strategy_label(row.get("strategy", "—")), _pct(row.get("cumulative_return")), _pct(row.get("annualized_return")), _pct(row.get("annualized_volatility")), _fmt(row.get("sharpe_ratio"), 3), _pct(row.get("maximum_drawdown")), f"{_safe_num(row.get('total_transaction_cost')):,.0f}"])
        story.extend([
            table(perf_rows, [39 * mm, 24 * mm, 23 * mm, 23 * mm, 18 * mm, 22 * mm, content_w - 149 * mm], compact=True), Spacer(1, 3 * mm),
            Image(str(charts["performance"]), width=content_w, height=77 * mm) if "performance" in charts else p("净值图未生成。", "small"),
            p("指标定义", "h2"), Image(str(equations["metrics"]), width=content_w, height=46 * mm),
            p("T 为实际交易日数；年化常数 A=252。最大回撤把初始资金 W0 作为第一个高水位，因此不会遗漏首日交易成本造成的回撤。", "small"), PageBreak(),
        ])

        story.extend(section("06", "调仓频率与流动性拓展", "Controlled experiment & capacity"))
        exp_rows = [["方案", "累计净收益", "Sharpe", "年化换手", "现金费用", "成交率"]]
        for _, row in experiment.head(4).iterrows():
            exp_rows.append([_strategy_label(row.get("strategy", "—")), _pct(row.get("cumulative_return")), _fmt(row.get("sharpe_ratio"), 3), _fmt(row.get("annualized_turnover"), 2), f"{_safe_num(row.get('total_transaction_cost')):,.0f}", _pct(row.get("aggregate_fill_ratio"))])
        limited_return = liquidity.iloc[0].get("limited_cumulative_return") if not liquidity.empty else None
        unlimited_return = liquidity.iloc[0].get("unlimited_cumulative_return") if not liquidity.empty else None
        limited_fill = liquidity.iloc[0].get("limited_fill_ratio") if not liquidity.empty else None
        story.extend([
            p("控制实验：只改变调仓频率", "h2"), p("资产池、因子、Top 5、费用、执行时点与权重规则保持一致；月度和周度的主要设计差异只有调仓频率。"), table(exp_rows, compact=True), Spacer(1, 4 * mm),
            Image(str(charts["experiments"]), width=content_w, height=55 * mm) if "experiments" in charts else p("实验图未生成。", "small"),
            kpis([(_pct(unlimited_return), "周度无限容量收益"), (_pct(limited_return), "周度容量受限收益"), (_pct(limited_fill), "容量受限成交率")]),
            p("换手与现金成本", "h2"), Image(str(equations["turnover"]), width=content_w, height=22 * mm),
            callout("容量限制只使用执行日前可得的历史成交额。未成交部分当日取消、不收费；因此受限策略会保留旧仓位，不能把它解释为简单缩小版的无限容量策略。"), PageBreak(),
        ])

        story.extend(section("07", "复现证据、局限与结论", "Audit trail & interpretation boundary"))
        hashes = manifest.get("hashes", {}) if isinstance(manifest.get("hashes"), Mapping) else {}
        hash_rows = [["复现对象", "SHA-256（前16位）"]]
        for key in ("config_sha256", "data_sha256", "source_sha256", "environment_sha256"):
            if key in hashes:
                hash_rows.append([key, str(hashes[key])[:16] + "…"])
        story.extend([
            kpis([("PASS" if audit.get("all_passed") else "FAIL", "账本审计"), (str(audit.get("strategies_audited", "—")), "净/毛账本数"), (str(audit.get("timing_violations", "—")), "时序违规"), (str(audit.get("capacity_violations", "—")), "容量违规")]),
            p("可复现记录", "h2"), table(hash_rows, [48 * mm, content_w - 48 * mm], compact=True),
            p(f"Run ID：{manifest.get('run_id', '—')}　·　实验指纹：{str(manifest.get('experiment_fingerprint', '—'))[:24]}…", "small"), p("必须保留的解释边界", "h2"),
        ])
        for index, item in enumerate(list(inputs.limitations or [])[:5], start=1):
            story.append(p(f"<b>{index}.</b> {item}", "small"))
        story.extend([Spacer(1, 2 * mm), callout("结论：这是一套以正确性和证据链为先的课程研究系统。历史收益只能说明固定样本与假设下的回放结果；下一步应优先引入动态资产池、真实停牌/涨跌停、最小交易单位和预先冻结的验证期。", warning=True), p("资料来源与设计借鉴", "h2")])
        for index, item in enumerate(list(inputs.source_notes or [])[:6], start=1):
            story.append(p(f"[{index}] {item}", "small"))

        def page_decor(canvas: Any, document: Any) -> None:
            canvas.saveState()
            if document.page == 1:
                canvas.setFillColor(colors.HexColor(NAVY)); canvas.rect(0, 0, page_w, page_h, stroke=0, fill=1)
                canvas.setStrokeColor(colors.HexColor("#35677B")); canvas.line(15 * mm, 14 * mm, page_w - 15 * mm, 14 * mm)
                canvas.setFillColor(colors.HexColor("#BFD8DF")); canvas.setFont(regular, 7.2)
                canvas.drawString(15 * mm, 9 * mm, "CF2026 · COMPUTATIONAL FINANCE · PROJECT 1"); canvas.drawRightString(page_w - 15 * mm, 9 * mm, "01 / 08")
            else:
                canvas.setFillColor(colors.HexColor(NAVY)); canvas.rect(0, page_h - 7 * mm, page_w, 7 * mm, stroke=0, fill=1)
                canvas.setFillColor(colors.HexColor(TEAL)); canvas.rect(0, page_h - 8.2 * mm, page_w, 1.2 * mm, stroke=0, fill=1)
                canvas.setStrokeColor(colors.HexColor(LINE)); canvas.line(15 * mm, 13 * mm, page_w - 15 * mm, 13 * mm)
                canvas.setFont(regular, 7.0); canvas.setFillColor(colors.HexColor(MUTED))
                canvas.drawString(15 * mm, 8.5 * mm, "CF2026 · 可复现因子研究与下一交易日开盘回测"); canvas.drawRightString(page_w - 15 * mm, 8.5 * mm, f"{document.page:02d} / 08")
            canvas.restoreState()

        document = SimpleDocTemplate(str(destination), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=17 * mm, title="CF2026 Project 1 - Reproducible Factor Research", author="CF2026 Project Team", subject="Audited Tushare ETF factor research and next-open backtest")
        document.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
        page_count = int(getattr(document, "page", 0))

    if page_count != 8:
        raise RuntimeError(f"polished report has {page_count} pages; expected exactly 8")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("polished report generation produced no PDF")
    return destination


__all__ = ["generate_polished_report"]
