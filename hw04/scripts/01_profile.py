#!/usr/bin/env python3
"""
HW4 Part A - 01_profile.py
Generic data-quality profiler for the Wildcat Capital extract.

Nothing below is hard-coded to a specific column. Keys and relationships are
inferred from naming conventions:
  * a table's primary key is its first column (dims always; facts if it ends in _id/_key)
  * a column whose name ends with a dimension's PK name is a foreign key
    (e.g. advisor_id, primary_advisor_id -> dim_advisor.advisor_id)
  * date-typed columns in fact tables are checked against dim_date

Run from your hw04/ folder:
    python scripts/01_profile.py
    python scripts/01_profile.py --data-dir data/clean --stage clean     # reuse after cleaning

Outputs:
    reports/profile_<stage>.csv      one row per table x column
    reports/dq_summary_<stage>.csv   one row per finding, tagged ERROR / WARN / INFO
"""

import argparse
import re
import warnings
from pathlib import Path

import pandas as pd

# Default table list = the eight files the assignment says to use (other files in the folder are ignored).
# Override with --tables, or --tables all to profile every CSV in the folder. All checks below are generic.
TABLES = [
    "dim_advisor", "dim_client", "dim_date", "dim_security", "dim_benchmark",
    "fact_fees", "fact_portfolio_snapshot", "fact_transactions",
]
# Optional row counts published with the extract; tables not listed simply skip this comparison
EXPECTED_ROWS = {
    "dim_advisor": 25, "dim_client": 2525, "dim_date": 1827, "dim_security": 500,
    "dim_benchmark": 8, "fact_fees": 122197, "fact_portfolio_snapshot": 129547,
    "fact_transactions": 298772,
}
NULL_TOKENS = {"null", "none", "n/a", "na", "nan", "nat", "-", "--", "?", "missing", "#n/a"}
START_WORDS = ("start", "open", "begin", "inception", "hire", "join", "onboard", "effective", "birth")
END_WORDS = ("end", "close", "term", "exit", "inactive", "leave", "until")
STATUS_WORDS = ("status", "active", "is_")
ENTITY_WORDS = ("name", "email", "ticker", "symbol", "cusip", "isin")

# ---------------------------------------------------------------- value classification
CATEGORY_PATTERNS = [
    ("number",         re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)$")),
    ("sci",            re.compile(r"^[+-]?\d+(\.\d+)?[eE][+-]?\d+$")),
    ("thousands",      re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$")),
    ("currency",       re.compile(r"^[+-]?\(?[+-]?\$\s?[\d,]*\.?\d+\)?$")),
    ("accounting",     re.compile(r"^\([\d,]*\.?\d+\)$")),
    ("percent",        re.compile(r"^[+-]?\d*\.?\d+\s?%$")),
    ("date_iso",       re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("datetime",       re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}")),
    ("date_slash",     re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")),
    ("date_ymd_slash", re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")),
    ("date_text",      re.compile(r"^(\d{1,2}[- ][A-Za-z]{3,9}[- ]\d{2,4}|[A-Za-z]{3,9}\.? \d{1,2},? \d{4})$")),
    ("bool",           re.compile(r"^(true|false|yes|no)$", re.I)),
]
FAMILY = {
    "number": "numeric", "sci": "numeric", "thousands": "numeric", "currency": "numeric",
    "accounting": "numeric", "percent": "numeric",
    "date_iso": "date", "datetime": "date", "date_slash": "date",
    "date_ymd_slash": "date", "date_text": "date", "bool": "bool",
}


def classify(v: str) -> str:
    t = v.strip()
    if t == "":
        return "blank"
    if t.lower() in NULL_TOKENS:
        return "null_token"
    for name, pat in CATEGORY_PATTERNS:
        if pat.match(t):
            return name
    return "text"


def shape(v: str) -> str:
    """'C0042' -> 'A9999', '2023-01-05' -> '9999-99-99', 'Smith ' -> 'Aa+ '."""
    s = re.sub(r"\d", "9", v)
    s = re.sub(r"[A-Z]", "A", s)
    s = re.sub(r"[a-z]", "a", s)
    s = re.sub(r"a{2,}", "a+", s)
    return s if s else "<blank>"


def norm_key(v: str) -> str:
    """Key normalisation used to show which mismatches are *format* problems."""
    v = re.sub(r"\s+", "", str(v)).upper()
    v = re.sub(r"\.0+$", "", v)                      # 45.0 -> 45
    return re.sub(r"(?<![0-9])0+(?=[0-9])", "", v)   # C0042 -> C42, 0042 -> 42


def to_num(s: pd.Series) -> pd.Series:
    t = s.str.strip()
    neg = t.str.match(r"^\(.*\)$")
    t = t.str.replace(r"[\$,%\s()]", "", regex=True)
    n = pd.to_numeric(t, errors="coerce")
    return n.where(~neg, -n)


_DATE_CACHE = {}


def _parse_one_date(x: str):
    """Parse one value; anything unparseable or outside pandas' range (e.g. 1000-01-01) -> NaT."""
    if x == "" or x.lower() in NULL_TOKENS:
        return pd.NaT
    try:
        if re.fullmatch(r"(19|20)\d{6}", x):            # 20230131 style date keys
            return pd.to_datetime(x, format="%Y%m%d")
        if not re.search(r"[-/ ,]", x):                  # bare numbers like 45 or 1000 are not dates
            return pd.NaT
        return pd.to_datetime(x)
    except Exception:                                    # bad text, impossible dates, out-of-bounds years
        return pd.NaT


def to_date(s: pd.Series, cache_key=None) -> pd.Series:
    if cache_key is not None and cache_key in _DATE_CACHE:
        return _DATE_CACHE[cache_key]
    t = s.str.strip()
    uniq = t.unique()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = {u: _parse_one_date(u) for u in uniq}
    result = pd.to_datetime(t.map(parsed), errors="coerce")
    if cache_key is not None:
        _DATE_CACHE[cache_key] = result
    return result


def examples(vc: pd.Series, mask: pd.Series, k: int = 5) -> str:
    sub = vc[mask].head(k)
    return " | ".join(f"{v!r} (x{c})" for v, c in sub.items())


# ---------------------------------------------------------------- findings collector
FINDINGS = []


def add(table, column, group, check, severity, rows, total, example="", detail=""):
    FINDINGS.append({
        "table": table, "column": column, "check_group": group, "check": check,
        "severity": severity, "rows_affected": int(rows),
        "pct_of_rows": round(rows / total, 6) if total else 0.0,
        "example": example, "detail": detail,
    })


# ---------------------------------------------------------------- group 1: column level
def profile_column(table: str, col: str, s: pd.Series) -> dict:
    n = len(s)
    vc = s.value_counts()
    vals = list(vc.index)
    cats = pd.Series([classify(v) for v in vals], index=vc.index)
    fams = cats.map(lambda c: FAMILY.get(c, c))

    cat_counts = vc.groupby(cats).sum()
    blank = int(cat_counts.get("blank", 0))
    null_tok = int(cat_counts.get("null_token", 0))
    non_null = n - blank - null_tok

    fam_counts = vc.groupby(fams).sum().drop(["blank", "null_token"], errors="ignore")
    expected = fam_counts.idxmax() if len(fam_counts) else "empty"
    fam_total = int(fam_counts.get(expected, 0))
    unparseable = 0 if expected in ("text", "empty") else non_null - fam_total

    in_fam = cats[fams == expected]
    cat_in_fam = vc.loc[in_fam.index].groupby(in_fam).sum().sort_values(ascending=False)
    dom_cat = cat_in_fam.index[0] if len(cat_in_fam) else ""
    nonstandard = fam_total - (int(cat_in_fam.iloc[0]) if len(cat_in_fam) else 0)
    formats = " | ".join(f"{c}:{k}" for c, k in cat_in_fam.items())

    shp = pd.Series([shape(v) for v in vals], index=vc.index)
    shape_counts = vc.groupby(shp).sum().sort_values(ascending=False)
    top_shapes = " | ".join(f"[{k}] {c / n:.1%}" for k, c in shape_counts.head(3).items())

    ws_mask = pd.Series([v != v.strip() for v in vals], index=vc.index, dtype=bool)
    dbl_mask = pd.Series([bool(re.search(r"\S\s{2,}\S", v)) for v in vals], index=vc.index, dtype=bool)
    lead_trail, double_sp = int(vc[ws_mask].sum()), int(vc[dbl_mask].sum())

    norm = pd.Series([re.sub(r"\s+", " ", v.strip()).lower() for v in vals], index=vc.index)
    distinct, distinct_norm = len(vc), norm.nunique()

    vmin = vmax = ""
    neg = zero = 0
    if expected == "numeric":
        num = to_num(s)
        vmin, vmax = num.min(), num.max()
        neg, zero = int((num < 0).sum()), int((num == 0).sum())
    elif expected == "date":
        d = to_date(s, (table, col))
        vmin, vmax = d.min(), d.max()
        stripped = s.str.strip()
        date_shaped = stripped.map(lambda v: FAMILY.get(classify(v)) == "date")
        not_real = date_shaped & d.isna()
        if not_real.any():
            add(table, col, "1-column", "date-shaped values that are not usable dates", "WARN",
                int(not_real.sum()), n,
                " | ".join(f"{v!r} (x{c})" for v, c in stripped[not_real].value_counts().head(5).items()),
                "Looks like a date but cannot be one (sentinel such as 1000-01-01, or impossible like 2023-02-30). "
                "Decide: placeholder 'unknown' member (structure) or error?")

    top_values = ""
    if distinct <= 25:
        top_values = " | ".join(f"{v!r}:{c}" for v, c in vc.items())

    # ---- findings
    key_like = bool(re.search(r"(_id|_key|_code)$", col.lower()))
    if blank:
        add(table, col, "1-column", "blank values", "WARN" if key_like else "INFO", blank, n, "",
            "Decide: legitimately empty (structure) or missing (defect)?")
    if null_tok:
        add(table, col, "1-column", "null-like text tokens", "WARN", null_tok, n,
            examples(vc, cats == "null_token"),
            "Text like 'None'/'N/A' standing in for missing; default read_csv would silently turn it into NaN.")
    if unparseable:
        bad = (fams != expected) & ~cats.isin(["blank", "null_token"])
        add(table, col, "1-column", f"values not parseable as {expected}", "ERROR", unparseable, n,
            examples(vc, bad), f"Column is mostly {expected}; these values will fail type conversion.")
    if nonstandard:
        add(table, col, "1-column", "mixed formats", "WARN", nonstandard, n,
            examples(vc, in_fam.reindex(vc.index).ne(dom_cat) & (fams == expected)),
            f"Formats found: {formats}. Majority format = {dom_cat}.")
    if lead_trail:
        add(table, col, "1-column", "leading/trailing whitespace", "WARN", lead_trail, n,
            examples(vc, ws_mask), "Breaks joins and groupings ('A1 ' != 'A1').")
    if double_sp:
        add(table, col, "1-column", "repeated internal spaces", "WARN", double_sp, n, examples(vc, dbl_mask))
    if distinct_norm < distinct and distinct <= 500:
        grp = norm.groupby(norm).filter(lambda g: len(g) > 1)
        ex = " | ".join(" / ".join(repr(v) for v in grp[grp == key].index) for key in grp.unique()[:4])
        add(table, col, "1-column", "case/spacing variants of same value", "WARN",
            int(vc[grp.index].sum()), n, ex, f"{distinct} raw values collapse to {distinct_norm} after trim+lowercase.")
    real_shapes = shape_counts.drop("<blank>", errors="ignore")
    if key_like and len(real_shapes) > 1:
        add(table, col, "1-column", "inconsistent key format", "WARN",
            int(real_shapes.iloc[1:].sum()), n, " | ".join(real_shapes.index[:5]),
            "Different shapes in one key column (e.g. lost leading zeros, '45.0'). Will break joins.")
    if distinct == 1 and n > 1:
        add(table, col, "1-column", "constant column", "INFO", n, n, repr(vals[0]))
    if neg:
        add(table, col, "1-column", "negative values", "INFO", neg, n, "",
            "Decide the sign rule for this column (legit e.g. withdrawals/losses, or an error?).")
    if expected == "date" and pd.notna(vmin) and (vmin.year < 1900 or vmax.year > 2030):
        add(table, col, "1-column", "implausible dates", "WARN", 0, n, f"min={vmin} max={vmax}")

    return {
        "table": table, "column": col, "rows": n, "blank": blank, "null_tokens": null_tok,
        "pct_missing": round((blank + null_tok) / n, 6) if n else 0,
        "distinct": distinct, "distinct_normalized": distinct_norm,
        "expected_type": expected, "pct_unparseable": round(unparseable / n, 6) if n else 0,
        "pct_nonstandard_format": round(nonstandard / n, 6) if n else 0,
        "formats_found": formats, "top_shapes": top_shapes,
        "leading_trailing_ws": lead_trail, "double_spaces": double_sp,
        "min": vmin, "max": vmax, "negatives": neg, "zeros": zero, "top_values": top_values,
    }


def find_pk(table: str, df: pd.DataFrame):
    first = df.columns[0]
    if table.startswith("dim_") or re.search(r"(_id|_key)$", first.lower()):
        return first
    return None


def is_date_col(table, col, df, types):
    if types.get((table, col)) == "date":
        return True
    if "date" in col.lower() or col.lower().endswith("_dt"):
        return to_date(df[col], (table, col)).notna().mean() > 0.9
    return False


# ---------------------------------------------------------------- group 2: single table
def table_checks(table, df, pk, types):
    n = len(df)
    exp = EXPECTED_ROWS.get(table)
    add(table, "", "2-table", "row count", "INFO" if exp in (None, n) else "WARN", n, n, "",
        f"Read {n:,} rows x {df.shape[1]} cols" + (f"; expected {exp:,}." if exp else "; no expected count given."))
    bad_headers = [c for c in df.columns if c != c.strip()]
    if bad_headers:
        add(table, "", "2-table", "column header whitespace", "WARN", 0, n, repr(bad_headers))

    if pk:
        keys = df[pk]
        nulls = int((keys.str.strip() == "").sum())
        if nulls:
            add(table, pk, "2-table", "blank primary key", "ERROR", nulls, n)
        dup = keys.duplicated(keep=False)
        if dup.any():
            add(table, pk, "2-table", "duplicate primary key", "ERROR", int(dup.sum()), n,
                " | ".join(f"{k!r} (x{c})" for k, c in keys[dup].value_counts().head(5).items()),
                "Rows involved in a duplicated key. A dimension with duplicate keys breaks a 1-to-many join.")
        ndup = keys.map(norm_key).duplicated(keep=False) & ~dup
        if ndup.any():
            add(table, pk, "2-table", "keys collide after normalisation", "WARN", int(ndup.sum()), n,
                " | ".join(keys[ndup].head(6).map(repr)), "Different raw keys that look like the same key.")

    full_dup = int(df.duplicated(keep="first").sum())
    if full_dup:
        add(table, "", "2-table", "exact duplicate rows", "ERROR", full_dup, n, "", "Extra copies (first copy not counted).")

    others = [c for c in df.columns if c != pk]
    if pk and others:
        same_content = int(df.duplicated(subset=others, keep="first").sum()) - full_dup
        if same_content > 0:
            add(table, "", "2-table", "same content under different key", "WARN", same_content, n, "",
                "Possible double-load under a new ID.")
    normdf = df.apply(lambda c: c.str.strip().str.lower().str.replace(r"\s+", " ", regex=True))
    near = int(normdf.duplicated(subset=others, keep="first").sum()) - int(df.duplicated(subset=others, keep="first").sum())
    if near > 0:
        add(table, "", "2-table", "near-duplicate rows (differ only by case/spacing)", "WARN", near, n)

    ent_cols = [c for c in others if any(w in c.lower() for w in ENTITY_WORDS)]
    if table.startswith("dim_") and ent_cols:
        ent_dup = normdf.duplicated(subset=ent_cols, keep=False) & normdf[ent_cols].ne("").all(axis=1)
        if ent_dup.any():
            add(table, ",".join(ent_cols), "2-table", "possible same entity under two IDs", "WARN",
                int(ent_dup.sum()), n, " | ".join(df.loc[ent_dup, pk].head(6)) if pk else "")

    # within-row contradictions: start-type date after end-type date
    date_cols = [c for c in df.columns if is_date_col(table, c, df, types)]
    starts = [c for c in date_cols if any(w in c.lower() for w in START_WORDS)]
    ends = [c for c in date_cols if any(w in c.lower() for w in END_WORDS)]
    for a in starts:
        for b in ends:
            if a == b:
                continue
            da, db = to_date(df[a], (table, a)), to_date(df[b], (table, b))
            bad = (da > db) & da.notna() & db.notna()
            if bad.any():
                add(table, f"{a} > {b}", "2-table", "start date after end date", "WARN", int(bad.sum()), n,
                    " | ".join(df.loc[bad, pk].head(5)) if pk else "")

    # status vs end-date: is a blank end date legitimate structure?
    status_cols = [c for c in df.columns if any(w in c.lower() for w in STATUS_WORDS) and df[c].nunique() <= 10]
    for sc in status_cols:
        for ec in ends:
            ct = pd.crosstab(df[sc].str.strip(), df[ec].str.strip().eq("").map({True: "end blank", False: "end filled"}))
            add(table, f"{sc} vs {ec}", "2-table", "status vs end-date crosstab", "INFO", 0, n, "",
                ct.to_string().replace("\n", " ; "))

    # recompute check: quantity x price vs amount/value
    qcols = [c for c in df.columns if re.search(r"share|quantity|qty|units", c.lower())]
    pcols = [c for c in df.columns if "price" in c.lower()]
    acols = [c for c in df.columns if re.search(r"amount|value", c.lower()) and "price" not in c.lower()]
    for q in qcols:
        for p in pcols:
            for a in acols:
                qv, pv, av = to_num(df[q]), to_num(df[p]), to_num(df[a])
                ok = qv.notna() & pv.notna() & av.notna()
                calc = qv * pv
                tol = (av.abs() * 0.005).clip(lower=0.01)
                mismatch = ok & ((calc - av).abs() > tol)
                sign_only = mismatch & ((calc.abs() - av.abs()).abs() <= tol)
                add(table, f"{q} x {p} vs {a}", "2-table", "recompute amount", "WARN" if mismatch.any() else "INFO",
                    int(mismatch.sum()), n, "",
                    f"{int(ok.sum()):,} comparable rows; {int(mismatch.sum()):,} mismatch, "
                    f"of which {int(sign_only.sum()):,} differ only in sign (sign convention?).")


# ---------------------------------------------------------------- group 3: referential integrity
def ri_checks(tables, pks, types):
    rels = []
    dims = {t: pks[t] for t in tables if t.startswith("dim_") and pks.get(t) and t != "dim_date"
            and pks[t].lower() not in ("id", "key")}
    for t, df in tables.items():
        for c in df.columns:
            if c == pks.get(t):
                continue
            matched = False
            for dt, dpk in dims.items():
                if dt != t and c.lower().endswith(dpk.lower()):
                    rels.append((t, c, dt, dpk))
                    matched = True
            if not matched and re.search(r"(_id|_key)$", c.lower()) and "date" not in c.lower():
                add(t, c, "3-RI", "id column not linked to any dimension", "INFO", 0, len(df), "",
                    "Confirm by hand: no dimension exists for it, or the key is named differently.")

    for t, c, dt, dpk in rels:
        fk, n = tables[t][c], len(tables[t])
        dimkeys = set(tables[dt][dpk])
        dimnorm = set(map(norm_key, dimkeys))
        null = fk.str.strip().eq("") | fk.str.strip().str.lower().isin(NULL_TOKENS)
        orphan = ~null & ~fk.isin(dimkeys)
        fixable = orphan & fk.map(norm_key).isin(dimnorm)
        nn = int((~null).sum())
        match_rate = (nn - int(orphan.sum())) / nn if nn else 1.0
        add(t, c, "3-RI", f"FK -> {dt}.{dpk}", "INFO", nn - int(orphan.sum()), n, "",
            f"match rate {match_rate:.2%} of non-blank keys")
        if orphan.any():
            add(t, c, "3-RI", f"orphan FK (not in {dt})", "ERROR", int(orphan.sum()), n,
                " | ".join(fk[orphan].value_counts().head(5).index.map(repr)),
                f"{fk[orphan].nunique()} distinct orphan keys; {int(fixable.sum()):,} rows would match after "
                f"trimming/case/leading-zero normalisation (format defect, not missing master data).")
        if null.any():
            add(t, c, "3-RI", "blank foreign key", "INFO", int(null.sum()), n, "",
                "Decide if legit (e.g. cash rows with no security) or missing.")

    if "dim_date" in tables:
        dd = tables["dim_date"]
        cal = None
        for c in [pks["dim_date"]] + [c for c in dd.columns if "date" in c.lower()]:
            parsed = to_date(dd[c], ("dim_date", c))
            if parsed.notna().mean() > 0.9:
                cal = pd.DatetimeIndex(parsed.dropna().dt.normalize().unique())
                add("dim_date", c, "3-RI", "calendar column used", "INFO", len(cal), len(dd), "",
                    f"{cal.min().date()} to {cal.max().date()}, {len(cal):,} distinct dates for {len(dd):,} rows")
                break
        if cal is not None:
            for t, df in tables.items():
                if not t.startswith("fact_"):
                    continue
                for c in df.columns:
                    if not is_date_col(t, c, df, types):
                        continue
                    d = to_date(df[c], (t, c))
                    present = d.notna()
                    orphan = present & ~d.dt.normalize().isin(cal)
                    rate = 1 - orphan.sum() / present.sum() if present.any() else 1
                    rels.append((t, c, "dim_date", "<date>"))
                    add(t, c, "3-RI", "date -> dim_date", "INFO", int(present.sum() - orphan.sum()), len(df), "",
                        f"match rate {rate:.2%}")
                    if orphan.any():
                        add(t, c, "3-RI", "date not in dim_date", "ERROR", int(orphan.sum()), len(df),
                            f"min={d[orphan].min().date()} max={d[orphan].max().date()}")
    return rels


# ---------------------------------------------------------------- group 4: cross-table business rules
def cross_table_checks(tables, types, rels):
    for t, c, dt, dpk in rels:
        if dt == "dim_date":
            continue
        fact = tables[t]
        dim = tables[dt].drop_duplicates(subset=[dpk])
        fact_dates = [x for x in fact.columns if is_date_col(t, x, fact, types)
                      and not re.search(r"birth|dob", x.lower())]
        for dc in [x for x in dim.columns if is_date_col(dt, x, tables[dt], types)]:
            low = dc.lower()
            kind = "start" if any(w in low for w in START_WORDS) else "end" if any(w in low for w in END_WORDS) else None
            if not kind:
                continue
            ref_map = pd.Series(to_date(dim[dc]).values, index=dim[dpk].values)
            ref = fact[c].map(ref_map)
            for fc in fact_dates:
                fd = to_date(fact[fc], (t, fc))
                bad = (fd < ref) if kind == "start" else (fd > ref)
                bad = bad & fd.notna() & ref.notna()
                if bad.any():
                    add(t, fc, "4-cross", f"{fc} {'before' if kind == 'start' else 'after'} {dt}.{dc}", "WARN",
                        int(bad.sum()), len(fact), "",
                        f"Joined on {c}. Activity outside the dimension's {kind} date: investigate.")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="Wildcat Capital")
    ap.add_argument("--stage", default="raw")
    ap.add_argument("--out-dir", default="reports")
    ap.add_argument("--tables", default=",".join(TABLES),
                    help="comma-separated table names to profile, or 'all' for every *.csv in --data-dir "
                         "(default: the eight assignment tables)")
    args = ap.parse_args()

    data, out = Path(args.data_dir), Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if args.tables == "all":
        names = sorted(p.stem for p in data.glob("*.csv"))
    else:
        names = [t.strip() for t in args.tables.split(",") if t.strip()]
    missing = [t for t in names if not (data / f"{t}.csv").exists()]
    if missing or not names:
        # Fail fast: a profile of a partial dataset would look complete and mislead the decision log
        raise SystemExit(f"ERROR: missing input file(s) in {data}/: {missing or 'no tables found'}. Nothing written.")
    tables = {t: pd.read_csv(data / f"{t}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
              for t in names}

    profile_rows, types, pks = [], {}, {}
    for t, df in tables.items():
        print(f"Profiling {t} ({len(df):,} rows)...")
        for c in df.columns:
            row = profile_column(t, c, df[c])
            profile_rows.append(row)
            types[(t, c)] = row["expected_type"]
        pks[t] = find_pk(t, df)
        table_checks(t, df, pks[t], types)

    rels = ri_checks(tables, pks, types)
    cross_table_checks(tables, types, rels)

    pd.DataFrame(profile_rows).to_csv(out / f"profile_{args.stage}.csv", index=False)
    f = pd.DataFrame(FINDINGS)
    f["_sev"] = f["severity"].map({"ERROR": 0, "WARN": 1, "INFO": 2})
    f = f.sort_values(["_sev", "table", "check_group"]).drop(columns="_sev")
    f.to_csv(out / f"dq_summary_{args.stage}.csv", index=False)

    print("\nRelationships detected:")
    for r in rels:
        print(f"  {r[0]}.{r[1]} -> {r[2]}.{r[3]}")
    print("\nFindings by table and severity:")
    print(f.pivot_table(index="table", columns="severity", values="check", aggfunc="count", fill_value=0))
    print(f"\nSaved {out / f'profile_{args.stage}.csv'} and {out / f'dq_summary_{args.stage}.csv'}")


if __name__ == "__main__":
    main()
