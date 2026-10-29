# Spike lane

Aegis pool, wide policy, fine-tuned Laya triage (unsafe <= 5%, T2 <= 5% auto-closed), 3 seeds x 3 days, priority routing. Spike and core columns are measured at the pre-spike staffing; auto-closed spike items count as not reviewed. `extra items routed as T2` = non-spike items the lane pulled up to T2 (its false positives plus base-traffic items of the category), summed over seeds. `seats added` = surge for the 6 spike hours only (no lead time), on top of the pre-spike profile, so that 90% of spike items (auto-closed ones count as missed) and, separately, 90% of core T2 items arriving in the window are read in 15 min (pooled over seeds).

Spike: one category made severe, 6 h on day 2, lane live 30 min after spike start.


## PII/Privacy

Before the spike: 5.9 seats.

| spike/h | lane | spike items | auto-closed unread | spike reviewed in 15 min | core T2 in 15 min (window) | extra items routed as T2 | seats added for the 6 h |
|---|---|---|---|---|---|---|---|
| 25 | none | 455 | 3.5% | 94.5% | 99.9% | 0 | 0 |
| 25 | hand | 455 | 2.2% | 96.5% | 99.8% | 10376 | 0 |
| 25 | drafted | 455 | 1.5% | 98.0% | 99.9% | 7194 | 0 |
| 25 | oracle | 455 | 0.2% | 99.6% | 99.9% | 2369 | 0 |
| 50 | none | 906 | 3.8% | 82.2% | 98.2% | 0 | 1 |
| 50 | hand | 906 | 2.6% | 88.4% | 96.8% | 10376 | 1 |
| 50 | drafted | 906 | 1.4% | 93.4% | 95.7% | 7194 | 0 |
| 50 | oracle | 906 | 0.3% | 98.7% | 95.8% | 2369 | 0 |
| 100 | none | 1809 | 4.5% | 10.3% | 93.7% | 0 | 3 |
| 100 | hand | 1809 | 3.2% | 16.6% | 16.2% | 10376 | 3 |
| 100 | drafted | 1809 | 1.7% | 20.3% | 20.0% | 7194 | 1 |
| 100 | oracle | 1809 | 0.3% | 32.7% | 33.3% | 2369 | 1 |

## Guns and Illegal Weapons

Before the spike: 5.9 seats.

| spike/h | lane | spike items | auto-closed unread | spike reviewed in 15 min | core T2 in 15 min (window) | extra items routed as T2 | seats added for the 6 h |
|---|---|---|---|---|---|---|---|
| 25 | none | 455 | 0.0% | 98.9% | 99.9% | 0 | 0 |
| 25 | hand | 455 | 0.0% | 100.0% | 99.9% | 2057 | 0 |
| 25 | drafted | 455 | 0.0% | 98.9% | 99.9% | 1890 | 0 |
| 25 | oracle | 455 | 0.0% | 100.0% | 99.9% | 459 | 0 |
| 50 | none | 906 | 0.0% | 84.1% | 95.9% | 0 | 1 |
| 50 | hand | 906 | 0.0% | 94.4% | 95.5% | 2057 | 0 |
| 50 | drafted | 906 | 0.0% | 93.8% | 96.3% | 1890 | 0 |
| 50 | oracle | 906 | 0.0% | 99.6% | 95.2% | 459 | 0 |
| 100 | none | 1809 | 0.0% | 74.4% | 93.7% | 0 | 3 |
| 100 | hand | 1809 | 0.0% | 60.6% | 63.8% | 2057 | 1 |
| 100 | drafted | 1809 | 0.0% | 63.1% | 68.3% | 1890 | 1 |
| 100 | oracle | 1809 | 0.0% | 62.7% | 63.0% | 459 | 1 |
