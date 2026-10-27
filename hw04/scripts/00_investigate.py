#!/usr/bin/env python3
"""
HW4 Part B support - 00_investigate.py
Tests each hypothesis from the profile against other columns/tables, so every
decision_log.md entry can cite evidence and a verification.

Run from hw04/:   python scripts/00_investigate.py > reports/investigation_raw.txt
Read-only: it never writes to the data.
"""
from pathlib import Path

import pandas as pd

D = Path("Wildcat Capital")
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)


def load(t):
    return pd.read_csv(D / f"{t}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")


def num(s):
    return pd.to_numeric(s.str.strip().str.replace(r"[%,$]", "", regex=True), errors="coerce")


def hdr(x):
    print("\n" + "=" * 78 + f"\n{x}\n" + "=" * 78)


adv, cli, dd, sec, bm = (load(t) for t in ["dim_advisor", "dim_client", "dim_date", "dim_security", "dim_benchmark"])
fees, snap, tx = (load(t) for t in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"])
sh, pr, am = num(tx.shares), num(tx.price), num(tx.amount)

# ---------------------------------------------------------------------------------
hdr("1. fact_transactions.security_id stored as '447.0'?")
sid = tx.security_id.str.strip()
print("decimal suffixes on non-blank ids:")
print(sid[sid != ""].str.extract(r"(\.\d+)$")[0].fillna("<none>").value_counts().to_string())
fixed = sid.str.replace(r"\.0+$", "", regex=True)
nb = fixed != ""
print(f"raw match rate:            {sid[nb].isin(set(sec.security_id)).mean():.4%}")
print(f"match after removing '.0': {fixed[nb].isin(set(sec.security_id)).mean():.4%}")

# ---------------------------------------------------------------------------------
hdr("2. Blank security_id / shares / price: which txn_types?")
print(pd.crosstab(tx.txn_type, sid.eq("").map({True: "security blank", False: "security filled"}), margins=True))
same = (tx.security_id.eq("") == tx.shares.eq("")).all() and (tx.shares.eq("") == tx.price.eq("")).all()
print("blank pattern identical in all three columns:", same)

# ---------------------------------------------------------------------------------
hdr("3. Negative shares")
neg = sh < 0
tol = (am.abs() * 0.005).clip(lower=0.01)
print("negative-share rows by txn_type:")
print(tx.loc[neg, "txn_type"].value_counts().to_string())
print(f"negative rows where |shares| x price = amount: {((sh.abs() * pr - am).abs() <= tol)[neg].mean():.2%}")
pos = sh > 0
print(f"positive rows where shares x price = amount:  {((sh * pr - am).abs() <= tol)[pos].mean():.2%}")
print("negative amounts anywhere in fact_transactions:", int((am < 0).sum()))
print(tx[neg].head(5).to_string(index=False))

# ---------------------------------------------------------------------------------
hdr("4. Orphan client_id in fact_transactions")
orph = ~tx.client_id.isin(set(cli.client_id))
o = tx[orph]
print(f"rows: {len(o)}, distinct ids: {o.client_id.nunique()}, id range {num(o.client_id).min():.0f}-{num(o.client_id).max():.0f}")
print("dim_client id range:", num(cli.client_id).min(), "-", num(cli.client_id).max())
print("txn_type:", o.txn_type.value_counts().to_dict())
print(f"amount total: {am[orph].sum():,.2f}   dates: {o.txn_date.min()} to {o.txn_date.max()}")
print("orphan ids found in fact_fees:", int(o.client_id.isin(set(fees.client_id)).sum()),
      " in snapshot:", int(o.client_id.isin(set(snap.client_id)).sum()))
print(o.head(5).to_string(index=False))

# ---------------------------------------------------------------------------------
hdr("5. dim_client: 2,525 clients but facts use 2,500. Duplicates?")
used = set(fees.client_id) | set(snap.client_id) | set(tx.client_id)
unused = cli[~cli.client_id.isin(used)]
print(f"clients with NO fact rows: {len(unused)}; ids: {sorted(num(unused.client_id).astype(int).tolist())}")
norm = cli.copy()
for c in ["first_name", "last_name", "city", "state", "zip_code", "age"]:
    norm[c] = norm[c].str.strip().str.lower()
u = norm[norm.client_id.isin(unused.client_id)]
k = norm[~norm.client_id.isin(unused.client_id)]
for keys in (["first_name", "last_name"], ["first_name", "last_name", "zip_code"],
             ["first_name", "last_name", "age"], ["first_name", "last_name", "city"]):
    m = u.merge(k, on=keys, suffixes=("_dup", "_orig"))
    print(f"match on {keys}: {m.client_id_dup.nunique()} of {len(u)} unused clients")
pairs = u.merge(k, on=["first_name", "last_name"], suffixes=("_dup", "_orig"))
print("\nfirst 4 candidate pairs (unused client, then the active client it resembles):")
for _, r in pairs.head(4).iterrows():
    print(cli[cli.client_id.isin([r.client_id_dup, r.client_id_orig])].to_string(index=False), "\n")
print("name-sharing rows that are NOT unused clients (coincidental same names):",
      int(norm.duplicated(["first_name", "last_name"], keep=False).sum()) - len(pairs) * 2)

# ---------------------------------------------------------------------------------
hdr("6. dim_client.state values")
print(cli.state.value_counts().to_string())

# ---------------------------------------------------------------------------------
hdr("7. dim_client.risk_profile blanks: any pattern?")
b = cli.risk_profile.eq("")
print(pd.crosstab(cli.client_tier, b.map({True: "blank", False: "filled"})))
print(pd.crosstab(cli.is_active, b.map({True: "blank", False: "filled"})))
print("client_since range of blanks:", cli.loc[b, "client_since"].min(), "to", cli.loc[b, "client_since"].max())

# ---------------------------------------------------------------------------------
hdr("8. dim_security blanks vs is_etf, and duplicate names")
print(pd.crosstab(sec.is_etf, sec.sector.eq("").map({True: "sector blank", False: "sector filled"})))
print(pd.crosstab(sec.is_etf, sec.expense_ratio_bps.eq("").map({True: "expense blank", False: "expense filled"})))
print(pd.crosstab(sec.asset_class, sec.is_etf))
print("\nsecurities sharing a name:")
print(sec[sec.name.duplicated(keep=False)].sort_values("name").to_string(index=False))

# ---------------------------------------------------------------------------------
hdr("9. Snapshot returns: does active_alpha = return_ytd - benchmark_return_ytd?")
rr = snap.return_ytd.str.strip()
pct = rr.str.endswith("%")
r = num(rr)
r_fixed = r.where(~pct, r / 100)
bb, a = num(snap.benchmark_return_ytd), num(snap.active_alpha_ytd)


def ok(x, y):
    return ((x - y).abs() < 1e-4)


print(f"rows with '%' strings: {pct.sum()}")
print(f"  identity with raw value:   {ok(a[pct], r[pct] - bb[pct]).mean():.2%}")
print(f"  identity after /100:       {ok(a[pct], r_fixed[pct] - bb[pct]).mean():.2%}")
big = (r_fixed.abs() > 1.5) & ~pct
abig = (a.abs() > 1.5)
print(f"\nrows with |return_ytd| > 1.5 (i.e. >150% YTD): {big.sum()}")
print(r_fixed[big].describe().to_string())
print(f"  identity as stored:        {ok(a[big], r_fixed[big] - bb[big]).mean():.2%}")
print(f"  identity if return /100:   {ok(a[big], r_fixed[big] / 100 - bb[big]).mean():.2%}")
print(f"  identity if both /100:     {ok(a[big] / 100, r_fixed[big] / 100 - bb[big]).mean():.2%}")
print(f"\nrows with |active_alpha_ytd| > 1.5: {abig.sum()}  (overlap with big returns: {(abig & big).sum()})")
print(f"  identity if alpha /100:    {ok(a[abig] / 100, r_fixed[abig] - bb[abig]).mean():.2%}")
normal = ~big & ~abig & ~pct
print(f"\nall other rows ({normal.sum():,}): identity holds {ok(a[normal], r_fixed[normal] - bb[normal]).mean():.4%}")
bad_normal = normal & ~ok(a, r_fixed - bb)
if bad_normal.any():
    print(snap.loc[bad_normal, ["snapshot_id", "return_ytd", "benchmark_return_ytd", "active_alpha_ytd"]].head(8).to_string(index=False))
print("\nsample of the big-return rows:")
print(snap.loc[big, ["snapshot_id", "client_id", "snapshot_date", "return_ytd", "benchmark_return_ytd", "active_alpha_ytd"]].head(8).to_string(index=False))

# ---------------------------------------------------------------------------------
hdr("10. Snapshot structure")
print("duplicate client_id+snapshot_date:", int(snap.duplicated(["client_id", "snapshot_date"]).sum()))
print("year column disagrees with snapshot_date:", int((snap.year != snap.snapshot_date.str[:4]).sum()))
print("month column disagrees with snapshot_date:", int((num(snap.month) != num(snap.snapshot_date.str[5:7])).sum()))
aum = num(snap.aum)
print("aum exactly 1000.00 (possible floor/placeholder):", int((aum == 1000).sum()))
cat = dict(zip(cli.client_id, cli.primary_account_type))
mm = snap.account_type != snap.client_id.map(cat)
print("snapshot account_type differs from client's primary_account_type:", int(mm.sum()))
risk = snap.client_id.map(dict(zip(cli.client_id, cli.risk_profile)))
print("\nbenchmark_id used by risk_profile:")
print(pd.crosstab(risk.replace("", "<blank>"), snap.benchmark_id))

# ---------------------------------------------------------------------------------
hdr("11. fact_fees: amount = aum_basis x bps / 10000 / 12 ?")
aumb, bps, fam = num(fees.aum_basis), num(fees.bps_charged), num(fees.amount)
calc = aumb * bps / 10000 / 12
hit = (calc - fam).abs() <= 0.01
print(f"overall match within 1 cent: {hit.mean():.2%}")
print(pd.crosstab(fees.fee_type, hit.map({True: "match", False: "mismatch"})))
if (~hit).any():
    print("ratio stored / recomputed on mismatches:")
    print((fam[~hit] / calc[~hit]).describe().to_string())
    print(fees[~hit].head(5).to_string(index=False))
print("\nbps_charged by fee_type:")
print(fees.assign(bps=bps).groupby("fee_type").bps.describe().to_string())
print("duplicate client+fee_date+fee_type:", int(fees.duplicated(["client_id", "fee_date", "fee_type"]).sum()))
print("aum_basis exactly 1000.00:", int((aumb == 1000).sum()))

hdr("12. fact_fees.aum_basis vs snapshot aum (same client, same month)")
s1 = snap.drop_duplicates(["client_id", "snapshot_date"])[["client_id", "snapshot_date", "aum"]]
m = fees.merge(s1, left_on=["client_id", "fee_date"], right_on=["client_id", "snapshot_date"], how="left")
has = m.aum.notna()
print(f"fee rows with a snapshot that month: {has.mean():.2%}")
print(f"aum_basis = snapshot aum (within 1 cent): {((num(m.aum_basis) - num(m.aum.fillna(''))).abs() <= 0.01)[has].mean():.2%}")

hdr("13. Advisory Fee transactions vs fact_fees (per client-month)")
txf = tx.assign(amt=am, ym=tx.txn_date.str[:7])
txf = txf[txf.txn_type == "Advisory Fee"].groupby(["client_id", "ym"]).amt.sum()
for types in (["Advisory"], ["Management"], ["Management", "Advisory"], sorted(fees.fee_type.unique())):
    fe = fees.assign(amt=fam, ym=fees.fee_date.str[:7])
    fe = fe[fe.fee_type.isin(types)].groupby(["client_id", "ym"]).amt.sum()
    j = pd.concat([txf.rename("tx"), fe.rename("fees")], axis=1)
    both = j.dropna()
    print(f"{types}: both={len(both):,} only_tx={int(j.fees.isna().sum()):,} only_fees={int(j.tx.isna().sum()):,} "
          f"equal within 1c={((both.tx - both.fees).abs() <= 0.01).mean():.2%} median ratio={(both.tx / both.fees).median():.4f}")

# ---------------------------------------------------------------------------------
hdr("14. Facts vs dimension business rules")
since = dict(zip(cli.client_id, cli.client_since))
for name, df, dc in [("fact_transactions", tx, "txn_date"), ("fact_fees", fees, "fee_date"),
                     ("fact_portfolio_snapshot", snap, "snapshot_date")]:
    s = df.client_id.map(since)
    bad = s.notna() & (df[dc] < s)
    print(f"{name}: rows dated before client_since = {int(bad.sum()):,}")
cadv = dict(zip(cli.client_id, cli.advisor_id))
for name, df in [("fact_transactions", tx), ("fact_fees", fees), ("fact_portfolio_snapshot", snap)]:
    exp = df.client_id.map(cadv)
    print(f"{name}: advisor_id differs from client's advisor in dim_client = {int((exp.notna() & (df.advisor_id != exp)).sum()):,}")
inactive = set(cli.client_id[cli.is_active == "False"])
print("transactions for is_active=False clients:", int(tx.client_id.isin(inactive).sum()),
      " latest:", tx.loc[tx.client_id.isin(inactive), "txn_date"].max())
tday = dict(zip(dd.date, dd.is_trading_day))
nt = tx.txn_date.map(tday).eq("0")
print("\ntransactions on non-trading days by type:")
print(pd.crosstab(tx.txn_type, nt.map({True: "non-trading day", False: "trading day"})))

# ---------------------------------------------------------------------------------
hdr("15. dim_date internal consistency")
dt = pd.to_datetime(dd.date)
checks = {
    "year": dt.dt.year.astype(str) == dd.year,
    "quarter": dt.dt.quarter.astype(str) == dd.quarter,
    "month": dt.dt.month.astype(str) == dd.month,
    "month_name": dt.dt.month_name() == dd.month_name,
    "day_of_week": dt.dt.day_name() == dd.day_of_week,
    "week_of_year(ISO)": dt.dt.isocalendar().week.astype(str).values == dd.week_of_year.values,
    "is_month_end": dt.dt.is_month_end.astype(int).astype(str) == dd.is_month_end,
    "is_quarter_end": dt.dt.is_quarter_end.astype(int).astype(str) == dd.is_quarter_end,
    "is_year_end": dt.dt.is_year_end.astype(int).astype(str) == dd.is_year_end,
    "is_trading_day = weekday": (dt.dt.weekday < 5).astype(int).astype(str) == dd.is_trading_day,
    "date_id in date order": (num(dd.date_id).values == dt.rank(method="first").astype(int).values),
}
for kname, v in checks.items():
    print(f"{kname:28s} {pd.Series(v).mean():.2%}")

hdr("17. Fees/snapshots before client_since: same month, or truly earlier?")
since_s = pd.Series(since)
for name, df, dc in [("fact_fees", fees, "fee_date"), ("fact_portfolio_snapshot", snap, "snapshot_date")]:
    s = df.client_id.map(since)
    bad = s.notna() & (df[dc] < s)
    same_m = bad & (df[dc].str[:7] == s.str[:7])
    print(f"{name}: {int(bad.sum())} before client_since -> {int(same_m.sum())} in the SAME month "
          f"(monthly row dated the 1st), {int((bad & ~same_m).sum())} in an EARLIER month")
    if (bad & ~same_m).any():
        print(df.loc[bad & ~same_m].assign(client_since=s).head(5).to_string(index=False))

hdr("18. Inactive clients: when does their activity stop?")
inact = set(cli.client_id[cli.is_active == "False"])
last_tx = tx[tx.client_id.isin(inact)].groupby("client_id").txn_date.max()
print("inactive clients:", len(inact), " with transactions:", len(last_tx))
print("year of last transaction:", last_tx.astype(str).str[:4].value_counts().sort_index().to_dict())
for name, df, dc in [("fact_fees", fees, "fee_date"), ("fact_portfolio_snapshot", snap, "snapshot_date")]:
    sub = df[df.client_id.isin(inact)]
    print(f"{name}: rows for inactive clients {len(sub):,}; latest {sub[dc].max()}; "
          f"rows after that client's last transaction month: "
          f"{int((sub[dc].str[:7] > sub.client_id.map(last_tx).fillna('9999').astype(str).str[:7]).sum()):,}")
act_last = tx[~tx.client_id.isin(inact)].groupby("client_id").txn_date.max()
print("ACTIVE clients whose last transaction is before 2024:", int((act_last < "2024-01-01").sum()))

hdr("19. aum exactly 1000.00: what happened before?")
sa = snap.assign(aumn=num(snap.aum)).sort_values(["client_id", "snapshot_date"])
sa["prev_aum"] = sa.groupby("client_id").aumn.shift()
floor = sa.aumn == 1000
print("rows:", int(floor.sum()), " clients:", sa.loc[floor, "client_id"].nunique())
print("rows per year:", sa.loc[floor, "year"].value_counts().sort_index().to_dict())
print("previous month's aum for these rows:")
print(sa.loc[floor, "prev_aum"].describe().to_string())
print("minimum aum that is NOT 1000:", sa.loc[~floor, "aumn"].min())
print(sa.loc[floor, ["client_id", "snapshot_date", "aum", "prev_aum", "return_ytd"]].head(6).to_string(index=False))

hdr("20. Advisory Fee debits vs fact_fees by QUARTER (fees billed quarterly?)")


def qtr(s):
    return s.str[:4] + "Q" + ((num(s.str[5:7]) - 1) // 3 + 1).astype(int).astype(str)


txq = tx.assign(amt=am, q=qtr(tx.txn_date))
txq = txq[txq.txn_type == "Advisory Fee"].groupby(["client_id", "q"]).amt.sum()
for types in (["Management"], ["Management", "Advisory"], sorted(fees.fee_type.unique())):
    fq = fees.assign(amt=fam, q=qtr(fees.fee_date))
    fq = fq[fq.fee_type.isin(types)].groupby(["client_id", "q"]).amt.sum()
    j = pd.concat([txq.rename("tx"), fq.rename("fees")], axis=1)
    both = j.dropna()
    print(f"{types}: both={len(both):,} only_tx={int(j.fees.isna().sum()):,} only_fees={int(j.tx.isna().sum()):,} "
          f"equal within $1={((both.tx - both.fees).abs() <= 1).mean():.2%} median ratio={(both.tx / both.fees).median():.4f}")
print("Advisory Fee debits per client per quarter:",
      tx[tx.txn_type == "Advisory Fee"].assign(q=qtr(tx.txn_date)).groupby(["client_id", "q"]).size().value_counts().sort_index().to_dict())
txa = am[tx.txn_type == "Advisory Fee"]
print("Advisory Fee debit amounts:", txa.describe().round(2).to_dict())

hdr("21. Clients sharing a name: same person?")
nd = cli.duplicated(["first_name", "last_name"], keep=False)
print("rows sharing first+last name:", int(nd.sum()))
for keys in (["first_name", "last_name", "age"], ["first_name", "last_name", "zip_code"],
             ["first_name", "last_name", "city"], ["first_name", "last_name", "age", "zip_code"]):
    print(f"  also sharing {keys[2:]}: {int(cli.duplicated(keys, keep=False).sum())}")

hdr("22. Big returns (|return_ytd| > 1.5 after % fix): which clients?")
big_all = r_fixed.abs() > 1.5
bc = snap.loc[big_all].groupby("client_id").size().sort_values(ascending=False)
print("rows:", int(big_all.sum()), " clients:", len(bc))
print("rows per client:", bc.describe().round(1).to_dict())
print("share of those clients' snapshots that are big:",
      round(big_all.groupby(snap.client_id).sum()[bc.index].sum() / snap.client_id.isin(bc.index).sum(), 3))
print("big rows by account_type:", snap.loc[big_all, "account_type"].value_counts().to_dict())

hdr("16. dim_advisor")
print(adv.to_string(index=False))
print("\ndim_benchmark:")
print(bm.to_string(index=False))
