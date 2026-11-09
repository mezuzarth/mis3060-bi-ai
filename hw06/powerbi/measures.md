# HW6 — Measure Library (Part A) and Design Questions (Part C)

All measures live in the `_Measures` table of `powerbi/hw06.pbix`. Model: `Wildcat_Star_Model.pbix` (8 tables, `dim_date` marked as the date table, all relationships many-to-one, single direction).

**Grain reminder.** `fact_portfolio_snapshot` has one row per **client per month**, dated the **1st of the month** (60 snapshot dates, Jan 2020 – Dec 2024). `aum` is a **balance** (semi-additive); `active_alpha_ytd` is a **year-to-date rate** (non-additive). `fact_fees` is one row per client per month, also dated the 1st.

**Additivity patterns used**
- **SUM**: additive, safe to sum across every dimension
- **Last balance**: semi-additive, take the balance at the last snapshot date in the filter (`LASTNONBLANK`)
- **Recompute-and-weight**: non-additive, rebuild the ratio from additive parts, weighting by `aum` where needed

---

## Base measures (from the ICEs)

```DAX
Total Fees = SUM ( fact_fees[amount] )
```
```DAX
Net Flows =
CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Deposit" )
    - CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Withdrawal" )
```
Pattern: **SUM**. Format: Currency, 2 decimals.

---

## 0. AUM (naive SUM) — ⚠️ WRONG ON PURPOSE, never put on a report

```DAX
AUM (naive SUM) = SUM ( fact_portfolio_snapshot[aum] )
```
- **Pattern:** SUM applied to a balance. This is the wrong pattern for `aum`.
- **Format:** Currency, 2 decimals
- **Meaning:** It adds every month's balance together. With no filter it shows **$566.7 B**, about 44× the real **$12.73 B**, because each client's money is counted once per month. It is kept only to show the trap.

## 1. Ending AUM

```DAX
Ending AUM =
CALCULATE (
    SUM ( fact_portfolio_snapshot[aum] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
- **Pattern:** Last balance. `LASTNONBLANK` finds the last date in the filter that has snapshot rows; `LASTDATE` would return Dec 31, which has no data because snapshots fall on the 1st.
- **Format:** Currency, 2 decimals
- **Meaning:** How much money Wildcat manages at the end of the selected period ($12.73 B on 1 Dec 2024).

## 2. Ending Clients

```DAX
Ending Clients =
CALCULATE (
    DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
- **Pattern:** Last balance (a client count is a stock, not a flow)
- **Format:** Whole number
- **Meaning:** How many clients hold money with us at the end of the period (2,325 today; 175 of the 2,500 clients in `dim_client` have left).

## 3. Avg AUM per Client

```DAX
Avg AUM per Client = DIVIDE ( [Ending AUM], [Ending Clients] )
```
- **Pattern:** Recompute (ratio of two last-balance measures)
- **Format:** Currency, 2 decimals
- **Meaning:** The size of a typical relationship at period end ($5.48 M firm-wide, $39.5 M for UHNW).

## 4. Ending AUM LY and AUM YoY %

```DAX
Ending AUM LY = CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) )
```
```DAX
AUM YoY % = DIVIDE ( [Ending AUM] - [Ending AUM LY], [Ending AUM LY] )
```
- **Pattern:** Last balance, time-shifted; YoY is a recompute. `LASTNONBLANK` runs *inside* the shifted dates, so 2024 compares 1 Dec 2024 to 1 Dec 2023. `DIVIDE` has no alternate result, so 2020 (no prior year) stays **blank** instead of a misleading 0%.
- **Format:** LY: Currency, 2 decimals; YoY: Percentage, 2 decimals
- **Meaning:** How much bigger the book is than a year ago (+19.58% in 2024).

## 5. Ending AUM PM and AUM MoM %

```DAX
Ending AUM PM = CALCULATE ( [Ending AUM], DATEADD ( dim_date[date], -1, MONTH ) )
```
```DAX
AUM MoM % = DIVIDE ( [Ending AUM] - [Ending AUM PM], [Ending AUM PM] )
```
- **Pattern:** Last balance, shifted one month; MoM is a recompute
- **Format:** PM: Currency, 2 decimals; MoM: Percentage, 2 decimals
- **Meaning:** Month-over-month change in the book (Dec 2024 vs Nov 2024: +4.25%).

## 6. Avg Monthly AUM

```DAX
Avg Monthly AUM =
DIVIDE (
    SUM ( fact_portfolio_snapshot[aum] ),
    DISTINCTCOUNT ( fact_portfolio_snapshot[snapshot_date] )
)
```
- **Pattern:** Recompute (Σ balance ÷ number of snapshot months). This is the average balance across months, not the ending one.
- **Format:** Currency, 2 decimals
- **Meaning:** The average size of the book over the period, which is the right base for annual revenue ($11.29 B in 2024 vs $12.73 B ending).

## 7. Fee Yield (bps)

```DAX
Fee Yield (bps) =
DIVIDE ( [Total Fees] * 12 * 10000, SUM ( fact_portfolio_snapshot[aum] ) )
```
- **Pattern:** Recompute-and-weight across **two fact tables**. Monthly fees (SUM) over monthly balances (Σ aum, which weights each month equally), annualised ×12, in basis points ×10,000. Both facts are filtered through the shared `dim_date` and `dim_client`.
- **Format:** Decimal number, 2 decimals
- **Meaning:** Annual fee revenue per dollar we manage (43.15 bps in 2024; Retail 82.8 bps vs UHNW 36.1 bps).

## 8. Organic Growth Rate

```DAX
Organic Growth Rate = DIVIDE ( [Net Flows], [Ending AUM LY] )
```
- **Pattern:** Recompute: a flow (SUM) divided by a prior balance (last balance, shifted)
- **Format:** Percentage, 2 decimals
- **Meaning:** Net new client money as a share of last year's book, i.e. growth that did not come from markets (0.73% in 2024).

## 9. AUM-Weighted Alpha

```DAX
AUM-Weighted Alpha =
VAR LastSnap =
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
RETURN
    CALCULATE (
        DIVIDE (
            SUMX (
                fact_portfolio_snapshot,
                fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd]
            ),
            SUM ( fact_portfolio_snapshot[aum] )
        ),
        LastSnap,
        fact_portfolio_snapshot[is_return_suspect] = 0
    )
```
- **Pattern:** Recompute-and-weight at the last snapshot. Σ(aum × alpha) ÷ Σ aum, read only on the last date because alpha is year-to-date, with flagged returns excluded.
- **Format:** Percentage, 2 decimals
- **Meaning:** How far our clients' dollars beat or trailed their benchmarks year-to-date (+1.45% in 2024).

## 10. Alpha Signal

```DAX
Alpha Signal =
VAR a = [AUM-Weighted Alpha]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( a ), BLANK (),
        a >= 0.02, "Outperforming",
        a <= -0.02, "Lagging",
        "In line"
    )
```
- **Pattern:** Recompute (a label derived from measure 9; text, so no aggregation)
- **Format:** Text (none)
- **Meaning:** A plain-English flag a manager can scan. Only 2022 and the Retail tier in 2024 are "Outperforming"; everything else is "In line".

## 11. Top 10 Client Share

```DAX
Top 10 Client Share =
VAR Top10Clients =
    TOPN ( 10, VALUES ( dim_client[client_id] ), [Ending AUM], DESC )
RETURN
    DIVIDE ( CALCULATE ( [Ending AUM], Top10Clients ), [Ending AUM] )
```
- **Pattern:** Recompute: last balance of a ranked subset ÷ last balance of everyone. `VALUES` (not `ALL`) keeps the current tier/year filter, so the top 10 are the top 10 *within* the slice.
- **Format:** Percentage, 2 decimals
- **Meaning:** Concentration risk: how much of the book walks out if our 10 largest clients leave (6.16% firm-wide; 8.13% of UHNW AUM).

---

## Report page **Measures** (in `hw06.pbix`)
- **Cards:** Ending AUM · Ending Clients · Avg AUM per Client · Top 10 Client Share
- **Table by `dim_date[year]`:** Ending AUM, AUM YoY %, Avg Monthly AUM, Fee Yield (bps), Organic Growth Rate, AUM-Weighted Alpha, Alpha Signal
- **Table by `dim_client[client_tier]`**, visual-level filter `dim_date[year]` = 2024: Ending AUM, Avg AUM per Client, AUM YoY %, Fee Yield (bps), Organic Growth Rate, AUM-Weighted Alpha, Alpha Signal, Top 10 Client Share

---

# Part C — Design questions

*All numbers come from `scripts/02_part_c_analysis.py` (output saved in `reports/part_c_evidence.txt`) and agree with the Power BI values in `reports/measure_reconciliation.csv`.*

### (a) `Ending AUM` vs `SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] )`

| | Value |
|---|---:|
| `Ending AUM` (no filters) | **$12,729,572,078.86** |
| `SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] )` | **$13,149,297,713.80** |
| Difference | **$419,725,634.94** |

`Ending AUM` runs `LASTNONBLANK` once over the whole model, finds **1 Dec 2024**, and sums every balance on that date. `SUMX` evaluates `[Ending AUM]` **once per client**, so each client gets their **own** last date. For the 2,325 current clients that is still 1 Dec 2024. For the **175 clients who have left** (last snapshot between Dec 2022 and Nov 2023), it returns their final balance from the month before they left. Those 175 stale balances add up to exactly **$419,725,634.94** (UHNW $252.1 M, HNW $137.1 M, Retail $30.5 M), which is money Wildcat no longer manages.

**"How much do we manage today?" → `Ending AUM`, $12.73 B.** The SUMX version is a sum of each client's most recent balance as of different dates, so it overstates the book by 3.3%.

### (b) Why `Fee Yield (bps)` (2024) < ICE 9 `Effective Fee Rate (bps)`

| 2024 | Numerator (fees × 12 × 10,000) | Denominator | bps |
|---|---|---|---:|
| Fee Yield | $48,714,005.93 in fees | Σ `fact_portfolio_snapshot[aum]` = $135.46 B | **43.15** |
| Effective Fee Rate | same fees | Σ `fact_fees[aum_basis]` = $128.39 B | **45.53** |

The numerators are identical, so the difference is entirely in the denominator. pandas evidence:
- 2024 has **27,900** snapshot client-months but only **26,216** fee client-months. **1,684 client-months have AUM but no fee row**, and they carry **$7.07 B (5.22%)** of 2024 Σ aum. There are no fee rows without a snapshot.
- Where both exist, `aum_basis` equals `aum` on **100%** of rows, so the two tables agree on balances.
- Recomputing Fee Yield over **only** the fee-paying client-months gives **45.53 bps**, exactly the Effective Fee Rate. That accounts for the entire gap.
- The gaps are scattered: 1,082 different clients each miss *some* months (none is unbilled all year), in every month and every tier (UHNW holds $5.23 B of the unbilled AUM).

**Data limitation:** `fact_fees` does not cover every client-month that `fact_portfolio_snapshot` does. The data cannot tell us *why*: waived fees, billing lags, or records missing from the extract. Effective Fee Rate measures pricing on the accounts that were billed (45.5 bps). Fee Yield measures revenue actually collected across all AUM (43.2 bps). The ~2.4 bps gap is either fee leakage ($7.07 B of unbilled AUM-months × 45.53 bps ÷ 12 ≈ **$2.7 M of 2024 revenue**) or a data-completeness problem, and someone in billing has to tell us which.

### (c) Why AUM-Weighted Alpha uses the last snapshot only, and excludes suspects

**Last snapshot only:** `active_alpha_ytd` is **year-to-date**. Each month's value is cumulative from January and replaces the previous month's, so it is a running total, not 12 separate observations. Averaging or weighting across months mixes a 1-month alpha (January 2024: −0.01%) with a 12-month alpha (December 2024: +1.45%). Doing that over all 60 months gives 0.38%, a number that means nothing. At the last snapshot of a year, the value *is* the full-year alpha.

**Exclude `is_return_suspect = 1`:** at the last snapshot 148 of 2,325 rows are flagged. Their alphas run from −121% to **+7,134%** (mean +231%), while clean rows stay between −49.8% and +49.5%. These are data errors, not performance, and a few of them can move a weighted average.

| Same rows: last snapshot (1 Dec 2024) | Value |
|---|---:|
| **AUM-weighted, suspects excluded (the measure)** | **1.448%** |
| Simple mean of `active_alpha_ytd`, suspects excluded | 0.879% |
| AUM-weighted, suspects **included** | 1.668% |

The simple mean is lower because larger clients outperformed: the bigger half of clients by AUM averaged +1.84% vs −0.08% for the smaller half. Weighting answers the question the firm cares about, "what alpha did the average **dollar** earn?" Including suspects adds 0.22 points of fake alpha and pushes the signal toward the +2% "Outperforming" threshold.

### (d) Organic Growth Rate by tier, 2024

| Tier | AUM YoY % | Organic Growth Rate | Growth not from flows | Net flows | Share of firm net flows |
|---|---:|---:|---:|---:|---:|
| Retail | 19.13% | **9.87%** | 9.26% | $44.2 M | 57% |
| HNW | 19.64% | 1.18% | 18.46% | $25.2 M | 33% |
| UHNW | 19.59% | **0.10%** | 19.49% | $8.1 M | 10% |

**What it says:** every tier grew about 19–20%, but for different reasons. Almost all HNW and UHNW growth came from **markets** (investment returns), not new money: UHNW, three-quarters of the book, added only 0.1% in net deposits. **Retail is where new money comes from.** It is only 4% of AUM but brought in 57% of 2024 net flows and grew nearly 10% organically. It is also the highest-yielding tier (82.8 bps vs 36.1 bps for UHNW).

**What it does not tell you:**
- **Why** the non-flow growth happened: market returns, dividends kept in the account, and fees deducted are all lumped together, and a down market would wipe that part out.
- **New vs. existing clients:** net flows mix new-client deposits with top-ups and withdrawals from existing clients.
- **Client attrition in dollars:** clients who left in 2023 are already gone from the Dec 2023 base, and the ratio doesn't show balances lost to departures.
- **Tier migration:** `client_tier` is the client's *current* tier, so a client who moved from HNW to UHNW is counted as UHNW in both years.
- **Scale and profitability:** 0.1% of a $9.6 B tier is still $8.1 M, and a ratio says nothing about the revenue or cost of serving each tier.
- It is one year, so it shows no trend.
