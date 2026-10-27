# HW4 Decision Log — Wildcat Capital

Written **before** the cleaning code, as the specification for `scripts/02_clean.py`.
Evidence comes from `reports/dq_summary_raw.csv`, `reports/profile_raw.csv` and
`reports/investigation_raw.txt` (`scripts/00_investigate.py`, read-only).

All decisions are final after the second run of `00_investigate.py` (sections 17–22).

---

## Order of operations in 02_clean.py (and why)

1. **Fix key formats first** (D1). Referential-integrity checks are meaningless until keys are in the same format; otherwise we would quarantine 197,175 rows that are actually fine.
2. **Standardize text and number formats** (D5, D12, D13), so later rules compare like with like.
3. **Correct values that can be reconciled** (D2), because the fix depends on the recompute check, which needs clean numbers.
4. **Quarantine what cannot be fixed** (D3), only after steps 1–3, so nothing repairable is removed.
5. **Add flag columns last** (D6, D14, D15, D17), computed on the cleaned values (e.g. the return flag must use returns *after* the `%` conversion).

---

## Defects: fixed

### D1 — fact_transactions.security_id stored as decimals
| Field | |
|---|---|
| **Table / column** | fact_transactions.security_id |
| **Evidence** | All 197,175 non-blank values end in `.0` (e.g. `447.0`); match rate to dim_security.security_id is **0.00%**. After removing `.0`, the match rate is **100.00%** |
| **Dimension violated** | Validity, Referential Integrity |
| **Decision** | Convert: strip the trailing `.0` |
| **Justification** | The ID is an integer that an upstream export wrote as a float. No value has a non-zero decimal, so nothing is guessed. Without this, no trade can be linked to its security |
| **Risk** | Very low. If a real ID had a fractional part we would merge two IDs, but none exists (asserted in the script) |
| **Verification** | Assert 100% match to dim_security after the fix; log 197,175 value changes |

### D2 — Negative shares on Buy transactions
| Field | |
|---|---|
| **Table / column** | fact_transactions.shares |
| **Evidence** | 836 rows have negative shares, **all 836 are `Buy`**. In 100% of them, \|shares\| × price = amount. `amount` is never negative, and all 196,339 positive-share rows also reconcile (shares × price = amount) |
| **Dimension violated** | Consistency (sign convention), Validity |
| **Decision** | Standardize: take the absolute value |
| **Justification** | The dataset's convention is positive shares with direction given by `txn_type` (Sells are positive too). The stored amount confirms the magnitude, so we are correcting only the sign, not inventing a number |
| **Risk** | If these were reversals or cancelled buys, we would overstate buy volume by 836 trades. Mitigation: every change is logged in value_changes.csv |
| **Verification** | Assert shares ≥ 0 for all rows and shares × price = amount (±0.5%) for 100% of the 197,175 trade rows |

### D5 — dim_client.state mixes codes and full names
| Field | |
|---|---|
| **Table / column** | dim_client.state |
| **Evidence** | 27 distinct values: 20 two-letter codes plus 78 rows with full names (Pennsylvania 25, Florida 15, New York 14, New Jersey 13, California 5, Illinois 4, Texas 2) |
| **Dimension violated** | Consistency |
| **Decision** | Standardize to USPS two-letter codes using an explicit 7-entry mapping |
| **Justification** | Geographic reporting would otherwise split PA into "PA" (414) and "Pennsylvania" (25) |
| **Risk** | Minimal; the mapping is fixed and every target code already exists in the column |
| **Verification** | Assert 20 distinct values, all 2 uppercase letters; log 78 value changes |

### D12 — return_ytd stored as percentage strings
| Field | |
|---|---|
| **Table / column** | fact_portfolio_snapshot.return_ytd |
| **Evidence** | 300 values like `-0.64%`. Check: active_alpha_ytd = return_ytd − benchmark_return_ytd holds **0%** using the raw number and **100%** after dividing by 100 |
| **Dimension violated** | Validity, Consistency |
| **Decision** | Convert: remove `%`, divide by 100 (decimal like the rest of the column) |
| **Justification** | A sibling column (alpha) independently confirms the correct scale, so this is a reconciled repair, not an assumption |
| **Risk** | None found; the reconciliation is exact |
| **Verification** | Assert the alpha identity holds for 100% of rows after the fix |

### D13 — Scientific notation in return columns
| Field | |
|---|---|
| **Table / column** | fact_portfolio_snapshot.return_ytd (135), active_alpha_ytd (756) |
| **Evidence** | Values such as `-9.5e-05` and `2e-05` among plain decimals |
| **Dimension violated** | Consistency (format only) |
| **Decision** | Standardize to plain decimal text; numeric value unchanged |
| **Justification** | Some BI tools and Excel imports treat `2e-05` as text |
| **Risk** | None; assert the numeric value is identical before and after |

---

## Defects: quarantined

### D3 — Transactions for clients that do not exist
| Field | |
|---|---|
| **Table / column** | fact_transactions.client_id |
| **Evidence** | 200 rows (200 distinct IDs, each appearing once), IDs 2702–3192, while dim_client runs 1–2525. None appear in fact_fees or fact_portfolio_snapshot; 0 would match after trimming or format normalisation. Value: **$10,888,495.37**, dated 2020-02-18 to 2024-12-19, across all six txn_types |
| **Dimension violated** | Referential Integrity |
| **Decision** | Quarantine to `data/audit/quarantine_fact_transactions_orphan_client.csv` |
| **Justification** | There is no client to attribute these to, and inventing one would be worse. Keeping them would create a blank client in every client-level report |
| **Risk** | Transaction totals in the clean data are $10.9M lower than in the source. Mitigation: the rows are kept in the quarantine file and documented in limitations, recoverable if master data arrives |
| **Verification** | Assert 298,772 = clean rows + 200 quarantined; client_id match rate 100% after |

---

## Suspicious but not correctable: flagged (0/1 column added, value unchanged)

### D6 — dim_client.risk_profile blank
| Field | |
|---|---|
| **Table / column** | dim_client.risk_profile → new `risk_profile_missing_flag` |
| **Evidence** | 76 blanks (3.0%); no pattern by tier (HNW 18 / Retail 49 / UHNW 9), status (active 72 / inactive 4), or onboarding date (2015–2022). Snapshots assign these clients benchmark 3 (60/40 Blend), the same benchmark as Balanced |
| **Dimension violated** | Completeness |
| **Decision** | Flag; leave the value blank |
| **Justification** | **Judgment call.** It is tempting to fill "Balanced" from the benchmark, but the 60/40 benchmark could simply be the system default for unassessed clients. A risk profile is a suitability determination with regulatory weight, so it must not be made up |
| **Risk** | Reports by risk profile show a 3% "unknown" bucket. If our caution is wrong, we under-report the Balanced group by up to 76 clients |

### D14 — Implausibly large YTD returns
| Field | |
|---|---|
| **Table / column** | fact_portfolio_snapshot.return_ytd / active_alpha_ytd → new `return_outlier_flag` |
| **Evidence** | 621 rows with \|return_ytd\| > 1.5 as stored (622 once the `%` strings are converted; median 516%, max 9,467%) across 93 clients (median 6 rows each, in runs of consecutive months; 12% of those clients' snapshots). 611 rows have \|active_alpha_ytd\| > 1.5. The alpha identity holds for 100% of them **as stored** and for 0% if scaled ÷100, so this is **not** a units error. Benchmark returns stay between −24% and +27% |
| **Dimension violated** | Accuracy / Plausibility |
| **Decision** | Flag where \|return_ytd\| > 1.5 or \|active_alpha_ytd\| > 1.5 (after D12); do not change |
| **Justification** | **Judgment call.** We cannot know the true return, and the row is internally consistent, so any correction would be invented. A flag lets Assignment 5 measures exclude these rows |
| **Risk** | Unflagged averages would be inflated. If some of these returns are real, excluding them by default hides genuine performance |

### D15 — AUM exactly $1,000.00
| Field | |
|---|---|
| **Table / column** | fact_portfolio_snapshot.aum (420 rows), fact_fees.aum_basis (386 rows) → new `aum_floor_flag` |
| **Evidence** | 420 snapshot rows (92 clients) at exactly 1000.00; the smallest value that is *not* 1000 is 1000.44, so nothing lies below the floor. The prior month is often far higher (e.g. client 1026: 33,870.66 → 1,000.00), and return_ytd then freezes at the same value (−0.960317 for four months). 386 fee rows use 1000.00 as aum_basis, and those fees recompute exactly from it |
| **Dimension violated** | Accuracy / Plausibility |
| **Decision** | Flag in both tables (`aum_floor_flag`); leave the value |
| **Justification** | **Judgment call.** The pattern (sudden drop, hard floor, frozen return) looks like a system minimum written when an account was emptied or closed, not a real balance. The true balance is unknown, so replacing it (with 0 or the prior value) would be invention |
| **Risk** | AUM totals overstate near-empty accounts by up to $1,000 each, and fees on these rows may have been charged on a floor value. The flag lets the committee exclude them |

### D17 — Trades dated on non-trading days
| Field | |
|---|---|
| **Table / column** | fact_transactions.txn_date → new `non_trading_day_trade_flag` (Buy/Sell only) |
| **Evidence** | 40,649 Buy/Sell rows (23,718 Buy + 16,931 Sell) fall on dates where dim_date.is_trading_day = 0, about 28.6% of trades, the same share as weekends in a week |
| **Dimension violated** | Accuracy / Plausibility (cross-table rule: fact vs dim_date) |
| **Decision** | Flag Buy/Sell rows; leave dates unchanged. Deposits, withdrawals, dividends and fees can post any day, so they are not flagged |
| **Justification** | Exchange trades cannot execute on weekends, but moving the date to the next trading day would invent a date. txn_date may be an order or entry date |
| **Risk** | If txn_date is an entry date, the flag is noise. Daily trading analyses should use the flag |

---

## Investigated: legitimate structure, left as is

| # | Table / column | Evidence | Dimension (apparent) | Decision | Justification / risk |
|---|---|---|---|---|---|
| D4 | fact_transactions security_id, shares, price blank | 101,597 blanks = exactly Deposit 35,981 + Withdrawal 29,850 + Advisory Fee 35,766; blank pattern identical across the 3 columns; 0 blanks on Buy/Sell/Dividend | Completeness | Leave as is; add a validation rule (blank ⇔ cash txn_type) | Cash movements have no security. Filling them would be invention. Risk: a BI tool that treats blank as 0 will dilute average price, so README_clean says to keep them null |
| D7 | dim_client: 25 clients with no fact rows | IDs 2501–2525; 0 match an active client on name, name+zip, name+age or name+city | — | Leave | Not duplicates; real clients with no activity in 2020–2024. A dimension may contain members with no facts |
| D8 | dim_client same first+last name | 107 rows share a name, but only 2 also share age, 0 share zip code, 0 share city | Uniqueness | Leave | Different people with common names; a duplicate person would share address details |
| D9 | dim_security sector (219) / expense_ratio_bps (281) blank | Sector blank for exactly the 219 ETFs; expense ratio blank for exactly the 281 stocks | Completeness | Leave; validation rule | ETFs have no single sector; stocks have no expense ratio |
| D10 | dim_security duplicate names | 3 pairs (e.g. "Davis PLC Fund") with different tickers, asset classes and benchmarks | Uniqueness | Leave | Ticker is unique (500/500); these are different securities |
| D11 | dim_advisor.certifications = 'None' | 6 advisors | Completeness (apparent) | Leave as the text 'None' | It means "no certifications", a real answer. Risk: pandas/Power BI read 'None' as null by default, so README_clean warns about it |
| D16 | Fees/snapshots dated before client_since | 858 fee rows and 930 snapshot rows, **all** in the same month as client_since (0 in an earlier month); 0 transactions before client_since | Consistency | Leave; assert "same month" in the script | Grain difference: monthly facts are dated the 1st, while a client who joins on the 17th is billed and valued for that month |
| D18 | Activity for is_active = False clients | 176 inactive clients; all 175 with transactions last traded in 2023; their fees and snapshots end 2023-11-01; nothing in 2024 | Consistency | Leave | "Inactive" means inactive now: they left during 2023, so earlier activity is real history. Months with fees but no trades (77 fee rows) are normal |
| D19 | Advisory Fee debits (fact_transactions) vs fact_fees | Equal in 0% of client-months and ≤0.19% of client-quarters for any fee-type combination; debits per client-quarter vary from 1 to 10 | Consistency | Leave as is; document as a limitation | **Judgment call.** The two sources cannot be reconciled at any grain, and choosing which is "right" would be guessing. fact_fees is treated as the system of record for fee revenue because it reconciles exactly to AUM × bps. Risk: fee revenue reported from fact_transactions will not tie to fact_fees |
| D20 | Profiler "inconsistent key format" on every ID column | Shapes 9 / 99 / 999 only; no leading zeros or decimals (except D1); all FKs match 100% | Consistency | Leave | False positive: integers simply have different lengths |
| D21 | dim_date | year, quarter, month, names, ISO week, month/quarter/year-end flags, trading-day flag and date_id order all 100% consistent with the date; 1,827 rows = 2020–2024 including two leap years | — | Leave | Clean |

## Reconciliations that passed (evidence the data is otherwise sound)
- fact_fees.amount = aum_basis × bps_charged ÷ 10,000 ÷ 12 for **100%** of 122,197 rows, all four fee types
- fact_fees.aum_basis = snapshot aum for the same client and month: **100%**
- Snapshot benchmark_id follows risk_profile **100%** (Aggressive/Mod. Aggressive → 1, Balanced → 3, Conservative/Mod. Conservative → 8)
- advisor_id in all three fact tables = the client's advisor in dim_client: **100%**
- Snapshot account_type = client's primary_account_type: **100%**
- Snapshot year/month columns = snapshot_date: **100%**; no duplicate client-month snapshots
