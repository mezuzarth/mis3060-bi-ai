"""HW5 check_model.py: proves the keys and grain claimed in star_design.md.

Run from any folder:  python hw05/check_model.py
Expects the eight Wildcat Capital Clean CSVs in the same folder as this script.
Prints PASS/FAIL for every check and exits with code 1 if any check fails.
"""
import sys
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent

# Row counts from the HW5 handout
EXPECTED_ROWS = {
    "dim_advisor": 25,
    "dim_benchmark": 8,
    "dim_client": 2_500,
    "dim_date": 1_827,
    "dim_security": 500,
    "fact_fees": 122_197,
    "fact_portfolio_snapshot": 129_547,
    "fact_transactions": 298_572,
}

DATE_COLUMNS = {
    "dim_date": "date",
    "fact_fees": "fee_date",
    "fact_portfolio_snapshot": "snapshot_date",
    "fact_transactions": "txn_date",
}

PRIMARY_KEYS = [
    ("dim_advisor", "advisor_id"),
    ("dim_benchmark", "benchmark_id"),
    ("dim_client", "client_id"),
    ("dim_date", "date_id"),
    ("dim_date", "date"),  # the column the facts actually join to
    ("dim_security", "security_id"),
    ("fact_fees", "fee_id"),
    ("fact_portfolio_snapshot", "snapshot_id"),
    ("fact_transactions", "txn_id"),
]

# (child table, child column, parent table, parent column)
FOREIGN_KEYS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]

# The only foreign key allowed to be blank, and the txn types allowed to leave it blank
OPTIONAL_FK = ("fact_transactions", "security_id")
CASH_TXN_TYPES = {"Deposit", "Withdrawal", "Advisory Fee"}

failures = []


def check(passed, label):
    """Record and print one check result."""
    print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    if not passed:
        failures.append(label)


def load_tables():
    """Load the eight expected CSVs once, failing clearly if any are missing."""
    missing = [name for name in EXPECTED_ROWS if not (DATA / f"{name}.csv").exists()]
    if missing:
        sys.exit(f"Missing CSV file(s) in {DATA}: {', '.join(missing)}")

    tables = {name: pd.read_csv(DATA / f"{name}.csv") for name in EXPECTED_ROWS}
    for table, column in DATE_COLUMNS.items():
        tables[table][column] = pd.to_datetime(tables[table][column], format="%Y-%m-%d")
    return tables


def profile(tables):
    print("===== PROFILE =====")
    for name, df in tables.items():
        print(f"\n{name}: {len(df):,} rows x {df.shape[1]} cols")
        print(df.dtypes.to_string())
        nulls = df.isna().sum()
        print("Nulls:", nulls[nulls > 0].to_dict())


def check_row_counts(tables):
    print("\n===== ROW COUNTS vs HANDOUT =====")
    for name, expected in EXPECTED_ROWS.items():
        actual = len(tables[name])
        check(actual == expected, f"{name}: {actual:,} rows (expected {expected:,})")


def check_primary_keys(tables):
    print("\n===== PRIMARY KEYS =====")
    for table, column in PRIMARY_KEYS:
        values = tables[table][column]
        check(values.is_unique and values.notna().all(),
              f"{table}[{column}] is unique with no nulls")


def check_foreign_keys(tables):
    print("\n===== FOREIGN KEYS =====")
    for child, column, parent, parent_column in FOREIGN_KEYS:
        values = tables[child][column]
        orphans = int((~values.dropna().isin(tables[parent][parent_column])).sum())
        blanks = int(values.isna().sum())
        check(orphans == 0,
              f"{child}.{column} -> {parent}[{parent_column}]: {orphans} orphans")
        if (child, column) == OPTIONAL_FK:
            print(f"         ({blanks:,} blanks allowed; tested below)")
        else:
            check(blanks == 0, f"{child}.{column}: {blanks} blanks")


def check_blank_security(tables):
    print("\n===== BLANK security_id ONLY ON CASH TRANSACTIONS =====")
    txns = tables["fact_transactions"]
    is_blank = txns["security_id"].isna()
    is_cash = txns["txn_type"].isin(CASH_TXN_TYPES)
    print(pd.crosstab(txns["txn_type"], is_blank.rename("security_blank")))
    check((is_blank == is_cash).all(),
          "security_id is blank exactly when txn_type is Deposit, Withdrawal or Advisory Fee")


def check_grain(tables):
    print("\n===== GRAIN =====")
    fees = tables["fact_fees"]
    snaps = tables["fact_portfolio_snapshot"]
    fee_month = fees["fee_date"].dt.to_period("M")
    snap_month = snaps["snapshot_date"].dt.to_period("M")

    fee_dupes = int(fees.assign(month=fee_month).duplicated(["client_id", "month"]).sum())
    check(fee_dupes == 0, f"fact_fees: one row per client per month ({fee_dupes} duplicates)")

    snap_dupes = int(snaps.assign(month=snap_month).duplicated(["client_id", "month"]).sum())
    check(snap_dupes == 0,
          f"fact_portfolio_snapshot: one row per client per month ({snap_dupes} duplicates)")

    year_month_agree = ((snaps["year"] == snaps["snapshot_date"].dt.year)
                        & (snaps["month"] == snaps["snapshot_date"].dt.month)).all()
    check(year_month_agree,
          "fact_portfolio_snapshot: stored year/month agree with snapshot_date")

    check((fees["fee_date"].dt.day == 1).all(), "fact_fees: every fee_date is the 1st of the month")
    check((snaps["snapshot_date"].dt.day == 1).all(),
          "fact_portfolio_snapshot: every snapshot_date is the 1st of the month")


def report_context(tables):
    """Figures quoted in star_design.md Part E that aren't pass/fail checks."""
    print("\n===== CONTEXT FOR PART E =====")
    post_departure = int(tables["fact_transactions"]["is_post_departure_txn"].sum())
    print(f"  Transactions flagged is_post_departure_txn: {post_departure:,}")


def main():
    tables = load_tables()
    profile(tables)
    check_row_counts(tables)
    check_primary_keys(tables)
    check_foreign_keys(tables)
    check_blank_security(tables)
    check_grain(tables)
    report_context(tables)

    print("\n" + "=" * 40)
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED:")
        for label in failures:
            print(f"  - {label}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()