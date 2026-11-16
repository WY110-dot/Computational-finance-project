import pandas as pd
df = pd.read_csv("outputs/diagnostics/daily_correlations.csv")
print(df.groupby('universe')[['pearson_corr', 'spearman_corr']].agg(['mean', 'count']))
for u in ["US9", "CN21"]:
    sub = df[df["universe"] == u]
    print(f"{u}: Pearson mean = {sub['pearson_corr'].mean():.6f}, Spearman mean = {sub['spearman_corr'].mean():.6f}, count = {len(sub)}")
