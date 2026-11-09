# Part D: Verification of Claude's `Top 10 Client Share`

Measure 11, drafted by Claude Desktop from my INFO.VIEW metadata (`claude/model_metadata.md`). The full prompt and reply are in `claude/dax_session.md`.

## 1. Did Claude's measure run as written?

Yes. I pasted it into `_Measures` exactly as Claude wrote it, and it was valid on the first try with no errors. I only set the format to Percentage, 2 decimals.

```DAX
Top 10 Client Share =
VAR LastSnap =
    LASTNONBLANK ( dim_date[Date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
VAR ClientAUM =
    FILTER (
        ADDCOLUMNS ( VALUES ( dim_client[client_id] ), "@AUM", CALCULATE ( [Ending AUM], LastSnap ) ),
        NOT ISBLANK ( [@AUM] )
    )
VAR Top10 = TOPN ( 10, ClientAUM, [@AUM], DESC, dim_client[client_id], ASC )
VAR Top10AUM = SUMX ( Top10, [@AUM] )
RETURN DIVIDE ( Top10AUM, [Ending AUM] )
```

Claude used only names from my metadata: `dim_date[Date]` (INFO.VIEW shows it capitalised), `dim_client[client_id]`, `fact_portfolio_snapshot`, and the existing `[Ending AUM]`. It invented no tables or columns.

**What the test returned.** I ran the measure for the grand total, each year, and each tier in 2024 in DAX query view, wrapping it in `FORMAT ( …, "0.0000000000" )` so the values came out unrounded:

| Slice | Power BI (Claude's measure) | pandas | Match |
|---|---:|---:|---|
| Total | 0.0615892675 | 0.0615892675 | ✓ |
| Year 2020 | 0.0704111532 | 0.0704111532 | ✓ |
| Year 2021 | 0.0637544613 | 0.0637544613 | ✓ |
| Year 2022 | 0.0553086505 | 0.0553086505 | ✓ |
| Year 2023 | 0.0603790892 | 0.0603790892 | ✓ |
| Year 2024 | 0.0615892675 | 0.0615892675 | ✓ |
| HNW 2024 | 0.0313967475 | 0.0313967475 | ✓ |
| Retail 2024 | 0.0183482183 | 0.0183482183 | ✓ |
| UHNW 2024 | 0.0812642675 | 0.0812642675 | ✓ |

All nine values agree with pandas to 10 decimal places. The grand total equals the 2024 row, as Claude said it should, because the last snapshot overall is 1 Dec 2024.

## 2. Rows of `reports/measure_reconciliation.csv` that prove it

| measure | slice | powerbi_value | pandas_value | match |
|---|---|---:|---:|---|
| Top 10 Client Share | Total | [from CSV] | 0.0615892675 | [TRUE] |
| Top 10 Client Share | Tier=HNW\|2024 | [from CSV] | 0.0313967475 | [TRUE] |
| Top 10 Client Share | Tier=Retail\|2024 | [from CSV] | 0.0183482183 | [TRUE] |
| Top 10 Client Share | Tier=UHNW\|2024 | [from CSV] | 0.0812642675 | [TRUE] |

The pandas side is independent of Power BI. It takes the snapshot rows on the slice's last date, ranks clients with `groupby("client_id")["aum"].sum().nlargest(10)`, and divides by the slice's total AUM. No TOPN, and nothing read from Power BI.

## 3. Edge cases checked

**Edge case 1: the grand total, and clients who left.** 175 clients (UHNW 9, HNW 50, Retail 116) have no snapshot after 2023. Claude's version fixes `LastSnap` (1 Dec 2024) *before* ranking, so these clients get BLANK and are filtered out. I checked whether the simpler hint version, `TOPN ( 10, VALUES ( dim_client[client_id] ), [Ending AUM] )`, would have gone wrong. It ranks each client on their *own* last snapshot, but the largest departed client's last balance is **$43,429,407.00**, below the 10th-largest current client (**$74,424,366.68**). So both versions pick the same 10 clients and return **6.1589%**. Claude's version is safer by design; in this data the two agree.

```DAX
// run in DAX query view: the hint version vs Claude's, side by side
DEFINE
    MEASURE _Measures[Top10 Hint Version] =
        VAR T = TOPN ( 10, VALUES ( dim_client[client_id] ), [Ending AUM], DESC )
        RETURN DIVIDE ( CALCULATE ( [Ending AUM], T ), [Ending AUM] )
EVALUATE
ROW ( "Claude", [Top 10 Client Share], "Hint version", [Top10 Hint Version] )
```
Result: **Claude 0.0615892675, hint version 0.0615892675**, identical.

**Edge case 2: the 2024 tier table (VALUES vs ALL).** Each tier gets its own top 10: HNW 3.14%, Retail 1.83%, UHNW 8.13%. All are under 100%, and none equals the firm-wide 6.16%. If the ranking used `ALL ( dim_client )` instead of `VALUES`, the firm-wide top 10 ($784.0M, all UHNW) would be divided by each tier's AUM. Retail would show **146.97%** and HNW **30.76%**, which is the ">100%" symptom in the guide's troubleshooting table. UHNW would not change (8.13%), because the firm's top 10 are all UHNW.

**Edge case 3: `dim_date[year] = 2022`.** Returns 5.53%, matching pandas at the 1 Dec 2022 snapshot. `LastSnap` moves to the slice's last date, so ranking and denominator use the same month.

**Edge case 4: ties and the tie-breaker.** At 1 Dec 2024, the 10th and 11th balances are not tied in any slice: firm/UHNW $74,424,366.68 vs $72,106,567.72, HNW $7,803,824.95 vs $7,754,987.10, Retail $928,501.84 vs $914,405.62. The `client_id ASC` tie-breaker therefore never changes the answer here, but it guarantees exactly 10 rows if a tie ever appears.

## 4. What I changed and why

Nothing in the logic. Claude's measure reconciled on every slice, so I kept it as written and set its format to **Percentage, 2 decimals**. I did not use the simpler hint version (`TOPN` over `VALUES` ranked by `[Ending AUM]`), because Claude's fixed-date ranking cannot be thrown off by departed clients' stale balances (edge case 1).

## 5. Claims Claude made that I confirmed or refuted

**Confirmed: "Without fixing LastSnap first, each client would be ranked on its own last snapshot, so a departed client could take a top-10 slot and push the share too low."** The mechanism is real. In pandas, taking each client's own last snapshot (what `[Ending AUM]` does per client inside TOPN) gives 175 departed clients holding stale balances worth $419.7M, the same gap as Part C(a). For this data, though, the *effect* is zero: the biggest stale balance ($43.4M) is far below the 10th-largest current client ($74.4M), and the side-by-side query in edge case 1 returns 6.1589% for both versions. The claim is correct in principle but makes no difference on the current data. It would matter if a large UHNW client left.

**Refuted for this data: "Zero or negative AUM … stays in the ranking and can push the share slightly above what you'd expect; consider `[@AUM] > 0`."** pandas shows the minimum `aum` in all 129,547 snapshot rows is **$1,000.00**, and no row is zero or negative. `NOT ISBLANK` and `> 0` would select exactly the same clients, so the change is unnecessary.
