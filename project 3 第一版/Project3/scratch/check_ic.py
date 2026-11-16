import pandas as pd
df = pd.read_csv("outputs/diagnostics/block_bootstrap.csv")
print("Columns:", df.columns.tolist())
print(df.head(2))
