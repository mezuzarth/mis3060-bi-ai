# Model metadata: `powerbi/hw06.pbix`

Exported from **DAX query view** with the three INFO.VIEW queries from `powerbi_dax_guide.md` §2. I exported after creating measures 0–10, so Claude can see and reuse `[Ending AUM]` and the other existing measures.

> **HOW TO FILL THIS IN (delete this box when done):** In Power BI, open DAX query view, paste one query, click **Run**, click **Copy** on the result grid, and paste it under its heading (inside the ``` fences). Repeat for all three.

---

## 1. Columns

```DAX
EVALUATE
SELECTCOLUMNS (
    FILTER ( INFO.VIEW.COLUMNS (), [DataCategory] <> "RowNumber" ),
    [Table], "Column", [Name], [DataType], "DAX formula", [Expression], [IsHidden]
)
ORDER BY [Table]
```

**Result:**
```
PASTE THE COLUMNS RESULT GRID HERE
```

## 2. Relationships

```DAX
EVALUATE INFO.VIEW.RELATIONSHIPS ()
```

**Result:**
```
PASTE THE RELATIONSHIPS RESULT GRID HERE
```

## 3. Measures

```DAX
EVALUATE
SELECTCOLUMNS (
    INFO.VIEW.MEASURES (),
    [Table], "Measure", [Name], "DAX formula", [Expression], [FormatString], [State]
)
```

**Result:**
```
PASTE THE MEASURES RESULT GRID HERE
```

---

## What the metadata does NOT say (added by hand; also given to Claude in the prompt)

| Table | Grain | Notes |
|---|---|---|
| `fact_portfolio_snapshot` | 1 row per client per month (2,500 clients, 60 months, 129,547 rows) | `snapshot_date` is the **1st of the month**. `aum` is a **balance** (semi-additive: never sum across months). `active_alpha_ytd`, `return_ytd`, `benchmark_return_ytd` are **year-to-date rates** (non-additive). `is_return_suspect = 1` flags unreliable returns. |
| `fact_fees` | 1 row per client per month billed | `fee_date` is the 1st of the month. `amount` is additive; `bps_charged` is a rate; `aum_basis` is a balance. Some client-months have no fee row. |
| `fact_transactions` | 1 row per transaction | `amount` is additive. `txn_type` ∈ Buy, Sell, Dividend, Deposit, Withdrawal, Advisory Fee. |
| `dim_date` | 1 row per day, 2020-01-01 to 2024-12-31 | Marked as the date table; joins `snapshot_date`, `fee_date`, `txn_date`. |
| `dim_client` | 1 row per client (2,500) | `client_tier` ∈ Retail, HNW, UHNW (current tier only). 175 clients have no snapshot after 2023. |

Model note: besides the 11 fact → dimension relationships, the posted model also has `dim_security[benchmark_id] → dim_benchmark[benchmark_id]`, so INFO.VIEW.RELATIONSHIPS returns 12 rows.
