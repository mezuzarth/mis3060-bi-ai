# HW4 — Cleaning the Wildcat Capital Data
MIS3060 Business Intelligence with AI · Villanova University

Audit, clean and validate the eight-table Wildcat Capital extract without inventing data, with a full audit trail.

## Structure
```
hw04/
├── README.md                     this file
├── decision_log.md               Part B: one entry per issue (written before cleaning code)
├── Wildcat Capital/              raw extract (read-only; not committed)
├── scripts/
│   ├── 00_investigate.py         read-only evidence checks for the decision log
│   ├── 01_profile.py             Part A: generic profiler (raw or clean)
│   ├── 02_clean.py               Part C: cleaning program with asserts
│   └── 03_validate.py            Part D: RI function, rules, reconciliations, IQR, scorecard
├── data/
│   ├── clean/                    8 clean tables + README_clean.md
│   └── audit/                    cleaning_log.csv, value_changes.csv, quarantine_*.csv
└── reports/
    ├── profile_raw.csv, dq_summary_raw.csv          Part A
    ├── investigation_raw.txt                         evidence for Part B
    ├── clean_run_output.txt                          Part C console output
    ├── data_quality_scorecard.csv                    Part D
    ├── ri_results.csv, rule_results.csv, reconciliations.csv, iqr_outliers.csv
    ├── validate_run_output.txt                       Part D console output
    └── cleaning_report.md                            Part E
```

## How to run
From the `hw04/` folder, with the eight raw CSVs in `Wildcat Capital/` (Python 3 + pandas):
```
python scripts/01_profile.py                                        # audit raw  -> reports/profile_raw.csv, dq_summary_raw.csv
python scripts/00_investigate.py > reports/investigation_raw.txt   # evidence for the decision log
python scripts/02_clean.py                                          # clean      -> data/clean/, data/audit/
python scripts/03_validate.py                                       # validate raw + clean -> reports/*.csv
```
`02_clean.py` stops with an `AssertionError` if any fix does not do what the decision log claims.

## Results at a glance
- Profiler found all **13 relationships** (10 ID-based, 3 date) by naming convention, with no per-table hard-coding
- **199,280** values changed (logged), **200** rows quarantined, **5** flag columns added; raw = clean + quarantined for all 8 tables
- Clean data: **100%** referential match on all 13 relationships, **43/43** business rules pass, **6/6** reconciliations at 100%

## Claude Code review findings
*(Fill in from your Claude Code reviews before each commit: what it flagged and what you did.)*

| Script | What Claude Code flagged | What I did |
|---|---|---|
| 01_profile.py | | |
| 02_clean.py | | |
| 03_validate.py | | |

## Commits
One or more per part (A–E), each message stating specifically what changed.
