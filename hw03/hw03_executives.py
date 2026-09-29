"""
MIS3060 - HW03: Executive and director changes from SEC EDGAR 8-K filings.

For five public companies, this script:
  1. Pulls the company's filing history from the SEC submissions API.
  2. Keeps 8-K filings that include Item 5.02 (departures / appointments of
     directors and officers) filed in the past 12 months.
  3. Downloads each 8-K, isolates the Item 5.02 section, and uses regular
     expressions to extract one row per person/event: event type, name,
     title, and effective date.
  4. Saves everything to hw03/executive_events.csv.

Run from the repo root:  python hw03/hw03_executives.py
"""

import csv
import os
import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# SEC requires a descriptive User-Agent on every request.
HEADERS = {"User-Agent": "MIS3060 Villanova mzuzarth@villanova.edu"}

# SEC allows at most 10 requests per second; wait 0.2 s after every request.
REQUEST_DELAY = 0.2

NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    {"company": "Apple Inc.", "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation", "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.", "ticker": "JPM", "cik": "0000019617"},
    {"company": "Walmart Inc.", "ticker": "WMT", "cik": "0000104169"},
]

CSV_COLUMNS = [
    "company", "ticker", "cik", "filing_date", "event_type",
    "person_name", "title", "effective_date",
]

# Output path is built from this script's own folder so it works no matter
# which directory the script is launched from.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "executive_events.csv")


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
# Step 1: Find Item 5.02 filings from the past 12 months
# ---------------------------------------------------------------------------

def get_executive_filings(cik):
    """Return 8-K / Item 5.02 filings filed in the past 365 days, newest first."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = sec_get(url).json()
    recent = data["filings"]["recent"]

    # Calculated each time the script runs, not hard-coded.
    cutoff = datetime.now() - timedelta(days=365)

    matches = []
    # The lists under filings.recent are parallel: index i in each list
    # describes the same filing.
    for i in range(len(recent["form"])):
        form = recent["form"][i]
        items = recent["items"][i] or ""
        filing_date = recent["filingDate"][i]
        if form != "8-K" or "5.02" not in items:
            continue
        if datetime.strptime(filing_date, "%Y-%m-%d") < cutoff:
            continue
        matches.append({
            "filing_date": filing_date,
            "accession": recent["accessionNumber"][i],
            "primary_doc": recent["primaryDocument"][i],
        })

    matches.sort(key=lambda f: f["filing_date"], reverse=True)
    return matches


# ---------------------------------------------------------------------------
# Step 2: Download the 8-K and isolate the Item 5.02 section
# ---------------------------------------------------------------------------

def html_to_text(html_bytes):
    """Strip HTML tags and collapse all runs of whitespace to single spaces."""
    soup = BeautifulSoup(html_bytes, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


def isolate_item_502(text):
    """Return the text from 'Item 5.02' up to the next Item heading or the signatures."""
    start = re.search(r"\bItem\s*5\.02\b", text, re.IGNORECASE)
    if not start:
        return None

    rest = text[start.end():]
    end_positions = []
    next_item = re.search(r"\bItem\s*\d{1,2}\.\d{2}\b", rest, re.IGNORECASE)
    if next_item:
        end_positions.append(next_item.start())
    signature = re.search(r"\bSIGNATURES?\b|\bSignatures?\s+Pursuant\b", rest)
    if signature:
        end_positions.append(signature.start())
    section = rest[:min(end_positions)] if end_positions else rest

    # Drop the standard heading ("Departure of Directors or Certain Officers;
    # Election of Directors; ...") so its words aren't mistaken for events.
    section = re.sub(
        r"^\W*Departure of Directors.{0,250}?(?:Compensatory Arrangements of Certain Officers|Appointment of Certain Officers)\W*",
        "", section, flags=re.IGNORECASE,
    )
    return section.strip()


def split_sentences(text):
    """Split on '. ' before a capital letter, but not after initials like 'A.' or 'Mr.'."""
    return [s for s in re.split(r"(?<=[a-z0-9)\"][a-z0-9)\"][.;])\s+(?=[A-Z\"(])", text) if s]


# ---------------------------------------------------------------------------
# Step 3a: Find people's names
# ---------------------------------------------------------------------------

# Capitalized words that are never part of a person's name.
NAME_STOPWORDS = {
    # sentence starters / function words
    "the", "a", "an", "on", "in", "as", "at", "by", "for", "of", "to", "and", "effective",
    "following", "upon", "pursuant", "under", "also", "additionally", "further", "during",
    "prior", "after", "before", "since", "with", "this", "these", "such", "each", "his", "her",
    "their", "its", "our", "we", "he", "she", "they", "it", "there", "if", "item", "form",
    # months and days
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday",
    # organizations and documents
    "company", "corporation", "inc", "co", "llc", "lp", "board", "directors", "director",
    "committee", "compensation", "nominating", "governance", "audit", "risk", "securities",
    "exchange", "act", "commission", "annual", "meeting", "shareholders", "stockholders",
    "exhibit", "plan", "agreement", "letter", "offer", "stock", "equity", "incentive", "award",
    "awards", "section", "report", "proxy", "statement", "fiscal", "year", "quarter", "press",
    "release", "apple", "microsoft", "nvidia", "jpmorgan", "chase", "walmart", "bank", "n.a",
    "u.s", "united", "states", "america", "sam's", "club", "international", "group",
    # titles
    "chief", "executive", "financial", "operating", "officer", "officers", "president", "vice",
    "senior", "general", "counsel", "secretary", "treasurer", "controller", "chair", "chairman",
    "chairwoman", "lead", "independent", "head", "global", "worldwide", "corporate", "legal",
    "operations", "technology", "marketing", "retail", "services", "human", "resources",
    "people", "principal", "accounting", "regulation", "ceo", "cfo", "coo", "evp", "svp",
}

HONORIFICS = {"mr", "ms", "mrs", "dr"}


def find_name_mentions(sentence):
    """
    Return a list of (start, end, name, is_surname_only) for each person-name
    mention in the sentence. Full names need at least two words; a single
    word is accepted only after an honorific (e.g. 'Mr. Smith').
    """
    mentions = []
    tokens = list(re.finditer(r"\S+", sentence))
    i = 0
    while i < len(tokens):
        # Collect a run of capitalized tokens (a comma or other punctuation ends the run).
        run = []
        j = i
        while j < len(tokens):
            raw = tokens[j].group(0)
            word = raw.strip("\"'(")
            if not word or not word[0].isupper():
                break
            run.append((tokens[j], raw))
            j += 1
            if re.search(r"[,;:)\"]$", raw) or (raw.endswith(".") and len(raw.rstrip(".")) > 1
                                              and raw.rstrip(".").lower() not in HONORIFICS
                                              and raw.rstrip(".").lower() not in {"jr", "sr"}):
                break  # punctuation (other than an initial or Mr.) ends the name
        i = j if j > i else i + 1
        if not run:
            continue

        # Clean each token and note whether an honorific starts the run.
        honorific = False
        words = []  # (match, cleaned word)
        for match, raw in run:
            word = raw.strip("\"'(),;:")
            word = re.sub(r"'s$", "", word)
            if word.rstrip(".").lower() in HONORIFICS and not words:
                honorific = True
                continue
            words.append((match, word))

        # Drop leading stopwords ("The Board appointed ..." / "Senior Vice President Jane ...").
        while words and words[0][1].rstrip(".").lower() in NAME_STOPWORDS:
            words.pop(0)
            honorific = False
        # Keep words up to the first stopword.
        kept = []
        for match, word in words:
            if word.rstrip(".").lower() in NAME_STOPWORDS or not re.match(r"^[A-Z][A-Za-z'\-]*\.?$", word):
                break
            kept.append((match, word))
        if not kept:
            continue

        name = " ".join(w for _, w in kept).rstrip(".") if not kept[-1][1].endswith(".") or len(kept[-1][1]) > 2 else " ".join(w for _, w in kept)
        name = re.sub(r"\.$", "", name) if not re.search(r"\b[A-Z]\.$", name) else name
        start, end = kept[0][0].start(), kept[-1][0].end()

        if len(kept) >= 2 and not re.search(r"\b[A-Z]\.$", name):
            mentions.append((start, end, name, False))
        elif len(kept) == 1 and honorific:
            mentions.append((start, end, name, True))
    return mentions


def resolve_name(name, is_surname_only, known_names):
    """Map 'Smith' (from 'Mr. Smith') or 'Jane Smith' to the full name already seen, e.g. 'Jane A. Smith'."""
    last = name.split()[-1]
    first = name.split()[0]
    for full in known_names:
        parts = full.split()
        if is_surname_only and parts[-1] == last:
            return full
        if not is_surname_only and parts[-1] == last and parts[0] == first:
            return full
    return None if is_surname_only else name


# ---------------------------------------------------------------------------
# Step 3b: Find departure / appointment language and attach it to a person
# ---------------------------------------------------------------------------

DEPARTURE_PATTERNS = [
    r"\bresign(?:s|ed|ing|ation)?\b",
    r"\bretir(?:e|es|ed|ing|ement)\b(?!\s+(?:plan|plans|benefits?|savings|program|eligib\w*|age)\b)",
    r"\bstep(?:s|ped|ping)?\s+down\b",
    r"\b(?:was|were|has been|have been|will be)\s+terminated\b",
    r"\btermination of (?:his|her|their) employment\b",
    r"\bnot\s+(?:to\s+)?(?:stand|standing|seek|seeking|be\s+standing|be\s+nominated)\s+for\s+re-?election\b",
    r"\bdepart(?:s|ed|ing|ure)?\b",
    r"\bleav(?:e|es|ing)\s+the\s+Company\b",
]

APPOINTMENT_PATTERNS = [
    r"\bappoint(?:s|ed|ing|ment)?\b",
    r"(?<!re-)\belect(?:s|ed|ing|ion)?\b(?!\s+(?:not\b|to\s+(?:retire|resign|step|leave|depart)))",
    r"\bnamed\b(?!\s+executive\s+officers?)",
    r"\bpromot(?:ed|ion)\b",
    r"\bsucceed(?:s|ed|ing)?\b(?!\s+by)",
]

# Verbs/nouns whose person may come right AFTER them ("the Board appointed Jane Smith",
# "the retirement of John Doe"). "succeed" is excluded: the name after it is the
# person who is leaving.
OBJECT_TRIGGER = re.compile(r"^(?:appoint|elect|named|promot|retirement|resignation|departure)", re.IGNORECASE)

# Severance-style language ("if his employment is terminated without cause")
# describes what *could* happen, not an actual departure.
HYPOTHETICAL_BEFORE = re.compile(r"\b(?:if|in the event|upon (?:a|any|his|her|their)|following (?:a|any)|prior to (?:a|any))\b[^.]{0,60}$", re.IGNORECASE)
HYPOTHETICAL_AFTER = re.compile(r"^[^.]{0,40}\b(?:without cause|for cause|good reason|for any reason)\b", re.IGNORECASE)
# Biography language ("was appointed CEO in 2019") describes the past, not this filing's event.
HISTORICAL_AFTER = re.compile(r"^[^.;]{0,60}?\b(?:in|since)\s+(?:[A-Z][a-z]+\s+)?(?:19|20)\d{2}\b")


def find_triggers(sentence):
    """Return a list of (start, end, event_type, word) for every event phrase in the sentence."""
    triggers = []
    for event_type, patterns in (("departure", DEPARTURE_PATTERNS), ("appointment", APPOINTMENT_PATTERNS)):
        for pattern in patterns:
            for m in re.finditer(pattern, sentence, re.IGNORECASE):
                before, after = sentence[:m.start()], sentence[m.end():]
                word = m.group(0)
                if event_type == "departure" and (HYPOTHETICAL_BEFORE.search(before) or HYPOTHETICAL_AFTER.search(after)):
                    continue
                if word.lower().endswith("ed") and HISTORICAL_AFTER.search(after):
                    continue
                triggers.append((m.start(), m.end(), event_type, word))
    return triggers


# ---------------------------------------------------------------------------
# Step 3c: Title and effective date
# ---------------------------------------------------------------------------

TITLE_WORD = r"(?:[A-Z][A-Za-z&'\-]*|of|and|&|for|the)"
TITLE = r"([A-Z][A-Za-z&'\-]*(?:,?\s+" + TITLE_WORD + r"){0,10})"
TITLE_KEYWORDS = re.compile(
    r"\b(?:Chief|Officer|President|Vice|Counsel|Director|Chair|Chairman|Chairwoman|Secretary|"
    r"Treasurer|Controller|Head|Executive|CEO|CFO|COO|Partner|Member)\b"
)
POSSESSIVE = r"(?:the\s+)?(?:Company's\s+|Corporation's\s+|Firm's\s+|its\s+|our\s+|[A-Z][A-Za-z]+'s\s+)?"
TITLE_PATTERNS = [
    # "as Chief Financial Officer", "to the position of Executive Vice President"
    r"\b(?:as|to the (?:positions?|roles?|offices?) of|(?:position|role|office) of)\s+(?:an?\s+)?" + POSSESSIVE + TITLE,
    # "the Company's Chief Operating Officer"
    r"(?:Company's|Corporation's|Firm's|\bits|\bour)\s+" + TITLE,
]
BOARD_PATTERN = re.compile(
    r"\b(?:to|from|of|on)\s+(?:the\s+)?(?:Company's\s+)?Board(?:\s+of\s+Directors)?\b|\bas an? (?:independent\s+)?(?:non-employee\s+)?director\b",
    re.IGNORECASE,
)

MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = MONTH + r"\s+\d{1,2},\s+\d{4}"


def clean_title(raw, known_names):
    """Trim a captured title at any person name and at trailing filler words."""
    title = raw
    for name in known_names:
        for piece in (name, name.split()[-1]):
            pos = title.find(piece)
            if pos > 0:
                title = title[:pos]
    # Stop at words that begin a new clause rather than continue the title.
    title = re.split(r"\s+(?:Effective|On|In|As|Mr\.|Ms\.|Mrs\.|Dr\.)\b", title)[0]
    title = re.sub(r"(?:,|\s+(?:of|and|&|for|the))+\s*$", "", title.strip())
    return title.strip(" ,") if TITLE_KEYWORDS.search(title) else None


def find_title(sentence, trigger_end, known_names):
    """Find the role mentioned with an event, preferring text right after the event phrase."""
    after = sentence[trigger_end:]
    for text in (after, sentence):
        for pattern in TITLE_PATTERNS:
            for m in re.finditer(pattern, text):
                title = clean_title(m.group(1), known_names)
                if title:
                    return title
        if BOARD_PATTERN.search(text):
            return "member of the Board of Directors"
    return None


def find_effective_date(sentences):
    """Find when the change takes effect, e.g. 'effective March 31, 2026'."""
    joined = " ".join(sentences)
    m = re.search(r"\beffective\s+(?:as\s+of\s+|on\s+)?(?:the\s+close\s+of\s+business\s+on\s+)?(" + DATE + ")", joined, re.IGNORECASE)
    if m:
        return m.group(1)
    if re.search(r"\beffective\s+immediately\b", joined, re.IGNORECASE):
        return "immediately"
    # "will retire on March 31, 2026" — a date stated after the event phrase.
    for sentence in sentences:
        for t_start, t_end, _, _ in find_triggers(sentence):
            m = re.search(r"\b(?:on|as of)\s+(" + DATE + ")", sentence[t_end:])
            if m:
                return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Step 3d: Put it together — one event per person
# ---------------------------------------------------------------------------

def extract_events(section):
    """
    Return a list of dicts (event_type, person_name, title, effective_date),
    one per person whose departure and/or appointment the section describes.
    """
    sentences = split_sentences(section)

    # First pass: learn every full name so "Mr. Smith" can be resolved later.
    known_names = []
    for sentence in sentences:
        for _, _, name, surname_only in find_name_mentions(sentence):
            if not surname_only and resolve_name(name, False, known_names) == name and name not in known_names:
                known_names.append(name)

    people = {}  # full name -> {"departure": [...], "appointment": [...], "sentences": [...]}
    for sentence in sentences:
        mentions = []
        for start, end, name, surname_only in find_name_mentions(sentence):
            full = resolve_name(name, surname_only, known_names)
            if full:
                mentions.append((start, end, full))

        for t_start, t_end, event_type, word in find_triggers(sentence):
            person = None
            # "the Board appointed Jane Smith" — name right after the verb.
            if OBJECT_TRIGGER.match(word):
                for start, end, full in mentions:
                    gap = sentence[t_end:start]
                    if 0 <= start - t_end <= 12 and re.fullmatch(r"\s*(?:of\s+)?(?:(?:Mr|Ms|Mrs|Dr)\.\s+)?", gap):
                        person = full
                        break
            # "Jane Smith ... will retire" — nearest name before the verb.
            if person is None:
                before = [m for m in mentions if m[1] <= t_start]
                if before:
                    person = before[-1][2]
            if person is None:
                continue

            record = people.setdefault(person, {"departure": [], "appointment": [], "sentences": []})
            record[event_type].append(find_title(sentence, t_end, known_names))
            if sentence not in record["sentences"]:
                record["sentences"].append(sentence)

    events = []
    for person, record in people.items():
        dep_titles = [t for t in record["departure"] if t]
        app_titles = [t for t in record["appointment"] if t]

        if record["departure"] and record["appointment"]:
            # "both" only when the person leaves one role AND takes a different one.
            if dep_titles and app_titles and dep_titles[0] != app_titles[0]:
                event_type = "both"
                title = f"{dep_titles[0]} / {app_titles[0]}"
            elif len(record["appointment"]) > len(record["departure"]):
                event_type, title = "appointment", (app_titles or dep_titles or [None])[0]
            else:
                event_type, title = "departure", (dep_titles or app_titles or [None])[0]
        elif record["departure"]:
            event_type, title = "departure", (dep_titles or [None])[0]
        else:
            event_type, title = "appointment", (app_titles or [None])[0]

        events.append({
            "event_type": event_type,
            "person_name": person,
            "title": title or NOT_FOUND,
            "effective_date": find_effective_date(record["sentences"]) or NOT_FOUND,
        })
    return events


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_filing(company, filing):
    """Download one 8-K and return its list of event rows."""
    cik_no_zeros = str(int(company["cik"]))
    accession_no_dashes = filing["accession"].replace("-", "")
    url = (f"https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/"
           f"{accession_no_dashes}/{filing['primary_doc']}")

    text = html_to_text(sec_get(url).content)
    section = isolate_item_502(text)
    if section is None:
        raise ValueError("Item 5.02 section not found")

    events = extract_events(section)
    if not events:
        # The filing is an Item 5.02 filing, but no person/event could be
        # identified (e.g. a compensation-only update). Keep one row so the
        # filing isn't silently dropped; NOT_FOUND marks it for manual review.
        events = [{"event_type": NOT_FOUND, "person_name": NOT_FOUND,
                   "title": NOT_FOUND, "effective_date": NOT_FOUND}]

    rows = []
    for event in events:
        rows.append({
            "company": company["company"],
            "ticker": company["ticker"],
            "cik": company["cik"],
            "filing_date": filing["filing_date"],
            **event,
        })
    return rows


def main():
    all_rows = []

    for company in COMPANIES:
        ticker = company["ticker"]
        try:
            filings = get_executive_filings(company["cik"])
        except Exception as e:
            print(f"WARNING: {ticker} - could not load filing list ({e}), skipping company")
            continue

        if not filings:
            print(f"{ticker}: No executive events in past 12 months")
            continue

        for filing in filings:
            try:
                rows = process_filing(company, filing)
            except Exception as e:
                print(f"WARNING: {ticker} {filing['filing_date']} - could not process filing, skipping ({e})")
                continue

            for row in rows:
                # Never leave a blank or None cell.
                for col in CSV_COLUMNS:
                    if row.get(col) in (None, ""):
                        row[col] = NOT_FOUND
                all_rows.append(row)
                print(f"{row['ticker']} | {row['filing_date']} | {row['event_type']} | "
                      f"{row['person_name']} | {row['title']}")

    # Written even when there are no events, so the file always has a header row.
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nSaved {len(all_rows)} events to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()