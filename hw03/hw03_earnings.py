"""
MIS3060 - HW03: Quarterly earnings dataset from SEC EDGAR 8-K filings.

For five public companies, this script:
  1. Pulls the company's filing history from the SEC submissions API.
  2. Keeps 8-K filings that include Item 2.02 (Results of Operations).
  3. Takes the four most recent of those filings (one per quarter).
  4. Downloads the earnings press release (Exhibit 99.x) for each filing.
  5. Uses regular expressions to extract revenue, diluted EPS, net income,
     and the reporting period.
  6. Saves everything to hw03/earnings_history.csv.

Run from the repo root:  python hw03/hw03_earnings.py
"""

import csv
import os
import re
import time

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# SEC requires a descriptive User-Agent on every request.
HEADERS = {"User-Agent": "MIS3060 Villanova mzuzarth@villanova.edu"}

# SEC allows at most 10 requests per second; wait 0.2 s after every request.
REQUEST_DELAY = 0.2

FILINGS_PER_COMPANY = 4
NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    {"company": "Apple Inc.", "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation", "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.", "ticker": "JPM", "cik": "0000019617"},
    {"company": "Walmart Inc.", "ticker": "WMT", "cik": "0000104169"},
]

CSV_COLUMNS = [
    "company", "ticker", "cik", "filing_date", "period",
    "revenue_reported", "eps_diluted", "net_income",
]

# Output path is built from this script's own folder so it works no matter
# which directory the script is launched from.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "earnings_history.csv")


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def sec_get(url):
    """GET a URL with the required User-Agent header, then pause for the rate limit."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response
    finally:
        time.sleep(REQUEST_DELAY)


# ---------------------------------------------------------------------------
# Step 1-2: Find and select earnings 8-K filings
# ---------------------------------------------------------------------------

def get_earnings_filings(cik):
    """Return the most recent 8-K / Item 2.02 filings for a 10-digit CIK."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = sec_get(url).json()
    recent = data["filings"]["recent"]

    matches = []
    # The lists under filings.recent are parallel: index i in each list
    # describes the same filing.
    for i in range(len(recent["form"])):
        form = recent["form"][i]
        items = recent["items"][i] or ""
        if form == "8-K" and "2.02" in items:
            matches.append({
                "filing_date": recent["filingDate"][i],
                "accession": recent["accessionNumber"][i],
                "primary_doc": recent["primaryDocument"][i],
            })

    # Dates are YYYY-MM-DD strings, so sorting them as text sorts them by date.
    matches.sort(key=lambda f: f["filing_date"], reverse=True)
    return matches[:FILINGS_PER_COMPANY]


# ---------------------------------------------------------------------------
# Step 3: Locate and download the press release
# ---------------------------------------------------------------------------

def find_press_release(folder_url, primary_doc):
    """Return the file name of the earnings press release in a filing folder, or None."""
    index = sec_get(folder_url + "index.json").json()
    names = [item["name"] for item in index["directory"]["item"]]

    # Candidate files: .htm documents other than the 8-K cover document.
    htm_files = [
        n for n in names
        if n.lower().endswith(".htm") and n.lower() != (primary_doc or "").lower()
    ]

    exhibit_99 = [n for n in htm_files if "99" in n]
    if exhibit_99:
        # Prefer Exhibit 99.1 (e.g. ex99-1.htm, ex991.htm, ex99_1.htm) over 99.2, etc.
        for name in exhibit_99:
            if re.search(r"99[-_.]?0?1(?!\d)", name):
                return name
        return exhibit_99[0]

    # Fallback: a few filers name the exhibit without "99"
    # (e.g. "q2fy26pr.htm"). Accept an obvious press-release name.
    for name in htm_files:
        if re.search(r"pr\.htm$|press|release", name, re.IGNORECASE):
            return name

    return None


def html_to_text(html_bytes):
    """Strip HTML tags and collapse all runs of whitespace to single spaces."""
    soup = BeautifulSoup(html_bytes, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Step 4: Regex extraction
# ---------------------------------------------------------------------------

# A dollar amount with a required unit, e.g. "$94.9 billion" or "$24,951 million".
MONEY_WITH_UNIT = r"\$\s?\d[\d,]*(?:\.\d+)?\s*(?:billion|million|thousand)\b"
# Up to 80 characters that are not a dollar sign: lets wording vary between
# the keyword and the figure while stopping at the first dollar amount.
GAP = r"[^$]{0,80}?"


def clean_money(value):
    """Normalize '$ 94.9  billion' -> '$94.9 billion'."""
    value = re.sub(r"\$\s+", "$", value)
    return re.sub(r"\s+", " ", value).strip()


def table_unit(text):
    """Detect the unit used in the financial tables ('in millions', etc.)."""
    if re.search(r"in millions", text, re.IGNORECASE):
        return " million"
    if re.search(r"in thousands", text, re.IGNORECASE):
        return " thousand"
    return ""


def first_match(patterns, text):
    """Return the first capture group of the first pattern that matches, else None."""
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def extract_revenue(text):
    # Sentences in the release, e.g. "quarterly revenue of $94.9 billion",
    # "Revenue was $76.4 billion", "revenue for the quarter ... of $46.7 billion".
    prose = [
        r"(?:total|quarterly|consolidated|record)?\s*(?:net\s+)?revenues?\s+(?:of|was|were)\s+(" + MONEY_WITH_UNIT + ")",
        r"net\s+sales\s+(?:of|was|were)\s+(" + MONEY_WITH_UNIT + ")",
        r"total\s+(?:net\s+)?revenues?" + GAP + "(" + MONEY_WITH_UNIT + ")",
        r"(?:revenues?|net\s+sales)" + GAP + "(" + MONEY_WITH_UNIT + ")",
    ]
    value = first_match(prose, text)
    if value:
        return clean_money(value)

    # Fallback: income-statement table row, e.g. "Total net sales $ 94,930".
    table = [
        r"total\s+net\s+sales\s+\$\s?([\d,]{3,}(?:\.\d+)?)",
        r"total\s+(?:net\s+)?revenues?(?:,\s*net)?\s+\$\s?([\d,]{3,}(?:\.\d+)?)",
        r"\brevenues?\s+\$\s?([\d,]{3,}(?:\.\d+)?)",
    ]
    value = first_match(table, text)
    if value:
        return "$" + value + table_unit(text)
    return NOT_FOUND


def extract_eps(text):
    eps = r"\$\s?(\d+\.\d{2})"
    patterns = [
        # "diluted earnings per share of $1.64", "Diluted earnings per share was $3.65"
        r"diluted\s+earnings\s+per\s+(?:common\s+)?share" + GAP + eps,
        # "earnings per diluted share for the quarter were $1.08"
        r"earnings\s+per\s+diluted\s+share" + GAP + eps,
        # "diluted EPS of $0.88"
        r"diluted\s+EPS" + GAP + eps,
        # "$5.24 per diluted share" / "($5.24 per share)"
        eps + r"\s+per\s+diluted\s+share",
        # "GAAP EPS of $0.88" (last resort; EPS usually means diluted in releases)
        r"\bEPS\b" + GAP + eps,
        eps + r"\s+per\s+share",
    ]
    value = first_match(patterns, text)
    return "$" + value if value else NOT_FOUND


def extract_net_income(text):
    prose = [
        # "net income of $24.8 billion", "Net income was $27.2 billion",
        # "net income attributable to Walmart of $7.0 billion"
        r"net\s+income(?:\s+attributable\s+to\s+[A-Za-z.&,\s]{1,40}?)?\s+(?:of|was|were)\s+(" + MONEY_WITH_UNIT + ")",
        r"net\s+income" + GAP + "(" + MONEY_WITH_UNIT + ")",
    ]
    value = first_match(prose, text)
    if value:
        return clean_money(value)

    # Fallback: table row, e.g. "Net income $ 14,736" or
    # "Consolidated net income attributable to Walmart $ 7,026".
    table = [
        r"net\s+income(?:\s+attributable\s+to\s+[A-Za-z.&,\s]{1,40}?)?\s+\$\s?([\d,]{3,}(?:\.\d+)?)",
    ]
    value = first_match(table, text)
    if value:
        return "$" + value + table_unit(text)
    return NOT_FOUND


def extract_period(text):
    ordinal = r"(?:first|second|third|fourth)"
    sep = r"[\s\-‐‑–]"  # space, hyphen, or dash variants
    patterns = [
        # "fourth quarter fiscal 2024", "second quarter of fiscal year 2026",
        # "second-quarter 2025", "fourth quarter of 2024"
        ordinal + sep + r"quarter(?:\s+of)?(?:\s+fiscal)?(?:\s+year)?\s+(?:fiscal\s+)?(?:year\s+)?\d{4}",
        # "fiscal 2024 fourth quarter"
        r"fiscal(?:\s+year)?\s+\d{4}\s+" + ordinal + sep + r"quarter",
        # "Q2 FY26", "Q4 fiscal 2025"
        r"\bQ[1-4]\s*(?:FY\s?|fiscal\s+)?'?\d{2,4}\b",
        # "2Q25"
        r"\b[1-4]Q\s?\d{2}\b",
    ]

    # Use whichever pattern appears earliest in the release (the headline /
    # opening sentence normally names the quarter being reported).
    best = None
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m and (best is None or m.start() < best.start()):
            best = m
    if best:
        return re.sub(r"\s+", " ", best.group(0)).strip()

    # Fallback: "quarter ended June 30, 2025"
    m = re.search(r"quarter\s+ended\s+[A-Z][a-z]+\.?\s+\d{1,2},\s+\d{4}", text, re.IGNORECASE)
    if m:
        return m.group(0)
    return NOT_FOUND


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_filing(company, filing):
    """Download one filing's press release and return a CSV row, or None if skipped."""
    ticker = company["ticker"]
    cik_no_zeros = str(int(company["cik"]))
    accession_no_dashes = filing["accession"].replace("-", "")
    folder_url = f"https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{accession_no_dashes}/"

    exhibit = find_press_release(folder_url, filing["primary_doc"])
    if not exhibit:
        print(f"WARNING: {ticker} {filing['filing_date']} - press release not found, skipping")
        return None

    text = html_to_text(sec_get(folder_url + exhibit).content)

    return {
        "company": company["company"],
        "ticker": ticker,
        "cik": company["cik"],
        "filing_date": filing["filing_date"],
        "period": extract_period(text),
        "revenue_reported": extract_revenue(text),
        "eps_diluted": extract_eps(text),
        "net_income": extract_net_income(text),
    }


def main():
    rows = []

    for company in COMPANIES:
        ticker = company["ticker"]
        try:
            filings = get_earnings_filings(company["cik"])
        except Exception as e:
            print(f"WARNING: {ticker} - could not load filing list ({e}), skipping company")
            continue

        if not filings:
            print(f"WARNING: {ticker} - no 8-K Item 2.02 filings found")
            continue

        for filing in filings:
            try:
                row = process_filing(company, filing)
                if row is None:
                    continue
                rows.append(row)
                print(
                    f"{row['ticker']} | {row['period']} | "
                    f"Revenue: {row['revenue_reported']} | "
                    f"EPS: {row['eps_diluted']} | "
                    f"Net Income: {row['net_income']}"
                )
            except Exception as e:
                print(f"WARNING: {ticker} {filing['filing_date']} - press release not found, skipping ({e})")
                continue

    # Guarantee no blank / None cells: a blank means "not processed",
    # NOT_FOUND means "processed but the regex found nothing".
    for row in rows:
        for col in CSV_COLUMNS:
            if row.get(col) in (None, ""):
                row[col] = NOT_FOUND

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()