"""Spike lane: a category the router does not treat as severe arrives in a 6-hour wave. Does one question hold the queue?

Core routing is fine-tuned Laya triage (unsafe <= 5% and T2 <= 5% auto-closed). Spike items are true tier 2.
Privacy (doxxing): the core router sends 5% of these items to T2. Weapons, the contrast: it already sends 74%.
A lane is one decision-model question: from spike start + DELAY, items above its threshold (90% recall of the category
on the calibration half) are routed as T2 and never auto-closed. Lanes: none, hand-written, drafted (draft.py), oracle.

Reported at the pre-spike staffing, and as seats added for the spike hours only so that 90% of spike items and 90% of
core T2 items arriving in the window are each read within 15 minutes.
Run after heldout.py and draft.py score: python src/spike.py  ->  results/spike.md
"""
from pathlib import Path

import numpy as np
import pandas as pd

import triage
from sim import (HANDLE_MEDIAN, HANDLE_SIGMA, SEEDS, SLA_PCT, SLA_S, Stream, find_seats, load_pool, make_stream, model_scores,
                 predicted_tiers, profile, simulate, true_tiers)

ROOT = Path(__file__).resolve().parent.parent
SPIKES = {"privacy": "PII/Privacy", "weapons": "Guns and Illegal Weapons"}
START, HOURS = 36 * 3600.0, 6        # day 2, 12:00 to 18:00
DELAY = 1800.0                       # assumption: detect, draft, approve
RATES = (25, 50, 100)                # extra spike items per hour
triage.SEVERE = 0.05                 # the 5.9-seat operating point; the 1% cap auto-closes almost nothing


def win(s):
    return (s.ta >= START) & (s.ta < START + HOURS * 3600)


def surge(kept, k0):
    """Fewest seats added for the spike hours only so that, separately, 90% of spike items and 90% of core T2 items
    arriving in the window are read in 15 min. Auto-closed spike items count as missed."""
    base = np.tile(profile(k0), kept[0][0].days)
    h = slice(int(START // 3600), int(START // 3600) + HOURS)

    def ok(x):
        p = base.copy()
        p[h] += x
        sp = sp_n = core = core_n = 0
        for k, spike, closed in kept:
            fast = simulate(k, p, "priority")["resp"] <= SLA_S[2]
            c = win(k) & (k.true == 2) & ~spike
            sp, sp_n = sp + (fast & spike).sum(), sp_n + spike.sum() + closed
            core, core_n = core + (fast & c).sum(), core_n + c.sum()
        return sp >= SLA_PCT * sp_n and core >= SLA_PCT * core_n

    lo, hi = -1, 64  # ok(hi) assumed
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (lo, mid) if ok(mid) else (mid, hi)
    return hi


def lane_scores(df, name, cat):
    s = df[["id"]].merge(pd.read_parquet(ROOT / "data/heldout_scores.parquet"), on="id").merge(
        pd.read_parquet(ROOT / "data/drafted_scores.parquet"), on="id")
    has = df.violated_categories.fillna("").str.contains(cat, regex=False).values
    return has, {"hand": s[f"layft_{name}"].values, "drafted": s[f"draft_layft_{name}"].values, "oracle": has * 1.0}


def streams(t, has_sim, rate):
    """Base traffic plus spike arrivals; `pred` holds the pool index so each policy can set its own predicted tier."""
    out = []
    for sd in SEEDS:
        b = make_stream(t, np.arange(len(t)), triage.MIX, sd)
        rng = np.random.default_rng(100 + sd)
        n = rng.poisson(rate * HOURS)
        ta = np.concatenate([b.ta, START + rng.random(n) * HOURS * 3600])
        idx = np.concatenate([b.pred, rng.choice(np.flatnonzero(has_sim), n)])
        true = np.concatenate([b.true, np.full(n, 2)])
        handle = np.concatenate([b.handle, HANDLE_MEDIAN[2] * rng.lognormal(0, HANDLE_SIGMA, n)])
        spike = np.r_[np.zeros(len(b.ta), bool), np.ones(n, bool)]
        o = np.argsort(ta, kind="stable")
        out.append((Stream(ta[o], true[o], idx[o], handle[o], b.days), spike[o]))
    return out


def route(s, p_old, p_lane):
    """Predicted tier per item (3 = auto-closed); the lane takes over from START + DELAY."""
    pred = p_old[s.pred]
    if p_lane is not None:
        on = s.ta >= START + DELAY
        pred[on] = p_lane[s.pred][on]
    return pred


def main():
    cal, sim = load_pool()
    t, tc = true_tiers(sim, "wide"), true_tiers(cal, "wide")
    _, gc = model_scores(cal, "laya-ft", "wide")
    _, gs = model_scores(sim, "laya-ft", "wide")
    p_old = np.where(gs < triage.close_tau(gc, tc, 0.05), 3, predicted_tiers(cal, sim, "laya-ft", "wide", 0.9))
    rows = [f"Spike: one category made severe, {HOURS} h on day 2, lane live {DELAY / 60:.0f} min after spike start.\n"]
    for name, cat in SPIKES.items():
        has_cal, lc = lane_scores(cal, name, cat)
        has_sim, ls = lane_scores(sim, name, cat)
        lanes = {"none": None} | {k: np.where(ls[k] >= np.quantile(lc[k][has_cal], 0.1), 2, p_old) for k in ls}
        base = [triage.keep(s, s.pred < 3) for s in
                (Stream(s.ta, s.true, p_old[s.pred], s.handle, s.days) for s, _ in streams(t, has_sim, 0))]
        k0 = find_seats(base, "priority")
        rows += [f"\n## {cat}\n\nBefore the spike: {k0['seats']:.1f} seats.\n",
                 "| spike/h | lane | spike items | auto-closed unread | spike reviewed in 15 min | core T2 in 15 min (window) "
                 "| extra items routed as T2 | seats added for the 6 h |", "|---|---|---|---|---|---|---|---|"]
        for rate in RATES:
            ss = streams(t, has_sim, rate)
            for lane, p_lane in lanes.items():
                n_sp = closed = ok_sp = core = ok_core = extra = 0
                kept = []
                for s, spike in ss:
                    pred = route(s, p_old, p_lane)
                    extra += ((pred == 2) & (p_old[s.pred] != 2) & ~spike).sum()
                    m = pred < 3
                    k = Stream(s.ta[m], s.true[m], pred[m], s.handle[m], s.days)
                    kept.append((k, spike[m], (spike & ~m).sum()))
                    r = simulate(k, profile(k0["k"]), "priority")
                    fast = r["resp"] <= SLA_S[2]
                    n_sp += spike.sum()
                    closed += (spike & ~m).sum()
                    ok_sp += (fast & spike[m]).sum()
                    c = win(k) & ~spike[m] & (k.true == 2)
                    core += c.sum()
                    ok_core += (fast & c).sum()
                need = surge(kept, k0["k"])
                rows.append(f"| {rate} | {lane} | {n_sp} | {100 * closed / n_sp:.1f}% | {100 * ok_sp / n_sp:.1f}% | "
                            f"{100 * ok_core / core:.1f}% | {extra} | {need} |")
                print(rows[-1], flush=True)
    (ROOT / "results/spike.md").write_text(
        "# Spike lane\n\nAegis pool, wide policy, fine-tuned Laya triage (unsafe <= 5%, T2 <= 5% auto-closed), "
        "3 seeds x 3 days, priority routing. Spike and core columns are measured at the pre-spike staffing; "
        "auto-closed spike items count as not reviewed. `extra items routed as T2` = non-spike items the lane "
        "pulled up to T2 (its false positives plus base-traffic items of the category), summed over seeds. `seats added` = surge for the 6 spike hours only (no lead time), on top of the pre-spike profile, so that 90% of spike items (auto-closed ones count as missed) and, separately, 90% of core T2 items arriving in the window are read in 15 min (pooled over seeds).\n\n" + "\n".join(rows) + "\n")
    print((ROOT / "results/spike.md").read_text())


if __name__ == "__main__":
    main()
