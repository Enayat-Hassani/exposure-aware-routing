"""A model writes the policy question: Claude sees 20 items from a spike and 20 ordinary items, never the category name,
and drafts one yes/no question for the decision model. One draft per held-out category, timed.

Examples come from Aegis rows outside the scored pool.
Run: python src/draft.py        ->  data/drafted_questions.json
     python src/draft.py score  ->  data/drafted_scores.parquet, results/drafted.md (base and fine-tuned Laya, 3,000 pool)
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from heldout import NEW
from probe import SEED, load_aegis

ROOT = Path(__file__).resolve().parent.parent
N = 20
PROMPT = """You run trust and safety operations. A spike of a new kind of content is arriving in the review queue.
Below are {n} items from the spike and {n} items of ordinary traffic (some ordinary items are also harmful, in other ways).

Write ONE yes/no question that a fast classifier will ask about every arriving item, so that items like the spike
answer yes and ordinary items answer no. Describe the kind of content in general terms; do not quote the examples.
Under 25 words. Reply with the question only.

SPIKE ITEMS:
{spike}

ORDINARY ITEMS:
{ordinary}
"""


def main():
    df, *_ = load_aegis()
    pool = pd.read_parquet(ROOT / "data/scores.parquet")
    rest = df[~df.id.isin(pool.id)]
    cats = rest.violated_categories.fillna("")
    fmt = lambda s: "\n".join(f"- {t[:300]!r}" for t in s)
    out = {}
    for name, (cat, hand) in NEW.items():
        inside = cats.str.contains(cat, regex=False)
        spike = rest[inside].sample(N, random_state=SEED).text
        ordinary = rest[~inside].sample(N, random_state=SEED).text
        t0 = time.time()
        r = subprocess.run(["claude", "-p", "--model", "sonnet", "--tools", "", "--strict-mcp-config"],
                           input=PROMPT.format(n=N, spike=fmt(spike), ordinary=fmt(ordinary)),
                           capture_output=True, text=True, timeout=300, check=True)
        out[name] = {"category": cat, "hand": hand, "drafted": r.stdout.strip().splitlines()[0],  # the CLI may append a note
                     "seconds": round(time.time() - t0, 1)}
        print(name, out[name]["seconds"], "s:", out[name]["drafted"], flush=True)
    (ROOT / "data/drafted_questions.json").write_text(json.dumps(out, indent=2))


def score():
    from laya import Router
    from heldout import MODELS
    from policy_sweep import auc
    qs = json.loads((ROOT / "data/drafted_questions.json").read_text())
    df, *_ = load_aegis()
    pool = pd.read_parquet(ROOT / "data/scores.parquet").merge(pd.read_parquet(ROOT / "data/heldout_scores.parquet"), on="id")
    out = ROOT / "data/drafted_scores.parquet"
    if out.exists():
        new = pd.read_parquet(out)
    else:
        texts = df.set_index("id").loc[pool.id, "text"].str.slice(0, 1500).tolist()
        spec = {n: {"type": "noul", "instructions": v["drafted"]} for n, v in qs.items()}
        new = pd.DataFrame({"id": pool.id})
        for pre, path in MODELS.items():
            router = Router() if path is None else Router(models={"english": str(path)}, default="english")
            ans = [router.predict({"body": t}, spec)["answers"] for t in texts]
            for n in qs:
                new[f"draft_{pre}_{n}"] = [a[n]["noul"] for a in ans]
        new.to_parquet(out)
    pool = pool.merge(new, on="id")
    cats = pool.violated_categories.fillna("")
    rows = []
    for n, v in qs.items():
        y = cats.str.contains(v["category"], regex=False)
        rows.append(f"| {v['category']} | {auc(y, pool[f'lay_{n}']):.2f} | {auc(y, pool[f'draft_lay_{n}']):.2f} | "
                    f"{auc(y, pool[f'layft_{n}']):.2f} | {auc(y, pool[f'draft_layft_{n}']):.2f} | {v['seconds']:.0f} s |")
    (ROOT / "results/drafted.md").write_text(
        "# Drafted vs hand-written questions\n\nAUC for one category against all other items, 3,000 Aegis pool. Drafted = "
        "Claude Sonnet saw 20 spike and 20 ordinary items, never the category name.\n\n"
        "| category | base, hand | base, drafted | fine-tuned, hand | fine-tuned, drafted | draft time |\n|---|---|---|---|---|---|\n"
        + "\n".join(rows) + "\n\nDrafted questions:\n\n" + "\n".join(f"- {v['category']}: {v['drafted']}" for v in qs.values()) + "\n")
    print((ROOT / "results/drafted.md").read_text())


if __name__ == "__main__":
    score() if sys.argv[1:2] == ["score"] else main()
