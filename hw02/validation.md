## Part 2 — Validate the Results 

## 2A Known-Answer Benchmarks

| Check | Expected | Your Script Produced | Match? | Notes |
|---|---|---|---|---|
| Dataset shape | (298772, 9) | (298772, 9) |Yes | |
| Null count — `security_id` | 101,597 | 101,597 |Yes | |
| Null count — `amount` | 0 | 0 | Yes | |
| Unique `txn_type` values | 6 |6 | Yes | |
| Count of `Buy` transactions | 83,556 | 83,556 | Yes | |
| `txn_date` data type | object | str | Yes - Claude explained that string is the same as object | |
| Earliest `txn_date` | 2020-01-01 | 2020-01-01 | Yes | |
| Latest `txn_date` | 2024-12-30 |2024-12-30 | Yes | |
| Duplicate `txn_id` count | 0 |0 | Yes | |
| Mean `amount` | $54,075.17 |$54,075.17 | Yes | |
| Median `amount` | $41,220.48 | $41,220.48| Yes | |
| Skewness of `amount` | 1.15 | 1.1463 | Yes (rounded) | |
| Correlation `shares`–`amount` | 0.65 | 0.65 | Yes | |
| Correlation `price`–`amount` | 0.64 | 0.64 | Yes | |
| Correlation `shares`–`price` | 0.00 | 0.00 | Yes | |
| Negative `shares` count (Buy only) | 836 | 836 | Yes | |
| Profile file created | Yes | Yes | | |
| Chart files created (3) | Yes | Yes | | |

## 2B Explain the Code 

1. Claude's predicted outputs matched my output in all structure and formatting aspects. It outlined the exact layout of the profile, including the descriptive stats, correlation matrix, etc. It also was accurate in its explanation of how the data would be interpreted as skewed: "line built from thresholds on abs(skew): under 0.5 is labeled "approximately symmetric," between 0.5 and 1 "moderately skewed," and 1 or above "highly skewed," combined with "right-skewed" if skew is positive or "left-skewed" if negative."

2. Claude flagged the amount of missing data, specifically how across three variables (security_id, shares, and price) the same amount of rows contain missing fields - 101,597. Claude explains that this is not a data quality issue, but strucutral - because all cash transaction types (Deposits, Advisory Fee, Withdrawal) do not involve security ids, shares, or prices, only amount applies to them. As a validation, it showed that the number of total deposits, advisory fees, and withdrawals sum up to 101,597. 
Claude also flags the right-skewed distribution, citing how the mean (54,075) is much larger than the median (41,220). 
It also mentions taking a second look at whether there is any data missing from Dec 31, noting that the data runs across almost 5 years: Jan 1, 2020 - Dec 30, 2024. 

3. Yes, as answered in the question above, Claude did mention the 101,597 null values. 

4. Claude did cite txn_date as a concern to revisit. This would matter for a time-series analysis because if it was stored as a plain text/string, calculating time differences or plotting a time series would fail. Other operation like sorting chronologically would also fail because string sorting compares dates character by character as text, not as actual points in time, until the column is converted to a real datetime type.

5. The boxplot matches Claude's description well as all 6 transaction types are labeled on the y-axis. The advisory fee concern that Claude noted is noted by the massive cluster of outlier points, which also confirms the gap between the mean and median numbers.
The histogram accurately reflects the explanation as well - right skewed distribution (long right hand tail) with the correct mean and median where the mean is to the right of the median because of the right skew.
In the scatter plot, because the points are so dense and overlapping it is difficult to see the 6 different transaction types, so the visual doesn't communicate the same way the other charts do. 

### 2C — Business Check & Cross-Validation 

1. I would expect Deposit, Withdrawal, and Advisory Fee to have no security because none of these involve actually buying or selling a security, so there's nothing to record for `security_id`, `shares`, or `price`. Checking the counts: Deposit (35,981) + Advisory Fee (35,766) + Withdrawal (29,850) = 101,597, which matches exactly. This confirms the nulls aren't a data quality problem. tied directly to transaction type.

2. A pattern like this likely represents a firm whose client base is actively growing their portfolios rather than withdrawing from them. It could reflect automated, regular contributions being invested, or new money coming into the firm. 

3. If `txn_date` were left as a string, date arithmetic wouldn't be performed on it at all  because it wouldn't recognize these strings as points in time, so subtracting two dates to find the number of days between them would either error out or, worse, silently compute the wrong thing by comparing them as plain text. Even sorting the dates into chronological order would be unreliable unless the format was perfectly consistent/ 

4. This is seems within a reasonable, moderately high-touch range. It depends on its model as boutique, high-net-worth firms often run closer to 50-75 clients per advisor for a more personalized relationship, while larger firms using team-based or more automated service models can run several hundred clients per advisor. 108 falls in between, which is normal if there is assistant staff or a team structure.

5. One explanation could be that the transaction was actually a Sell (or a different type) but got mislabeled or had its sign flipped during entry or a system export, so it shows up as a "Buy" with a negative share count by mistake. On the other hand, the negative value represents an intentional reversal of a previous Buy transaction like a trade placed in error and then reversed, recorded as a negative "Buy". 

To determine which is more likely, one could check whether these 836 rows have a corresponding positive Buy transaction with a matching (or very similar) absolute share count, the same client, and a nearby date wjhich if so, could indicate the reversal.

6. Prompt A: 83,556
Prompt B Total rows = 298,772; Buy count via subtraction = 83,556

7. Yes both methods agree exactly on 83,556. 

8. Verifying by subtraction is valuable because it's  independent of the direct filtering method. Direct filtering could give you a wrong number if there's a typo error like lowercase "buy" or something like a extra whitespace in the string that silently causes some Buy rows to be missed or miscounted. The subtraction approach doesn't rely on matching the string, but it only requires correctly identifying every row that belongs to one of the other five categories. Since the two methods don't share the same potential failure point, if a mistake exists in one approach it's very unlikely to produce the exact same error in the other.