"""Static report figures. Light surface, validated categorical palette, no dual axes."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter, MaxNLocator
import numpy as np
import pandas as pd

# Reference categorical palette (validated light mode). Slots in fixed order.
BLUE, ORANGE, AQUA, YELLOW = '#2a78d6', '#eb6834', '#1baf7a', '#eda100'
INK, INK2, MUTED = '#0b0b0b', '#52514e', '#898781'
GRID, AXIS, SURFACE = '#e1e0d9', '#c3c2b7', '#fcfcfb'
ORDINAL = ['#86b6ef', '#2a78d6', '#184f95']

plt.rcParams.update({
    'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE,
    'savefig.facecolor': SURFACE, 'font.size': 9,
    'axes.edgecolor': AXIS, 'axes.labelcolor': INK2,
    'xtick.color': MUTED, 'ytick.color': MUTED,
    'text.color': INK, 'axes.titlecolor': INK,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6,
    'grid.linestyle': '-', 'axes.axisbelow': True,
    'legend.frameon': False, 'figure.dpi': 150,
})


def _label_end(ax, x, y, text):
    ax.annotate(text, xy=(x, y), xytext=(5, 0), textcoords='offset points',
                va='center', fontsize=8, color=INK2, clip_on=False)


def _label_ends(ax, entries, min_gap_frac=0.09):
    """Direct-label several line ends without collisions.

    entries: list of (x, y, text). Labels are pushed apart vertically in data
    coordinates; a hairline leader connects each label to its true endpoint.
    """
    finite = [e for e in entries if np.isfinite(e[1])]
    if not finite:
        return
    ymin = min(e[1] for e in finite)
    ymax = max(e[1] for e in finite)
    span = max(ymax - ymin, 1e-12)
    # A small floor keeps labels apart when all series end near the same value.
    gap = max(span * min_gap_frac, 0.04)
    items = sorted(finite, key=lambda e: e[1])
    ys = [e[1] for e in items]
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + gap)
    top = max(ymax, ys[-1])
    shift = max(0.0, top - (ymax + span * 0.04))
    ys = [y - shift for y in ys]
    for (x, y0, text), y in zip(items, ys):
        if abs(y - y0) > 1e-12:
            ax.plot([x, x], [y0, y], color=AXIS, lw=0.7, clip_on=False)
        ax.annotate(text, xy=(x, y), xytext=(5, 0), textcoords='offset points',
                    va='center', fontsize=8, color=INK2, clip_on=False)


def _caption(fig, text):
    fig.text(0.01, 0.005, text, fontsize=7.5, color=MUTED, ha='left', va='bottom')


def nav_plot(series, out):
    """series: ordered dict name -> (x, y, color). All indexed to 1 at start."""
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ends = []
    for name, (x, y, color) in series.items():
        ax.plot(x, y, color=color, lw=1.6, label=name)
        ends.append((x.iloc[-1], float(y.iloc[-1]), f'{name}  {y.iloc[-1]:.2f}x'))
    ax.axhline(1, color=AXIS, lw=0.8)
    ax.set_ylabel('Growth of $1')
    ax.set_title('TSMOM and benchmark, net of 10 bp per side')
    ax.legend(loc='upper left', fontsize=8, ncol=2)
    ax.margins(x=0.18)
    _label_ends(ax, ends)
    fig.tight_layout(rect=[0, 0.035, 1, 1])
    _caption(fig, 'Daily NAV, initial = 1. Gross rerun uses zero fees. Source: fixed nine-ETF snapshot, 2000-2024.')
    fig.savefig(out / 'nav.png', bbox_inches='tight')
    plt.close(fig)


def gross_net_plot(net, gross, out):
    fig, ax = plt.subplots(figsize=(9, 4.0))
    for df, label, color in [(gross, 'Gross (0 bp)', ORANGE), (net, 'Net (10 bp)', BLUE)]:
        ax.plot(df.date, df.nav, color=color, lw=1.5, label=label)
        _label_end(ax, df.date.iloc[-1], df.nav.iloc[-1], label)
    ax.set_ylabel('Growth of $1')
    ax.set_title('Diversified TSMOM: gross vs net')
    ax.legend(loc='upper left', fontsize=8)
    ax.margins(x=0.16)
    fig.tight_layout(rect=[0, 0.035, 1, 1])
    _caption(fig, 'Independent zero-fee rerun; positions can differ because reinvested capital differs.')
    fig.savefig(out / 'gross_net.png', bbox_inches='tight')
    plt.close(fig)


def predictability_plot(pred, out, horizon=12):
    d = pred[(pred.scope == 'asset') & (pred.horizon_months == horizon)].copy()
    d = d.sort_values('beta').reset_index(drop=True)
    se = np.where(d.t_beta.abs() > 0, d.beta.abs() / d.t_beta.abs(), np.nan)
    ypos = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.barh(ypos, d.beta, color=BLUE, height=0.62, label='Per-asset beta')
    ax.errorbar(d.beta, ypos, xerr=1.96 * se, fmt='none', ecolor=INK2, elinewidth=1, capsize=3)
    ax.axvline(0, color=AXIS, lw=0.9)
    ax.set_yticks(ypos, d.asset)
    for y, (b, n) in enumerate(zip(d.beta, d.n)):
        ax.text(b + (0.02 if b >= 0 else -0.02), y, f'{b:+.3f}', va='center',
                ha='left' if b >= 0 else 'right', fontsize=7.5, color=INK2)
    pooled = pred[(pred.scope == 'pooled') & (pred.horizon_months == horizon)]
    subtitle = ''
    if len(pooled):
        p = pooled.iloc[0]
        subtitle = f'Pooled FE beta = {p.beta:+.4f} (t = {p.t_beta:.2f}, N = {int(p.n)})'
    ax.set_xlabel('Beta of next-month return on sign of trailing 12-month return')
    ax.set_title('Time-series predictability by sector ETF\n' + subtitle, fontsize=10)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=3))
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    ax.grid(axis='y', visible=False)
    fig.tight_layout(rect=[0, 0.035, 1, 1])
    _caption(fig, 'Bars: per-asset OLS with Newey-West lag 12; whiskers: 95% HAC interval.')
    fig.savefig(out / 'predictability.png', bbox_inches='tight')
    plt.close(fig)


def extreme_plot(ext, out):
    keep = ext[ext.bin.isin(['bottom_10pct', 'middle_80pct', 'top_10pct'])].copy()
    order = ['bottom_10pct', 'middle_80pct', 'top_10pct']
    keep['bin'] = pd.Categorical(keep.bin, order, ordered=True)
    keep = keep.sort_values('bin')
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    bars = ax.bar(keep.bin, keep.mean_tsmom * 100, color=ORDINAL, width=0.62, label='Mean TSMOM return')
    for bar, v, n in zip(bars, keep.mean_tsmom * 100, keep.months):
        if v >= 0:
            ax.text(bar.get_x() + bar.get_width() / 2, v + 0.06,
                    f'{v:+.2f}%  (n={n})', ha='center', va='bottom', fontsize=8, color=INK2)
        else:
            # Inside the bar near zero: avoids a collision with the x tick label.
            ax.text(bar.get_x() + bar.get_width() / 2, -0.06,
                    f'{v:+.2f}%  (n={n})', ha='center', va='top', fontsize=8, color='white')
    ax.axhline(0, color=AXIS, lw=0.9)
    ax.set_ylabel('Mean monthly return (%)')
    ax.set_title('Diversified TSMOM in extreme market months')
    ax.grid(axis='x', visible=False)
    fig.tight_layout(rect=[0, 0.035, 1, 1])
    _caption(fig, 'Market = equal-weight nine ETFs. Bins use the 10th/90th percentile of monthly market return.')
    fig.savefig(out / 'extreme.png', bbox_inches='tight')
    plt.close(fig)


def lookback_plot(sens, out):
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    x = np.arange(len(sens))
    w = 0.36
    ax.bar(x - w / 2, sens.gross_sharpe, width=w, color=ORANGE, label='Gross Sharpe')
    ax.bar(x + w / 2, sens.net_sharpe, width=w, color=BLUE, label='Net Sharpe (10 bp)')
    for xi, g, n in zip(x, sens.gross_sharpe, sens.net_sharpe):
        ax.text(xi - w / 2, g + 0.015, f'{g:.2f}', ha='center', va='bottom', fontsize=7.5, color=INK2)
        ax.text(xi + w / 2, n + 0.015, f'{n:.2f}', ha='center', va='bottom', fontsize=7.5, color=INK2)
    ax.set_xticks(x, [f'{h}m' for h in sens.lookback_months])
    ax.set_xlabel('Look-back horizon')
    ax.set_ylabel('Annualized Sharpe ratio')
    ax.set_title('Sensitivity to look-back horizon')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(axis='x', visible=False)
    fig.tight_layout(rect=[0, 0.035, 1, 1])
    _caption(fig, 'Same 40% per-asset volatility target, 10 bp per side except the gross bar.')
    fig.savefig(out / 'sensitivity_lookback.png', bbox_inches='tight')
    plt.close(fig)


def cost_plot(cost, out):
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    ax.plot(cost.cost_bps, cost.sharpe, color=BLUE, lw=1.8, marker='o', ms=6,
            label='Net Sharpe')
    for x, y in zip(cost.cost_bps, cost.sharpe):
        ax.annotate(f'{y:.2f}', (x, y), xytext=(0, 8), textcoords='offset points',
                    ha='center', fontsize=7.5, color=INK2)
    ax.set_xlabel('Transaction cost (bp per side)')
    ax.set_ylabel('Annualized Sharpe ratio')
    ax.set_title('Net Sharpe vs transaction cost')
    ax.legend(loc='lower left', fontsize=8)
    fig.tight_layout(rect=[0, 0.035, 1, 1])
    _caption(fig, 'Fees are charged on executed notional; financing and borrow costs are excluded.')
    fig.savefig(out / 'sensitivity_cost.png', bbox_inches='tight')
    plt.close(fig)


def exposure_plot(daily, out):
    # Show the target exposure set at each monthly rebalance; daily marks would
    # draw a crowded sawtooth and obscure the regime changes.
    reb = daily[daily.rebalance].copy()
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.fill_between(reb.date, 0, reb.gross_exposure, color=BLUE, alpha=0.12,
                    linewidth=0, label='_nolegend_')
    ax.plot(reb.date, reb.gross_exposure, color=BLUE, lw=1.1, label='Gross exposure')
    ax.plot(reb.date, reb.net_exposure, color=ORANGE, lw=1.3, label='Net exposure')
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_ylabel('Fraction of NAV')
    ax.set_title('Diversified TSMOM exposures at monthly rebalance')
    ax.legend(loc='upper left', fontsize=8)
    ax.margins(x=0.06)
    fig.tight_layout(rect=[0, 0.035, 1, 1])
    _caption(fig, 'Gross = sum of absolute target weights; net = signed sum. Targets set at month-end, executed next open.')
    fig.savefig(out / 'exposure.png', bbox_inches='tight')
    plt.close(fig)


def architecture_plot(out):
    fig, ax = plt.subplots(figsize=(9, 2.4))
    ax.axis('off')
    boxes = ['Fixed ETF snapshot\nSHA-256', 'P1 validation\n+ price panel',
             'Monthly signals\nsign(r t-h,t)', 'EWMA vol\n+ 1/N scaling',
             'Signed ledger\nopen t+1, 10 bp', 'HAC tests\n+ report']
    n = len(boxes)
    for i, text in enumerate(boxes):
        x = 0.012 + i * (0.98 / n)
        ax.text(x + 0.075, 0.52, text, ha='center', va='center', fontsize=8,
                color=INK2, bbox=dict(boxstyle='round,pad=0.6', fc='#eaf2fb', ec=BLUE, lw=0.9),
                transform=ax.transAxes)
        if i < n - 1:
            ax.annotate('', xy=(x + 0.155, 0.52), xytext=(x + 0.135, 0.52),
                        xycoords='axes fraction',
                        arrowprops=dict(arrowstyle='->', color=BLUE, lw=1.1))
    fig.tight_layout()
    fig.savefig(out / 'architecture.png', bbox_inches='tight')
    plt.close(fig)
