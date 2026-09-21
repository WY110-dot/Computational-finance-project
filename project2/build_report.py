"""Build a compact Chinese report from audited numerical outputs."""
from pathlib import Path
import json,html
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

ROOT=Path(__file__).resolve().parent;OUT=ROOT/'outputs'
FONT='STSong-Light';pdfmetrics.registerFont(UnicodeCIDFont(FONT))
STYLE=ParagraphStyle('body',fontName=FONT,fontSize=10,leading=16,spaceAfter=8,wordWrap='CJK',textColor=colors.HexColor('#243748'))
TITLE=ParagraphStyle('title',parent=STYLE,fontSize=23,leading=31,spaceAfter=17,textColor=colors.HexColor('#126477'))
H1=ParagraphStyle('h1',parent=STYLE,fontSize=17,leading=24,spaceAfter=13,textColor=colors.HexColor('#126477'))
H2=ParagraphStyle('h2',parent=STYLE,fontSize=12,leading=19,spaceBefore=7,spaceAfter=7,textColor=colors.HexColor('#126477'))
SMALL=ParagraphStyle('small',parent=STYLE,fontSize=8.4,leading=12,spaceAfter=6)
CELL=ParagraphStyle('cell',parent=STYLE,fontSize=8.4,leading=12,spaceAfter=0)
WIDTH=507
def P(s,style=STYLE):return Paragraph(html.escape(str(s)).replace('\n','<br/>'),style)
def T(rows,widths=None):
    t=Table([[P(c,CELL) for c in row] for row in rows],colWidths=widths or [WIDTH/len(rows[0])]*len(rows[0]),repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6f0f2')),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LINEBELOW',(0,0),(-1,0),.8,colors.HexColor('#126477')),('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#b4c8cc'))]))
    return t
def F(name,height):return Image(str(OUT/'figures'/name),width=WIDTH,height=height,kind='proportional',hAlign='CENTER')
def pct(x):return f'{100*x:.2f}%'
def number(x):return f'{x:,.2f}'
def foot(c,doc):
    c.setFont(FONT,8);c.setFillColor(colors.HexColor('#60717e'));c.drawString(44,24,'CF2026 Project 1  |  日频量化投研框架')
    c.drawRightString(551,24,str(doc.page));c.setStrokeColor(colors.HexColor('#d9e4e6'));c.line(44,37,551,37)

def main():
    s=pd.read_csv(OUT/'strategy_summary.csv').set_index('strategy');fs=pd.read_csv(OUT/'factor_summary.csv')
    q=json.loads((OUT/'quality_report.json').read_text());m=json.loads((OUT/'run_manifest.json').read_text());cfg=m['config']
    audit=json.loads((OUT/'audit.json').read_text());maxerr=max(max(v.values()) for v in audit.values())
    w=s.loc['momentum_weekly'];mth=s.loc['momentum_monthly'];liq=s.loc['momentum_liquidity'];ew=s.loc['equal_weight_monthly']
    names={'momentum_weekly':'动量 / 周度','momentum_monthly':'动量 / 月度','reversal_weekly':'反转 / 周度','low_vol_weekly':'低波动 / 周度','momentum_liquidity':'动量 / 流动性限制','equal_weight_monthly':'等权 / 月度基准'}
    pages=[];md=[]
    def add(title,flows,prose):
        if pages:pages.append(PageBreak())
        pages.extend([P(title,TITLE if not md else H1),*flows]);md.append('## '+title+'\n\n'+prose+'\n')
    add('AI辅助日频量化投研框架',[P('CF2026 Project 1 研究报告',H2),
        P('从固定数据快照到可检验的策略净值：九只美国行业ETF，2015—2024年。'),
        P('本项目建立数据、因子、组合、成交、绩效和独立验证六个模块。三个因子采用同一字段契约，信号在收盘后形成、下一交易日开盘执行；交易成本按实际买卖额扣除。目标是验证研究系统的正确性和可复现性，而非寻找满足某个收益门槛的策略。'),
        T([['研究设计','本次选择'],['资产与样本','九只固定传统行业ETF；2015-01-02至2024-12-31；2516个交易日'],['因子与组合','20日动量、5日反转、20日低波动；分数越高越优；前三等权'],['主要对照','动量周度与月度调仓，其余设置相同'],['自主拓展','前20日流动性代理预算、部分成交、未成交不收费']],[95,412]),
        Spacer(1,8),F('architecture.png',130),
        P(f'主要发现：周度动量净累计收益{pct(w.total_return)}，月度动量为{pct(mth.total_return)}，同池等权基准为{pct(ew.total_return)}。三个因子的平均Rank IC均略低于零。结果支持降低换手、关注成本，但不支持宣称已经获得稳定超额收益。'),
        P('全部比较为历史描述性结果。固定资产池、已调整价格快照、开盘成交及成交容量近似均有适用边界。',SMALL)],
        f'样本：{m["research_start"]}至{m["research_end"]}，{m["research_days"]}个交易日。\n\n'+s.to_csv())
    quality_rows=[['资产','保留行数','缺失单元格','非法记录','覆盖区间']]
    quality_rows += [[x['asset'],x['retained_rows'],x['missing_cells'],x['invalid_rows'],x['first']+' 至 '+x['last']] for x in q['by_asset']]
    add('1  数据范围、快照与质量',[P('数据来源与固定范围',H2),
        P('读取公开仓库保存的Yahoo/yfinance格式ETF历史数据，固定Git提交而非获取最新变动版本。原始CSV完整保留并计算SHA-256，下载时间、源路径及Git blob标识写入source_manifest.json。研究不调用上游策略或预测模型。'),
        P(f'原始文件合计{q["raw_rows"]:,}行。按预先设定样本及100个自然日预热窗口，保留{q["clean_rows"]:,}行、{q["calendar_days"]}个日期。回测期为2516日。只截取时间、检查并排序，不按异常收益删除记录，不把缺失值填零。'),
        T(quality_rows,[45,65,75,65,257]),Spacer(1,10),
        P('价格口径及其限制',H2),
        P('源文件为已调整OHLC，包含公司行动字段但没有独立原始价格与复权因子。源下载代码调用stock.history(period="max")，结合库默认行为按已调整价格使用；原获取时的库版本并未保存，故不能声称已独立重建每次公司行动。开盘和收盘保持同一口径，不再额外记一遍分红现金。'),
        P('账本持仓是调整后价格单位，允许小数单位。来源成交量仍为标称份数，因此“调整后价格×成交量”仅作为流动性压力代理，不能等同于真实历史美元成交额。固定九只ETF也不是无幸存者偏差的全市场。',SMALL)],
        f'原始行数{q["raw_rows"]}，清洗后{q["clean_rows"]}，缺失网格{q["missing_grid_cells"]}。\n\n数据限制详见data/DATA_DICTIONARY.md。')
    add('2  因子卡与时间对齐',[T([['因子','定义与预期','输入与失效情形'],
        ['20日动量','C(t)/C(t-20)-1；越大越优','已调整收盘；趋势反转、拥挤交易时可能失效'],
        ['5日反转','-[C(t)/C(t-5)-1]；越大越优','已调整收盘；持续趋势中逆势持仓可能亏损'],
        ['20日低波动','-std(r(t-19),…,r(t))，样本标准差','r为收盘简单收益；风险偏好上升时可能落后']],[87,202,218]),
        Spacer(1,12),P('统一接口与缺失规则',H2),
        P('输出为date、asset、factor、value。公式通过注册器与回测器分离。动量与反转要求窗口两端价格有效；低波动要求20个有效日收益。缺失保持NaN，不向前填补因子。主策略仅依赖截面顺序，故不去极值或中性化；保留原始分布，展示百分位排名。'),
        P('前向标签',H2),P('y(t,5) = O(t+6) / O(t+1) - 1。\n形成日t收盘后计算因子，t+1开盘可成交，t+6开盘退出对应五个交易日持有期。标签不会进入权重或下单模块。末六个形成日没有完整标签，相关系数保留缺失。'),
        P('相关系数与分组',H2),
        P('逐日跨资产计算Pearson IC和Spearman Rank IC，再沿时间汇总；并列秩使用平均秩。有效资产少于6或任一序列为常数时记缺失。三分组按形成时分数从低到高划分，并列按代码稳定分配；标签缺失只减少原组有效人数，不重新分组。'),
        P('多日标签重叠，分组均值仅是未扣费的排序诊断，不能逐日连续复利成策略净值。IC数值不是收益率或预测正确率。',SMALL)],
        '因子定义、缺失规则和时间对齐见本页及src/factors.py。前向标签y(t,5)=O(t+6)/O(t+1)-1。')
    add('3  组合、成交与现金账本',[P('可执行时序',H2),
        P('在样本新周或新月的第一个交易日开盘调仓，读取上一交易日收盘分数。选前三只等权，目标投入交易前开盘估值的99%，留1%缓冲。等权基准持有同池九只。假设允许按开盘参考价配比，未模拟开盘集合竞价提交截止时间和盘口冲击。'),
        T([['配置','定义'],['资金、成本','初始100万美元；买入和卖出各10bp；按实际成交金额收取'],['现金约束','先卖后买；买入资金不足时同比缩放；不借款、不卖空'],['异常处理','缺开盘价不成交；因子不足6只时不调仓；未成交量当日取消'],['估值缺失','仅现有持仓可沿用最近收盘价并记录；连续超过5个样本交易日则失败'],['毛净口径','零费率独立重跑；毛净差含资金路径差异，不等于累计手续费']],[89,418]),
        Spacer(1,10),P('独立核算关系',H2),
        P('Fee(t) = cb × Buy(t) + cs × Sell(t)\nCash(t) = Cash(t-1) + Sell(t) - Buy(t) - Fee(t)\nUnits(t) = Units(t-1) + ExecutedDollars(t) / Open(t)\nV(t) = Cash(t) + sum[Units(t) × Close(t)]\nReturn(t) = V(t)/V(t-1)-1'),
        P('最大回撤包括初始资金V0，因此第一天发生的交易成本不会被漏掉。年化交易日取252，波动率和Sharpe分母均使用样本标准差，无风险日收益设0。双边换手为实际买卖金额之和除以交易前价值。'),
        P('为保持可审计性，逐日输出净值、现金、买卖额、费用、换手和未成交额；逐资产输出调整后单位及估值；逐订单保留信号日期与实际成交日期。',SMALL)],
        '现金与持仓双账本，收费仅对实际成交金额；净值、现金、持仓和成交量可独立重算。')
    icrows=[['因子','覆盖率','IC均值','Rank IC均值','有效日期']]
    icrows += [[x.factor,pct(x.coverage),f'{x.ic_mean:.4f}',f'{x.rank_ic_mean:.4f}',int(x.ic_days)] for x in fs.itertuples()]
    add('4  三个因子的诊断结果',[T(icrows,[105,75,85,115,127]),Spacer(1,8),
        P('回测区间的因子覆盖率均为100%；有效标签形成日2510天，每个完整标签日有9只资产。全期平均Rank IC略为负，时间序列正负交替，不能据此认定稳定预测能力。原始分布的均值、标准差及1%、50%、99%分位保存在factor_summary.csv。'),
        F('ic.png',235),F('groups.png',178),
        P('左图按形成时原组计算五日平均标签，右图为截面百分位分布。小截面使相关系数波动较大，分组优势不稳定；未对重叠标签和多重研究选择进行推断校正，结果仅作描述性诊断。',SMALL)],fs.to_markdown(index=False) if False else fs.to_csv(index=False))
    perf=[['策略','累计净收益','年化收益','年化波动','Sharpe','最大回撤']]
    perf += [[names[n],pct(r.total_return),pct(r.annual_return),pct(r.annual_vol),f'{r.sharpe:.3f}',pct(r.max_drawdown)] for n,r in s.iterrows()]
    add('5  策略绩效与同池基准',[T(perf,[125,82,75,75,65,85]),Spacer(1,9),F('nav.png',232),
        P(f'相同样本和成本下，等权月度基准净累计收益{pct(ew.total_return)}、年化{pct(ew.annual_return)}。所测因子择时配置均未超越它。低波动策略年化波动{pct(s.loc["low_vol_weekly","annual_vol"])}，但较低风险不自动带来更高收益。'),
        P('不以历史最高净收益重新指定主策略。九只行业ETF共享股票市场风险，净值整体上涨不等于因子有预测增量；需要对照共同资产池、交易成本及持仓变化，不能只展示正收益曲线。'),
        P('年化收益采用(VN/V0)^(252/N)-1；年化波动为sqrt(252)×std(日收益)；Sharpe使用同频超额收益。费用直接反映在净值中。',SMALL)],s.to_csv())
    compare=[['指标','动量周度','动量月度'],['累计现金费用 / USD',number(w.total_cost),number(mth.total_cost)],
        ['年化双边换手 / 倍',f'{w.annual_turnover:.2f}',f'{mth.annual_turnover:.2f}'],['累计净收益',pct(w.total_return),pct(mth.total_return)],
        ['零费率重跑收益',pct(w.gross_rerun_total_return),pct(mth.gross_rerun_total_return)]]
    add('6  对照实验：只改变调仓频率',[P('事先预期：减少调仓次数会降低交易负担；收益和Sharpe不预设改善。两组保持资产、样本、因子窗口、持仓数、现金预算和费率完全一致。'),
        T(compare,[180,163,164]),Spacer(1,8),F('risk_cost.png',268),
        P(f'月度累计费用比周度减少{number(w.total_cost-mth.total_cost)}美元，年化双边换手从{w.annual_turnover:.2f}倍降至{mth.annual_turnover:.2f}倍。净收益改善符合较低交易负担的解释，但零费率重跑也存在差异，因此不能把全部收益改善归因于费用。'),
        P('调仓频率同时改变持仓更新节奏和机会暴露；只有“改变频率”的整体策略差具有本实验定义。该比较不构成月度调仓普遍优于周度的统计结论。',SMALL)],
        '\n'.join(' | '.join(map(str,row)) for row in compare)+'\n\n毛净收益为分别重跑，不是同一路径减费。')
    add('7  拓展、验证与复现',[P('自主拓展：流动性预算与部分成交',H2),
        P('在相同周度动量信号上，单资产成交额不超过前20个完整日价格成交量代理均值的0.1%。先完成受限卖单，再按现金约束同比缩放买单。未成交量当日取消；容量无限时应精确退化为基础回测。'),
        T([['指标','基础版','受限版'],['净累计收益',pct(w.total_return),pct(liq.total_return)],['金额成交比例',pct(w.fill_ratio),pct(liq.fill_ratio)],
           ['平均持仓数',f'{w.mean_holdings:.3f}',f'{liq.mean_holdings:.3f}'],['累计成本 / USD',number(w.total_cost),number(liq.total_cost)]],[180,163,164]),
        P('部分成交可能留下旧持仓，因此实际持仓数可以超过目标3只。这是执行限制的结果，不通过伪造成交维持目标权重。该预算采用复权价格成交量代理，未校准真实开盘容量，拓展价值是正确接入约束并审计，而非证明真实市场容量。'),
        P('验证与复现',H2),
        P(f'13项小情景和故障注入测试覆盖因子、标签、现金、成交成本、缺价、未来信息隔离、初始回撤及容量退化。六组净回测及零费率回测均通过账本核验，净组最大审计残差{maxerr:.2e}。另以相同数据和配置重跑主策略，verify.py输出误差与测试日志。'),
        P('运行：uv sync --frozen；uv run --frozen python run.py；uv run --frozen python build_report.py；uv run --frozen python verify.py。代码、配置、输入及输出有SHA-256清单。完整源码和数据获取脚本随包提供。',SMALL),
        P('局限、下一步与来源',H2),
        P('本次不宣称样本外有效或统计显著。下一步首先引入原始价格及独立复权因子、动态资产池和真实成交容量数据，再在预先冻结的验证期比较。AI辅助任务拆解、代码与报告草拟；提交者仍需理解并亲自复核运行结果。',SMALL),
        P('[1] 课程任务：CF2026_Project1.pdf，第5—19页。\n[2] 数据：github.com/miguel-merlin/etf-directional-forecasting；固定提交及每文件哈希见data/source_manifest.json。\n[3] 复权说明：help.yahoo.com/kb/SLN28256.html；yfinance历史接口文档链接见数据字典。',SMALL)],
        f'受限版成交比例{pct(liq.fill_ratio)}，累计净收益{pct(liq.total_return)}。13项测试和独立账本核验，报告残差{maxerr:.3e}。局限包括固定池、调整后快照、容量代理、无独立验证期和描述性统计。')
    dest=ROOT/'output/pdf';dest.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(dest/'CF2026_Project1_Report.pdf'),pagesize=(595.28,841.89),leftMargin=44,rightMargin=44,topMargin=43,bottomMargin=47,
        title='CF2026 Project 1 - Daily Quantitative Research Framework',author='')
    doc.build(pages,onFirstPage=foot,onLaterPages=foot)
    (ROOT/'REPORT.md').write_text('# CF2026 Project 1 研究报告（可编辑结果稿）\n\n'+'\n'.join(md)+'\n\n详细定义和复现步骤见README.md、RESEARCH_PROTOCOL.md及data/DATA_DICTIONARY.md。\n',encoding='utf-8')
    print(dest/'CF2026_Project1_Report.pdf')

if __name__=='__main__':main()
