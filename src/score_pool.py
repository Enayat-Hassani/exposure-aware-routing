"""Score a fixed Aegis pool once with Detoxify and base Laya so the simulator never calls a model.

Run: python src/score_pool.py   ->  data/scores.parquet   (Laya: ~20 min on the M2)
"""
from pathlib import Path

import numpy as np
import pandas as pd

from policy_sweep import GROUPS
from probe import SEED, load_aegis

ROOT = Path(__file__).resolve().parent.parent
N_SAFE, N_UNSAFE = 1200, 1800
GENERAL_Q = "Is this harmful, abusive or against community guidelines?"


def main():
    df, *_ = load_aegis()
    pool = pd.concat([df[df.tier == 0].sample(N_SAFE, random_state=SEED),
                      df[df.tier > 0].sample(N_UNSAFE, random_state=SEED)]).reset_index(drop=True)
    texts = pool.text.str.slice(0, 1500).tolist()

    from detoxify import Detoxify
    model = Detoxify("original", device="mps")
    parts = [model.predict(texts[i:i + 64]) for i in range(0, len(texts), 64)]
    det = {k: [x for p in parts for x in p[k]] for k in parts[0]}
    out = pool[["id", "violated_categories", "prompt_label"]].copy()
    for k in ("toxicity", "severe_toxicity", "obscene", "threat", "insult", "identity_attack"):
        out[f"det_{k}"] = np.array(det[k])

    from laya import Router
    router = Router()
    qs = {n: q for n, (_, q) in GROUPS.items() if n != "composite"} | {"general": GENERAL_Q}
    spec = {n: {"type": "noul", "instructions": q} for n, q in qs.items()}
    lay = {n: [] for n in qs}
    for i, t in enumerate(texts):
        a = router.predict({"body": t}, spec)["answers"]
        for n in qs:
            lay[n].append(a[n]["noul"])
        if i % 250 == 0:
            print(i, flush=True)
    for n, v in lay.items():
        out[f"lay_{n}"] = v
    out.to_parquet(ROOT / "data/scores.parquet")
    print("done", out.shape)


if __name__ == "__main__":
    main()
