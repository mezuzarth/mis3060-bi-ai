"""
Script:      explore_transactions.py
Purpose:     Exploratory data profile of the Wildcat Capital transactions
             dataset -- shape, dtypes, missingness, descriptive stats,
             txn_type breakdown, duplicate check, amount distribution
             (incl. skewness), amount-by-type summary, correlation
             structure between shares/price/amount, and a look at
             negative share values by transaction type. Also renders
             three diagnostic charts and writes a full text record of
             every printed check to hw02/hw02_profile.txt.
Dataset:     data/raw/fact_transactions.csv (Wildcat Capital transaction data)
Author:      Megan Zuzarth
Generated:   2026-09-16
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_PATH = Path("data/raw/fact_transactions.csv")
CHARTS_DIR = Path("hw02/charts")
PROFILE_PATH = Path("hw02/hw02_profile.txt")
EXPECTED_SHAPE = (298772, 9)

CHARTS_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Small helper so every printed line also lands in the text file
# ---------------------------------------------------------------------------
class Tee:
    """Writes to stdout and to an open file handle at the same time."""

    def __init__(self, file_handle):
        self.file_handle = file_handle

    def log(self, *args, sep=" ", end="\n"):
        text = sep.join(str(a) for a in args) + end
        sys.stdout.write(text)
        self.file_handle.write(text)


def section(tee, title):
    tee.log()
    tee.log("=" * 78)
    tee.log(title)
    tee.log("=" * 78)


def main():
    with open(PROFILE_PATH, "w") as f:
        tee = Tee(f)
        log = tee.log

        # -------------------------------------------------------------
        # Load
        # -------------------------------------------------------------
        section(tee, "LOAD")
        df = pd.read_csv(DATA_PATH)
        log(f"Loaded '{DATA_PATH}' into a DataFrame.")

        # -------------------------------------------------------------
        # Shape
        # -------------------------------------------------------------
        section(tee, "SHAPE")
        log(f"Rows: {df.shape[0]:,}")
        log(f"Columns: {df.shape[1]:,}")
        if df.shape != EXPECTED_SHAPE:
            log(
                f"WARNING: expected shape {EXPECTED_SHAPE}, "
                f"but got {df.shape}. Check that the file loaded correctly."
            )
        else:
            log(f"Shape matches the expected {EXPECTED_SHAPE}.")

        # -------------------------------------------------------------
        # Columns + dtypes
        # -------------------------------------------------------------
        section(tee, "COLUMNS AND DATA TYPES")
        for col in df.columns:
            log(f"  {col:<20s} {str(df[col].dtype)}")

        # -------------------------------------------------------------
        # Missing values
        # -------------------------------------------------------------
        section(tee, "MISSING VALUES BY COLUMN")
        null_counts = df.isnull().sum()
        for col, n in null_counts.items():
            log(f"  {col:<20s} {n:,}")

        # -------------------------------------------------------------
        # Descriptive stats for numeric columns
        # -------------------------------------------------------------
        section(tee, "DESCRIPTIVE STATISTICS (NUMERIC COLUMNS)")
        numeric_df = df.select_dtypes(include=[np.number])
        desc = numeric_df.describe()
        log(desc.to_string())

        # -------------------------------------------------------------
        # txn_type breakdown
        # -------------------------------------------------------------
        section(tee, "TRANSACTION TYPE BREAKDOWN")
        type_counts = df["txn_type"].value_counts().sort_values(ascending=False)
        type_pct = (type_counts / len(df) * 100).round(2)
        breakdown = pd.DataFrame({"count": type_counts, "pct": type_pct})
        log(breakdown.to_string())

        # -------------------------------------------------------------
        # Unique clients / advisors / securities + date range
        # -------------------------------------------------------------
        section(tee, "ENTITY COUNTS AND DATE RANGE")
        log(f"Unique clients:    {df['client_id'].nunique():,}")
        log(f"Unique advisors:   {df['advisor_id'].nunique():,}")
        log(f"Unique securities: {df['security_id'].nunique():,}")

        txn_dates = pd.to_datetime(df["txn_date"])
        log(f"Earliest txn_date: {txn_dates.min().date()}")
        log(f"Latest txn_date:   {txn_dates.max().date()}")

        # -------------------------------------------------------------
        # Duplicate txn_id check
        # -------------------------------------------------------------
        section(tee, "DUPLICATE CHECK (txn_id)")
        dup_count = df["txn_id"].duplicated().sum()
        log(f"Duplicate txn_id rows: {dup_count:,}")
        if dup_count == 0:
            log("Confirmed: no duplicate txn_id values.")
        else:
            log("WARNING: duplicate txn_id values found -- investigate.")

        # -------------------------------------------------------------
        # Amount: mean, median, skewness
        # -------------------------------------------------------------
        section(tee, "AMOUNT DISTRIBUTION SUMMARY")
        amount_mean = df["amount"].mean()
        amount_median = df["amount"].median()
        amount_skew = df["amount"].skew()
        log(f"Mean:     {amount_mean:,.2f}")
        log(f"Median:   {amount_median:,.2f}")
        log(f"Skewness: {amount_skew:.4f}")
        if abs(amount_skew) < 0.5:
            skew_note = "approximately symmetric"
        elif abs(amount_skew) < 1:
            skew_note = "moderately skewed"
        else:
            skew_note = "highly skewed"
        direction = "right" if amount_skew > 0 else "left"
        log(f"Interpretation: {skew_note} ({direction}-skewed).")

        # -------------------------------------------------------------
        # Group by txn_type: count, mean amount, median amount
        # -------------------------------------------------------------
        section(tee, "AMOUNT BY TRANSACTION TYPE")
        by_type = (
            df.groupby("txn_type")["amount"]
            .agg(count="count", mean_amount="mean", median_amount="median")
            .round(2)
            .sort_values("mean_amount", ascending=False)
        )
        log(by_type.to_string())

        # -------------------------------------------------------------
        # Correlation matrix: shares, price, amount
        # -------------------------------------------------------------
        section(tee, "CORRELATION MATRIX (shares, price, amount)")
        corr_cols = ["shares", "price", "amount"]
        corr = df[corr_cols].corr().round(2)
        log(corr.to_string())

        # Find the three strongest correlations, excluding self-correlation
        pairs = []
        for i, c1 in enumerate(corr_cols):
            for j, c2 in enumerate(corr_cols):
                if i < j:
                    pairs.append((c1, c2, corr.loc[c1, c2]))
        pairs.sort(key=lambda p: abs(p[2]), reverse=True)

        log()
        log("Strongest correlations (excluding a variable with itself):")
        for rank, (c1, c2, val) in enumerate(pairs[:3], start=1):
            log(f"  {rank}. {c1} vs {c2}: {val:.2f}")

        # -------------------------------------------------------------
        # Negative shares by txn_type
        # -------------------------------------------------------------
        section(tee, "NEGATIVE SHARES BY TRANSACTION TYPE")
        neg_shares = df[df["shares"] < 0]
        if len(neg_shares) == 0:
            log("No negative share values found.")
        else:
            neg_summary = neg_shares.groupby("txn_type")["shares"].agg(
                min="min", max="max", count="count"
            )
            log(neg_summary.to_string())

        section(tee, "PROFILE COMPLETE")
        log(f"Text record written to: {PROFILE_PATH}")

    # -------------------------------------------------------------------
    # Charts (not written to the text profile)
    # -------------------------------------------------------------------

    # 1. Histogram of amount with mean/median marked
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(df["amount"], bins=100, color="steelblue", edgecolor="white", alpha=0.85)
    ax.axvline(
        amount_mean, color="firebrick", linestyle="--", linewidth=2,
        label=f"Mean = {amount_mean:,.2f}",
    )
    ax.axvline(
        amount_median, color="darkorange", linestyle="--", linewidth=2,
        label=f"Median = {amount_median:,.2f}",
    )
    ax.set_title("Distribution of Transaction Amount")
    ax.set_xlabel("Amount")
    ax.set_ylabel("Frequency")
    ax.legend()
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "hist_amount.png", dpi=150)
    plt.close(fig)

    # 2. Horizontal box plot of amount by txn_type
    fig, ax = plt.subplots(figsize=(10, 6))
    type_order = (
        df.groupby("txn_type")["amount"].median().sort_values().index.tolist()
    )
    data_by_type = [df.loc[df["txn_type"] == t, "amount"] for t in type_order]
    try:
        ax.boxplot(data_by_type, vert=False, tick_labels=type_order, showfliers=True)
    except TypeError:
        # older matplotlib versions use 'labels' instead of 'tick_labels'
        ax.boxplot(data_by_type, vert=False, labels=type_order, showfliers=True)
    ax.set_title("Transaction Amount by Type")
    ax.set_xlabel("Amount")
    ax.set_ylabel("Transaction Type")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "box_amount_by_type.png", dpi=150)
    plt.close(fig)

    # 3. Scatter plot of shares vs amount, colored by txn_type
    fig, ax = plt.subplots(figsize=(10, 6))
    for t in df["txn_type"].unique():
        subset = df[df["txn_type"] == t]
        ax.scatter(subset["shares"], subset["amount"], s=8, alpha=0.4, label=t)
    ax.set_title("Shares vs. Amount by Transaction Type")
    ax.set_xlabel("Shares")
    ax.set_ylabel("Amount")
    ax.legend(markerscale=2, title="txn_type")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "scatter_shares_amount.png", dpi=150)
    plt.close(fig)

    print(f"\nCharts saved to: {CHARTS_DIR}/")


if __name__ == "__main__":
    main()