Part 2 - Business Context Exploration
-------------------------------------------------------------------------
| Claude Prompt | Summary Response | Follow Up Question |
| --- | --- | --- |
| Wildcat’s borrower data includes credit score, debt-to-income ratio, and annual income. Which of these are most important for assessing consumer credit risk, how are they typically interpreted together, and what might each tell a lender about a borrower’s ability to repay? | Credit score reflects a borrower's past repayment behavior and reliability, DTI measures current capacity or financial breathing room, and income is mainly the denominator that makes DTI meaningful plus a basic check that earnings can support the loan size. Lenders weigh credit score and DTI most heavily since they capture willingness and capacity respectively, while income alone is the weakest standalone signal. In practice all three are read together: score sets a baseline risk tier, DTI acts as a serviceability cutoff, and income sanity-checks whether the loan size fits the borrower's earnings. | Based on these three risk indicators, what borrower profiles should Wildcat be most cautious about, and why? |
| Why is it important for a portfolio committee to evaluate Auto, Personal, Home Improvement, Education, and Business loans separately rather than looking only at the overall portfolio, and what strategic insights could this segmentation provide? | Aggregate portfolio metrics can mask problems in individual loan categories, since strong performance in one segment can offset deterioration in another and hide where risk actually lives. Auto, Personal, Home Improvement, Education, and Business loans each have distinct risk drivers, collateral structures, and sensitivity to economic conditions, so they need to be evaluated on their own terms rather than blended together. Segmenting this way lets a committee spot concentration risk, set differentiated underwriting and pricing, and make better decisions about where to grow or pull back, rather than acting on a misleading average. | When comparing Auto, Personal, Home Improvement, Education, and Business loans, which performance and risk indicators should Wildcat prioritize to determine which segments are healthiest and which require attention? |       
| Why might a lender monitor delinquent loans separately from defaulted loans, and how could the distinction between these two statuses help Wildcat identify and manage emerging credit risk? | Delinquency (payments past due) and default (a more severe, often unrecoverable loss) sit at different points on the same distress continuum, so lumping them together would hide how much cure potential a struggling loan still has. Tracking delinquency separately, especially in buckets like 30/60/90 days, gives Wildcat a leading indicator of credit stress before it hardens into an actual loss, allowing time for interventions like outreach or modified terms. Watching both side by side, along with the roll rate from delinquent to defaulted, also separates how well servicing/collections is working from how much reserve capital is actually needed, giving the committee a clearer read on emerging risk by segment or vintage rather than just reacting to losses already realized. | What actions could Wildcat take when delinquency begins increasing to prevent more loans from progressing to default? | 

Part 3 - Prompt Engineering Comparison
-------------------------------------------------------------------------
**Question**: What are the most important metrics for measuring credit risk in a consumer loan portfolio?

|     | Zero-shot | Role-assigned | Few-shot |
| --- | --- | --- | --- |
|  **Complete Prompt** | Cell B1 | Cell C1 | Cell D1 |
| **First 150 Words of Response** | Cell B2 | Cell C2 | Cell D2 |
| **Evaluation** | Cell B2 | Cell C2 | Cell D2 |

**Conclusion**: 

Part 4 - Fact-Check One Claim
-------------------------------------------------------------------------
