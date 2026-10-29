# Probe results: aegis

Aegis 2.0 train+validation+test pooled, deduplicated, 23,428 prompts. Tier rule: user prompts only. T2 if unsafe and any category in ['Hate/Identity Hate', 'Sexual', 'Sexual (minor)', 'Suicide and Self Harm', 'Threat', 'Violence']; T1 if unsafe otherwise; T0 if safe.

| Tier | Share |
|---|---|
| T0 | 47.93% (11,228) |
| T1 | 30.81% (7,219) |
| T2 | 21.26% (4,981) |

T2 items in the pool: 4,981

## Scoring 100 per tier (seed 0), T2 vs rest

| Model | AUC | Best-F1 threshold | T2 precision | T2 recall | items/s (M2) |
|---|---|---|---|---|---|
| Detoxify | 0.825 | 0.002 | 0.70 | 0.73 | 9.2 |
| Laya base (noul) | 0.725 | 0.107 | 0.46 | 0.82 | 3.7 |

Mean score by tier (T0, T1, T2):

- Detoxify: 0.007, 0.027, 0.151
- Laya: 0.188, 0.194, 0.374

Detoxify score = max(threat, identity_attack, severe_toxicity, obscene); the original model has no sexual_explicit head.
Precision/recall are at the F1-optimal threshold on this 300-item sample (T2 base rate 33%, not the real rate).
