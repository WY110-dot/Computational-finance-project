"""Data-driven Chinese submission report. No manually copied performance data."""
from pathlib import Path
import json
from html import escape
import numpy as np
import pandas as pd
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether

NAVY=colors.HexColor('#123B4A'); TEAL=colors.HexColor('#17677B'); GOLD=colors.HexColor('#BC8736')
def pct(v): return f'{float(v)*100:.2f}%'
def num(v): return f'{float(v):.3f}'


def build_report(root, out):
    root,out=Path(root),Path(out)
    dest=out/'report'; dest.mkdir(parents=True,exist_ok=True)
    font='Chinese'
    try:
        pdfmetrics.registerFont(TTFont(font,'C:/Windows/Fonts/msyh.ttc',subfontIndex=0))
    except Exception:
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light')); font='STSong-Light'
    styles={
        'body':ParagraphStyle('body',fontName=font,fontSize=9.5,leading=16,textColor=NAVY,spaceAfter=9,wordWrap='CJK'),
        'small':ParagraphStyle('small',fontName=font,fontSize=8,leading=12,textColor=NAVY,spaceAfter=6,wordWrap='CJK'),
        'title':ParagraphStyle('title',fontName=font,fontSize=25,leading=36,textColor=NAVY,spaceAfter=20,wordWrap='CJK'),
        'h1':ParagraphStyle('h1',fontName=font,fontSize=18,leading=26,textColor=NAVY,spaceAfter=15,wordWrap='CJK'),
        'h2':ParagraphStyle('h2',fontName=font,fontSize=11.5,leading=19,textColor=TEAL,spaceBefore=8,spaceAfter=8,wordWrap='CJK'),
        'cell':ParagraphStyle('cell',fontName=font,fontSize=8,leading=12,textColor=NAVY,wordWrap='CJK'),
    }
    story=[]; md=[]
    def p(text,style='body'):
        story.append(Paragraph(escape(text).replace('\n','<br/>'),styles[style])); md.append(text+'\n')
    def title(text):
        if story: story.append(PageBreak())
        story.append(Paragraph(escape(text),styles['h1'])); md.append('\n## '+text+'\n')
    def table(headers,rows,widths=None):
        cells=[[Paragraph(escape(str(x)),styles['cell']) for x in row] for row in [headers]+rows]
        t=Table(cells,colWidths=widths or [490/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E4EEF0')),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),
            ('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F5F8F8')]),
            ('LINEBELOW',(0,0),(-1,0),.7,TEAL),('LINEBELOW',(0,-1),(-1,-1),.4,colors.HexColor('#C8D6DA'))]))
        story.extend([t,Spacer(1,10)])
        md.append('| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n')
    def image(path,width=490,maxheight=235,caption=''):
        if not path.exists(): raise FileNotFoundError(path)
        from PIL import Image as PILImage
        w,h=PILImage.open(path).size
        factor=min(width/w,maxheight/h)
        story.append(Image(str(path),width=w*factor,height=h*factor,hAlign='CENTER'))
        if caption: p(caption,'small')
        md.append(f'![{caption}]({path.relative_to(out).as_posix() if path.is_relative_to(out) else "../../references/"+path.name})\n')
    summary=pd.read_csv(out/'integration/unified_summary.csv')
    base=pd.read_csv(out/'strategy_summary.csv').set_index('strategy_id')
    boot=pd.read_csv(out/'integration/paired_bootstrap.csv')
    bridge=pd.read_csv(out/'integration/bridge_summary.csv')
    funding=pd.read_csv(out/'integration/funding_sensitivity.csv')
    alpha=pd.read_csv(out/'integration/benchmark_alpha.csv')
    reg=pd.read_csv(out/'integration/predictive_regressions.csv')
    single=pd.read_csv(out/'research/R1_single_asset_metrics.csv')
    classes=pd.read_csv(out/'research/asset_class_variance_decomposition.csv')
    r=summary[(summary.universe=='CN21')&(summary['sample']=='full')].set_index('strategy')
    aq=pd.read_csv(out/'reference/aqr_tsmom_original_paper_factors.csv').TSMOM
    aq_sr=aq.mean()/aq.std(ddof=1)*np.sqrt(12)
    execution=pd.read_csv(out/'integration/execution_monthly_returns.csv',index_col=0,parse_dates=True)
    es=execution.mean()/execution.std(ddof=1)*np.sqrt(12)
    positive=int((single.sharpe>0).sum())
    facts={'authors':['杨皓博','袁思扬','缪梓航'],'aqr_sharpe':float(aq_sr),'single_positive':positive,
        'cn_r1_sharpe':float(r.loc['tsmom12','sharpe']),'cn_passive_sharpe':float(r.loc['passive_long','sharpe']),
        'execution_monthly_sharpe':es.to_dict()}
    (dest/'report_facts.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding='utf-8')
    trace=[]
    for source,frame,section in [
        ('integration/unified_summary.csv',summary,'03/04/07'),
        ('integration/paired_bootstrap.csv',boot,'07'),
        ('integration/bridge_summary.csv',bridge,'06'),
        ('integration/funding_sensitivity.csv',funding,'05'),
        ('research/asset_class_variance_decomposition.csv',classes,'05'),
        ('strategy_summary.csv',base.reset_index(),'06')]:
        for index,row in frame.iterrows():
            for field in frame.select_dtypes(include='number').columns:
                value=row[field]
                if pd.notna(value):
                    trace.append({'report_section':section,'source_file':'outputs/'+source,
                        'zero_based_row':index,'column':field,'unrounded_value':value})
    pd.DataFrame(trace).to_csv(dest/'report_trace.csv',index=False)

    p('CF2026  /  PROJECT 02  /  2026.10.29','small')
    p('时间序列动量\n在 ETF 替代样本中的复现','title')
    p('资产池、交易约束与多期限信号的受控检验','h2')
    p('杨皓博 · 袁思扬 · 缪梓航\n计算金融课程 Project 2 | 小组整合提交版')
    story.append(Spacer(1,12))
    p('研究结论','h2')
    p(f'在 21 只国内及跨境 ETF 的 79 个月样本中，12M TSMOM 的月频 Sharpe 为 {num(r.loc["tsmom12","sharpe"])}，低于同风险预算被动多头的 {num(r.loc["passive_long","sharpe"])}。在 9 只美国行业 ETF 的长样本中也未观察到稳定的相对优势。我们实现并核验了核心方法，但不将替代样本表现表述为原文数值复现成功。')
    table(['证据层','主要发现'],[
        ['原方法核对','主策略为 12 个月回看、1 个月持有；跨资产分散，不是 1/3/12 月平均。'],
        ['交易约束','删除空头、规范杠杆预算、次日开盘及费用分别桥接；不混同风险缩放与信号增益。'],
        ['自主扩展','3/6/12 月组合降低部分风险，但收益、换手与统计不确定性构成明显权衡。'],
        ['复现实验','统一两个资产池、统一月频评价、报告同事前风险对照与配对分块 bootstrap。']], [90,400])
    p('范围说明：本研究是 ETF 方法迁移与适用边界检验，不是对 58 个全球期货/远期的完整重建。所有绩效由随包快照与代码计算；参考序列复算与自主 ETF 实验严格分开。','small')

    title('01  研究目标与原文对应')
    p('Moskowitz、Ooi 与 Pedersen（2012）研究跨资产时间序列动量。本文将原文第 236 页 Eq. (5)、Fig. 2 上部和 Fig. 3 作为主要实现与对照目标。课程要求强调方法、核验和差异解释，因此我们保留未改善和未重现相对优势的结果。')
    table(['原文对象','本次对应','比较边界'],[
        ['Eq. (5)，p.236','12M 符号 × 40%/事前波动率 × 下月收益；资产间 1/N 平均','ETF 调整价收益代理期货超额收益'],
        ['Fig. 2 上部，p.237','逐资产 TSMOM Sharpe 分布','正 Sharpe 不等于显著预测能力'],
        ['Fig. 3，p.239','TSMOM 与同风险预算被动多头累计财富','不编造未提供的原文被动多头序列'],
        ['Eq. (3)，p.233','单个滞后月符号与波动率标准化收益回归','ETF 代理诊断；月份聚类，非 HAC'],
        ['Fig. 4，p.239','完整非重叠季度与市场代理散点','本包使用被动 ETF 代理，非原文 S&P 500']],[105,200,185])
    p(f'原文图中单资产均为正收益、52/58 在 5% 水平显著。本次 CN21 中 {positive}/{len(single)} 只资产 Sharpe 为正，不能据此认定相同显著性。AQR 已保存因子序列为 1985-01 至 2009-12 共 {len(aq)} 个月，独立复算算术年化均值 {pct(12*aq.mean())}、波动率 {pct(np.sqrt(12)*aq.std())}、Sharpe {num(aq_sr)}。此数是参考序列计算结果，不是从论文 Table 2 读出的 Sharpe。')
    image(out/'figures/original_replication_targets.png',maxheight=285,caption='原/新目标并排：左侧原文 Fig. 2 上部与 Fig. 3（刊发页 237、239）；右侧 CN21 自主计算。资产、区间与收益定义不同，只作标明边界的方向及排序比较。')

    title('02  方法、信息集与 P1 平台接入')
    p('形成日 t 的收盘后，按可得历史数据确定合格资产集合 E_t。12 个月内 13 个连续月末价格和至少 252 个连续日收益可用，才允许进入形成时集合；N_t 不依赖未来收益是否缺失。缺少持有期收益会显式报错，不能静默缩小分母或填零。')
    p('s(i,t) = sign[P(i,t) / P(i,t-12) - 1]\nw(i,t) = (1/N_t) × s(i,t) × 0.40 / σ(i,t)\nR(t+1) = Σ_i w(i,t) × r(i,t+1)\nEWMA 方差：λ = 60/61；有限历史归一化加权均值与方差；σ² = 261 × 加权日方差。','h2')
    p('理论研究层：月末到月末收益、允许有符号和杠杆头寸，原始基线不额外做 12% 组合波动目标。执行层：P1 Broker 次日开盘交易，持仓与现金非负、99% 风险预算上限、按实际成交扣单边 3 bp；零成本和 10 bp 为费用对照。分数份额和无滑点为显式简化。')
    table(['模块','复用与新增'],[
        ['data / backtest / recorder','复用 P1 复权校验、次日开盘 Broker、订单/成交/持仓/现金账本和哈希记录。'],
        ['tsmom / research_backtest','袁思扬分支新增的月末信号、合格性与多空研究回测保留为基线。'],
        ['integration','整合主分支统计诊断思路并校正；新增 US9 适配、共同区间、风险对齐、融资与 bootstrap。'],
        ['final_report / verify_final','统一读取运行表格生成中文报告；独立目录重跑比对、执行审计与打包校验。']],[130,360])
    p('研究设计为回顾性：两位组员已查看过这些历史结果，本文不声称预注册或完全未见样本外。新扩展参数在 config/integration.json 固定，并完整报告，不按最大历史 Sharpe 选择赢家。','small')

    title('03  数据、样本与可比性')
    table(['样本','来源与区间','主要差异'],[
        ['CN21','Tushare 原始价与复权因子快照；2020-02 至 2026-08，79 个持有月','21 只中国上市 ETF；债券、黄金、境内与跨境权益；动态合格数。'],
        ['US9','组员提供的公开仓库 Yahoo 格式调整 OHLC；2000-01 至 2024-12，300 月','9 只 SPDR 行业 ETF；单一股票资产大类；原始 CSV SHA-256 逐一验证。'],
        ['共同区间','2020-02 至 2024-12，59 个月','固定日期与方法；资产结构、货币、交易日历仍不同。'],
        ['AQR 参考','Original Paper Data，本地 XLSX 固定快照；1985–2009','只用于参考指标复算，不进入 ETF 信号、调参或持仓。']],[75,215,200])
    p('CN21 原始价格和复权因子分开保存，形成调整价与可交易原始价；US9 已调整 OHLC 的上游加工不完全可重建，保留来源限制。US9 的 Dividends 等列不再另加到调整价收益，避免重复计算。CN21 的复权因子也不另造分红现金流。')
    p('共同区间结果（月频 gross；同一 12M 实现）','h2')
    common=summary[(summary['sample']=='common')&summary.strategy.isin(['tsmom12','passive_long'])]
    table(['资产池 / 策略','算术年化','波动率','Sharpe','最大月回撤'],[
        [f'{z.universe} / '+('12M' if z.strategy=='tsmom12' else 'Passive'),pct(z.ann_mean),pct(z.ann_vol),num(z.sharpe),pct(z.max_drawdown)] for z in common.itertuples()],[140,90,85,80,95])
    p('共同区间内两个资产池的 12M 均低于对应被动多头；这支持“结果依赖样本和资产池”的描述，不能在两个观测组合上识别纯粹的跨资产分散因果效应。跨境 ETF 仍可能受汇率、溢折价与本地交易时段影响。','small')

    title('04  核心复现：组合与逐资产结果')
    full=summary[(summary['sample']=='full')&summary.strategy.isin(['tsmom12','passive_long','multi_horizon'])]
    table(['资产池 / 策略','算术年化','CAGR','Sharpe','月回撤'],[
        [z.universe+' / '+{'tsmom12':'12M','passive_long':'Passive','multi_horizon':'Multi'}[z.strategy],pct(z.ann_mean),pct(z.cagr),num(z.sharpe),pct(z.max_drawdown)] for z in full.itertuples()],[140,90,85,80,95])
    image(out/'figures/unified_nav.png',maxheight=205,caption='图 1：两个资产池的完整持有期累计财富。按月收益复利，起始资本 1；两边时间跨度不同。')
    p(f'CN21 中 {positive}/{len(single)} 个单资产 Sharpe 为正，原始资产数不等于每月合格资产数。债券与黄金对收益有较大贡献；总体 12M 虽为正收益，却未超过同逆波动风险预算的被动组合。US9 同样未稳定优于被动多头。因此结论限于替代样本，既不宣称原文被推翻，也不把正收益本身当成独立的择时增益。')

    title('05  资产贡献与资金成本敏感性')
    table(['资产大类','年化收益贡献','总方差贡献占比'],[
        [z.asset_class,pct(z.ann_mean_return_contribution),pct(z.variance_contribution_ratio)] for z in classes.itertuples()],[180,155,155])
    p('贡献以原始 R1 权重固定分解：类别月度收益贡献之和等于组合月收益，类别协方差 Cov(R_c,R)/Var(R) 之和等于 1。固定权重移除是暴露归因，不是重新优化的可交易替代策略；移除效果存在协方差交互，不应机械相加。')
    p(f'R1 平均总暴露为 {r.loc["tsmom12","mean_gross"]:.2f} 倍，长期资产现金收益被杠杆放大；删除空头后的 Bridge 仍有 {r.loc["long_only_bridge","mean_gross"]:.2f} 倍总暴露，不能称为无杠杆实盘。低波资产的名义权重与资金成本必须同时披露。')
    table(['融资年费率','算术年化','月频 Sharpe','最大月回撤'],[
        [pct(z.funding_rate),pct(z.ann_mean),num(z.sharpe),pct(z.max_drawdown)] for z in funding.itertuples()],[115,125,125,125])
    p('敏感性按 max(net exposure - 1, 0) × 年费率 / 12 扣资金成本；保留原始形成日权重，不建模每日保证金、借券费、短仓抵押折扣、现金利息或再投资反馈。它是有明确方向的融资压力测试，不是券商账户净收益估计。资金成本越高，该杠杆 ETF 代理收益越弱。','small')

    title('06  逐步桥接交易约束')
    labels=['原始多空研究','仅删除空头','归一化 99% 预算','次日开盘，0 bp','次日开盘，3 bp']
    table(['桥接阶段','算术年化','月频 Sharpe','最大月回撤'],[
        [labels[i],pct(z.ann_mean),num(z.sharpe),pct(z.max_drawdown)] for i,z in enumerate(bridge.itertuples())],[175,105,105,105])
    p('B0→B1：将负信号权重置零，资产集合、原始 1/N 和 40%/σ 尺度不变。B1→B2：所有合格资产逆波动预算归一到 99%，负信号对应预算留在现金。B2→B3：切到 P1 次日开盘与日频账本，包含权重漂移、原始价/复权账本机制等执行约定；此步是执行层整体桥接，不声称只识别开盘价一个因素。B3→B4：仅增加实际成交费率 3 bp。')
    p('日频指标和月频指标为什么不能混用','h2')
    table(['执行策略','日频 Sharpe','月频 Sharpe','日频最大回撤'],[
        [label,num(base.loc[key,'sharpe']),num(es[col]),pct(base.loc[key,'max_drawdown'])]
        for label,key,col in [('12M','T1_tsmom12_3bps','T1_base_3bps'),('Multi','T2_multi_horizon_3bps','T2_base_3bps'),('Passive','T3_passive_long_3bps','T3_base_3bps')]], [115,120,120,135])
    table(['执行策略','平均总暴露','年换手','累计费用 / 元'],[
        [label,num(base.loc[key,'mean_gross_exposure']),num(base.loc[key,'turnover_ann']),f'{base.loc[key,"total_fees"]:,.2f}']
        for label,key in [('12M','T1_tsmom12_3bps'),('Multi','T2_multi_horizon_3bps')]], [115,120,120,135])
    p('同一账本先按月复合，再计算月频 Sharpe，排序可能与日频不同；序列相关及非线性复合使两种估计不必相同。本报告主研究比较固定为月频，日频仅补充执行风险。日内可见回撤可能大于月末可见回撤，表中已分开标注。')

    title('07  自主扩展：同风险预算再检验')
    p('扩展只将 12M 信号替换为三个符号的等权平均 a = (s3+s6+s12)/3。其取值为 ±1、±1/3；符号冲突会降低仓位。为区分信号变化和风险减少，再将两个组合分别缩放至同一事前 12% 波动目标；使用形成日 EWMA 协方差，最后施加总暴露 6 倍上限。实际波动率不必等于 12%。')
    risk=summary[(summary['sample']=='full')&summary.strategy.str.contains('risk12')]
    table(['资产池 / 同风险策略','算术年化','实现波动','Sharpe'],[
        [z.universe+' / '+('12M' if z.strategy.startswith('tsmom') else 'Multi'),pct(z.ann_mean),pct(z.ann_vol),num(z.sharpe)] for z in risk.itertuples()],[175,105,105,105])
    image(out/'figures/risk_normalized.png',maxheight=180,caption='图 2：原始单资产风险预算与同事前组合风险目标的 Sharpe 对照。全部为月频 gross。')
    p('配对分块 bootstrap：95% Sharpe 差值区间','h2')
    b6=boot[boot.block_months==6]
    table(['比较：Multi - 12M','点估计','95% 区间'],[
        [z.universe+' / '+z.comparison,num(z.delta_sharpe),f'[{num(z.sharpe_ci_low)}, {num(z.sharpe_ci_high)}]'] for z in b6.itertuples()],[275,75,140])
    p('固定种子 20261029，循环移动分块、成对抽样、每组 2000 次；3/6/12 月块长全部保存在 paired_bootstrap.csv。研究层 CN21 原始多期限劣于 12M，但区间对块长敏感；同风险版本及执行层均不足以建立多期限稳定优势。此为探索性不确定性分析，未做全搜索选择偏差校正。','small')

    title('08  预测回归、alpha 与极端行情')
    p('将两种回归明确分开：原文 Eq. (3) 型诊断使用单个滞后月收益的符号，因变量为下月收益除以形成日波动率；额外累计 12M 检验使用过去一年累计收益符号。两者都采用 pooled OLS、常数项和月份聚类标准误，不添加未披露的资产固定效应，不把月份聚类称作 HAC。')
    cumulative=reg[reg.model=='cumulative_12m_extension']
    table(['资产池','累计 12M β','月份聚类 t','观测数 / 月簇'],[
        [z.universe,num(z.beta),num(z.t_beta_month_cluster),f'{z.n_obs} / {z.n_month_clusters}'] for z in cumulative.itertuples()],[90,125,125,150])
    p('额外 alpha 相对同逆波动预算的 passive long 估计，采用 HAC 6 月标准误；不等于论文对 MSCI World、SMB、HML、UMD 等因子的完整 alpha。单一基准下的显著截距也不能单独证明独立的择时信息。完整系数在 benchmark_alpha.csv，1–24 月滞后结果在 predictive_regressions.csv。')
    image(out/'figures/quarterly_proxy.png',maxheight=205,caption='图 3：非重叠完整季度收益。横轴为同资产池 passive ETF 代理，纵轴为 12M TSMOM；这是扩展诊断，不是原文 S&P 500 散点的逐点复现。')
    p('危机及 V 形反转应结合当时持仓解释：下跌后留下的空头可能在快速反弹中亏损；不能写成“持有多头导致反弹损失”。图形只提供描述性证据，不能仅凭肉眼形状判定稳定的危机保护。','small')

    title('09  核验、手算与可重复性证据')
    p('核验分三层：独立公式例子验证数学定义；订单/成交/持仓/现金审计验证执行账本；干净输出目录重跑验证相同输入下结果是否一致。通过这些检查并不意味着不存在未覆盖的模型或数据问题。')
    table(['独立检查','预期与实现'],[
        ['EWMA 手算','收益 [0.01,-0.01,0.02]、衰减 1/2，历史权重 [1,2,4]/7；均值 0.01，方差 3/17500。'],
        ['权重与收益','两资产手算检查正负权重、1/N、40%/σ、贡献加总；缺失未来收益不改变形成日资格。'],
        ['信息泄漏反例','改变形成日后的价格，形成日风险缩放不变；协方差目标与 gross 上限独立检查。'],
        ['配对重采样','两条完全相同的序列应得到精确为零的收益与 Sharpe 差及区间。'],
        ['回撤初始资本','[-20%,+10%] 的序列必须包含初始高水位 1，最大回撤为 -20%。'],
        ['账本','8 套执行账本审计检查时序、资金与持仓守恒、拒单不收费、无借款和无卖空。']],[115,375])
    verification=out/'verification.json'
    if verification.exists():
        v=json.loads(verification.read_text(encoding='utf-8'))
        p(f'本次正式验证：测试 {v["tests"]["passed"]} 项通过、{v["tests"]["skipped"]} 项跳过；独立输出目录重跑比较 {v["reproducibility"]["tables_compared"]} 张数值/明细表，最大绝对偏差 {v["reproducibility"]["max_absolute_difference"]:.3g}；执行审计通过 {v["audits_passed"]} 套。详见 outputs/verification.json 与 tests.xml。')
    else:
        p('验证记录由 python verify_final.py --rerun 生成；本报告仅在正式打包时读取已完成的记录。')
    p('源文件、配置、锁文件、数据快照和输出的 SHA-256 进入运行证据；包内 FILE_MANIFEST.json 覆盖提交文件。报告 PDF 的最终哈希由打包阶段生成，避免报告自引用。跨平台 BLAS 或字体差异可能引入细微浮点和排版差异，数值比较采用显式容差。')

    title('10  结论、限制与可检验的下一步')
    p('结论一：在两个 ETF 替代资产池中完成了 12M TSMOM 的核心方法实现，但没有稳定重现原文相对同风险预算 passive long 的优势。正收益、单资产正 Sharpe 和参考序列复算通过分别回答不同问题，不能相互替代。')
    p('结论二：21 ETF 原始收益对低波资产杠杆与融资假设敏感。通过做空约束、预算归一、执行与费用的逐步桥接，可以定位变化出现的阶段；仍不能将所有差距唯一归因于某个市场机制。')
    p('结论三：多期限扩展体现风险、收益和换手权衡；同事前风险比较和配对 bootstrap 不支持稳定改进的强结论。将未改善结果保留下来，使策略设计的边界比“挑选最佳回测”更清晰。')
    table(['限制','对解释的影响'],[
        ['资产与收益','ETF 调整价 ≠ 期货超额收益；没有外汇/商品完整覆盖与展期规则，CN/US 货币也不同。'],
        ['样本选择','固定现存 ETF 名单、合格资产动态进入，仍存在幸存者与选择偏差；79 月不算长。'],
        ['执行简化','分数份额、固定费率、无滑点与容量限制；期货式理论头寸未完整建模融资借券。'],
        ['推断边界','月份聚类不覆盖所有跨期依赖；bootstrap 与不同参数均为探索，未留完全未见样本。'],
        ['归因边界','两个资产池不是随机实验；市场、区间、资产结构与币种影响不能完全分离。']],[100,390])
    p('下一步应优先获取可核验的期货超额收益与展期序列，按原文共同资产、共同区间重建；其次预先固定规则后积累真正未见时期。继续增加参数或追求更高历史 Sharpe，不是当前证据缺口的直接解决方案。')

    title('11  复现入口、团队贡献与参考文献')
    p('复现顺序：安装锁定环境 → python run_final.py → python verify_final.py --rerun。常用命令、文件索引和依赖安装替代方法见根目录 README.md。完整计算离线，首次安装 Python 依赖需要网络。原始历史项目与虚拟环境不进入提交包。')
    table(['交付内容','定位'],[
        ['最终报告','outputs/report/Project2_Final_Report.pdf 与同源 Markdown'],
        ['统一结果','outputs/integration/：共同区间、风险归一、bootstrap、桥接、回归和资金成本'],
        ['P1 执行证据','outputs/backtests/：orders、fills、holdings、ledger、audit'],
        ['公式与平台','docs/METHODOLOGY.md、PROTOCOL.md、DATA.md、CONTRIBUTIONS.md'],
        ['可重复性','outputs/verification.json、tests.xml、run_manifest_final.json、FILE_MANIFEST.json']],[110,380])
    p('团队与 AI 披露','h2')
    p('杨皓博、袁思扬、缪梓航共同署名。原始贡献依据仓库分支与提交记录：袁思扬版本提供 quantcf/P1 接入、研究与执行分层、21 ETF 研究和追踪；缪梓航版本提供美国行业 ETF 复现与统计诊断；本次在杨皓博发起的小组整合工作中，AI 协助方法核对、代码整合、受控实验、测试、报告与打包。署名不表示本工具已核实每位成员个人阅读、手算或口头答辩情况。')
    p('参考文献与来源','h2')
    for x in [
        '[1] Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012). Time series momentum. Journal of Financial Economics, 104(2), 228–250. DOI: 10.1016/j.jfineco.2011.11.003. 本包 references/ 附论文及目标图。',
        '[2] AQR Capital Management. Time Series Momentum: Original Paper Data. XLSX 快照与 SHA-256 随包提供；来源 images.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Time-Series-Momentum-Original-Paper-Data.xlsx。',
        '[3] Tushare ETF 日行情与复权因子固定快照。文件级来源、日期与校验见 data/manifests/source_manifest.json。',
        '[4] US9：miguel-merlin/etf-directional-forecasting，commit b3b583b10cce9a29cb97ab65d08f5854c0ffd001。来源逐文件记录在 data/us_sector/source_manifest.json。',
        '[5] 小组代码仓库：github.com/WY110-dot/Computational-finance-project。main 294ca84 与 ysy_proj2 163e50a 为本次整合基础。',
        '[6] CF2026 Project 2 课程任务书：核心结论复现、P1 接入、结果对照、差异归因与自主扩展。']:
        p(x,'small')

    def footer(canvas,doc):
        canvas.saveState(); canvas.setStrokeColor(colors.HexColor('#BFD0D5'))
        canvas.line(52,47,A4[0]-52,47); canvas.setFont(font,8); canvas.setFillColor(TEAL)
        canvas.drawString(52,32,'CF2026 | Time Series Momentum | 小组整合提交版')
        canvas.drawRightString(A4[0]-52,32,str(doc.page)); canvas.restoreState()
    pdf=dest/'Project2_Final_Report.pdf'
    doc=SimpleDocTemplate(str(pdf),pagesize=A4,rightMargin=52,leftMargin=52,topMargin=48,bottomMargin=62,
        title='时间序列动量在 ETF 替代样本中的复现',author='杨皓博、袁思扬、缪梓航')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    (dest/'Project2_Final_Report.md').write_text('\n'.join(md),encoding='utf-8')
    (dest/'summary_zh.md').write_text('\n'.join(md[:18]),encoding='utf-8')
    return pdf
