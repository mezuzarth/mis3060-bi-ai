# HW3 AI Usage Log

## Prompt 1: Specification A 
Write a Python script saved as hw03/hw03_earnings.py that builds a dataset of quarterly earnings figures for five public companies by pulling their earnings press releases from SEC EDGAR 8-K filings. Use only the requests, beautifulsoup4, re, csv, time, and os libraries.

Companies
Use these CIK numbers exactly as written:

Company	Ticker	CIK
Apple Inc.	AAPL	0000320193
Microsoft Corporation	MSFT	0000789019
NVIDIA Corporation	NVDA	0001045810
JPMorgan Chase & Co.	JPM	0000019617
Walmart Inc.	WMT	0000104169
Requirements
User-Agent header: Every HTTP request in the script must include the header User-Agent: MIS3060 Villanova mzuzarth@villanova.edu. Define the header once at the top of the script and pass it to every requests.get() call, not just the first one. Wait 0.2 seconds between requests to respect SEC's rate limit of 10 requests per second.

Find earnings filings: For each company, request https://data.sec.gov/submissions/CIK{cik}.json using the 10-digit CIK. The filings are stored under filings.recent as parallel lists (form, items, filingDate, accessionNumber, primaryDocument), where the same index position in each list refers to the same filing. Keep only filings where form equals "8-K" and the items field contains "2.02" (Results of Operations).

Select four filings: Sort the matching filings by filingDate from newest to oldest and keep the four most recent for each company (one per quarter).

Get the press release text: For each filing:

Build the filing folder URL: https://www.sec.gov/Archives/edgar/data/{CIK with leading zeros removed}/{accession number with dashes removed}/
Request index.json in that folder to get the list of files.
Identify the earnings press release as the .htm file whose name contains "99" (usually Exhibit 99.1, e.g., ex99-1.htm or ex991.htm).
Download that file and use BeautifulSoup to strip the HTML, leaving plain text with extra whitespace collapsed.
If no press release exhibit is found or a download fails, print a warning such as WARNING: [Ticker] [filing_date] - press release not found, skipping and continue to the next filing. The script must never crash because of one bad filing; wrap each filing's processing in a try/except block.
Extract fields: Use regular expressions on the plain text to extract:

Revenue: the quarterly revenue figure with its unit (e.g., "$94.9 billion" or "$24,951 million"). Look for phrases like "revenue of", "revenue was", "net sales of", "total revenue".
Diluted EPS: the diluted earnings per share (e.g., "$1.64"). Look for phrases like "diluted earnings per share", "earnings per diluted share", "diluted EPS".
Net income: the quarterly net income with its unit (e.g., "$24.8 billion").
Reporting period: the quarter being reported (e.g., "fourth quarter fiscal 2024" or "second quarter 2025").
Make the patterns case-insensitive and allow for variations in wording.
Print progress: After each filing is processed, print one line in this exact format: [Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X

Save to CSV: Save all rows to hw03/earnings_history.csv with these columns, in this order: company, ticker, cik, filing_date, period, revenue_reported, eps_diluted, net_income. Build the output path from the script's own folder (using os.path.dirname(__file__)) so the script works when run from the repo root with python hw03/hw03_earnings.py. When finished, print a confirmation with the number of rows saved.

Missing data: If a regex finds no match for a field, store the string "NOT_FOUND" in that cell. Never leave a cell blank or store None, because a blank cell and a failed extraction mean different things.

## Prompt 2: Specification B 
Write a Python script saved as `hw03/hw03_executives.py` that builds a dataset of executive and director departures and appointments for the same five companies, using SEC EDGAR 8-K filings from the past 12 months. Use only the `requests`, `beautifulsoup4`, `re`, `csv`, `time`, `os`, and `datetime` libraries.

### Companies
Use these CIK numbers exactly as written:

| Company | Ticker | CIK |
|---|---|---|
| Apple Inc. | AAPL | 0000320193 |
| Microsoft Corporation | MSFT | 0000789019 |
| NVIDIA Corporation | NVDA | 0001045810 |
| JPMorgan Chase & Co. | JPM | 0000019617 |
| Walmart Inc. | WMT | 0000104169 |

### Requirements

1. **User-Agent header:** Every HTTP request must include the header `User-Agent: MIS3060 Villanova mzuzarth@villanova.edu`. Define it once at the top of the script and pass it to every `requests.get()` call. Wait 0.2 seconds between requests to respect SEC's rate limit.

2. **Find executive-change filings:** For each company, request `https://data.sec.gov/submissions/CIK{cik}.json` using the 10-digit CIK. The filings are stored under `filings.recent` as parallel lists (`form`, `items`, `filingDate`, `accessionNumber`, `primaryDocument`), where the same index position in each list refers to the same filing. Keep only filings where:
   - `form` equals `"8-K"`,
   - the `items` field contains `"5.02"` (Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers), and
   - `filingDate` is within the past 12 months, calculated from today's date when the script runs (`datetime.now() - timedelta(days=365)`), not a hard-coded date.

3. **Download and extract events:** For each matching filing:
   - Build the URL of the main 8-K document: `https://www.sec.gov/Archives/edgar/data/{CIK with leading zeros removed}/{accession number with dashes removed}/{primaryDocument}`
   - Download it and use BeautifulSoup to strip the HTML to plain text with extra whitespace collapsed.
   - Isolate the Item 5.02 section: the text from "Item 5.02" up to the next "Item" heading (such as "Item 9.01") or the signature section.
   - From that section, extract:
     - **event_type:** `"departure"` if the text describes someone resigning, retiring, stepping down, being terminated, or not standing for re-election; `"appointment"` if it describes someone being appointed, elected, named, or promoted; `"both"` only if a single person's event involves leaving one role and taking another (for example, moving from CFO to COO).
     - **person_name:** the person's full name (for example, "Jane A. Smith"). Names usually appear right before words like "resigned", "was appointed", "will retire", or "was elected".
     - **title:** the person's role (for example, "Chief Financial Officer", "Executive Vice President", "member of the Board of Directors").
     - **effective_date:** the date the change takes effect (for example, "effective March 31, 2026"). If no effective date is stated, use `"NOT_FOUND"`.
   - If any field cannot be extracted, store the string `"NOT_FOUND"` rather than a blank or `None`.
   - Wrap each filing's processing in a try/except block. If a download or extraction fails, print a warning like `WARNING: [Ticker] [filing_date] - could not process filing, skipping` and continue to the next filing. The script must never crash because of one bad filing.

4. **Multiple events per filing:** If a filing describes more than one person or event (for example, one executive departs and another is appointed), create a separate row for each event. The output should have one row per event, not one row per filing.

5. **Print progress:** Print each event as it is extracted, in this exact format:
   `[Ticker] | [Date] | [Event Type] | [Name] | [Title]`
   where `[Date]` is the filing date.

6. **Companies with no events:** If a company has no Item 5.02 filings in the past 12 months, print `[Ticker]: No executive events in past 12 months` and move on to the next company. This is valid data, not an error, and must not crash or silently skip the company.

7. **Save to CSV:** Save all events to `hw03/executive_events.csv` with these columns, in this order:
   `company`, `ticker`, `cik`, `filing_date`, `event_type`, `person_name`, `title`, `effective_date`.
   Build the output path from the script's own folder (using `os.path.dirname(__file__)`) so the script works when run from the repo root with `python hw03/hw03_executives.py`. If no events are found for any company, still create the CSV with just the header row. When finished, print a confirmation with the number of events saved.

## Prompt 3: Timeline
Write Python using yfinance to get the most recent quarterly revenue and net income for AAPL. Print the quarter end date along with the values.



## Iterations and fixes
 No iteration was needed for the earnings pipeline - all 20 filings extracted revenue, EPS, and net income on the first run (0 NOT_FOUND rows). The first run of the executive events pipeline produced a false row where "Regulation S-K" (an SEC rule referenced in the filing) was extracted as a person's name, because both words are capitalized. I added "regulation" to the script's name stopword list and reran, which removed the bad row (27 → 26 events). Validation  revealed that the extraction captured John Furner's board seat but missed his CEO title, did not create a departure row for Doug McMillon, and counted Furner a second time in a later filing. 

## Something the generated script did that I would not have thought to specify
The executives script keeps a row with every field set to NOT_FOUND when an Item 5.02 filing contains no identifiable person or event (for example, a compensation-only update), instead of dropping the filing. I would not have thought to specify this, but it keeps those filings visible and auditable, and it made it clear in the timeline that 5 of the 26 rows were not actual leadership changes and I did not need to adjust it.