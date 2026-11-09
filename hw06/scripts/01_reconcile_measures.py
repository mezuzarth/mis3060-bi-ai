"""
HW6 Part B - Reconcile every Power BI measure to an independent pandas calculation.

Run from anywhere:   python scripts/01_reconcile_measures.py

Inputs
  - Wildcat Capital Clean CSVs (looked up in hw06/, hw06/data/ or WILDCAT_DATA_DIR;
    file names may carry a download suffix such as "fact_fees (3).csv")
  - reports/powerbi_values.csv   columns: measure, slice, value   (exported from DAX query view)

Outputs
  - reports/pandas_values.csv           every pandas value (always written)
  - reports/measure_reconciliation.csv  measure, slice, powerbi_value, pandas_value, abs_diff, match

The pandas side NEVER reads anything from Power BI: every value is recomputed from the CSVs,
mirroring the filter context each DAX measure sees.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HW_DIR = Path(__file__).resolve().parents[1]
REPORTS = HW_DIR / "reports"

# ----------------------------------------------------------------------------- tolerances
CURRENCY = {
    "AUM (naive SUM)", "Ending AUM", "Avg AUM per Client", "Ending AUM LY",
    "Ending AUM PM", "Avg Monthly AUM", "Total Fees", "Net Flows",
}
COUNT = {"Ending Clients"}
TEXT = {"Alpha Signal"}
TOL_CURRENCY = 0.01
TOL_RATIO = 0.0001   # applies to %, ratios and bps


# ----------------------------------------------------------------------------- load data
def find_csv(stem: str) -> Path:
    """Find '<stem>.csv' or '<stem> (n).csv' in the usual places."""
    folders = [Path(os.environ["WILDCAT_DATA_DIR"])] if "WILDCAT_DATA_DIR" in os.environ else []
    folders += [HW_DIR, HW_DIR / "data", HW_DIR.parent / "data"]
    for folder in folders:
        hits = sorted(folder.glob(f"{stem}*.csv")) if folder.exists() else []
        hits = [h for h in hits if h.stem == stem or h.stem.startswith(stem + " (")]
        if hits:
            return hits[0]
    sys.exit(f"Could not find {stem}.csv - put the Wildcat Capital Clean CSVs in hw06/ or hw06/data/")


def load():
    snap = pd.read_csv(find_csv("fact_portfolio_snapshot"), parse_dates=["snapshot_date"])
    fees = pd.read_csv(find_csv("fact_fees"), parse_dates=["fee_date"])
    txns = pd.read_csv(find_csv("fact_transactions"), parse_dates=["txn_date"])
    clients = pd.read_csv(find_csv("dim_client"), usecols=["client_id", "client_tier"])
    dates = pd.read_csv(find_csv("dim_date"), parse_dates=["date"])

    # Attach the dimension attributes the slices filter on (like the model's relationships)
    for df in (snap, fees, txns):
        df["client_tier"] = df["client_id"].map(clients.set_index("client_id")["client_tier"])
    return snap, fees, txns, dates


# ----------------------------------------------------------------------------- filter context
class Context:
    """A filter context: a date window from dim_date plus an optional client tier."""

    def __init__(self, start, end, tier=None):
        self.start, self.end, self.tier = pd.Timestamp(start), pd.Timestamp(end), tier

    def shifted(self, years=0, months=0):
        # SAMEPERIODLASTYEAR / DATEADD shift the dim_date window; tier filter stays
        off = pd.DateOffset(years=years, months=months)
        return Context(self.start + off, self.end + off, self.tier)

    def apply(self, df, date_col):
        out = df[(df[date_col] >= self.start) & (df[date_col] <= self.end)]
        if self.tier is not None:
            out = out[out["client_tier"] == self.tier]
        return out


def last_snapshot(snap, ctx):
    """Rows at the LASTNONBLANK snapshot date inside the context (empty if none)."""
    rows = ctx.apply(snap, "snapshot_date")
    if rows.empty:
        return rows
    return rows[rows["snapshot_date"] == rows["snapshot_date"].max()]


def div(a, b):
    """DIVIDE(): blank (NaN) when the denominator is blank or zero."""
    if b is None or pd.isna(b) or b == 0 or a is None or pd.isna(a):
        return np.nan
    return a / b


# ----------------------------------------------------------------------------- measures
def measures(snap, fees, txns, ctx):
    s = ctx.apply(snap, "snapshot_date")
    f = ctx.apply(fees, "fee_date")
    t = ctx.apply(txns, "txn_date")

    last = last_snapshot(snap, ctx)
    ending_aum = last["aum"].sum() if not last.empty else np.nan
    ending_clients = last["client_id"].nunique() if not last.empty else np.nan

    ly = last_snapshot(snap, ctx.shifted(years=-1))
    ending_aum_ly = ly["aum"].sum() if not ly.empty else np.nan
    pm = last_snapshot(snap, ctx.shifted(months=-1))
    ending_aum_pm = pm["aum"].sum() if not pm.empty else np.nan

    total_fees = f["amount"].sum()
    net_flows = (t.loc[t["txn_type"] == "Deposit", "amount"].sum()
                 - t.loc[t["txn_type"] == "Withdrawal", "amount"].sum())
    sum_aum = s["aum"].sum()

    clean = last[last["is_return_suspect"] == 0]
    alpha = div((clean["aum"] * clean["active_alpha_ytd"]).sum(), clean["aum"].sum())
    if pd.isna(alpha):
        signal = ""
    elif alpha >= 0.02:
        signal = "Outperforming"
    elif alpha <= -0.02:
        signal = "Lagging"
    else:
        signal = "In line"

    # Top 10: rank clients by their balance at the context's last snapshot date
    top10 = last.groupby("client_id")["aum"].sum().nlargest(10).sum() if not last.empty else np.nan

    return {
        "AUM (naive SUM)": sum_aum if not s.empty else np.nan,
        "Total Fees": total_fees,
        "Net Flows": net_flows,
        "Ending AUM": ending_aum,
        "Ending Clients": ending_clients,
        "Avg AUM per Client": div(ending_aum, ending_clients),
        "Ending AUM LY": ending_aum_ly,
        "AUM YoY %": div(ending_aum - ending_aum_ly, ending_aum_ly),
        "Ending AUM PM": ending_aum_pm,
        "AUM MoM %": div(ending_aum - ending_aum_pm, ending_aum_pm),
        "Avg Monthly AUM": div(sum_aum, s["snapshot_date"].nunique()),
        "Fee Yield (bps)": div(total_fees * 12 * 10000, sum_aum),
        "Organic Growth Rate": div(net_flows, ending_aum_ly),
        "AUM-Weighted Alpha": alpha,
        "Alpha Signal": signal,
        "Top 10 Client Share": div(top10, ending_aum),
    }


# Which measures are reported for which slice (matches powerbi_export_query.dax)
TOTAL_MEASURES = [
    "AUM (naive SUM)", "Total Fees", "Net Flows", "Ending AUM", "Ending Clients",
    "Avg AUM per Client", "Ending AUM LY", "AUM YoY %", "Ending AUM PM", "AUM MoM %",
    "Avg Monthly AUM", "Fee Yield (bps)", "Organic Growth Rate", "AUM-Weighted Alpha",
    "Alpha Signal", "Top 10 Client Share",
]
YEAR_MEASURES = [
    "AUM (naive SUM)", "Ending AUM", "Ending AUM LY", "AUM YoY %", "Avg Monthly AUM",
    "Fee Yield (bps)", "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal",
]
TIER_MEASURES = [
    "Ending AUM", "Avg AUM per Client", "Ending AUM LY", "AUM YoY %", "Fee Yield (bps)",
    "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal", "Top 10 Client Share",
]
MONTH_MEASURES = ["Ending AUM", "Ending AUM PM", "AUM MoM %"]


def pandas_values(snap, fees, txns, dates):
    d0, d1 = dates["date"].min(), dates["date"].max()   # the whole of dim_date = no filter
    rows = []

    def add(ctx, names, slice_label):
        m = measures(snap, fees, txns, ctx)
        rows.extend({"measure": n, "slice": slice_label, "pandas_value": m[n]} for n in names)

    add(Context(d0, d1), TOTAL_MEASURES, "Total")
    for y in sorted(dates["year"].unique()):
        add(Context(f"{y}-01-01", f"{y}-12-31"), YEAR_MEASURES, f"Year={y}")
    for tier in sorted(snap["client_tier"].dropna().unique()):
        add(Context("2024-01-01", "2024-12-31", tier), TIER_MEASURES, f"Tier={tier}|2024")
    add(Context("2024-12-01", "2024-12-31"), MONTH_MEASURES, "Month=2024-12")
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- compare
def to_number(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    text = str(x).strip().replace(",", "").replace("$", "")
    if text == "" or text.lower() in {"nan", "(blank)", "blank"}:
        return np.nan
    pct = text.endswith("%")
    val = float(text.rstrip("%"))
    return val / 100 if pct else val


def compare(row):
    m, pbi, pd_val = row["measure"], row["powerbi_value"], row["pandas_value"]
    if m in TEXT:
        a = "" if pd.isna(pbi) else str(pbi).strip()
        b = "" if pd.isna(pd_val) else str(pd_val).strip()
        return pd.Series({"abs_diff": np.nan, "match": a == b})
    a, b = to_number(pbi), to_number(pd_val)
    if np.isnan(a) and np.isnan(b):           # both blank (e.g. 2020 has no prior year)
        return pd.Series({"abs_diff": 0.0, "match": True})
    if np.isnan(a) or np.isnan(b):
        return pd.Series({"abs_diff": np.nan, "match": False})
    tol = TOL_CURRENCY if (m in CURRENCY or m in COUNT) else TOL_RATIO
    diff = abs(a - b)
    return pd.Series({"abs_diff": diff, "match": diff <= tol})


def main():
    REPORTS.mkdir(exist_ok=True)
    snap, fees, txns, dates = load()
    pv = pandas_values(snap, fees, txns, dates)
    pv.to_csv(REPORTS / "pandas_values.csv", index=False)
    print(f"pandas: {len(pv)} values -> reports/pandas_values.csv")

    pbi_path = REPORTS / "powerbi_values.csv"
    if not pbi_path.exists():
        print("reports/powerbi_values.csv not found yet - export it from DAX query view, then rerun.")
        return

    # sep=None sniffs comma or tab, so a grid pasted straight from DAX query view also works
    pbi = pd.read_csv(pbi_path, sep=None, engine="python", dtype=str, keep_default_na=False,
                      encoding="utf-8-sig")
    pbi.columns = [c.strip().strip("[]").lower() for c in pbi.columns]
    pbi = pbi.rename(columns={"value": "powerbi_value"})
    pbi["measure"] = pbi["measure"].str.strip()
    pbi["slice"] = pbi["slice"].str.strip()

    rec = pv.merge(pbi[["measure", "slice", "powerbi_value"]], on=["measure", "slice"], how="outer",
                   indicator=True)
    missing = rec[rec["_merge"] != "both"]
    rec = rec.drop(columns="_merge")
    rec[["abs_diff", "match"]] = rec.apply(compare, axis=1)
    rec.loc[missing.index, "match"] = False
    rec = rec[["measure", "slice", "powerbi_value", "pandas_value", "abs_diff", "match"]]
    rec.to_csv(REPORTS / "measure_reconciliation.csv", index=False)

    n_ok = int(rec["match"].sum())
    print(f"reconciliation: {n_ok}/{len(rec)} rows match -> reports/measure_reconciliation.csv")
    if not missing.empty:
        print("\nRows present on only one side (check measure/slice spelling):")
        print(missing[["measure", "slice", "_merge"]].to_string(index=False))
    bad = rec[~rec["match"]]
    if not bad.empty:
        print("\nMismatches:")
        print(bad.to_string(index=False))


if __name__ == "__main__":
    main()
