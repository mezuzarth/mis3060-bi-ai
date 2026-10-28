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
| 01_profile.py | (High) A missing input CSV was printed and skipped, so the script could write a profile of a partial dataset that looked complete | Fixed: the script now stops with an error and writes nothing if any expected file is missing |
| 01_profile.py | (Medium) Table list and expected row counts were hard-coded to this extract | Partly fixed: the table list is now a --tables option (default = the 8 assignment files; all = every CSV in the folder), and row counts are optional. The checks themselves were already generic |
| 01_profile.py | (Low) Primary and foreign keys are detected from naming conventions, so unconventional names could be missed | Accepted: it found exactly the 13 relationships the assignment specifies; noted as a limitation, since other naming would need a hand-written mapping |
| 02_clean.py |(High) txn_date >= client_since assert seemed stricter than D16’s same-month rule |Not a bug: D16’s same-month allowance applies to the monthly fee/snapshot tables; transactions are daily and 0 precede client_since. Added a comment and a cleaning-log entry to make this explicit |
| 02_clean.py |(Medium) Quarantine raw_line_number was derived from the DataFrame index, not proven to match the raw file |Added an assert that row order is unchanged before quarantine, and the quarantine file now holds the untouched raw values |
| 02_clean.py |(Medium) Step 0 (whitespace) printed only a count, not a before/after check |Fixed: prints before/after counts and asserts both |
| 02_clean.py | (Low) State assert checked the final set of codes, not each row’s mapping|Fixed: asserts every changed row equals the mapping of its own original value |
| 03_validate.py | | |

## Commits
One or more per part (A–E), each message stating specifically what changed.
