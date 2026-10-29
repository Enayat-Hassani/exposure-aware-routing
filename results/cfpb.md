# CFPB: templated filings and relief, read at arrival

Test 4000 complaints received 2025-05-06 to 2026-06-15; train 50000 before 2025-01-01. Credit reporting 69% of test. Templated 62.2%, monetary relief 2.0%, any relief 27.9%.

## Templated bulk filings

| score | AUC all | AUC on first copies* |
|---|---|---|
| hash (earlier copy exists) | 0.94 | 0.50 |
| TF-IDF | 0.88 | 0.80 |
| Laya: form letter? | 0.69 | 0.68 |

*first copies: 293 templated complaints with no earlier copy, against all non-templated.

## Relief

AUC, and share of positives caught by a priority lane taking the top 20% of complaints.

| outcome | score | AUC all | AUC outside credit reporting | top-20% capture |
|---|---|---|---|---|
| monetary | form (product picked) | 0.89 | 0.73 | 95% |
| monetary | TF-IDF, 50k labels | 0.94 | 0.85 | 95% |
| monetary | Laya: money back? | 0.68 | 0.60 | 49% |
| monetary | Laya: fixable error? | 0.57 | 0.59 | 29% |
| relief | form (product picked) | 0.43 | 0.55 | 21% |
| relief | TF-IDF, 50k labels | 0.53 | 0.64 | 20% |
| relief | Laya: money back? | 0.49 | 0.50 | 17% |
| relief | Laya: fixable error? | 0.49 | 0.50 | 20% |

Questions:

- templated: Is this a generic form letter citing laws or regulations, rather than a personal account of a specific event?
- monetary: Is the consumer asking for money back for a specific charge, fee or loss?
- fixable: Does the consumer describe a specific error or problem that the company could correct?
