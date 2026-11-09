# HW6: DAX Measure Library (AUM & Performance)
MIS3060 Business Intelligence with AI · Villanova University · Megan Zuzarth

A library of 12 DAX measures on Wildcat Capital's portfolio snapshot (ending AUM, growth, fee yield, organic growth, AUM-weighted alpha, concentration), each matched to its additivity class. Every value is reconciled to an independent pandas calculation from the clean CSVs.

## Structure

```
hw06/
├── README.md                          this file
├── *.csv                              Wildcat Capital Clean CSVs (pandas input)
├── powerbi/
│   ├── hw06.pbix                      posted model + _Measures table + "Measures" report page
│   ├── measures.md                    Part A documentation (DAX, pattern, meaning) + Part C answers
│   └── powerbi_export_query.dax       one DAX query that exports every reconciliation value
├── scripts/
│   ├── 01_reconcile_measures.py       Part B: pandas recompute + reconciliation
│   ├── 02_part_c_analysis.py          Part C: pandas evidence for questions (a)–(d)
│   └── make_export_query.py           helper: regenerates powerbi_export_query.dax from the script's slice lists
├── reports/
│   ├── powerbi_values.csv             Power BI values (measure, slice, value), from DAX query view
│   ├── pandas_values.csv              pandas values (written by script 01)
│   ├── measure_reconciliation.csv     measure, slice, powerbi_value, pandas_value, abs_diff, match
│   └── part_c_evidence.txt            output of script 02
└── claude/
    ├── model_metadata.md              INFO.VIEW exports + grain/additivity notes
    ├── dax_session.md                 Part D prompt(s) and Claude's full responses
    └── verification.md                Part D verification
```

## How to run

Requires Python 3 with pandas (`pip install pandas`).

```bash
cd hw06
python scripts/01_reconcile_measures.py     # -> reports/pandas_values.csv and reports/measure_reconciliation.csv
python scripts/02_part_c_analysis.py        # -> reports/part_c_evidence.txt
```

The scripts find the CSVs in `hw06/` or `hw06/data/` (download suffixes like `fact_fees (3).csv` are fine), or in the folder named by the environment variable `WILDCAT_DATA_DIR`.

**Getting the Power BI side:** open `powerbi/hw06.pbix` → **DAX query view** → paste `powerbi/powerbi_export_query.dax` → **Run** → **Copy** the result grid (with headers) → paste into `reports/powerbi_values.csv`. The script accepts either comma- or tab-separated input. The query wraps each number in `FORMAT ( v, "0.0000000000" )` so values come out unrounded, not as `$12.73B`.

## Reconciliation coverage (91 rows)

| Slice | Measures |
|---|---|
| Grand total (`Total`) | all 16: naive SUM, Total Fees, Net Flows, measures 1–11 including LY/PM/YoY/MoM |
| By year (`Year=2020` … `Year=2024`) | naive SUM, 1, 4 (LY + YoY), 6, 7, 8, 9, 10 |
| By tier, 2024 (`Tier=HNW\|2024`, …) | 1, 3, 4 (LY + YoY), 7, 8, 9, 10, 11 |
| December 2024 (`Month=2024-12`) | Ending AUM, 5 (PM + MoM) |

Tolerances: 0.01 for currency and counts, 0.0001 for ratios, percentages and bps, and an exact match for `Alpha Signal` (text). Blank on both sides (e.g. 2020 YoY, which has no prior year) counts as a match.

**`AUM (naive SUM)` is included on purpose.** Power BI and pandas both give $566,681,084,542.48 at the grand total, 44× the true Ending AUM of $12,729,572,078.86. Both tools make the same mistake when a balance is summed across months.

**Result: 91 / 91 rows match.** The largest absolute difference is 0.00009, on `AUM (naive SUM)` at the grand total ($566.7 B, floating-point rounding), well inside the 0.01 tolerance. Every ratio row differs by less than 0.0000000001.

## Mismatches and fixes

All 91 rows matched on the first run, so no measure or pandas calculation needed fixing. Two problems came up earlier, before the reconciliation:

- **Card visuals showed nothing.** The measure was fine: a DAX query returned $12,729,572,078.86 and a table visual displayed it. The new Card visual just doesn't render on Apporto's Power BI.
- **`dim_date` went empty (0 rows).** This happened after the model tried to recalculate. The posted model's queries point to CSVs on the instructor's `E:\` drive, which Apporto can't reach. I repointed all 8 sources to my own copies of the Wildcat Capital Clean CSVs and refreshed. Ending AUM, the 1,827 dates and the 129,547 snapshot rows were unchanged, so it is the same data, and the 91/91 reconciliation confirms it.

## AI process

- **Claude** (desktop app) drafted the DAX library, `01_reconcile_measures.py`, `02_part_c_analysis.py` and the export query. I ran the scripts myself in VS Code.
- **Claude Desktop** drafted measure 11, `Top 10 Client Share`, from my exported metadata (`claude/dax_session.md`). It ran as written and reconciled on every slice. I tested its claims in Power BI and pandas (`claude/verification.md`).
- **Claude Code review** of the scripts before committing:

| What Claude Code flagged | What I did |
|---|---|
| [FILL IN] | [FILL IN] |
| [FILL IN] | [FILL IN] |

## Notes
- **Model:** 12 relationships (the 11 fact → dimension relationships plus `dim_security → dim_benchmark`), all many-to-one and single direction. INFO.VIEW.RELATIONSHIPS shows a 13th, a hidden auto date/time link on `dim_client[client_since]`, which no measure uses.
- **`dim_date` marked as the date table:** the posted model didn't have it marked (Power BI had created a hidden auto-date table on `dim_date[date]`). I marked it after reloading the data.
- **Data sources:** repointed from the instructor's `E:\OneDrive…\Wildcat Capital Clean\` paths to my own copies of the same CSVs so the model could refresh (see *Mismatches and fixes*).
- **Cards on the Measures page:** Power BI's Card visual renders blank on Apporto, but the values are correct (the same measure in a table visual shows $12,729,572,078.86), so the cards should display normally in a current Power BI Desktop.
- `hw06.pbix` is about 22 MB, under GitHub's 100 MB limit.
