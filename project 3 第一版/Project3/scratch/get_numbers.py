import pandas as pd
df = pd.read_csv("outputs/experiments_inventory.csv")
for u in ["US9", "CN21"]:
    for strat in ["A", "B", "C", "A0"]:
        sub = df[(df["universe"]==u) & (df["candidate_id"]==strat) & (df["cost_bps"]==3.0)]
        if not sub.empty:
            r = sub.iloc[0]
            print(f"{u} {strat} 3bps: ann_return={r['ann_return']*100:.2f}%, sharpe={r['sharpe']:.3f}, mdd={r['max_drawdown']*100:.2f}%, daily_mdd={r['max_drawdown_daily']*100:.2f}%, fees={r['fees']:.2f}")
