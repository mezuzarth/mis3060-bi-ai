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
- Clean data: **100%** referential match on all 13 relationships, **44/44** business rules pass, **6/6** reconciliations at 100%

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
| 03_validate.py | (High) pct_referential_match blank for some tables|Not a bug: blank only for tables with no foreign keys, where it doesn’t apply. Added fk_relationships_checked and documented the metric definitions |
| 03_validate.py |(High) Type validity excludes blanks |Intentional: blanks are measured by completeness, so they aren’t counted twice. Documented in the script header|
| 03_validate.py |(Medium) No rule requiring security_id on Buy/Sell/Dividend| Fixed: added the rule (now 44 rules)|
| 03_validate.py | (Medium) RI function only does exact text matching|Exact matching kept as the default (matches BI joins, exposes format defects); added an optional normalize= argument for reuse in Assignment 5 |
| 03_validate.py |(Low) Pooled rule-pass rate is hard to interpret| Accepted: per-rule detail is in rule_results.csv; definition documented|
| 03_validate.py |(Low) IQR meaning is narrative only |Accepted: the assignment asks for that sentence; IQR flags are never used to change data|

## Commits
## Commits
- b352f51 HW4 Part A: generic profiler (4 check groups), finds 10 ID + 3 date relationships; profile_raw + dq_summary_raw
- b46ad76 HW4 Part A: add profile_raw and dq_summary_raw reports; allow required CSVs in hw04/.gitignore
- 6e67b3f HW4 Part B: decision log, 21 entries; 6 defects fixed/quarantined, 5 flags, 10 legit structures verified
- 74eafe2 HW4 Part C: clean 8 tables - 200 orphan txns quarantined, 199,280 value changes logged, 5 flag columns; raw = clean + quarantined
- 06427c0 HW4 Part A: Claude Code review fixes - fail fast on missing input files, --tables option
- 971e3dd HW4 Part C: Claude Code review fixes - raw-value quarantine with verified line numbers, before/after on every step
- c0e3490 HW4 Part D: Claude Code review fixes - security_id rule (44 rules), fk_relationships_checked, optional key normalization, metric definitions
- e9db513 HW4 Part D: Claude Code review fixes - security_id rule (44 rules), fk_relationships_checked, optional key normalization; report updated to match
