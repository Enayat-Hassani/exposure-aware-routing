"""Can a decision model read a CFPB complaint at arrival and tell (a) a templated bulk filing, (b) one likely to end in relief?

Data: 5 of 67 parquet shards of the CFPB complaint database (HF mirror Mouwiya/cfpb-consumer-complaints), narratives only.
Test: 4,000 complaints received from 2025-01-01. Train (baselines only): 50,000 received before 2025, so nothing is
learned from the future. Base Laya answers three plain questions; it sees no CFPB labels.

Baselines, each something a complaints team already has at arrival:
- form: relief rate of the product the consumer picked on the web form (learned on train)
- hash: an earlier complaint (in the loaded shards) opens with the same 200 characters
- TF-IDF + logistic regression on the 50,000 labelled train complaints

Templated = the first 200 characters (whitespace collapsed) appear in another complaint in the loaded shards.

Run: python src/cfpb.py  ->  data/cfpb_scores.parquet (cached), results/cfpb.md
"""
from pathlib import Path

import numpy as np
import pandas as pd

from policy_sweep import auc

ROOT = Path(__file__).resolve().parent.parent
N_TEST, N_TRAIN, CUT = 4000, 50000, "2025-01-01"
QS = {  # written once before scoring
    "templated": "Is this a generic form letter citing laws or regulations, rather than a personal account of a specific event?",
    "monetary": "Is the consumer asking for money back for a specific charge, fee or loss?",
    "fixable": "Does the consumer describe a specific error or problem that the company could correct?",
}


def load():
    d = pd.concat(pd.read_parquet(f) for f in sorted((ROOT / "data/raw/cfpb").glob("*.parquet")))
    d = d[d.consumer_complaint_narrative.fillna("").str.len() > 0].drop_duplicates("complaint_id")
    d["date"] = pd.to_datetime(d.date_received.astype(str).str.slice(0, 19))  # shards mix tz-aware and naive stamps
    d["text"] = d.consumer_complaint_narrative.str.slice(0, 1500)
    key = d.consumer_complaint_narrative.str.replace(r"\s+", " ", regex=True).str.slice(0, 200)
    d["templated"] = key.duplicated(keep=False)
    d = d.assign(key=key).sort_values(["date", "complaint_id"])
    d["earlier_copy"] = d.groupby("key").cumcount() > 0
    d["monetary"] = d.company_response_to_consumer == "Closed with monetary relief"
    d["relief"] = d.company_response_to_consumer.str.contains("relief", na=False)
    return d


def capture(y, s, top=0.2):
    """Share of positives found in the top `top` of items by score (what a priority lane of that size would catch)."""
    return y[s >= np.quantile(s, 1 - top)].sum() / y.sum()


def main():
    d = load()
    test = d[d.date >= CUT].sample(N_TEST, random_state=0)
    train = d[d.date < CUT].sample(N_TRAIN, random_state=0)

    out = ROOT / "data/cfpb_scores.parquet"
    if out.exists():
        test = test.merge(pd.read_parquet(out), on="complaint_id")
    else:
        from laya import Router
        router, spec = Router(), {n: {"type": "noul", "instructions": q} for n, q in QS.items()}
        ans = []
        for i, t in enumerate(test.text):
            ans.append(router.predict({"body": t}, spec)["answers"])
            if i % 250 == 0:
                print(i, flush=True)
        sc = pd.DataFrame({"complaint_id": test.complaint_id.values} | {f"lay_{n}": [a[n]["noul"] for a in ans] for n in QS})
        sc.to_parquet(out)
        test = test.merge(sc, on="complaint_id")

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=200000)
    xtr, xte = vec.fit_transform(train.text), vec.transform(test.text)
    for y in ("monetary", "relief", "templated"):
        lr = LogisticRegression(C=4, max_iter=2000, class_weight="balanced").fit(xtr, train[y])
        test[f"tfidf_{y}"] = lr.predict_proba(xte)[:, 1]
    for y in ("monetary", "relief"):
        test[f"form_{y}"] = test["product"].map(train.groupby("product")[y].mean()).fillna(train[y].mean())

    credit = test["product"].str.contains("Credit reporting")
    lines = [f"# CFPB: templated filings and relief, read at arrival\n",
             f"Test {len(test)} complaints received {test.date.min():%Y-%m-%d} to {test.date.max():%Y-%m-%d}; "
             f"train {len(train)} before {CUT}. Credit reporting {credit.mean():.0%} of test. "
             f"Templated {test.templated.mean():.1%}, monetary relief {test.monetary.mean():.1%}, any relief {test.relief.mean():.1%}.\n",
             "## Templated bulk filings\n",
             "| score | AUC all | AUC on first copies* |\n|---|---|---|"]
    first = test.templated & ~test.earlier_copy  # templated, but no earlier copy exists yet: the hash cannot see it
    sub = first | ~test.templated
    for name, s in (("hash (earlier copy exists)", test.earlier_copy.astype(float)), ("TF-IDF", test.tfidf_templated),
                    ("Laya: form letter?", test.lay_templated)):
        lines.append(f"| {name} | {auc(test.templated, s):.2f} | {auc(test.templated[sub], s[sub]):.2f} |")
    lines += [f"\n*first copies: {first.sum()} templated complaints with no earlier copy, against all non-templated.\n",
              "## Relief\n",
              "AUC, and share of positives caught by a priority lane taking the top 20% of complaints.\n",
              "| outcome | score | AUC all | AUC outside credit reporting | top-20% capture |\n|---|---|---|---|---|"]
    for y in ("monetary", "relief"):
        for name, col in (("form (product picked)", f"form_{y}"), ("TF-IDF, 50k labels", f"tfidf_{y}"),
                          ("Laya: money back?", "lay_monetary"), ("Laya: fixable error?", "lay_fixable")):
            s = test[col]
            lines.append(f"| {y} | {name} | {auc(test[y], s):.2f} | {auc(test[y][~credit], s[~credit]):.2f} | "
                         f"{capture(test[y].values, s.values):.0%} |")
    lines += ["\nQuestions:\n"] + [f"- {n}: {q}" for n, q in QS.items()]
    (ROOT / "results/cfpb.md").write_text("\n".join(lines) + "\n")
    print((ROOT / "results/cfpb.md").read_text())


if __name__ == "__main__":
    main()
