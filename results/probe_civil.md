# Probe results

civil_comments validation, 97,320 rows. Tier rule: T2 if threat/sexual_explicit/identity_attack >= 0.5 or severe_toxicity >= 0.2; T1 if toxicity >= 0.5; else T0.

| Tier | Share |
|---|---|
| T0 | 91.87% (89,404) |
| T1 | 6.74% (6,556) |
| T2 | 1.40% (1,360) |

T2 items in the full test split: 1,391

## Scoring 100 per tier (seed 0), T2 vs rest

| Model | AUC | Best-F1 threshold | T2 precision | T2 recall | items/s (M2) |
|---|---|---|---|---|---|
| Detoxify | 0.704 | 0.002 | 0.48 | 0.87 | 11.1 |
| Laya base (noul) | 0.742 | 0.166 | 0.50 | 0.83 | 2.6 |

Mean score by tier (T0, T1, T2):

- Detoxify: 0.011, 0.156, 0.185
- Laya: 0.101, 0.284, 0.379

Detoxify score = max(threat, identity_attack, severe_toxicity, obscene); the original model has no sexual_explicit head.
Precision/recall are at the F1-optimal threshold on this 300-item sample (T2 base rate 33%, not the real 10%).
