#!/usr/bin/env python3
"""
HW4 Part D - 03_validate.py
Referential integrity, business rules, cross-table reconciliations, IQR outliers,
and a raw-vs-clean data quality scorecard.

Run from hw04/:   python scripts/03_validate.py

Outputs (reports/):
  data_quality_scorecard.csv   one row per table per stage (raw / clean)
  ri_results.csv               every relationship x stage
  rule_results.csv             every business rule x stage
  reconciliations.csv          cross-table / recompute checks x stage
  iqr_outliers.csv             IQR outlier flags x stage

Scorecard metric definitions (each measures one quality dimension, so they do not overlap):
  pct_completeness       non-blank cells / all cells (original columns only). Legitimate blanks
                         (cash rows, ETF sector, stock expense ratio) lower it by design.
  pct_key_uniqueness     distinct primary-key values / rows.
  pct_type_validity      NON-blank cells that parse as the column's expected type / non-blank cells.
                         Blanks are measured by completeness, not here, so a blank is never counted
                         twice as a defect.
  pct_rule_pass          rule checks passed / rule checks applicable, pooled across the table's rules
                         (per-rule detail is in rule_results.csv).
  pct_referential_match  non-blank foreign-key values found in their dimension / non-blank FK values,
                         pooled across the table's outgoing relationships. Blank when the table has
                         no foreign keys (fk_relationships_checked = 0): not applicable, not 100%.
"""
from pathlib import Path

import pandas as pd

STAGES = {"raw": Path("Wildcat Capital"), "clean": Path("data/clean")}
OUT = Path("reports")
TABLES = ["dim_advisor", "dim_client", "dim_date", "dim_security", "dim_benchmark",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]


# =====================================================================================
#  Reusable referential-integrity check  (keep for Assignment 5)
# =====================================================================================
def check_referential_integrity(fact_df, fact_key, dim_df, dim_key, normalize=None):
    """
    Check that every non-blank value of fact_df[fact_key] exists in dim_df[dim_key].

    By default keys are compared as trimmed text, exactly as a BI tool would join them
    ('447.0' does NOT match '447'), so format defects show up as orphans instead of being hidden.
    For other data, pass normalize=<function applied to each key on both sides>, e.g.
    normalize=lambda k: k.upper() or normalize=lambda k: k.lstrip("0").

    Returns a dict:
      rows                  rows in fact_df
      null_key_rate         share of rows whose key is blank (can be legitimate)
      match_rate            share of NON-blank keys found in the dimension
      orphan_row_count      rows whose non-blank key is not in the dimension
      distinct_orphan_keys  sorted list of those keys
      orphan_rows           DataFrame of the orphan rows (for quarantine/inspection)
    """
    fk = fact_df[fact_key].astype(str).str.strip()
    null = fk.eq("") | fk.str.lower().isin({"nan", "none", "null"})
    dk = dim_df[dim_key].astype(str).str.strip()
    if normalize is not None:
        fk, dk = fk.map(normalize), dk.map(normalize)
    dim_keys = set(dk)
    orphan = ~null & ~fk.isin(dim_keys)
    n_nonnull = int((~null).sum())
    return {
        "rows": len(fk),
        "null_key_rate": float(null.mean()) if len(fk) else 0.0,
        "match_rate": 1 - orphan.sum() / n_nonnull if n_nonnull else 1.0,
        "orphan_row_count": int(orphan.sum()),
        "distinct_orphan_keys": sorted(fk[orphan].unique().tolist()),
        "orphan_rows": fact_df[orphan],
    }


# 10 ID-based relationships + 3 date relationships
RELATIONSHIPS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]

# =====================================================================================
#  Schema: primary keys and expected type of every original column
# =====================================================================================
PK = {"dim_advisor": "advisor_id", "dim_client": "client_id", "dim_date": "date_id",
      "dim_security": "security_id", "dim_benchmark": "benchmark_id", "fact_fees": "fee_id",
      "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}
SCHEMA = {
    "dim_advisor": dict(advisor_id="int", first_name="text", last_name="text", region="text",
                        years_experience="int", aum_target_mm="int", certifications="text"),
    "dim_client": dict(client_id="int", first_name="text", last_name="text", age="int", city="text",
                       state="text", zip_code="zip", risk_profile="text", client_tier="text",
                       primary_account_type="text", initial_aum="dec", client_since="date",
                       advisor_id="int", is_active="bool"),
    "dim_date": dict(date_id="int", date="date", year="int", quarter="int", month="int", month_name="text",
                     week_of_year="int", day_of_week="text", is_month_end="int", is_quarter_end="int",
                     is_year_end="int", is_trading_day="int"),
    "dim_security": dict(security_id="int", ticker="text", name="text", asset_class="text", sector="text",
                         benchmark_id="int", is_etf="bool", expense_ratio_bps="dec"),
    "dim_benchmark": dict(benchmark_id="int", name="text", asset_class="text", ticker_proxy="text"),
    "fact_fees": dict(fee_id="int", client_id="int", advisor_id="int", fee_date="date", fee_type="text",
                      aum_basis="dec", bps_charged="dec", amount="dec"),
    "fact_portfolio_snapshot": dict(snapshot_id="int", client_id="int", advisor_id="int", benchmark_id="int",
                                    snapshot_date="date", year="int", month="int", aum="dec", return_ytd="dec",
                                    benchmark_return_ytd="dec", active_alpha_ytd="dec", cash_pct="dec",
                                    account_type="text"),
    "fact_transactions": dict(txn_id="int", client_id="int", advisor_id="int", security_id="int",
                              txn_date="date", txn_type="text", shares="dec", price="dec", amount="dec"),
}
PATTERNS = {"int": r"-?\d+", "dec": r"-?(\d+(\.\d*)?|\.\d+)", "date": r"\d{4}-\d{2}-\d{2}",
            "bool": r"True|False", "zip": r"\d{5}"}

# =====================================================================================
#  Allowed code lists
# =====================================================================================
USPS = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ "
           "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
REGIONS = {"Northeast", "Southeast", "Mid-Atlantic", "Midwest", "West"}
CERTS = {"CFA", "CFP", "CIMA", "CFP, CFA", "CFP, CIMA", "None"}      # 'None' = no certification (D11)
RISK = {"Conservative", "Moderately Conservative", "Balanced", "Moderately Aggressive", "Aggressive"}
TIERS = {"Retail", "HNW", "UHNW"}
ACCOUNTS = {"Taxable", "IRA", "Roth IRA", "Trust", "529"}
ASSET_CLASSES = {"Equity", "Fixed Income", "Alternative", "Cash Equivalent"}
SECTORS = {"Communication Services", "Consumer Discretionary", "Consumer Staples", "Energy", "Financials",
           "Healthcare", "Industrials", "Materials", "Real Estate", "Technology", "Utilities"}
FEE_TYPES = {"Management", "Advisory", "Custodial", "Performance"}
TXN_TYPES = {"Buy", "Sell", "Dividend", "Deposit", "Withdrawal", "Advisory Fee"}
SECURITY_TXN = {"Buy", "Sell", "Dividend"}
RISK_TO_BENCHMARK = {"Aggressive": "1", "Moderately Aggressive": "1", "Balanced": "3",
                     "Conservative": "8", "Moderately Conservative": "8"}


def n(s):
    return pd.to_numeric(s, errors="coerce")


def between(s, lo, hi):
    v = n(s)
    return (v >= lo) & (v <= hi)




# Each rule: (table, rule name, applicable(df) -> mask, passes(df, tables) -> mask)
def everyone(df):
    return pd.Series(True, index=df.index)


def nonblank(col):
    return lambda df: df[col] != ""


RULES = [
    # dim_advisor
    ("dim_advisor", "years_experience 0-60", everyone, lambda d, T: between(d.years_experience, 0, 60)),
    ("dim_advisor", "aum_target_mm > 0", everyone, lambda d, T: n(d.aum_target_mm) > 0),
    ("dim_advisor", "region in allowed list", everyone, lambda d, T: d.region.isin(REGIONS)),
    ("dim_advisor", "certifications in allowed list", everyone, lambda d, T: d.certifications.isin(CERTS)),
    # dim_client
    ("dim_client", "age 18-110", everyone, lambda d, T: between(d.age, 18, 110)),
    ("dim_client", "zip_code is 5 digits", everyone, lambda d, T: d.zip_code.str.fullmatch(r"\d{5}")),
    ("dim_client", "state is a USPS code", everyone, lambda d, T: d.state.isin(USPS)),
    ("dim_client", "risk_profile in allowed list (when present)", nonblank("risk_profile"),
     lambda d, T: d.risk_profile.isin(RISK)),
    ("dim_client", "client_tier in allowed list", everyone, lambda d, T: d.client_tier.isin(TIERS)),
    ("dim_client", "primary_account_type in allowed list", everyone, lambda d, T: d.primary_account_type.isin(ACCOUNTS)),
    ("dim_client", "initial_aum > 0", everyone, lambda d, T: n(d.initial_aum) > 0),
    ("dim_client", "client_since <= 2024-12-31", everyone, lambda d, T: d.client_since <= "2024-12-31"),
    ("dim_client", "is_active True/False", everyone, lambda d, T: d.is_active.isin({"True", "False"})),
    # dim_date
    ("dim_date", "quarter 1-4", everyone, lambda d, T: between(d.quarter, 1, 4)),
    ("dim_date", "month 1-12", everyone, lambda d, T: between(d.month, 1, 12)),
    ("dim_date", "week_of_year 1-53", everyone, lambda d, T: between(d.week_of_year, 1, 53)),
    ("dim_date", "is_* flags are 0/1", everyone,
     lambda d, T: d[["is_month_end", "is_quarter_end", "is_year_end", "is_trading_day"]].isin({"0", "1"}).all(axis=1)),
    ("dim_date", "year matches date", everyone, lambda d, T: d.year == d.date.str[:4]),
    # dim_security
    ("dim_security", "ticker is 1-5 capital letters", everyone, lambda d, T: d.ticker.str.fullmatch(r"[A-Z]{1,5}")),
    ("dim_security", "ticker unique", everyone, lambda d, T: ~d.ticker.duplicated(keep=False)),
    ("dim_security", "asset_class in allowed list", everyone, lambda d, T: d.asset_class.isin(ASSET_CLASSES)),
    ("dim_security", "sector blank iff ETF, else allowed", everyone,
     lambda d, T: ((d.is_etf == "True") & (d.sector == "")) | ((d.is_etf == "False") & d.sector.isin(SECTORS))),
    ("dim_security", "expense_ratio present iff ETF, 0-300 bps", everyone,
     lambda d, T: ((d.is_etf == "True") & between(d.expense_ratio_bps, 0, 300))
     | ((d.is_etf == "False") & (d.expense_ratio_bps == ""))),
    # dim_benchmark
    ("dim_benchmark", "name present", everyone, lambda d, T: d.name != ""),
    # fact_fees
    ("fact_fees", "fee_type in allowed list", everyone, lambda d, T: d.fee_type.isin(FEE_TYPES)),
    ("fact_fees", "aum_basis > 0", everyone, lambda d, T: n(d.aum_basis) > 0),
    ("fact_fees", "bps_charged 0-300", everyone, lambda d, T: between(d.bps_charged, 0, 300)),
    ("fact_fees", "amount > 0", everyone, lambda d, T: n(d.amount) > 0),
    ("fact_fees", "fee_date is 1st of month", everyone, lambda d, T: d.fee_date.str[8:10] == "01"),
    # fact_portfolio_snapshot
    ("fact_portfolio_snapshot", "aum > 0", everyone, lambda d, T: n(d.aum) > 0),
    ("fact_portfolio_snapshot", "cash_pct 0-1", everyone, lambda d, T: between(d.cash_pct, 0, 1)),
    ("fact_portfolio_snapshot", "return_ytd >= -1 (cannot lose >100%)", everyone, lambda d, T: n(d.return_ytd) >= -1),
    ("fact_portfolio_snapshot", "benchmark_return_ytd -1 to 1", everyone, lambda d, T: between(d.benchmark_return_ytd, -1, 1)),
    ("fact_portfolio_snapshot", "year 2020-2024", everyone, lambda d, T: between(d.year, 2020, 2024)),
    ("fact_portfolio_snapshot", "month 1-12", everyone, lambda d, T: between(d.month, 1, 12)),
    ("fact_portfolio_snapshot", "snapshot_date is 1st of month", everyone, lambda d, T: d.snapshot_date.str[8:10] == "01"),
    ("fact_portfolio_snapshot", "account_type in allowed list", everyone, lambda d, T: d.account_type.isin(ACCOUNTS)),
    # fact_transactions
    ("fact_transactions", "txn_type in allowed list", everyone, lambda d, T: d.txn_type.isin(TXN_TYPES)),
    ("fact_transactions", "amount > 0", everyone, lambda d, T: n(d.amount) > 0),
    ("fact_transactions", "shares > 0 on Buy/Sell/Dividend (sign rule)", lambda d: d.txn_type.isin(SECURITY_TXN),
     lambda d, T: n(d.shares) > 0),
    ("fact_transactions", "security_id present on Buy/Sell/Dividend", lambda d: d.txn_type.isin(SECURITY_TXN),
     lambda d, T: d.security_id != ""),
    ("fact_transactions", "price > 0 on Buy/Sell/Dividend", lambda d: d.txn_type.isin(SECURITY_TXN),
     lambda d, T: n(d.price) > 0),
    ("fact_transactions", "security/shares/price blank on cash types", lambda d: ~d.txn_type.isin(SECURITY_TXN),
     lambda d, T: (d[["security_id", "shares", "price"]] == "").all(axis=1)),
    ("fact_transactions", "txn_date within 2020-2024", everyone,
     lambda d, T: (d.txn_date >= "2020-01-01") & (d.txn_date <= "2024-12-31")),
]


# =====================================================================================
#  Cross-table reconciliations: each returns (rows compared, rows matched)
# =====================================================================================
def rec_fee_recompute(T):
    f = T["fact_fees"]
    calc = n(f.aum_basis) * n(f.bps_charged) / 10000 / 12
    return len(f), int(((calc - n(f.amount)).abs() <= 0.01).sum())


def rec_fee_aum_vs_snapshot(T):
    f, s = T["fact_fees"], T["fact_portfolio_snapshot"]
    m = f.merge(s[["client_id", "snapshot_date", "aum"]].drop_duplicates(["client_id", "snapshot_date"]),
                left_on=["client_id", "fee_date"], right_on=["client_id", "snapshot_date"], how="left")
    return len(m), int(((n(m.aum_basis) - n(m.aum)).abs() <= 0.01).sum())


def rec_alpha_identity(T):
    s = T["fact_portfolio_snapshot"]
    diff = n(s.active_alpha_ytd) - (n(s.return_ytd) - n(s.benchmark_return_ytd))
    return len(s), int((diff.abs() < 1e-4).sum())


def rec_trade_amount(T):
    t = T["fact_transactions"]
    t = t[t.txn_type.isin(SECURITY_TXN)]
    amt = n(t.amount)
    ok = (n(t.shares) * n(t.price) - amt).abs() <= (amt.abs() * 0.005).clip(lower=0.01)
    return len(t), int(ok.sum())


def rec_benchmark_vs_risk(T):
    s, c = T["fact_portfolio_snapshot"], T["dim_client"]
    expected = s.client_id.map(dict(zip(c.client_id, c.risk_profile))).map(RISK_TO_BENCHMARK)
    has = expected.notna()
    return int(has.sum()), int((s.benchmark_id[has] == expected[has]).sum())


def rec_advisor_consistency(T):
    c = T["dim_client"]
    adv = dict(zip(c.client_id, c.advisor_id))
    total = ok = 0
    for t in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
        exp = T[t].client_id.map(adv)
        has = exp.notna()
        total += int(has.sum())
        ok += int((T[t].advisor_id[has] == exp[has]).sum())
    return total, ok


RECONCILIATIONS = [
    ("fact_fees", "amount = aum_basis x bps / 10000 / 12", rec_fee_recompute),
    ("fact_fees vs fact_portfolio_snapshot", "aum_basis = snapshot aum (same client-month)", rec_fee_aum_vs_snapshot),
    ("fact_portfolio_snapshot", "active_alpha = return_ytd - benchmark_return_ytd", rec_alpha_identity),
    ("fact_transactions", "shares x price = amount (Buy/Sell/Dividend)", rec_trade_amount),
    ("fact_portfolio_snapshot vs dim_client", "benchmark_id matches client risk_profile", rec_benchmark_vs_risk),
    ("facts vs dim_client", "fact advisor_id = client's advisor", rec_advisor_consistency),
]

# IQR: numeric columns with no natural upper bound
IQR_COLUMNS = [("fact_transactions", "amount"), ("fact_portfolio_snapshot", "aum"), ("fact_fees", "amount")]
IQR_SENTENCE = ("Flagged does not mean wrong: these amounts are heavily right-skewed because Wildcat serves "
                "Retail, HNW and UHNW clients, so the IQR rule flags many legitimate large accounts and trades; "
                "the flags direct review and are never used to change or delete data.")


# =====================================================================================
#  Run one stage
# =====================================================================================
def load(stage_dir):
    return {t: pd.read_csv(stage_dir / f"{t}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
            for t in TABLES}


def run_stage(stage, T):
    ri_rows, rule_rows, rec_rows, iqr_rows, score = [], [], [], [], []

    # referential integrity
    ri_by_table = {}
    for ft, fk, dt, dk in RELATIONSHIPS:
        r = check_referential_integrity(T[ft], fk, T[dt], dk)
        nonnull = round(r["rows"] * (1 - r["null_key_rate"]))
        ri_rows.append({"stage": stage, "relationship": f"{ft}.{fk} -> {dt}.{dk}", "rows": r["rows"],
                        "null_key_rate": round(r["null_key_rate"], 6), "match_rate": round(r["match_rate"], 6),
                        "orphan_rows": r["orphan_row_count"], "distinct_orphan_keys": len(r["distinct_orphan_keys"]),
                        "orphan_key_examples": " | ".join(r["distinct_orphan_keys"][:5])})
        agg = ri_by_table.setdefault(ft, [0, 0, 0])
        agg[0] += nonnull
        agg[1] += nonnull - r["orphan_row_count"]
        agg[2] += 1

    # business rules
    rules_by_table = {}
    for t, name, applies, passes in RULES:
        d = T[t]
        app = applies(d).fillna(False).astype(bool)
        ok = passes(d, T).fillna(False).astype(bool) & app
        rule_rows.append({"stage": stage, "table": t, "rule": name, "applicable_rows": int(app.sum()),
                          "passed": int(ok.sum()), "failed": int(app.sum() - ok.sum()),
                          "pass_rate": round(ok.sum() / app.sum(), 6) if app.sum() else 1.0})
        agg = rules_by_table.setdefault(t, [0, 0])
        agg[0] += int(app.sum())
        agg[1] += int(ok.sum())

    # reconciliations
    for scope, name, fn in RECONCILIATIONS:
        total, ok = fn(T)
        rec_rows.append({"stage": stage, "scope": scope, "reconciliation": name, "rows_compared": total,
                         "rows_matched": ok, "match_rate": round(ok / total, 6) if total else 1.0})

    # IQR outliers
    for t, col in IQR_COLUMNS:
        v = n(T[t][col]).dropna()
        q1, q3 = v.quantile(0.25), v.quantile(0.75)
        lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        flagged = (v < lo) | (v > hi)
        iqr_rows.append({"stage": stage, "table": t, "column": col, "q1": round(q1, 2), "q3": round(q3, 2),
                         "lower_fence": round(lo, 2), "upper_fence": round(hi, 2), "rows": len(v),
                         "flagged": int(flagged.sum()), "pct_flagged": round(flagged.mean(), 6),
                         "max_value": round(v.max(), 2), "interpretation": IQR_SENTENCE})

    # scorecard
    for t in TABLES:
        d = T[t]
        cols = [c for c in SCHEMA[t] if c in d.columns]
        missing_cols = set(SCHEMA[t]) - set(d.columns)
        assert not missing_cols, f"{stage}/{t}: columns missing from file: {missing_cols}"
        cells = d[cols]
        nonblank_cells = cells != ""
        valid = 0
        for c in cols:
            typ = SCHEMA[t][c]
            nb = d[c] != ""
            if typ == "text":
                ok = nb
            else:
                ok = nb & d[c].str.fullmatch(PATTERNS[typ]).fillna(False)
                if typ == "date":
                    ok &= pd.to_datetime(d[c].where(ok), format="%Y-%m-%d", errors="coerce").notna()
            valid += int(ok.sum())
        ri = ri_by_table.get(t)
        rl = rules_by_table.get(t, [0, 0])
        score.append({
            "table": t, "stage": stage, "rows": len(d),
            "pct_completeness": round(100 * nonblank_cells.values.mean(), 4),
            "pct_key_uniqueness": round(100 * d[PK[t]].nunique() / len(d), 4),
            "pct_type_validity": round(100 * valid / nonblank_cells.values.sum(), 4),
            "pct_rule_pass": round(100 * rl[1] / rl[0], 4) if rl[0] else 100.0,
            "pct_referential_match": round(100 * ri[1] / ri[0], 4) if ri else None,
            "fk_relationships_checked": ri[2] if ri else 0,
        })
    return ri_rows, rule_rows, rec_rows, iqr_rows, score


def main():
    OUT.mkdir(exist_ok=True)
    results = {k: [] for k in ["ri", "rules", "rec", "iqr", "score"]}
    for stage, path in STAGES.items():
        print(f"Validating {stage} tables from {path}/ ...")
        for key, rows in zip(results, run_stage(stage, load(path))):
            results[key].extend(rows)

    ri = pd.DataFrame(results["ri"])
    rules = pd.DataFrame(results["rules"])
    rec = pd.DataFrame(results["rec"])
    iqr = pd.DataFrame(results["iqr"])
    score = pd.DataFrame(results["score"]).sort_values(["table", "stage"], ascending=[True, False])

    ri.to_csv(OUT / "ri_results.csv", index=False)
    rules.to_csv(OUT / "rule_results.csv", index=False)
    rec.to_csv(OUT / "reconciliations.csv", index=False)
    iqr.to_csv(OUT / "iqr_outliers.csv", index=False)
    score.to_csv(OUT / "data_quality_scorecard.csv", index=False)

    pd.set_option("display.width", 220)
    print("\n=== Referential integrity (13 relationships) ===")
    print(ri.pivot(index="relationship", columns="stage", values="match_rate")[["raw", "clean"]].to_string())
    print("\n=== Business rules that fail in either stage ===")
    pv = rules.pivot_table(index=["table", "rule"], columns="stage", values="failed", aggfunc="sum")[["raw", "clean"]]
    print(pv[(pv.raw > 0) | (pv.clean > 0)].to_string() if ((pv.raw > 0) | (pv.clean > 0)).any() else "none")
    print(f"({len(RULES)} rules checked in total)")
    print("\n=== Cross-table reconciliations (match rate) ===")
    print(rec.pivot(index="reconciliation", columns="stage", values="match_rate")[["raw", "clean"]].to_string())
    print("\n=== IQR outliers (clean) ===")
    print(iqr[iqr.stage == "clean"][["table", "column", "upper_fence", "flagged", "pct_flagged", "max_value"]].to_string(index=False))
    print(IQR_SENTENCE)
    print("\n=== Data quality scorecard ===")
    print(score.to_string(index=False))
    print(f"\nSaved scorecard, RI, rules, reconciliations and IQR results to {OUT}/")


if __name__ == "__main__":
    main()
