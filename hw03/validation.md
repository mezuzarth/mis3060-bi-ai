# HW3 Validation

## 5A — Known-Answer Check: Earnings
Company/quarter checked: Apple fiscal Q3 2026 (quarter ended June 2026)

| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| Apple Q3 FY2026 Revenue | $109.4 billion  https://www.apple.com/newsroom/2026/07/apple-reports-third-quarter-results/ | $109.4 billion | Yes |
| Apple Q3 FY2026 EPS Diluted | $2.02 https://www.apple.com/newsroom/2026/07/apple-reports-third-quarter-results/ | $2.02 |Yes |

Both values matched exactly.

## 5B — Known-Answer Check: Executive Events
Event checked: Walmart, filed 2025-11-14, John R. Furner (appointment)
Source: Walmart press release, "Walmart Announces John Furner as President and Chief Executive Officer," November 14, 2025 (Exhibit 99.1 to the 8-K) ([link](PASTE LINK))

| Check | Source Confirms? | Notes |
|---|---|---|
| Person name and title | Name: Yes. Title: Partial | The release confirms the Board elected John Furner as President and Chief Executive Officer and also elected him to the Board. My CSV captured only "member of the Board of Directors" and missed the CEO title, which is the primary one. |
| Event type (departure/appointment) | Yes, but incomplete | "Appointment" is correct for Furner. The same filing also announces that Doug McMillon will retire as CEO on January 31, 2026, but my pipeline did not create a departure row for McMillon. |
| Effective date | Partial | CSV shows February 1, 2026, which is the correct effective date for the CEO role. However, his Board election was effective immediately (November 14, 2025). The pipeline paired the Board title with the CEO effective date, mixing two separate events.

Additional finding: John Furner appears a second time in executive_events.csv (filed 2026-01-16, appointment, title NOT_FOUND). That later filing most likely covers the executives filling his former roles, and the script picked up his name as a new appointment. 

## 5C — Cross-Validation: Earnings via Yahoo Finance
Quarter compared: Apple fiscal Q3 2026 (Apple quarter end: June 27, 2026; yfinance quarter end: 2026-06-30)

| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | $109.4 billion | $109,417,000,000 ($109.4 billion) | Yes |
| Net Income | $29,789 million | $29,789,000,000 ($29,789 million) | Yes |

 Both metrics match. Revenue differs only by rounding, since the press release prose reports one decimal place ($109.4 billion) while yfinance reports the exact figure ($109.417 billion).