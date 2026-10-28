#!/usr/bin/env python3
"""
HW4 Part C - 02_clean.py
Reads the eight raw Wildcat Capital tables, applies the decisions in decision_log.md
one at a time, and writes a NEW set of eight tables plus an audit trail.

Run from hw04/:   python scripts/02_clean.py

  * raw files are never modified (checked by file hash at the end)
  * after every step: rows affected, a before/after check, and an assert
    (the script stops if a fix did not do what the decision log claims)
  * nothing is deleted silently: removed rows go to data/audit/quarantine_*.csv,
    and raw rows = clean rows + quarantined rows is asserted for every table

Outputs
  data/clean/<same 8 file names>.csv
  data/audit/cleaning_log.csv      table, issue, action, rows_affected, note
  data/audit/value_changes.csv     table, key_column, key, column, old_value, new_value
  data/audit/quarantine_*.csv      one file per quarantined set
"""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("Wildcat Capital")
CLEAN = Path("data/clean")
AUDIT = Path("data/audit")

TABLES = ["dim_advisor", "dim_client", "dim_date", "dim_security", "dim_benchmark",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]
KEYS = {"dim_advisor": "advisor_id", "dim_client": "client_id", "dim_date": "date_id",
        "dim_security": "security_id", "dim_benchmark": "benchmark_id", "fact_fees": "fee_id",
        "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

STATE_MAP = {"Pennsylvania": "PA", "Florida": "FL", "New York": "NY", "New Jersey": "NJ",
             "California": "CA", "Illinois": "IL", "Texas": "TX"}
CASH_TYPES = {"Deposit", "Withdrawal", "Advisory Fee"}   # no security, shares or price (D4)
TRADE_TYPES = {"Buy", "Sell"}                            # exchange trades (D17)
RETURN_OUTLIER = 1.5                                     # |YTD return| above 150% (D14)
AUM_FLOOR = 1000.0                                       # system floor value (D15)

LOG, CHANGES, QUARANTINE = [], [], {}


# ------------------------------------------------------------------ helpers
def num(s):
    return pd.to_numeric(s, errors="coerce")


def fmt(x):
    """Plain decimal text, shortest exact form: 2e-05 -> '0.00002'."""
    return np.format_float_positional(float(x), trim="-")


def header(n, title):
    print(f"\n{'=' * 78}\nStep {n}: {title}\n{'=' * 78}")


def log(table, issue, action, rows, note=""):
    LOG.append({"table": table, "issue": issue, "action": action, "rows_affected": int(rows), "note": note})
    print(f"   logged -> {action} | {int(rows):,} rows | {note}")


def change(table, df, col, mask, new_values):
    """Apply new values to df.loc[mask, col] and record every old -> new pair."""
    key = KEYS[table]
    new_values = pd.Series(new_values, index=df.index[mask]).astype(str)
    CHANGES.append(pd.DataFrame({
        "table": table, "key_column": key, "key": df.loc[mask, key].values, "column": col,
        "old_value": df.loc[mask, col].values, "new_value": new_values.values,
    }))
    df.loc[mask, col] = new_values


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ load
raw_hash = {t: md5(RAW / f"{t}.csv") for t in TABLES}
T = {t: pd.read_csv(RAW / f"{t}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig") for t in TABLES}
RAW_ROWS = {t: len(df) for t, df in T.items()}
RAW_COLS = {t: list(df.columns) for t, df in T.items()}
adv, cli, dd, sec = T["dim_advisor"], T["dim_client"], T["dim_date"], T["dim_security"]
fees, snap, tx = T["fact_fees"], T["fact_portfolio_snapshot"], T["fact_transactions"]
RAW_TX = T["fact_transactions"].copy()                   # untouched copy, used for the quarantine file
RAW_TX.insert(0, "raw_line_number", RAW_TX.index + 2)   # line in the raw CSV (+1 header, +1 for 1-based)
print("Loaded raw rows:", RAW_ROWS)

# ------------------------------------------------------------------ step 0
header(0, "Guard: stray whitespace in any cell (profile found none)")
def ws_cells():
    return sum(int((df[c] != df[c].str.strip()).sum()) for df in T.values() for c in df.columns)


ws_before = ws_cells()
total_ws = 0
for t, df in T.items():
    for c in df.columns:
        m = df[c] != df[c].str.strip()
        if m.any():
            change(t, df, c, m, df.loc[m, c].str.strip())
            log(t, f"whitespace in {c}", "standardize (trim)", m.sum())
            total_ws += int(m.sum())
ws_after = ws_cells()
print(f"cells with stray whitespace: before {ws_before} -> after {ws_after} | cells trimmed: {total_ws}")
assert ws_after == 0 and total_ws == ws_before

# ------------------------------------------------------------------ step 1  (D1)
header(1, "fact_transactions.security_id '447.0' -> '447'  [D1]")
dim_sec = set(sec.security_id)
nb = tx.security_id != ""
before = tx.security_id[nb].isin(dim_sec).mean()
assert not tx.security_id.str.contains(r"\.\d*[1-9]").any(), "an ID has a non-zero decimal: stripping would merge IDs"
m = tx.security_id.str.fullmatch(r"\d+\.0+")
change("fact_transactions", tx, "security_id", m, tx.loc[m, "security_id"].str.replace(r"\.0+$", "", regex=True))
after = tx.security_id[nb].isin(dim_sec).mean()
print(f"rows changed: {m.sum():,} | FK match to dim_security: {before:.2%} -> {after:.2%}")
assert after == 1.0, "security_id still has orphans after the fix"
assert not tx.security_id.str.contains(r"\.").any()
log("fact_transactions", "security_id stored as decimal ('447.0')", "convert", m.sum(),
    f"FK match {before:.2%} -> {after:.2%}")

# ------------------------------------------------------------------ step 2  (D5)
header(2, "dim_client.state full names -> USPS codes  [D5]")
is_code = cli.state.str.fullmatch(r"[A-Z]{2}")
codes_before = set(cli.state[is_code])
unmapped = set(cli.state[~is_code]) - set(STATE_MAP)
assert not unmapped, f"state values with no mapping: {unmapped}"
assert set(cli.state[~is_code].map(STATE_MAP)) <= codes_before, "a mapped code is not already in use"
n_before = cli.state.nunique()
m = cli.state.isin(STATE_MAP)
old_state = cli.loc[m, "state"].copy()
change("dim_client", cli, "state", m, cli.loc[m, "state"].map(STATE_MAP))
assert (cli.loc[m, "state"] == old_state.map(STATE_MAP)).all(), "a row was not mapped to its own code"
print(f"rows changed: {m.sum()} | distinct states: {n_before} -> {cli.state.nunique()}")
assert cli.state.str.fullmatch(r"[A-Z]{2}").all()
assert set(cli.state) == codes_before
log("dim_client", "state mixes codes and full names", "standardize", m.sum(),
    f"distinct values {n_before} -> {cli.state.nunique()}")


# ------------------------------------------------------------------ step 3  (D12)
def alpha_identity(s):
    r, b, a = num(s.return_ytd), num(s.benchmark_return_ytd), num(s.active_alpha_ytd)
    return ((a - (r - b)).abs() < 1e-4).mean()


header(3, "fact_portfolio_snapshot.return_ytd '-0.64%' -> -0.0064  [D12]")
before = alpha_identity(snap)
m = snap.return_ytd.str.endswith("%")
new = snap.loc[m, "return_ytd"].str.rstrip("%").astype(float).div(100).round(10).map(fmt)
change("fact_portfolio_snapshot", snap, "return_ytd", m, new)
after = alpha_identity(snap)
print(f"rows changed: {m.sum()} | alpha = return - benchmark holds: {before:.4%} -> {after:.4%}")
assert after == 1.0, "alpha identity does not hold for every row after the % conversion"
assert not snap.return_ytd.str.contains("%").any()
log("fact_portfolio_snapshot", "return_ytd stored as % string", "convert", m.sum(),
    f"reconciled: alpha identity {before:.4%} -> {after:.4%}")

# ------------------------------------------------------------------ step 4  (D13)
header(4, "Scientific notation -> plain decimals (value unchanged)  [D13]")
for col in ["return_ytd", "active_alpha_ytd"]:
    m = snap[col].str.contains(r"[eE]")
    old = num(snap.loc[m, col])
    change("fact_portfolio_snapshot", snap, col, m, old.map(fmt))
    print(f"{col}: rows changed {m.sum()}")
    assert (num(snap.loc[m, col]).values == old.values).all(), f"{col}: numeric value changed"
    assert not snap[col].str.contains(r"[eE]").any()
    log("fact_portfolio_snapshot", f"{col} in scientific notation", "standardize", m.sum(), "numeric value identical")
assert alpha_identity(snap) == 1.0

# ------------------------------------------------------------------ step 5  (D2)
header(5, "fact_transactions.shares: negative Buys -> positive  [D2]")
sh, pr, am = num(tx.shares), num(tx.price), num(tx.amount)
tol = (am.abs() * 0.005).clip(lower=0.01)
m = sh < 0
assert set(tx.loc[m, "txn_type"]) == {"Buy"}, "negative shares outside Buy: decision log does not cover this"
assert ((sh.abs() * pr - am).abs() <= tol)[m].all(), "|shares| x price does not reconcile to amount"
change("fact_transactions", tx, "shares", m, tx.loc[m, "shares"].str.lstrip("-"))
sh2 = num(tx.shares)
trade = tx.security_id != ""
recon = ((sh2 * pr - am).abs() <= tol)[trade].mean()
print(f"rows changed: {m.sum()} | negative shares now: {(sh2 < 0).sum()} | shares x price = amount on trade rows: {recon:.2%}")
assert (sh2[trade] > 0).all()
assert recon == 1.0
log("fact_transactions", "negative shares on Buy", "standardize (absolute value)", m.sum(),
    "reconciled: |shares| x price = amount for 100% of affected rows")

# ------------------------------------------------------------------ step 6  (D3)
header(6, "Quarantine transactions whose client_id is not in dim_client  [D3]")
dim_cli = set(cli.client_id)
m = ~tx.client_id.isin(dim_cli)
# No row has been removed or reordered yet, so tx's index still points at the raw CSV row (asserted)
assert tx.index.equals(RAW_TX.index) and (tx.txn_id == RAW_TX.txn_id).all(), "row order changed before quarantine"
q = RAW_TX.loc[m[m].index].copy()                     # quarantine the ORIGINAL raw values
ids = num(q.client_id)
q["quarantine_reason"] = (f"client_id not in dim_client (orphan FK, ids {ids.min():.0f}-{ids.max():.0f}); "
                          "values are exactly as in the raw file")
QUARANTINE["fact_transactions_orphan_client"] = ("fact_transactions", q)
amt = num(q.amount).sum()
tx = tx[~m].copy()
T["fact_transactions"] = tx
print(f"rows quarantined: {len(q)} | distinct ids: {q.client_id.nunique()} | amount: ${amt:,.2f}")
assert tx.client_id.isin(dim_cli).all()
assert len(tx) + len(q) == RAW_ROWS["fact_transactions"]
log("fact_transactions", "orphan client_id", "quarantine", len(q), f"amount ${amt:,.2f} removed from clean data")

# ------------------------------------------------------------------ step 7  flags
header(7, "Flag columns (0/1) for values that cannot be corrected without inventing data")


def add_flag(table, df, name, mask, issue, note):
    df[name] = mask.astype(int)
    assert df[name].isin([0, 1]).all() and df[name].sum() == int(mask.sum())
    print(f"{table}.{name}: {int(mask.sum()):,} rows flagged")
    log(table, issue, f"flag ({name})", mask.sum(), note)


add_flag("dim_client", cli, "risk_profile_missing_flag", cli.risk_profile == "",
         "risk_profile blank [D6]", "left blank: a suitability rating must not be invented")

r, a = num(snap.return_ytd), num(snap.active_alpha_ytd)
add_flag("fact_portfolio_snapshot", snap, "return_outlier_flag",
         (r.abs() > RETURN_OUTLIER) | (a.abs() > RETURN_OUTLIER),
         "implausible YTD return/alpha [D14]",
         f"|return|>{RETURN_OUTLIER}: {(r.abs() > RETURN_OUTLIER).sum()}, |alpha|>{RETURN_OUTLIER}: {(a.abs() > RETURN_OUTLIER).sum()}; values unchanged")

add_flag("fact_portfolio_snapshot", snap, "aum_floor_flag", num(snap.aum) == AUM_FLOOR,
         "aum at 1000.00 system floor [D15]", "value unchanged")
add_flag("fact_fees", fees, "aum_floor_flag", num(fees.aum_basis) == AUM_FLOOR,
         "aum_basis at 1000.00 system floor [D15]", "value unchanged")

trading = tx.txn_date.map(dict(zip(dd.date, dd.is_trading_day)))
assert trading.notna().all(), "a txn_date is missing from dim_date"
add_flag("fact_transactions", tx, "non_trading_day_trade_flag",
         tx.txn_type.isin(TRADE_TYPES) & (trading == "0"),
         "Buy/Sell dated on a non-trading day [D17]", "date unchanged")

# ------------------------------------------------------------------ step 8  legitimate structure
header(8, "Verify structures we decided to LEAVE AS IS (asserts, no changes)")
cash = tx.txn_type.isin(CASH_TYPES)
for col in ["security_id", "shares", "price"]:
    assert ((tx[col] == "") == cash).all(), f"{col}: blank does not line up with cash txn_types"
log("fact_transactions", "blank security_id/shares/price [D4]", "leave as is", 0,
    f"verified: blank on exactly the {cash.sum():,} cash rows (Deposit/Withdrawal/Advisory Fee)")

etf = sec.is_etf == "True"
assert ((sec.sector == "") == etf).all() and ((sec.expense_ratio_bps == "") == ~etf).all()
log("dim_security", "blank sector / expense_ratio_bps [D9]", "leave as is", 0,
    f"verified: sector blank on exactly {etf.sum()} ETFs, expense ratio blank on exactly {(~etf).sum()} stocks")

since = dict(zip(cli.client_id, cli.client_since))
for t, df, dc in [("fact_fees", fees, "fee_date"), ("fact_portfolio_snapshot", snap, "snapshot_date")]:
    s = df.client_id.map(since)
    early = df[dc] < s
    assert (df.loc[early, dc].str[:7] == s[early].str[:7]).all(), f"{t}: a row is in a month before client_since"
    log(t, "dated before client_since [D16]", "leave as is", 0,
        f"verified: all {early.sum()} such rows are in the client's first month (monthly grain)")
# Transactions are DAILY grain, so the same-month allowance above does not apply: no trade may precede client_since
early_tx = int((tx.txn_date < tx.client_id.map(since)).sum())
assert early_tx == 0, f"{early_tx} transactions dated before client_since"
log("fact_transactions", "dated before client_since [D16]", "leave as is", 0,
    "verified: 0 transactions before client_since (daily grain, so no same-month allowance)")

log("dim_advisor", "certifications = 'None' [D11]", "leave as is", 0,
    f"{(adv.certifications == 'None').sum()} advisors with no certifications; real value, not missing")
log("fact_transactions", "Advisory Fee debits vs fact_fees [D19]", "leave as is", 0,
    "cannot be reconciled at month or quarter grain; fact_fees is the system of record")

# ------------------------------------------------------------------ step 9  reconciliations still hold
header(9, "Cross-table reconciliations after cleaning")
calc = num(fees.aum_basis) * num(fees.bps_charged) / 10000 / 12
fee_ok = ((calc - num(fees.amount)).abs() <= 0.01).mean()
mrg = fees.merge(snap[["client_id", "snapshot_date", "aum"]], left_on=["client_id", "fee_date"],
                 right_on=["client_id", "snapshot_date"], how="left")
aum_ok = ((num(mrg.aum_basis) - num(mrg.aum)).abs() <= 0.01).mean()
print(f"fee amount = aum_basis x bps / 10000 / 12: {fee_ok:.2%}")
print(f"fee aum_basis = snapshot aum (same client-month): {aum_ok:.2%}")
print(f"snapshot alpha = return - benchmark: {alpha_identity(snap):.2%}")
assert fee_ok == 1.0 and aum_ok == 1.0 and alpha_identity(snap) == 1.0

# ------------------------------------------------------------------ write + conservation
header(10, "Row conservation, column check, write outputs")
q_rows = {t: 0 for t in TABLES}
for name, (t, qdf) in QUARANTINE.items():
    q_rows[t] += len(qdf)
summary = []
for t in TABLES:
    df = T[t]
    assert list(df.columns[:len(RAW_COLS[t])]) == RAW_COLS[t], f"{t}: original columns changed"
    extra = list(df.columns[len(RAW_COLS[t]):])
    assert all(c.endswith("_flag") for c in extra), f"{t}: unexpected new column {extra}"
    assert RAW_ROWS[t] == len(df) + q_rows[t], f"{t}: rows not conserved"
    summary.append({"table": t, "raw_rows": RAW_ROWS[t], "clean_rows": len(df), "quarantined_rows": q_rows[t],
                    "raw = clean + quarantined": RAW_ROWS[t] == len(df) + q_rows[t], "flag_columns_added": ", ".join(extra)})
print(pd.DataFrame(summary).to_string(index=False))

CLEAN.mkdir(parents=True, exist_ok=True)
AUDIT.mkdir(parents=True, exist_ok=True)
for t in TABLES:
    T[t].to_csv(CLEAN / f"{t}.csv", index=False)
pd.DataFrame(LOG).to_csv(AUDIT / "cleaning_log.csv", index=False)
pd.concat(CHANGES, ignore_index=True).to_csv(AUDIT / "value_changes.csv", index=False)
for name, (t, qdf) in QUARANTINE.items():
    qdf.to_csv(AUDIT / f"quarantine_{name}.csv", index=False)

for t in TABLES:
    assert md5(RAW / f"{t}.csv") == raw_hash[t], f"raw file {t} was modified!"
n_changes = sum(len(c) for c in CHANGES)
print(f"\nRaw files unchanged (hash check passed). value_changes rows: {n_changes:,}")
print(f"Wrote 8 clean tables to {CLEAN}/ and the audit trail to {AUDIT}/")
