"""
HW6 Part C - pandas evidence for the design questions (a)-(d).

Run:  python scripts/02_part_c_analysis.py      (writes reports/part_c_evidence.txt)
Uses the same CSV lookup as 01_reconcile_measures.py.
"""

import importlib.util
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("rec", HERE / "01_reconcile_measures.py")
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)

snap, fees, txns, dates = rec.load()
lines = []


def out(text=""):
    print(text)
    lines.append(str(text))


money = lambda x: f"${x:,.2f}"
LAST = snap["snapshot_date"].max()

# --------------------------------------------------------------------------- (a)
out("=== (a) Ending AUM vs SUMX over clients ===")
last_rows = snap[snap["snapshot_date"] == LAST]
ending_aum = last_rows["aum"].sum()
own_last = snap.loc[snap.groupby("client_id")["snapshot_date"].idxmax()]   # each client's own last row
sumx = own_last["aum"].sum()
departed = own_last[own_last["snapshot_date"] < LAST]
out(f"Ending AUM (one last date, {LAST.date()}):     {money(ending_aum)}")
out(f"SUMX(VALUES(client_id), [Ending AUM]):         {money(sumx)}")
out(f"Difference:                                    {money(sumx - ending_aum)}")
out(f"Clients whose last snapshot is before {LAST.date()}: {len(departed)}, "
    f"last balances total {money(departed['aum'].sum())}")
out(f"Their last snapshot dates range {departed['snapshot_date'].min().date()} "
    f"to {departed['snapshot_date'].max().date()}")
out("Departed clients by tier:\n" + departed.groupby("client_tier")["aum"].agg(["count", "sum"]).to_string())
out(f"Largest departed client's last balance: {money(departed['aum'].max())}  "
    f"(10th-largest client today: {money(last_rows['aum'].nlargest(10).min())})")

# --------------------------------------------------------------------------- (b)
out("\n=== (b) Fee Yield vs Effective Fee Rate, 2024 ===")
s24 = snap[snap["snapshot_date"].dt.year == 2024]
f24 = fees[fees["fee_date"].dt.year == 2024]
fee_yield = f24["amount"].sum() * 12 * 10000 / s24["aum"].sum()
eff_rate = f24["amount"].sum() * 12 * 10000 / f24["aum_basis"].sum()
out(f"Fee Yield (bps)          = fees x 12 x 10,000 / SUM(snapshot aum)    = {fee_yield:.4f}")
out(f"Effective Fee Rate (bps) = fees x 12 x 10,000 / SUM(fee aum_basis)  = {eff_rate:.4f}")
out(f"Same numerator ({money(f24['amount'].sum())}); denominators: snapshot aum {money(s24['aum'].sum())} "
    f"vs aum_basis {money(f24['aum_basis'].sum())}")

keys_s = s24[["client_id", "snapshot_date", "aum", "client_tier"]].rename(columns={"snapshot_date": "d"})
keys_f = f24[["client_id", "fee_date", "aum_basis", "amount"]].rename(columns={"fee_date": "d"})
m = keys_s.merge(keys_f, on=["client_id", "d"], how="outer", indicator=True)
both = m[m["_merge"] == "both"]
no_fee = m[m["_merge"] == "left_only"]
fee_only = m[m["_merge"] == "right_only"]
out(f"Snapshot client-months 2024: {len(s24):,}; fee client-months 2024: {len(f24):,}")
out(f"Client-months with a snapshot but NO fee row: {len(no_fee):,}  "
    f"(AUM {money(no_fee['aum'].sum())} = {no_fee['aum'].sum() / s24['aum'].sum():.2%} of 2024 sum of aum)")
out(f"Client-months with a fee but no snapshot: {len(fee_only):,}")
out(f"Where both exist, aum_basis == aum on {(abs(both['aum'] - both['aum_basis']) < 0.005).mean():.2%} of rows")
out(f"Fee Yield using only fee-paying client-months: "
    f"{f24['amount'].sum() * 12 * 10000 / both['aum'].sum():.4f} bps")
nf_clients = set(no_fee["client_id"])
fully_unbilled = nf_clients - set(both["client_id"])
out(f"  of the {len(nf_clients)} clients with a missing fee month, {len(fully_unbilled)} were never billed in 2024")
out("No-fee client-months by tier:\n" + no_fee.groupby("client_tier")["aum"].agg(["count", "sum"]).to_string())
out("No-fee client-months by month:\n" + no_fee.groupby(no_fee["d"].dt.month).size().to_string())

# --------------------------------------------------------------------------- (c)
out("\n=== (c) AUM-Weighted Alpha ===")
clean = last_rows[last_rows["is_return_suspect"] == 0]
w_clean = (clean["aum"] * clean["active_alpha_ytd"]).sum() / clean["aum"].sum()
w_all = (last_rows["aum"] * last_rows["active_alpha_ytd"]).sum() / last_rows["aum"].sum()
simple = clean["active_alpha_ytd"].mean()
out(f"Rows at last snapshot: {len(last_rows)}, suspects: {int(last_rows['is_return_suspect'].sum())}")
out(f"Weighted, suspects excluded (the measure): {w_clean:.6f}")
out(f"Simple mean, same rows:                    {simple:.6f}")
out(f"Weighted, suspects included:               {w_all:.6f}")
sus = last_rows[last_rows["is_return_suspect"] == 1]
out(f"Suspect rows: alpha min {sus['active_alpha_ytd'].min():.4f}, max {sus['active_alpha_ytd'].max():.4f}, "
    f"mean {sus['active_alpha_ytd'].mean():.4f}; clean rows: min {clean['active_alpha_ytd'].min():.4f}, "
    f"max {clean['active_alpha_ytd'].max():.4f}")
all_months = snap[snap["is_return_suspect"] == 0]
out(f"Wrong way - weighted over ALL 60 months (mixes Jan YTD with Dec YTD): "
    f"{(all_months['aum'] * all_months['active_alpha_ytd']).sum() / all_months['aum'].sum():.6f}")
jan = snap[(snap["snapshot_date"] == "2024-01-01") & (snap["is_return_suspect"] == 0)]
out(f"Jan-2024 weighted YTD alpha (one month in): {(jan['aum'] * jan['active_alpha_ytd']).sum() / jan['aum'].sum():.6f}")
by_size = clean.assign(big=clean["aum"] >= clean["aum"].median())
out("Mean alpha, smaller vs larger half of clients by AUM:\n"
    + by_size.groupby("big")["active_alpha_ytd"].mean().to_string())

# --------------------------------------------------------------------------- (d)
out("\n=== (d) Organic growth by tier, 2024 ===")
t24 = txns[txns["txn_date"].dt.year == 2024]
rows = []
for tier in ["Retail", "HNW", "UHNW"]:
    ly = snap[(snap["snapshot_date"] == "2023-12-01") & (snap["client_tier"] == tier)]["aum"].sum()
    end = s24[(s24["snapshot_date"] == "2024-12-01") & (s24["client_tier"] == tier)]["aum"].sum()
    tt = t24[t24["client_tier"] == tier]
    dep = tt.loc[tt["txn_type"] == "Deposit", "amount"].sum()
    wd = tt.loc[tt["txn_type"] == "Withdrawal", "amount"].sum()
    rows.append({"tier": tier, "AUM Dec-23": ly, "AUM Dec-24": end, "change": end - ly,
                 "deposits": dep, "withdrawals": wd, "net flows": dep - wd,
                 "organic %": (dep - wd) / ly, "YoY %": end / ly - 1,
                 "non-flow growth %": (end - ly - (dep - wd)) / ly,
                 "share of firm net flows": None})
d = pd.DataFrame(rows)
d["share of firm net flows"] = d["net flows"] / d["net flows"].sum()
pd.set_option("display.float_format", lambda x: f"{x:,.4f}")
pd.set_option("display.width", 250)
out(d.to_string(index=False))

(rec.REPORTS / "part_c_evidence.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n-> reports/part_c_evidence.txt")
