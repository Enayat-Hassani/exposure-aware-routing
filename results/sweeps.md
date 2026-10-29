# Sweeps

Seats = average seats on duty (24/7, following the arrival shape); 3 seeds x 3 days pooled. Every ops number is an assumption.

## Baseline

Severity priority, mix 60/30/10, no cap, occupancy <= 85%: 7.0 seats on duty on average = 42 FTE at 40 h/week and 30% shrinkage.

## 1. What the cap costs (oracle tiers)

Cap = weighted exposure per rolling 60 min (T1=1, T2=3). `priority_over_pct` = share of seat-hours the unmanaged baseline spends over that cap. `price_pct_occ95` repeats the price with a 95% occupancy ceiling.

| label | base_seats | aware_seats | price_pct | priority_over_pct | price_pct_occ95 |
|---|---|---|---|---|---|
| none | 7.0 | 7.0 | 0.0 | 0.0 | n/a |
| 60 | 7.0 | 7.0 | 0.0 | 4.4 | 10.7 |
| 50 | 7.0 | 7.2 | 3.0 | 43.8 | 15.3 |
| 45 | 7.0 | 7.5 | 7.7 | 71.9 | 20.7 |
| 40 | 7.0 | 8.2 | 17.9 | 90.3 | 32.0 |
| 35 | 7.0 | 9.3 | 32.7 | 96.6 | 48.7 |
| 30 | 7.0 | 10.7 | 52.4 | 99.0 | 70.7 |

## 2. Router error at cap 45 (wide policy)

Threshold set so the model finds `recall` of true T2 on the calibration half; `flagged_t2_pct` and `t2_precision` are measured on the simulated stream (10% true T2).

### 2a. Seats needed to meet every SLA (n/a = more than 40 seats)

| label | aware_seats | price_pct | flagged_t2_pct | t2_precision | t2_recall |
|---|---|---|---|---|---|
| oracle@1.0 | 7.5 | 7.7 | 10.0 | 1.0 | 1.0 |
| detoxify@0.5 | 12.7 | 81.0 | 14.2 | 0.4 | 0.5 |
| detoxify@0.7 | 16.8 | 140.5 | 25.7 | 0.3 | 0.7 |
| detoxify@0.8 | 21.5 | 207.7 | 38.0 | 0.2 | 0.8 |
| detoxify@0.9 | 28.7 | 309.5 | 54.8 | 0.2 | 0.9 |
| detoxify@0.95 | n/a | n/a | 84.4 | 0.1 | 0.9 |
| laya@0.5 | 11.8 | 68.5 | 11.1 | 0.4 | 0.5 |
| laya@0.7 | 14.9 | 113.1 | 20.4 | 0.3 | 0.7 |
| laya@0.8 | 18.9 | 170.2 | 30.1 | 0.3 | 0.8 |
| laya@0.9 | 24.3 | 247.6 | 44.0 | 0.2 | 0.9 |
| laya@0.95 | 29.4 | 319.6 | 56.7 | 0.2 | 0.9 |

### 2b. Fixed headcount = the oracle's 7.5 seats

`hidden_pct` = share of seat-hours truly over the cap. SLA columns = % of items meeting their SLA by true tier.

| label | hidden_pct | sla_t0 | sla_t1 | sla_t2 | backlog_pct |
|---|---|---|---|---|---|
| oracle@1.0 | 0.0 | 100.0 | 100.0 | 93.3 | 0.0 |
| detoxify@0.5 | 1.0 | 96.6 | 18.6 | 3.7 | 25.2 |
| detoxify@0.7 | 0.6 | 89.6 | 21.9 | 3.5 | 25.4 |
| detoxify@0.8 | 0.0 | 82.4 | 55.9 | 23.4 | 28.9 |
| detoxify@0.9 | 0.1 | 69.9 | 37.8 | 12.4 | 41.8 |
| detoxify@0.95 | 0.0 | 30.5 | 18.4 | 6.1 | 69.6 |
| laya@0.5 | 1.2 | 99.7 | 16.9 | 3.4 | 26.2 |
| laya@0.7 | 0.1 | 93.5 | 17.2 | 3.1 | 26.1 |
| laya@0.8 | 0.1 | 88.2 | 29.5 | 3.6 | 26.4 |
| laya@0.9 | 0.0 | 78.6 | 50.5 | 12.9 | 33.6 |
| laya@0.95 | 0.0 | 69.0 | 34.3 | 7.6 | 43.7 |

## 3. Queue mix at cap 45 (oracle; T1 fixed at 30%)

| label | base_seats | aware_seats | price_pct |
|---|---|---|---|
| T2=5% | 6.2 | 6.2 | 0.0 |
| T2=10% | 7.0 | 7.5 | 7.7 |
| T2=15% | 7.9 | 10.4 | 31.6 |

## 4. Policy to headcount at cap 45 (40% of items unsafe; models at 90% T2 recall on the calibration half)

| label | t2_share_pct | base_seats | aware_seats | price_pct | flagged_t2_pct | t2_precision | t2_recall |
|---|---|---|---|---|---|---|---|
| narrow/oracle | 5.9 | 6.4 | 6.4 | 0.0 | 5.9 | 1.0 | 1.0 |
| narrow/detoxify | 5.9 | 6.4 | 38.6 | 501.3 | 77.9 | 0.1 | 0.9 |
| narrow/laya | 5.9 | 6.4 | 24.2 | 276.6 | 44.4 | 0.1 | 0.9 |
| standard/oracle | 14.9 | 7.7 | 10.2 | 31.9 | 14.9 | 1.0 | 1.0 |
| standard/detoxify | 14.9 | 7.7 | 30.7 | 297.8 | 58.4 | 0.2 | 0.9 |
| standard/laya | 14.9 | 7.7 | 25.9 | 235.7 | 46.7 | 0.3 | 0.9 |
| wide/oracle | 15.5 | 7.8 | 10.6 | 35.8 | 15.5 | 1.0 | 1.0 |
| wide/detoxify | 15.5 | 7.8 | 29.6 | 280.2 | 56.2 | 0.2 | 0.9 |
| wide/laya | 15.5 | 7.8 | 25.5 | 227.8 | 45.9 | 0.3 | 0.9 |
