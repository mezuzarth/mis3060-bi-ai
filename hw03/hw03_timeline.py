"""
HW03 - Corporate Events Timeline

Reads hw03/earnings_history.csv and hw03/executive_events.csv, matches each
executive event to the nearest earnings filing for the same company, and
classifies the event's timing relative to that earnings filing.

Output: hw03/corporate_events_timeline.csv
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths: works whether this script sits in the repo root or inside hw03/
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR if SCRIPT_DIR.name == "hw03" else SCRIPT_DIR / "hw03"

EARNINGS_PATH = DATA_DIR / "earnings_history.csv"
EVENTS_PATH = DATA_DIR / "executive_events.csv"
OUTPUT_PATH = DATA_DIR / "corporate_events_timeline.csv"

DATE_COL = "filing_date"
SAME_WEEK_DAYS = 7

# Candidate names for the column that identifies the company in both tables.
# The first one found in BOTH files is used as the join key.
COMPANY_KEY_CANDIDATES = ["ticker", "symbol", "cik", "company", "company_name", "name"]


def find_company_key(events: pd.DataFrame, earnings: pd.DataFrame) -> str:
    """Return the company identifier column shared by both tables."""
    ev_cols = {c.lower(): c for c in events.columns}
    ea_cols = {c.lower(): c for c in earnings.columns}
    for cand in COMPANY_KEY_CANDIDATES:
        if cand in ev_cols and cand in ea_cols and ev_cols[cand] == ea_cols[cand]:
            return ev_cols[cand]
    raise KeyError(
        "Could not find a shared company column. Looked for: "
        f"{COMPANY_KEY_CANDIDATES}. Events columns: {list(events.columns)}; "
        f"earnings columns: {list(earnings.columns)}"
    )


def classify(signed_days: float) -> str:
    """signed_days = event date - earnings date (negative = event came first)."""
    if pd.isna(signed_days):
        return "no earnings data"
    if abs(signed_days) <= SAME_WEEK_DAYS:
        return "same week"
    return "before earnings" if signed_days < 0 else "after earnings"


def direction(signed_days: float) -> str:
    """Plain before/after direction, used for the summary and final count."""
    if pd.isna(signed_days):
        return "n/a"
    if signed_days < 0:
        return "before"
    if signed_days > 0:
        return "after"
    return "same day"


def main() -> None:
    # --- Load ---------------------------------------------------------------
    earnings = pd.read_csv(EARNINGS_PATH)
    events = pd.read_csv(EVENTS_PATH)

    for name, df in [("earnings_history", earnings), ("executive_events", events)]:
        if DATE_COL not in df.columns:
            raise KeyError(f"{name}.csv has no '{DATE_COL}' column: {list(df.columns)}")
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")

    key = find_company_key(events, earnings)
    print(f"Joining on company column: '{key}'\n")

    # --- 1. Find the nearest earnings filing for each event ------------------
    # Rename earnings columns (except the key) so both tables' columns survive.
    earn = earnings.rename(
        columns={c: f"earnings_{c}" for c in earnings.columns if c != key}
    )
    earn_date_col = f"earnings_{DATE_COL}"

    ev = events.reset_index().rename(columns={"index": "_event_id"})

    # Cartesian match within each company, then keep the closest earnings row.
    merged = ev.merge(earn, on=key, how="left")
    merged["_signed_days"] = (merged[DATE_COL] - merged[earn_date_col]).dt.days
    merged["_abs_days"] = merged["_signed_days"].abs()

    # Sort so the smallest gap comes first; ties go to the earlier earnings date.
    merged = merged.sort_values(["_event_id", "_abs_days", earn_date_col], na_position="last")
    timeline = merged.drop_duplicates("_event_id", keep="first").copy()

    timeline["days_to_nearest_earnings"] = timeline["_abs_days"].astype("Int64")

    # --- 2. Categorize timing -------------------------------------------------
    timeline["event_timing"] = timeline["_signed_days"].apply(classify)
    timeline["_direction"] = timeline["_signed_days"].apply(direction)

    # --- 3. Save ----------------------------------------------------------------
    timeline = timeline.sort_values([key, DATE_COL])
    out_cols = [c for c in timeline.columns if not c.startswith("_")]
    out = timeline[out_cols].copy()
    for col in (DATE_COL, earn_date_col):
        out[col] = out[col].dt.strftime("%Y-%m-%d")
    out.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(out)} rows to {OUTPUT_PATH}\n")

    # --- 4. Per-company summary ------------------------------------------------
    print("=" * 70)
    print("EXECUTIVE EVENTS BY COMPANY")
    print("=" * 70)

    # Pick a descriptive column from the events table to label each event, if any.
    label_col = next(
        (c for c in ["event_type", "description", "event", "executive", "title", "form_type"]
         if c in events.columns),
        None,
    )

    all_companies = sorted(set(earnings[key].dropna()) | set(events[key].dropna()))
    for company in all_companies:
        rows = timeline[timeline[key] == company]
        print(f"\n{company}")
        if rows.empty:
            print("  (no executive events)")
            continue
        for _, r in rows.iterrows():
            label = f" | {r[label_col]}" if label_col else ""
            ev_date = r[DATE_COL].strftime("%Y-%m-%d") if pd.notna(r[DATE_COL]) else "?"
            if pd.isna(r["_signed_days"]):
                print(f"  {ev_date}{label}: no earnings filing found for this company")
                continue
            ea_date = r[earn_date_col].strftime("%Y-%m-%d")
            days = int(r["_abs_days"])
            if r["_direction"] == "same day":
                when = f"same day as earnings on {ea_date}"
            else:
                when = f"{days} days {r['_direction']} earnings on {ea_date}"
            print(f"  {ev_date}{label}: {when}  [{r['event_timing']}]")

    # --- 5. Final count ---------------------------------------------------------
    counts = timeline["_direction"].value_counts()
    timing_counts = timeline["event_timing"].value_counts()

    print("\n" + "=" * 70)
    print("FINAL COUNT (all companies)")
    print("=" * 70)
    print(f"Before an earnings announcement: {counts.get('before', 0)}")
    print(f"After an earnings announcement:  {counts.get('after', 0)}")
    if counts.get("same day", 0):
        print(f"Same day as earnings:            {counts.get('same day', 0)}")
    if counts.get("n/a", 0):
        print(f"No earnings data for company:    {counts.get('n/a', 0)}")
    print(f"Total events:                    {len(timeline)}")

    print("\nBy event_timing category (same week = within 7 days either side):")
    for cat in ["before earnings", "same week", "after earnings", "no earnings data"]:
        if timing_counts.get(cat, 0) or cat != "no earnings data":
            print(f"  {cat:<17} {timing_counts.get(cat, 0)}")


if __name__ == "__main__":
    main()