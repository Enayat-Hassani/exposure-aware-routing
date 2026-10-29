# Exposure-aware routing

Can a moderation queue handle a new kind of harmful content before anyone has labelled it?

A moderation team uses a model to decide which reported posts are urgent. In this test, a new wave of doxxing arrives for six hours. Doxxing means posts that share someone's private details, such as a home address. The model was not built to treat these posts as urgent, so they wait in the normal queue.

This repo simulates that queue and tests one fix. Claude reads 20 posts from the wave and writes a yes/no question. A decision model (Laya) then asks that question about every new post. Posts that answer yes go to the urgent queue.

## Main results

- Without the question, the team needed **3 extra moderators** for the six hours. That was the number needed to read 90% of the doxxing posts within 15 minutes. With the question live 30 minutes into the wave, the team needed **1**. A perfect rule, one that knows exactly which posts are doxxing, also needed 1.
- The question changes the order of the queue. It does not add capacity. With no extra moderator, other urgent posts read on time fell from 94% to 20%.
- Claude wrote the question in 12 seconds. It was not told the category. For doxxing, its question worked better than a hand-written one. For criminal planning and profanity, the hand-written question was better.
- We also tried the same idea on CFPB consumer complaints. The task was to predict which complaints end with money paid back. The question did poorly (AUC 0.68). The product field on the complaint form did much better on its own (0.89). When labels or form data exist, use them.

These results come from a simulation. It uses 3 random seeds and counts moderators in whole numbers. So a difference of one moderator is about the smallest difference it can show.

## Terms

- **Tier.** How severe a post is. T0 is safe, T1 is harmful, and T2 is severe. T2 posts must be read within 15 minutes, T1 within 60 minutes, and T0 within 24 hours.
- **Seat.** One moderator on shift. We convert seats to FTE (full-time employees) with 30% shrinkage. Shrinkage is the share of paid time when staff are not available, for example leave or training.
- **Decision model.** A model that takes a plain-language question with each item. It returns a score for how likely the answer is yes. This repo uses [Laya](https://pypi.org/project/laya/), both the base model and a fine-tuned version.
- **AUC.** A score for how well a model ranks positive items above negative ones. 0.5 is chance. 1.0 is perfect.

## Detailed results

| Doxxing wave, extra posts an hour | No question | Hand-written | Drafted | Perfect rule |
|---|---|---|---|---|
| 50 | 1 | 1 | 0 | 0 |
| 100 | 3 | 3 | 1 | 1 |

The table shows extra moderators needed for the six spike hours. We also ran a weapons wave as a comparison. The router already treats weapons as severe. At 100 posts an hour, weapons needed 3 extra moderators with no question and 1 with any question.

Full tables: [results/spike.md](results/spike.md), [results/drafted.md](results/drafted.md), [results/cfpb.md](results/cfpb.md).

Other experiments in this repo, each with its own results file:

- [results/sweeps.md](results/sweeps.md): the headcount cost of an exposure cap. The cap limits how much severe content one moderator reads per hour.
- [results/triage.md](results/triage.md): seats saved by auto-closing posts the model is confident are safe. The rule is that at most 1% of severe posts may be closed unread, at 95% confidence.
- [results/heldout.md](results/heldout.md): how fine-tuned Laya does on six categories it was not fine-tuned for.
- [results/policy_sweep.md](results/policy_sweep.md), [results/probe_aegis.md](results/probe_aegis.md): whether base Laya follows a changed question, and how well Detoxify and Laya separate the tiers.

## Data

- [Aegis 2.0](https://huggingface.co/datasets/nvidia/Aegis-AI-Content-Safety-Dataset-2.0) (NVIDIA): prompts that people labelled with harm categories. We score a fixed pool of 3,000 prompts once. Half of the pool sets thresholds. The other half is the simulated stream of posts.
- [CFPB complaints](https://huggingface.co/datasets/Mouwiya/cfpb-consumer-complaints): 5 of 67 parquet shards, placed in `data/raw/cfpb/`. Test complaints are from 2025 onward. Training data is from before 2025.
- [Civil Comments](https://huggingface.co/datasets/google/civil_comments): used only in the first probe.

## Method

Posts arrive on a daily curve that peaks in the evening. Each moderator takes the oldest post from the most urgent predicted tier. Handle times vary randomly by tier (log-normal). To find the number of seats, the code searches for the smallest team that meets every tier's time target. Occupancy, the share of time moderators are busy, must stay under 85%. Every operations number is an assumption, listed at the top of `src/sim.py`.

Auto-close thresholds are set on the calibration half of the pool. Each limit on missed posts must hold with 95% confidence. We use the Clopper-Pearson method, a standard way to put a safe upper bound on a rate measured from a sample.

## Limits

- One dataset of short prompts, not live moderation traffic.
- The spike test assumes someone notices the wave and collects 20 examples within 30 minutes. Nothing here detects the wave.
- Extra moderators start the moment the wave starts.
- No measure of moderator wellbeing. Exposure is only a weighted count of severe posts read.

## Running it

You need Python 3.11+, about 16 GB of memory for fine-tuning, and the `claude` CLI for `draft.py`.

```
uv sync
uv run python src/score_pool.py      # Detoxify and base Laya scores, ~20 min
uv run python src/finetune.py        # fine-tuned Laya
uv run python src/baseline.py        # TF-IDF baseline
uv run python src/heldout.py
uv run python src/draft.py && uv run python src/draft.py score
uv run python src/spike.py           # results/spike.md
uv run pytest -q
```

`src/sim.py`, `src/triage.py`, `src/policy_sweep.py` and `src/cfpb.py` each write their own results file.
