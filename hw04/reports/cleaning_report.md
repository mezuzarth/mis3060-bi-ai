# Wildcat Capital: Data Quality and Cleaning Report
**To:** Portfolio Committee  **Re:** Data warehouse extract, 8 tables, 2020–2024

## Executive summary
We audited all eight tables (555,401 rows) of the Wildcat Capital extract and produced a clean copy (555,201 rows) with a full audit trail. Two defects would have broken reporting outright. **Every trade (197,175 rows) failed to link to its security** because security IDs were stored as decimals (`447.0`), and **200 transactions ($10.9 million) belonged to clients who do not exist**. After cleaning, all 13 table relationships match 100%, all 43 business rules pass, and all six reconciliation checks agree in 100% of rows. We corrected only what other data could prove. Values we could not prove were flagged, not changed, so the committee can decide how to treat them.

## What we changed

| Issue | Table | Rows | Action | How we verified it |
|---|---|---:|---|---|
| Security IDs stored as `447.0` | fact_transactions | 197,175 | Converted to `447` | Match to securities rose from 0.00% to 100% |
| Clients that do not exist (IDs 2702–3192) | fact_transactions | 200 | Quarantined ($10,888,495.37) | No match in any table, even after format fixes |
| Negative share counts on Buys | fact_transactions | 836 | Sign corrected | \|shares\| × price equals the stored amount in all 836 |
| Returns stored as `-0.64%` text | fact_portfolio_snapshot | 300 | Converted to decimal (−0.0064) | Alpha = return − benchmark: 99.77% → 100% |
| Returns in scientific notation | fact_portfolio_snapshot | 891 | Reformatted, value unchanged | Numeric value identical before and after |
| State names mixed with codes | dim_client | 78 | "Pennsylvania" → "PA" (7 names) | 27 distinct values → 20, all valid codes |
| Missing risk profile | dim_client | 76 | Flagged, left blank | — |
| Returns above 150% YTD | fact_portfolio_snapshot | 632 | Flagged, unchanged | — |
| AUM at exactly $1,000 | snapshot / fees | 420 / 386 | Flagged, unchanged | — |
| Trades dated on weekends | fact_transactions | 40,630 | Flagged, unchanged | — |

In total, 199,280 individual values were changed and each is listed in `value_changes.csv`. Raw rows equal clean rows plus quarantined rows for every table.

**Before and after (from `data_quality_scorecard.csv`)**

| fact_transactions | Raw | Clean |
|---|---:|---:|
| Referential match | 81.95% | 100.00% |
| Type validity | 91.73% | 100.00% |
| Rule pass | 99.94% | 100.00% |

fact_portfolio_snapshot type validity rose from 99.93% to 100%, and dim_client rule pass from 99.66% to 100%. Completeness stays at 88.67% for transactions and 87.50% for securities **by design** (see judgment call 1).

## Key judgment calls

**1. Not every blank is missing data.** 101,597 raw transactions (101,528 after quarantine) have no security, shares or price. These are exactly the Deposits, Withdrawals and Advisory Fees, which involve no security. Likewise, sector is blank for exactly the 219 ETFs and expense ratio for exactly the 281 stocks. We left these blank. *Risk:* a BI tool that turns blanks into zeros would understate average prices, so the clean-data README instructs keeping them null.

**2. Implausible returns were flagged, not "fixed."** 622 monthly snapshots (93 clients) show year-to-date returns above 150%, up to 9,467%. We flagged 632 rows, which also covers 10 where only alpha exceeds 150%. A tempting fix is to assume they were entered ×100 and divide. We tested that: the relationship *alpha = return − benchmark* holds in 100% of these rows as stored and in 0% if rescaled. So they are not a units error, and we cannot know the true values. *Risk:* if some returns are genuine, excluding flagged rows hides real performance. If they are wrong and unflagged, average returns are badly inflated.

**3. Missing risk profiles were not inferred.** All 76 clients without a risk profile are benchmarked to the 60/40 Blend, the same as Balanced clients. We did not label them "Balanced," because a risk profile is a suitability determination and the benchmark may simply be a system default. *Risk:* reports by risk profile show a 3% "unknown" group.

**4. Fee data comes from one source of truth.** Advisory Fee debits in the transaction table cannot be reconciled to the fee table at monthly or quarterly level (at most 0.19% of client-quarters agree). We treat `fact_fees` as authoritative because every fee recomputes exactly as AUM × bps ÷ 10,000 ÷ 12. *Risk:* fee revenue taken from the transaction table will not tie to fee revenue from the fee table.

## Limitations
- **Transaction totals are $10,888,495.37 lower than the source** because 200 transactions with unknown clients are quarantined. They are kept for recovery if client records arrive.
- **Flagged values are unverified:** 632 return outliers, 420 snapshots and 386 fees on a $1,000 AUM floor, and 40,630 weekend-dated trades. The source system owner should confirm them.
- **The two fee sources disagree** (judgment call 4).
- **IQR outlier checks flag 2.42% of transaction amounts, 10.24% of AUM values and 9.28% of fee amounts.** These are mostly legitimate large UHNW accounts, so flagged does not mean wrong.

