# HW5 Star Schema Design — Wildcat Capital

## Part A — Keys

| Table | Type | Primary key | Foreign keys (column → table[column]) |
|---|---|---|---|
| dim_advisor | Dimension | `advisor_id` | — |
| dim_benchmark | Dimension | `benchmark_id` | — |
| dim_client | Dimension | `client_id` | `advisor_id` → dim_advisor[advisor_id] |
| dim_date | Dimension | `date_id` | — |
| dim_security | Dimension | `security_id` | `benchmark_id` → dim_benchmark[benchmark_id] |
| fact_fees | Fact | `fee_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`fee_date` → dim_date[date] |
| fact_portfolio_snapshot | Fact | `snapshot_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`benchmark_id` → dim_benchmark[benchmark_id]<br>`snapshot_date` → dim_date[date] |
| fact_transactions | Fact | `txn_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`security_id` → dim_security[security_id] (can be blank)<br>`txn_date` → dim_date[date] |

**Blank key:** `fact_transactions.security_id` is blank on 101,528 rows, all of them
Deposit, Withdrawal or Advisory Fee transactions, which move cash and involve no security.
Every Buy, Sell and Dividend row has a valid `security_id`.

**Verification:** `check_model.py` confirms every primary key is unique with no nulls,
and every foreign key has zero orphans (every value exists in the table it points to).
Fact dates match `dim_date[date]`, not `dim_date[date_id]`.

## Part B — Grain

- **fact_transactions:** One row represents a single transaction (a buy, sell, dividend,
  deposit, withdrawal or advisory fee debit) for one client on one date.
- **fact_portfolio_snapshot:** One row represents one client's portfolio position for one
  month, dated the first day of that month.
- **fact_fees:** One row represents the one fee charged to one client in one month, dated
  the first day of that month.

**Verification:** `check_model.py` confirms each fact's ID is unique, and that
`fact_portfolio_snapshot` and `fact_fees` are each unique on client + month
(129,547 and 122,197 rows, zero duplicates). All snapshot and fee dates fall on day 1.

## Part C — Measures

### fact_fees
| Column | Type | How it may be summed or averaged |
|---|---|---|
| `amount` | Additive | Fee dollars can be summed across clients, advisors and months (e.g. total fees for 2024). |
| `aum_basis` | Semi-additive | The asset balance the fee was charged on; sum across clients for one month, but never across months (12 months of balances is not "annual AUM"). |
| `bps_charged` | Non-additive | A rate; never sum it. Average it weighted by `aum_basis`, or recompute as total amount ÷ total basis. |

### fact_portfolio_snapshot
| Column | Type | How it may be summed or averaged |
|---|---|---|
| `aum` | Semi-additive | Sum across clients for one month (total AUM); across time take the latest month's value or an average, never a sum. |
| `return_ytd` | Non-additive | A percentage that is already cumulative year-to-date; never sum across clients or months. Use the latest month and weight by `aum` across clients. |
| `benchmark_return_ytd` | Non-additive | Same as `return_ytd`: a cumulative percentage, so take the latest month and never sum. |
| `active_alpha_ytd` | Non-additive | Return minus benchmark return; a difference of percentages, so it cannot be summed. Use AUM-weighted averages. |
| `cash_pct` | Non-additive | A share of the portfolio; average it weighted by `aum` rather than summing or taking a simple average. |

### fact_transactions
| Column | Type | How it may be summed or averaged |
|---|---|---|
| `amount` | Additive | Dollar amounts can be summed across clients, securities and dates, but filter by `txn_type` first, since deposits, fees and trades mean different things. |
| `shares` | Additive (within a security) | Shares can be summed for one security; summing across different securities produces a meaningless count. |
| `price` | Non-additive | A per-share price; never sum it. Use a share-weighted average (total amount ÷ total shares). |

### Numeric columns that are not measures
- **Keys:** `fee_id`, `snapshot_id`, `txn_id`, `client_id`, `advisor_id`, `benchmark_id`, `security_id`
- **Date parts:** `year`, `month` in fact_portfolio_snapshot
- **Flags:** `is_return_suspect`, `is_post_departure_txn` (filters, or counted to find how many rows are flagged, never summed as values)

### Numeric dimension attributes that should never be summed
- **dim_advisor:** `years_experience`, `aum_target_mm`
- **dim_client:** `age`, `zip_code`, `initial_aum` (a one-time starting value; actual AUM comes from the snapshot fact)
- **dim_security:** `expense_ratio_bps` (a rate)
- **dim_date:** `year`, `quarter`, `month`, `week_of_year`, and the `is_*` flags

## Part E — Relationships and design

### Model summary
The model has 13 relationships: 12 active and 1 inactive. Every relationship is
many-to-one (*:1) from the fact (or child dimension) to the dimension, with single
cross-filter direction so dimensions filter facts. `dim_date` is marked as the date
table on its `date` column.

| From (many) | To (one) | Status |
|---|---|---|
| fact_fees[client_id] | dim_client[client_id] | Active |
| fact_fees[advisor_id] | dim_advisor[advisor_id] | Active |
| fact_fees[fee_date] | dim_date[date] | Active |
| fact_portfolio_snapshot[client_id] | dim_client[client_id] | Active |
| fact_portfolio_snapshot[advisor_id] | dim_advisor[advisor_id] | Active |
| fact_portfolio_snapshot[benchmark_id] | dim_benchmark[benchmark_id] | Active |
| fact_portfolio_snapshot[snapshot_date] | dim_date[date] | Active |
| fact_transactions[client_id] | dim_client[client_id] | Active |
| fact_transactions[advisor_id] | dim_advisor[advisor_id] | Active |
| fact_transactions[security_id] | dim_security[security_id] | Active |
| fact_transactions[txn_date] | dim_date[date] | Active |
| dim_security[benchmark_id] | dim_benchmark[benchmark_id] | Active |
| dim_client[advisor_id] | dim_advisor[advisor_id] | **Inactive** |

**Conformed dimensions:** `dim_date`, `dim_client` and `dim_advisor` are shared by all
three fact tables, so one date, client or advisor filter applies consistently across
transactions, fees and snapshots. `dim_benchmark` is shared by the snapshot fact
(directly) and the transactions fact (through `dim_security`). `dim_security` is used
only by `fact_transactions`.

**Validation in Power BI:** card visuals counting each table's primary key match the
handout row counts for all eight tables. An advisor slicer (advisor 1) reduced all three
fact tables (fees 122,197 → 5,008; snapshots 129,547 → 5,304; transactions 298,572 →
12,661), confirming the advisor relationships filter every fact.

### (a) Transactions with no `security_id`
101,528 transactions have a blank `security_id`: every Deposit (35,956), Withdrawal
(29,830) and Advisory Fee (35,742) row. These transactions move cash into, out of, or
from an account and do not involve a security, so there is nothing for the key to point
to. Every Buy, Sell and Dividend row has a valid `security_id` with no orphans. This is
not a defect; it is a legitimately optional foreign key. In Power BI these rows appear
under a single `(Blank)` security, which is expected, and they are still counted in
transaction totals by client, advisor and date.

### (b) Which `advisor_id` relationships are active
I kept the three fact → `dim_advisor` relationships active and made
`dim_client` → `dim_advisor` inactive. With all four active, each fact could reach
`dim_advisor` by two paths (directly, or through `dim_client`), which Power BI does not
allow. The fact's `advisor_id` records the advisor who actually handled that transaction,
fee or snapshot at the time, while `dim_client[advisor_id]` is only the client's current
advisor. The is_post_departure_txn flag marks 2,410 transactions recorded after an advisor’s departure, so advisors do change, and attributing
activity through the client's current advisor would credit the wrong advisor for past
work. With this design, an advisor filter changes the fact tables but not the client
count (dim_client stayed at 2,500), because the client → advisor path is inactive.

### (c) Joining facts to the date dimension
I joined `txn_date`, `fee_date` and `snapshot_date` to `dim_date[date]`, not
`dim_date[date_id]`. The facts store calendar dates and contain no `date_id`, so a join
on `date_id` would match nothing. Every fact date exists in `dim_date[date]` (zero
orphans in `check_model.py`), and `date` is unique, so it works as the one side of the
relationship. It is also the column `dim_date` is marked on as the date table, which
time-intelligence functions in Assignment 6 require.

### (d) Star or snowflake
Two relationships connect one dimension to another: `dim_client` → `dim_advisor` and
`dim_security` → `dim_benchmark`, so the model is technically a snowflake. I kept both,
but treat them differently. `dim_security` → `dim_benchmark` is active because it creates
no second path: it lets a benchmark filter transactions through their securities, while
the snapshot fact links to `dim_benchmark` directly. `dim_client` → `dim_advisor` is
kept but inactive (see b), so it can be switched on in a specific DAX measure with
`USERELATIONSHIP` if a report needs clients by current advisor. In everyday use the
model behaves as a star around the three fact tables.

## Part F — Reflection

### 1. Fees: "How much fee revenue did each advisor bring in during 2024, by fee type?"
**One visual, no DAX.** A matrix with `dim_advisor[last_name]` on rows,
`fact_fees[fee_type]` on columns, `fact_fees[amount]` as values (Sum), and
`dim_date[year]` = 2024 as a filter. `amount` is additive, and the fees fact links
directly to both the advisor and date dimensions, so Power BI's default Sum gives the
correct answer. The limit is the fee *rate*: an effective rate by advisor would need
total amount ÷ total `aum_basis`, because averaging `bps_charged` gives every client
equal weight regardless of account size. That requires a DAX measure.

### 2. Transactions: "Which sectors saw the most buying in 2024?"
**One visual, no DAX.** A bar chart with `dim_security[sector]` on the axis and
`fact_transactions[amount]` as the value, filtered to `txn_type` = Buy and year = 2024.
`amount` is additive, and the security relationship lets sector filter the trades
directly. The `txn_type` filter is essential: `amount` mixes trades, dividends,
deposits, withdrawals and fees, so summing it unfiltered produces a meaningless total.
Cash rows (no security) fall under `(Blank)` and are excluded once the filter is set.

### 3. Portfolio snapshot: "How has each advisor's AUM grown quarter by quarter, 2020–2024?"
**Not answerable in one visual without DAX.** `aum` is semi-additive: it can be summed
across clients for one month, but not across months. Placing quarters on the axis makes
Power BI's default Sum add three monthly balances together, overstating AUM roughly
threefold. The correct answer uses each quarter's *last* snapshot, which requires a DAX
measure (e.g. `LASTNONBLANK` over the snapshot dates). The date table doesn't help
directly: snapshots are dated the 1st of each month, so `dim_date[is_quarter_end]`
never matches a snapshot row.

**Schema changes that would fix it:** date each snapshot at month-end (the date the
balance actually represents), or add flags to the snapshot fact such as
`is_quarter_last_snapshot` and `is_year_last_snapshot`. Either lets a single filter keep
only the period-end rows, after which a plain Sum of `aum` across clients is correct.
The same table has a second limitation: `return_ytd` and `active_alpha_ytd` are
non-additive percentages, so an advisor-level return needs an AUM-weighted DAX average.
Storing a return amount in dollars (`aum` × return) would make that component additive
and the weighted return a simple ratio of two sums.