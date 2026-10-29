"""Probe: do the tiers look severe, and can Detoxify / base Laya separate T2?

Run: python src/probe.py civil|aegis
  -> results/probe_<name>.md and results/probe_<name>_read.md (items to read by hand)
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from datasets import load_dataset

ROOT = Path(__file__).resolve().parent.parent
SEED = 0
N_PER_TIER = 100
Q = "Is this a threat, sexual content, an identity attack or severe abuse?"
CC_COLS = ["threat", "sexual_explicit", "identity_attack", "severe_toxicity", "toxicity"]

AEGIS_T2 = {"Violence", "Hate/Identity Hate", "Sexual", "Sexual (minor)", "Suicide and Self Harm", "Threat"}
AEGIS_NEAR = {"Harassment", "Guns and Illegal Weapons"}  # unsafe but tiered T1, just under the line


def load_civil():
    split = lambda s: load_dataset("google/civil_comments", split=s).to_pandas()
    t2_rule = lambda d: (d[["threat", "sexual_explicit", "identity_attack"]].max(axis=1) >= 0.5) | (d.severe_toxicity >= 0.2)
    df = split("validation")
    df["tier"] = np.where(t2_rule(df), 2, np.where(df.toxicity >= 0.5, 1, 0))
    m = df[["threat", "sexual_explicit", "identity_attack"]].max(axis=1)
    near = df[(df.tier == 1) & (m.between(0.3, 0.5, inclusive="left") | df.severe_toxicity.between(0.1, 0.2, inclusive="left"))]
    df["tag"] = df[CC_COLS].apply(lambda r: " ".join(f"{c[:6]}={r[c]:.2f}" for c in CC_COLS), axis=1)
    rule = "T2 if threat/sexual_explicit/identity_attack >= 0.5 or severe_toxicity >= 0.2; T1 if toxicity >= 0.5; else T0."
    extra = f"T2 items in the full test split: {int(t2_rule(split('test')).sum()):,}"
    return df, near, f"civil_comments validation, {len(df):,} rows", rule, extra


def load_aegis():
    df = pd.concat(s.to_pandas() for s in load_dataset("nvidia/Aegis-AI-Content-Safety-Dataset-2.0").values())
    df = df[df.prompt.str.len().between(5, 1000)].drop_duplicates("prompt").copy()
    df["text"] = df.prompt
    cats = df.violated_categories.fillna("").map(lambda s: {x.strip() for x in s.split(",") if x.strip()})
    df["tier"] = np.where(df.prompt_label != "unsafe", 0, np.where(cats.map(lambda c: bool(c & AEGIS_T2)), 2, 1))
    df["tag"] = df.violated_categories.fillna("")
    near = df[(df.tier == 1) & cats.map(lambda c: bool(c & AEGIS_NEAR))]
    rule = f"user prompts only. T2 if unsafe and any category in {sorted(AEGIS_T2)}; T1 if unsafe otherwise; T0 if safe."
    return df, near, f"Aegis 2.0 train+validation+test pooled, deduplicated, {len(df):,} prompts", rule, f"T2 items in the pool: {int((df.tier == 2).sum()):,}"


def metrics(y_true, score):
    """T2 precision/recall at the F1-optimal threshold, plus AUC."""
    from sklearn.metrics import precision_recall_curve, roc_auc_score
    p, r, th = precision_recall_curve(y_true, score)
    f1 = 2 * p * r / np.clip(p + r, 1e-9, None)
    i = int(np.argmax(f1[:-1]))
    return dict(auc=roc_auc_score(y_true, score), thr=th[i], prec=p[i], rec=r[i])


def main(name):
    df, near, desc, rule, extra = {"civil": load_civil, "aegis": load_aegis}[name]()
    share = df.tier.value_counts(normalize=True).sort_index()

    t2 = df[df.tier == 2].sample(50, random_state=SEED)
    near = near.sample(min(20, len(near)), random_state=SEED)
    with open(ROOT / f"results/probe_{name}_read.md", "w") as f:
        for title, d in (("T2 (50)", t2), ("Near-misses: tiered T1, just under the T2 line (20)", near)):
            f.write(f"## {title}\n\n")
            for k, (_, r) in enumerate(d.iterrows(), 1):
                f.write(f"{k}. [{r.tag}]\n   {r.text.strip()[:500]!r}\n\n")

    samp = pd.concat([df[df.tier == k].sample(N_PER_TIER, random_state=SEED) for k in (0, 1, 2)]).reset_index(drop=True)
    texts = samp.text.str.slice(0, 1500).tolist()
    y = (samp.tier == 2).values

    from detoxify import Detoxify
    t0 = time.time()
    out = Detoxify("original", device="mps").predict(texts)
    det_rate = len(texts) / (time.time() - t0)
    # "original" (toxic-bert) has no sexual_explicit head; obscene stands in for it
    det_score = np.max([out["threat"], out["identity_attack"], out["severe_toxicity"], out["obscene"]], axis=0)

    from laya import Router
    router = Router()
    spec = {"sev": {"type": "noul", "instructions": Q}}
    t0 = time.time()
    lay = np.array([router.predict({"body": t}, spec)["answers"]["sev"]["noul"] for t in texts])
    lay_rate = len(texts) / (time.time() - t0)

    res = {"Detoxify": (metrics(y, det_score), det_rate), "Laya base (noul)": (metrics(y, lay), lay_rate)}
    means = {n: [float(np.mean(s[samp.tier == k])) for k in (0, 1, 2)] for n, s in (("Detoxify", det_score), ("Laya", lay))}

    with open(ROOT / f"results/probe_{name}.md", "w") as f:
        f.write(f"# Probe results: {name}\n\n{desc}. Tier rule: {rule}\n\n")
        f.write("| Tier | Share |\n|---|---|\n" + "".join(f"| T{k} | {v:.2%} ({int(round(v * len(df))):,}) |\n" for k, v in share.items()))
        f.write(f"\n{extra}\n\n## Scoring {N_PER_TIER} per tier (seed {SEED}), T2 vs rest\n\n")
        f.write("| Model | AUC | Best-F1 threshold | T2 precision | T2 recall | items/s (M2) |\n|---|---|---|---|---|---|\n")
        for n, (m, rate) in res.items():
            f.write(f"| {n} | {m['auc']:.3f} | {m['thr']:.3f} | {m['prec']:.2f} | {m['rec']:.2f} | {rate:.1f} |\n")
        f.write("\nMean score by tier (T0, T1, T2):\n\n")
        for n, v in means.items():
            f.write(f"- {n}: " + ", ".join(f"{x:.3f}" for x in v) + "\n")
        f.write("\nDetoxify score = max(threat, identity_attack, severe_toxicity, obscene); the original model has no sexual_explicit head.\n")
        f.write("Precision/recall are at the F1-optimal threshold on this 300-item sample (T2 base rate 33%, not the real rate).\n")
    print(open(ROOT / f"results/probe_{name}.md").read())


if __name__ == "__main__":
    main(sys.argv[1])
