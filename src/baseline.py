"""Fair baseline for the fine-tuned Laya: TF-IDF + logistic regression trained on the same rows and labels.

Run after finetune.py: python src/baseline.py  ->  data/scores.parquet (+ tfidf_*)
"""
import json
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from probe import load_aegis

ROOT = Path(__file__).resolve().parent.parent


def main():
    rows = [json.loads(l) for l in open(ROOT / "data/processed/laya_train.jsonl")]
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    x = vec.fit_transform([r["state"] for r in rows])
    df, *_ = load_aegis()
    pool = pd.read_parquet(ROOT / "data/scores.parquet")
    xp = vec.transform(df.set_index("id").loc[pool.id, "text"].str.slice(0, 1500))
    for q in rows[0]["expected"]:
        lr = LogisticRegression(C=4, max_iter=2000, class_weight="balanced").fit(x, [r["expected"][q] for r in rows])
        pool[f"tfidf_{q}"] = lr.predict_proba(xp)[:, 1]
    pool.to_parquet(ROOT / "data/scores.parquet")
    print("done", pool.shape)


if __name__ == "__main__":
    main()
