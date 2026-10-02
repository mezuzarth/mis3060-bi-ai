import pandas as pd

df = pd.read_csv("data/raw/fact_transactions.csv")

total_rows = len(df)
other_counts = df["txn_type"].isin(["Sell", "Deposit", "Withdrawal", "Dividend", "Advisory Fee"]).sum()
buy_by_subtraction = total_rows - other_counts

print(f"Total rows: {total_rows}")
print(f"Buy count via subtraction: {buy_by_subtraction}")
