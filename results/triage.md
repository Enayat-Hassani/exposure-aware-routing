# Triage vs reviewing everything

Aegis pool, wide policy, mix 60/30/10, 3 seeds x 3 days, priority routing, no cap. Kept items go severity-first on predicted tier (T2 at 90% recall). `closed_pct` = items auto-closed, never reviewed. Two-sided rows also auto-remove items scored confidently unsafe (`removed_pct`); `wrong_removed_pct` = truly safe share of those. `exposure_avoided_pct` = share of total exposure weight (0/1/3) no moderator reads. Thresholds are set on the calibration half so each budget (unsafe closed <= miss, T2 closed <= 1%, safe share of removed <= miss) holds with 95% confidence (Clopper-Pearson). Miss rates are measured on the simulated stream (true tiers).

| label | seats | fte | closed_pct | unsafe_missed_pct | t2_missed_pct | removed_pct | wrong_removed_pct | exposure_avoided_pct |
|---|---|---|---|---|---|---|---|---|
| no model (review all, FIFO) | 7.0 | 42.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| perfect triage | 4.8 | 28.5 | 60.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| detoxify, miss <= 2% | 6.9 | 41.5 | 2.5 | 0.7 | 0.0 | 0.0 | 0.0 | 0.0 |
| detoxify, two-sided, 2% | 6.9 | 41.5 | 2.5 | 0.7 | 0.0 | 0.0 | 0.0 | 0.0 |
| detoxify, miss <= 5% | 6.8 | 41.0 | 3.7 | 1.2 | 0.0 | 0.0 | 0.0 | 0.0 |
| detoxify, two-sided, 5% | 6.8 | 41.0 | 3.7 | 1.2 | 0.0 | 0.0 | 0.0 | 0.0 |
| detoxify, miss <= 10% | 6.8 | 41.0 | 3.7 | 1.2 | 0.0 | 0.0 | 0.0 | 0.0 |
| detoxify, two-sided, 10% | 6.8 | 41.0 | 3.7 | 1.2 | 0.0 | 0.0 | 0.0 | 0.0 |
| laya, miss <= 2% | 6.9 | 41.5 | 0.9 | 0.4 | 0.0 | 0.0 | 0.0 | 0.0 |
| laya, two-sided, 2% | 6.9 | 41.5 | 0.9 | 0.4 | 0.0 | 0.0 | 0.0 | 0.0 |
| laya, miss <= 5% | 6.7 | 40.0 | 7.2 | 3.3 | 0.2 | 0.0 | 0.0 | 0.0 |
| laya, two-sided, 5% | 6.7 | 40.0 | 7.2 | 3.3 | 0.2 | 0.0 | 0.0 | 0.0 |
| laya, miss <= 10% | 6.7 | 40.0 | 7.2 | 3.3 | 0.2 | 0.0 | 0.0 | 0.0 |
| laya, two-sided, 10% | 6.7 | 40.0 | 7.2 | 3.3 | 0.2 | 0.0 | 0.0 | 0.0 |
| laya-ft, miss <= 2% | 7.0 | 42.0 | 0.6 | 0.2 | 0.6 | 0.0 | 0.0 | 0.0 |
| laya-ft, two-sided, 2% | 7.0 | 42.0 | 0.6 | 0.2 | 0.6 | 0.0 | 0.0 | 0.0 |
| laya-ft, miss <= 5% | 7.0 | 42.0 | 0.6 | 0.2 | 0.6 | 0.0 | 0.0 | 0.0 |
| laya-ft, two-sided, 5% | 7.0 | 42.0 | 0.6 | 0.2 | 0.6 | 0.0 | 0.0 | 0.0 |
| laya-ft, miss <= 10% | 7.0 | 42.0 | 0.6 | 0.2 | 0.6 | 0.0 | 0.0 | 0.0 |
| laya-ft, two-sided, 10% | 4.8 | 28.5 | 0.6 | 0.2 | 0.6 | 21.5 | 9.1 | 45.9 |
| tfidf, miss <= 2% | 6.8 | 41.0 | 7.0 | 0.4 | 0.0 | 0.0 | 0.0 | 0.0 |
| tfidf, two-sided, 2% | 6.8 | 41.0 | 7.0 | 0.4 | 0.0 | 0.0 | 0.0 | 0.0 |
| tfidf, miss <= 5% | 6.8 | 41.0 | 7.0 | 0.4 | 0.0 | 0.0 | 0.0 | 0.0 |
| tfidf, two-sided, 5% | 6.8 | 41.0 | 7.0 | 0.4 | 0.0 | 0.0 | 0.0 | 0.0 |
| tfidf, miss <= 10% | 6.8 | 41.0 | 7.0 | 0.4 | 0.0 | 0.0 | 0.0 | 0.0 |
| tfidf, two-sided, 10% | 6.8 | 41.0 | 7.0 | 0.4 | 0.0 | 0.0 | 0.0 | 0.0 |
