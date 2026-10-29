"""Does a triage model save headcount? No model (review everything, FIFO) vs a bot that decides the confident ends.

One-sided: auto-close items the model is sure are safe. Two-sided: also auto-remove items it is sure are unsafe,
so no moderator reads them; that is also exposure avoided.

python src/triage.py  ->  results/triage.md
"""
from pathlib import Path

import numpy as np
from scipy.stats import beta

from sim import SEEDS, W, Stream, find_seats, load_pool, make_stream, model_scores, predicted_tiers, true_tiers

MIX = (0.6, 0.3, 0.1)
MISS = (0.02, 0.05, 0.10)   # share of truly unsafe items the model may auto-close
# The same budget is the share of auto-removed items that may be truly safe (wrongly removed).
SEVERE = 0.01               # share of truly severe (T2) items that may be auto-closed, whatever the budget
DELTA = 0.05                # each budget must hold with 95% confidence on the calibration half


def ucb(k, n, d=DELTA):
    """One-sided Clopper-Pearson upper bound on a rate seen k times in n."""
    k = np.asarray(k)
    return np.where(k >= n, 1.0, beta.ppf(1 - d, k + 1, np.maximum(n - k, 1)))


def lcb(k, n, d=DELTA):
    k = np.asarray(k)
    return np.where(k <= 0, 0.0, beta.ppf(d, np.maximum(k, 1), n - k + 1))


def close_tau(g, tc, miss):
    """Auto-close below this score: unsafe items closed <= miss and T2 closed <= SEVERE, jointly at 95% (Bonferroni, d/2)."""
    taus = []
    for m, b in ((tc >= 1, miss), (tc == 2, SEVERE)):
        x = np.sort(g[m])
        ok = np.flatnonzero(ucb(np.arange(len(x)), len(x), DELTA / 2) <= b)  # at most k items strictly below x[k]
        taus.append(x[ok[-1]] if len(ok) else -np.inf)
    return min(taus)


def remove_hi(g, tc, miss):
    """Auto-remove at or above this score: truly safe share of removed items <= miss at 95% confidence, in the stream mix.

    The share is mix-weighted pass rates, mix0*F0 / sum(mix*F), bounded with F0 high and F1, F2 low (Bonferroni, d/3).
    shortcut: still the deepest cut that passes, so a little selection bias remains; use fixed-sequence testing if it shows.
    """
    x = np.sort(g)[::-1]
    n = np.bincount(tc, minlength=3)
    # count every item scoring >= each cut, so items tied at the cut are counted (they are removed too)
    at_or_above = [n[k] - np.searchsorted(np.sort(g[tc == k]), x, side="left") for k in range(3)]
    f = [(ucb if k == 0 else lcb)(at_or_above[k], n[k], DELTA / 3) for k in range(3)]
    share = MIX[0] * f[0] / sum(MIX[k] * f[k] for k in range(3))
    ok = np.flatnonzero(share <= miss)
    return x[ok[-1]] if len(ok) else np.inf


def keep(s, m):
    return Stream(s.ta[m], s.true[m], s.pred[m], s.handle[m], s.days)


def main():
    cal, sim = load_pool()
    t = true_tiers(sim, "wide")
    rows = []

    def add(label, streams, closed, removed=()):
        r = find_seats(streams, "priority")
        rem = np.concatenate([s.true for s in removed]) if removed else np.array([], int)
        exp_all = sum(W[s.true].sum() for s in (*streams, *closed, *removed))
        tru = np.concatenate([s.true for s in closed]) if closed else np.array([], int)
        n = sum(len(s.ta) for s in (*streams, *closed, *removed))
        unsafe = sum((s.true >= 1).sum() for s in (*streams, *closed, *removed))
        t2 = sum((s.true == 2).sum() for s in (*streams, *closed, *removed))
        rows.append(dict(label=label, seats=r["seats"] if r else None, fte=r["fte"] if r else None,
                         closed_pct=100 * len(tru) / n, unsafe_missed_pct=100 * (tru >= 1).sum() / unsafe,
                         t2_missed_pct=100 * (tru == 2).sum() / t2, removed_pct=100 * len(rem) / n,
                         wrong_removed_pct=100 * (rem == 0).mean() if len(rem) else 0.0,
                         exposure_avoided_pct=100 * W[rem].sum() / exp_all))

    full = [make_stream(t, np.full(len(t), 2), MIX, sd) for sd in SEEDS]  # one queue, arrival order
    add("no model (review all, FIFO)", full, [])
    ss = [make_stream(t, t, MIX, sd) for sd in SEEDS]
    add("perfect triage", [keep(s, s.true >= 1) for s in ss], [keep(s, s.true == 0) for s in ss])

    tc = true_tiers(cal, "wide")
    for model in ("detoxify", "laya") + tuple(m for m, c in (("laya-ft", "layft_general"), ("tfidf", "tfidf_general")) if c in cal):
        _, gc = model_scores(cal, model, "wide")
        _, gs = model_scores(sim, model, "wide")
        tiers = predicted_tiers(cal, sim, model, "wide", 0.9)
        for miss in MISS:
            # pred = 3 marks auto-closed so the same stream draw can be split
            p = np.where(gs < close_tau(gc, tc, miss), 3, tiers)
            ss = [make_stream(t, p, MIX, sd) for sd in SEEDS]
            add(f"{model}, miss <= {miss:.0%}", [keep(s, s.pred < 3) for s in ss], [keep(s, s.pred == 3) for s in ss])
            p2 = np.where(gs >= remove_hi(gc, tc, miss), 4, p)
            ss = [make_stream(t, p2, MIX, sd) for sd in SEEDS]
            add(f"{model}, two-sided, {miss:.0%}", [keep(s, s.pred < 3) for s in ss], [keep(s, s.pred == 3) for s in ss],
                [keep(s, s.pred == 4) for s in ss])

    cols = ["label", "seats", "fte", "closed_pct", "unsafe_missed_pct", "t2_missed_pct", "removed_pct", "wrong_removed_pct",
            "exposure_avoided_pct"]
    cell = lambda v: "n/a" if v is None else f"{v:.1f}" if isinstance(v, float) else str(v)
    table = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n" + "".join(
        "| " + " | ".join(cell(r[c]) for c in cols) + " |\n" for r in rows)
    out = Path(__file__).resolve().parent.parent / "results/triage.md"
    out.write_text("# Triage vs reviewing everything\n\nAegis pool, wide policy, mix 60/30/10, 3 seeds x 3 days, "
                   "priority routing, no cap. Kept items go severity-first on predicted tier (T2 at 90% recall). `closed_pct` = items auto-closed, never reviewed. "
                   "Two-sided rows also auto-remove items scored confidently unsafe (`removed_pct`); `wrong_removed_pct` = truly safe share of those. "
                   "`exposure_avoided_pct` = share of total exposure weight (0/1/3) no moderator reads. "
                   "Thresholds are set on the calibration half so each budget (unsafe closed <= miss, T2 closed <= 1%, "
                   "safe share of removed <= miss) holds with 95% confidence (Clopper-Pearson). "
                   "Miss rates are measured on the simulated stream (true tiers).\n\n" + table)
    print(out.read_text())


if __name__ == "__main__":
    main()
