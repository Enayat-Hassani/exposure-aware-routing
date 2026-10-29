# Exposure-aware routing

Can a moderation queue handle a new kind of harmful content before anyone has labelled it?

A moderation team uses a model to decide which reported posts are urgent. A new wave, here doxxing (posts that share someone's private details), arrives for six hours. The model was not built to treat it as urgent, so the posts wait in the normal queue. This repo simulates that queue and tests one fix: Claude reads 20 posts from the wave and writes a yes/no question, and a decision model (Laya) asks that question of every new post. Posts that answer yes go to the urgent queue.

## Main results

- Reading 90% of the doxxing posts within 15 minutes needed **3 extra moderators** for the six hours. With the drafted question live 30 minutes into the wave, it needed **1**, the same as a rule that knows exactly which posts are doxxing.
- The question changes the order of the queue. It does not add capacity. With no extra moderator, other urgent posts read on time fell from 94% to 20%.
- Claude wrote the question in 12 seconds without being told the category. For doxxing it beat a hand-written question. For criminal planning and profanity the hand-written one was better.
- On CFPB consumer complaints, the same kind of question predicted monetary relief poorly (AUC 0.68). The product field on the complaint form alone scored 0.89. Where labels or form data exist, they win.

The queue is simulated, with 3 random seeds and whole moderators, so a difference of one moderator is about the smallest it can show.

## Terms

- **Tier.** T0 safe, T1 harmful, T2 severe. T2 must be read within 15 minutes, T1 within 60, T0 within 24 hours.
- **Seat.** One moderator on shift. Seats are converted to FTE with 30% shrinkage.
- **Decision model.** A model that takes a plain-language question with each item and returns a yes/no score. [Laya](https://pypi.org/project/laya/) is used here, base and fine-tuned.
- **AUC.** How well a score ranks positives above negatives: 0.5 is chance, 1.0 is perfect.

## Detailed results

| Doxxing wave, extra posts an hour | No question | Hand-written | Drafted | Perfect rule |
|---|---|---|---|---|
| 50 | 1 | 1 | 0 | 0 |
| 100 | 3 | 3 | 1 | 1 |

Extra moderators for the six spike hours. Weapons, a category the router already treats as severe, needs 3 with no question and 1 with any question at 100 posts an hour. Full tables: [results/spike.md](results/spike.md), [results/drafted.md](results/drafted.md), [results/cfpb.md](results/cfpb.md).

Other experiments in this repo, each with its own results file:

- [results/sweeps.md](results/sweeps.md): the headcount cost of capping how much severe content one moderator reads per hour.
- [results/triage.md](results/triage.md): seats saved by auto-closing posts the model is confident are safe, when at most 1% of severe posts may be closed unread at 95% confidence.
- [results/heldout.md](results/heldout.md): fine-tuned Laya on six categories it was not fine-tuned for.
- [results/policy_sweep.md](results/policy_sweep.md), [results/probe_aegis.md](results/probe_aegis.md): whether base Laya follows a changed question, and how well Detoxify and Laya separate the tiers.

## Data

- [Aegis 2.0](https://huggingface.co/datasets/nvidia/Aegis-AI-Content-Safety-Dataset-2.0) (NVIDIA): prompts labelled by people with harm categories. A fixed pool of 3,000 is scored once; half sets thresholds, half is the simulated stream.
- [CFPB complaints](https://huggingface.co/datasets/Mouwiya/cfpb-consumer-complaints): 5 of 67 parquet shards, placed in `data/raw/cfpb/`. Test complaints are from 2025 on; training data is from before.
- [Civil Comments](https://huggingface.co/datasets/google/civil_comments): used only in the first probe.

## Method

Each simulated day follows an evening-peaked arrival curve. Moderators take the oldest item of the highest predicted tier. Handle times are log-normal by tier. Seats are found by bisection: the fewest that meet every tier's target with occupancy under 85%. Every operations number is an assumption, listed at the top of `src/sim.py`.

Auto-close thresholds are set on the calibration half so that each miss budget holds with 95% confidence (Clopper-Pearson).

## Limits

- One dataset of short prompts, not live moderation traffic.
- The spike test assumes someone notices the wave and collects 20 examples within 30 minutes. Nothing here detects the wave.
- Added moderators arrive the moment the wave starts.
- No measure of moderator wellbeing. Exposure is a weighted count of severe items read, nothing more.

## Running it

Needs Python 3.11+, about 16 GB of memory for fine-tuning, and the `claude` CLI for `draft.py`.

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
