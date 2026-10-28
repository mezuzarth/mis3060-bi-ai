# Wildcat Capital — Clean Data (`data/clean/`)

Produced by `scripts/02_clean.py` from the raw extract in `Wildcat Capital/` (raw files are never modified; checked by file hash).
Every change is listed in `data/audit/value_changes.csv` (199,280 rows), every step in `data/audit/cleaning_log.csv`, and removed rows in `data/audit/quarantine_fact_transactions_orphan_client.csv`.

| Table | Raw rows | Clean rows | Quarantined | Flag columns added |
|---|---:|---:|---:|---|
| dim_advisor | 25 | 25 | 0 | — |
| dim_client | 2,525 | 2,525 | 0 | risk_profile_missing_flag |
| dim_date | 1,827 | 1,827 | 0 | — |
| dim_security | 500 | 500 | 0 | — |
| dim_benchmark | 8 | 8 | 0 | — |
| fact_fees | 122,197 | 122,197 | 0 | aum_floor_flag |
| fact_portfolio_snapshot | 129,547 | 129,547 | 0 | return_outlier_flag, aum_floor_flag |
| fact_transactions | 298,772 | 298,572 | 200 | non_trading_day_trade_flag |

## Relationships (star schema)

Three fact tables, five dimensions. All joins are **many-to-one** (fact → dimension), single direction, and match 100% in the clean data (`reports/ri_results.csv`).

| From (many) | To (one) |
|---|---|
| fact_transactions.client_id | dim_client.client_id |
| fact_transactions.advisor_id | dim_advisor.advisor_id |
| fact_transactions.security_id | dim_security.security_id (blank on cash rows; see below) |
| fact_transactions.txn_date | dim_date.date |
| fact_fees.client_id | dim_client.client_id |
| fact_fees.advisor_id | dim_advisor.advisor_id |
| fact_fees.fee_date | dim_date.date |
| fact_portfolio_snapshot.client_id | dim_client.client_id |
| fact_portfolio_snapshot.advisor_id | dim_advisor.advisor_id |
| fact_portfolio_snapshot.benchmark_id | dim_benchmark.benchmark_id |
| fact_portfolio_snapshot.snapshot_date | dim_date.date |
| dim_client.advisor_id | dim_advisor.advisor_id (snowflake link) |
| dim_security.benchmark_id | dim_benchmark.benchmark_id (snowflake link) |

Note: dim_date joins on its `date` column (ISO `YYYY-MM-DD`), not on `date_id`. fact_fees and fact_portfolio_snapshot are **monthly** (always dated the 1st); fact_transactions is **daily**.

## Column-type settings a BI tool needs

| Column(s) | Set to | Why |
|---|---|---|
| All `*_id` columns | Whole number (or Text, consistently on both sides of a join) | Keys must have the same type on both sides of a relationship |
| `dim_client.zip_code` | **Text** | Leading zeros (e.g. `00533`); as a number it becomes 533 |
| `dim_date.date`, `client_since`, `fee_date`, `snapshot_date`, `txn_date` | Date | ISO format; mark dim_date as the date table |
| `is_etf`, `is_active` | True/False | Stored as the text `True`/`False` |
| `is_month_end`, `is_quarter_end`, `is_year_end`, `is_trading_day`, all `*_flag` columns | Whole number (0/1) | Can be summed to count rows |
| `return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd`, `cash_pct` | Decimal number, **formatted as %** | Stored as decimals: 0.05 = 5% |
| `aum`, `aum_basis`, `initial_aum`, `amount`, `price` | Fixed decimal / currency | Dollar amounts |
| `shares`, `bps_charged`, `expense_ratio_bps` | Decimal number | |
| `dim_advisor.certifications` | **Text, do not convert `None` to null** | `None` means "no certifications", a real value (6 advisors) |
| `security_id`, `shares`, `price` on cash rows | Leave **null**, never 0 | Blank by design on Deposit/Withdrawal/Advisory Fee rows; 0 would distort average price and share counts |

## Flag columns added (0/1, original values unchanged)

| Table.column | Rows = 1 | Meaning |
|---|---:|---|
| dim_client.risk_profile_missing_flag | 76 | Risk profile blank; not filled because a suitability rating must not be invented |
| fact_portfolio_snapshot.return_outlier_flag | 632 | \|return_ytd\| > 1.5 (622 rows) or \|active_alpha_ytd\| > 1.5 (611 rows), i.e. over 150% YTD. Internally consistent, so not a units error, but implausible |
| fact_portfolio_snapshot.aum_floor_flag | 420 | AUM exactly 1,000.00, an apparent system floor (nothing lies below it; balance drops suddenly and return freezes) |
| fact_fees.aum_floor_flag | 386 | Fee calculated on the 1,000.00 floor value |
| fact_transactions.non_trading_day_trade_flag | 40,630 | Buy or Sell dated on a weekend (dim_date.is_trading_day = 0) |

Recommended use: exclude `return_outlier_flag = 1` from average-return measures by default, and show flagged rows separately rather than deleting them.

## Known limitations (chosen not to fix)

1. **200 transactions quarantined ($10,888,495.37).** Their client_ids (2702–3192) do not exist in dim_client and cannot be repaired. Clean transaction totals are lower than the source by this amount. They are kept in the quarantine file in case the client master data is supplied later.
2. **76 clients have no risk profile.** The snapshot system assigns them the 60/40 benchmark (the same as Balanced), but that may be a default, so we did not infer "Balanced".
3. **632 snapshot rows have implausible returns or alpha** (622 returns above 150%, across 93 clients). The true values are unknown; they are flagged, not corrected.
4. **420 snapshot / 386 fee rows sit on a $1,000 AUM floor.** The real balance is unknown; fees on these rows were charged on the floor value.
5. **40,630 trades fall on weekends.** txn_date may be an order or entry date rather than the execution date; dates were not moved.
6. **Advisory Fee debits in fact_transactions do not reconcile to fact_fees** at monthly or quarterly level. fact_fees is the system of record for fee revenue because it recomputes exactly from AUM × bps ÷ 10,000 ÷ 12. Fee figures from the two tables will not tie.
7. **25 clients (IDs 2501–2525) have no activity.** They are not duplicates (no name, zip, age or city match), so they are kept.
8. **Completeness below 100% is expected** in fact_transactions (88.67%) and dim_security (87.50%). Those blanks are legitimate structure: no security on cash rows, no sector for ETFs, no expense ratio for stocks.
