"""Fine-tune Laya on Aegis prompts outside the scored pool, then score the pool with it (columns `layft_*`).

Same five questions as score_pool.py, one yes/no answer each from the Aegis labels.
Run: python src/finetune.py   ->  data/laya_ft/ (checkpoint), data/scores.parquet (+ layft_*)
     python src/finetune.py score data/laya_ft/checkpoint_latest   ->  score the pool with a saved checkpoint only
"""
import json
import sys
from pathlib import Path

import pandas as pd

from policy_sweep import GROUPS
from probe import SEED, load_aegis
from score_pool import GENERAL_Q

ROOT = Path(__file__).resolve().parent.parent
N_TRAIN = 4000   # rows x 5 questions; ~3 h on the M2 at 2 epochs (estimate)
QS = {n: q for n, (_, q) in GROUPS.items() if n != "composite"} | {"general": GENERAL_Q}


def main():
    df, *_ = load_aegis()
    pool = pd.read_parquet(ROOT / "data/scores.parquet")
    questions = {n: {"type": "noul", "instructions": q} for n, q in QS.items()}
    if sys.argv[1:2] == ["score"]:
        return score(df, pool, questions, sys.argv[2])
    rest = df[~df.id.isin(pool.id)]
    assert len(rest) == len(df) - len(pool), "pool ids must all come from Aegis"
    # Same 40/60 safe/unsafe balance as the pool, so thresholds do not shift because of the mix alone.
    tr = pd.concat([rest[rest.tier == 0].sample(int(N_TRAIN * 0.4), random_state=SEED),
                    rest[rest.tier > 0].sample(int(N_TRAIN * 0.6), random_state=SEED)])
    cats = tr.violated_categories.fillna("").map(lambda s: {x.strip() for x in s.split(",") if x.strip()})
    path = ROOT / "data/processed/laya_train.jsonl"
    path.parent.mkdir(exist_ok=True)
    with open(path, "w") as f:
        for text, c, label in zip(tr.text.str.slice(0, 1500), cats, tr.prompt_label):
            exp = {n: bool(c & GROUPS[n][0]) for n in QS if n != "general"} | {"general": label == "unsafe"}
            f.write(json.dumps({"state": text, "questions": questions, "expected": exp}) + "\n")

    from laya.train import TrainConfig, finetune, resolve_checkpoint_dir
    out_dir = ROOT / "data/laya_ft"
    # soft-ce: the vendor measured no gain from the default rlcd term (#741). Batch 1 x 32 fits 16 GB.
    cfg = TrainConfig(epochs=2, micro_batch=1, grad_accum=32, loss="soft-ce", log_every=200)
    summary = finetune(str(path), resolve_checkpoint_dir("convaiinnovations/laya"), str(out_dir), cfg)
    (ROOT / "results/finetune_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    score(df, pool, questions, str(out_dir))


def score(df, pool, questions, model_dir):
    from laya import Router
    router = Router(models={"english": model_dir}, default="english")
    texts = df.set_index("id").loc[pool.id, "text"].str.slice(0, 1500).tolist()  # the pool file keeps no text
    scores = {n: [] for n in QS}
    for i, t in enumerate(texts):
        a = router.predict({"body": t}, questions)["answers"]
        for n in QS:
            scores[n].append(a[n]["noul"])
        if i % 250 == 0:
            print(i, flush=True)
    for n, v in scores.items():
        pool[f"layft_{n}"] = v
    pool.to_parquet(ROOT / "data/scores.parquet")
    print("done", pool.shape)


if __name__ == "__main__":
    main()
