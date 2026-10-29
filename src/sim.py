"""Queue simulation: severity-priority routing vs exposure-aware routing, and what the cap costs in headcount.

Every ops number below is an assumption; results are sweeps, not point estimates.
Exposure is measured on true tiers; the router only sees predicted tiers, so a missed severe item is hidden exposure.
"""
import heapq
import math
from collections import deque
from typing import NamedTuple

import numpy as np

W = np.array([0, 1, 3])                 # exposure weight per true tier
HANDLE_MEDIAN = np.array([20.0, 45.0, 120.0])  # seconds, lognormal
HANDLE_SIGMA = 0.5
SLA_S = np.array([86400.0, 3600.0, 900.0])     # T0 24 h, T1 60 min, T2 15 min
SLA_PCT = 0.9
WINDOW = 3600.0                         # rolling exposure window
RECOVERY = 300.0                        # no new severe item for 5 min after finishing one
DAYS = 3
RATE = 500.0                            # mean arrivals per hour
SHAPE = 1 + 0.5 * np.cos(2 * np.pi * (np.arange(24) - 20) / 24)  # evening peak at 20:00, mean 1
HOURS_PER_FTE_WEEK, SHRINKAGE = 40, 0.30  # paid FTE per seat on duty 24/7
OCC_MAX = 0.85                          # planning occupancy ceiling; the lax T0 SLA alone would let a team run at ~95%


class Stream(NamedTuple):
    ta: np.ndarray       # arrival time, s
    true: np.ndarray     # true tier
    pred: np.ndarray     # tier the router sees
    handle: np.ndarray   # handle time, s (drawn from the true tier)
    days: int


def make_stream(true_pool, pred_pool, mix, seed, rate=RATE, days=DAYS):
    """Poisson arrivals with a daily shape; items drawn from the pool at the tier mix `mix` (true tiers)."""
    rng = np.random.default_rng(seed)
    counts = rng.poisson(np.tile(rate * SHAPE, days))
    ta = np.sort(np.concatenate([h * 3600.0 + rng.random(c) * 3600.0 for h, c in enumerate(counts)]))
    tiers = rng.choice(3, size=len(ta), p=mix)
    by_tier = [np.flatnonzero(true_pool == k) for k in range(3)]
    idx = np.array([rng.choice(by_tier[k]) for k in tiers])
    handle = HANDLE_MEDIAN[tiers] * rng.lognormal(0, HANDLE_SIGMA, len(ta))
    return Stream(ta, tiers, np.asarray(pred_pool)[idx], handle, days)


def profile(k):
    """Seats on duty per clock hour, following the arrival shape."""
    return np.maximum(1, np.ceil(k * SHAPE)).astype(int)


def simulate(s, prof, policy, route_cap=math.inf, report_cap=math.inf):
    """policy: 'priority' (T2>T1>T0, oldest first) or 'aware' (cap + recovery + lowest-exposure seat for severe)."""
    n, end = len(s.ta), s.days * 86400.0
    queues = [deque(), deque(), deque()]
    nmax = int(prof.max())
    busy, last2 = [0.0] * nmax, [-math.inf] * nmax
    win = [deque() for _ in range(nmax)]
    sp, st = [0] * nmax, [0] * nmax      # rolling exposure: router's view, true
    done, over = [], set()
    start = np.full(n, -1.0)

    def prune(i, t):
        while win[i] and win[i][0][0] <= t - WINDOW:
            _, wp, wt = win[i].popleft()
            sp[i] -= wp
            st[i] -= wt

    def begin(k, i, t):
        fin = t + s.handle[k]
        busy[i] = fin
        heapq.heappush(done, fin)
        prune(i, t)
        wp, wt = W[s.pred[k]], W[s.true[k]]
        win[i].append((t, wp, wt))
        sp[i] += wp
        st[i] += wt
        if st[i] > report_cap:
            over.add((i, int(t // 3600)))
        if s.pred[k] == 2:
            last2[i] = fin
        start[k] = t

    def dispatch(t):
        free = [i for i in range(prof[int(t // 3600) % len(prof)]) if busy[i] <= t]
        for tier in (2, 1, 0):
            q = queues[tier]
            while q and free:
                if policy == "priority" or tier == 0:
                    i = free[0]
                else:
                    for j in free:
                        prune(j, t)
                    ok = [j for j in free if sp[j] + W[tier] <= route_cap and (tier < 2 or t - last2[j] >= RECOVERY)]
                    if not ok:
                        break
                    i = min(ok, key=lambda j: sp[j]) if tier == 2 else ok[0]
                free.remove(i)
                begin(q.popleft(), i, t)

    a, hour = 0, 0.0
    while True:
        t = min(s.ta[a] if a < n else math.inf, done[0] if done else math.inf, hour)
        if t > end:
            break
        while a < n and s.ta[a] <= t:
            queues[s.pred[a]].append(a)
            a += 1
        while done and done[0] <= t:
            heapq.heappop(done)
        if t >= hour:
            hour += 3600.0
        dispatch(t)

    started = start >= 0
    resp = np.where(started, start - s.ta + s.handle, end - s.ta)
    counted = started | (resp > SLA_S[s.true])   # unstarted items count only once they have already missed
    met = counted & (resp <= SLA_S[s.true])
    seat_hours = int(np.tile(prof, s.days).sum())
    return dict(
        met=np.array([met[s.true == k].sum() for k in range(3)]),
        counted=np.array([counted[s.true == k].sum() for k in range(3)]),
        over=len(over), seat_hours=seat_hours, seats=float(prof.mean()),
        started=started, resp=resp, backlog=sum(len(q) for q in queues), n=n,
        occ=float(s.handle[started].sum()) / (seat_hours * 3600),
    )


def find_seats(streams, policy, route_cap=math.inf, report_cap=math.inf, lo=1.0, hi=40.0, iters=9, occ_max=OCC_MAX):
    """Smallest k (seats on duty scale) at which every tier meets its SLA, pooled over replications.
    Occupancy (handle time / seat time) must stay under `occ_max`. The queue must also be stable: a backlog left at the end is under 0.5% of arrivals, because a 24 h T0 SLA
    cannot show an overload inside a 3-day run.
    shortcut: bisection assumes feasibility rises with k; the result is re-checked at the returned k.
    """
    def run(k):
        rs = [simulate(s, profile(k), policy, route_cap, report_cap) for s in streams]
        met, counted = sum(r["met"] for r in rs), sum(r["counted"] for r in rs)
        att = np.where(counted > 0, met / np.maximum(counted, 1), 1.0)  # a tier with no items cannot miss its SLA
        return att, rs, (att >= SLA_PCT).all() and all(
            r["backlog"] <= 0.005 * r["n"] and r["occ"] <= occ_max for r in rs)

    if not run(hi)[2]:
        return None
    for _ in range(iters):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if run(mid)[2] else (mid, hi)
    att, rs, _ = run(hi)
    seats = rs[0]["seats"]
    return dict(k=hi, seats=seats, fte=seats * 168 / HOURS_PER_FTE_WEEK / (1 - SHRINKAGE), att=att,
                over_pct=100 * sum(r["over"] for r in rs) / sum(r["seat_hours"] for r in rs))


# ---- experiments: python src/sim.py  ->  results/sweeps.md, results/sweeps.csv ----------------------------------

CATS = {"violence": {"Violence", "Threat"}, "hate": {"Hate/Identity Hate"}, "sexual": {"Sexual", "Sexual (minor)"},
        "selfharm": {"Suicide and Self Harm"}}
POLICIES = {"narrow": ["violence"], "standard": ["violence", "hate", "sexual"], "wide": list(CATS)}
DET_HEAD = {"violence": "det_threat", "hate": "det_identity_attack", "sexual": "det_obscene"}  # no self-harm head
CAP = 45
SEEDS = (1, 2, 3)


def load_pool():
    """Scored Aegis pool split in half: calibration (thresholds) and simulation (item stream)."""
    import pandas as pd
    from pathlib import Path
    df = pd.read_parquet(Path(__file__).resolve().parent.parent / "data/scores.parquet")
    df["cats"] = df.violated_categories.fillna("").map(lambda s: {x.strip() for x in s.split(",") if x.strip()})
    cal = np.random.default_rng(0).random(len(df)) < 0.5
    return df[cal].reset_index(drop=True), df[~cal].reset_index(drop=True)


def true_tiers(df, policy):
    sev = set().union(*(CATS[c] for c in POLICIES[policy]))
    return np.where(df.cats.map(lambda c: bool(c & sev)), 2, np.where(df.prompt_label == "unsafe", 1, 0))


def model_scores(df, model, policy):
    """(severe score, general-harm score) for one model under one policy."""
    if model in ("laya", "laya-ft", "tfidf"):
        pre = {"laya": "lay_", "laya-ft": "layft_", "tfidf": "tfidf_"}[model]
        return np.max([df[pre + c] for c in POLICIES[policy]], axis=0), df[pre + "general"].values
    sev = [df[DET_HEAD[c]] if c in DET_HEAD else np.zeros(len(df)) for c in POLICIES[policy]]
    return np.max(sev, axis=0), df.det_toxicity.values


def predicted_tiers(cal, sim, model, policy, recall):
    """Thresholds set on the calibration half: T2 at `recall` of true T2 items, T1/unsafe at 90%."""
    tc, (sc, gc) = true_tiers(cal, policy), model_scores(cal, model, policy)
    tau2, tau1 = np.quantile(sc[tc == 2], 1 - recall), np.quantile(gc[tc >= 1], 0.1)
    ss, gs = model_scores(sim, model, policy)
    return np.where(ss >= tau2, 2, np.where(gs >= tau1, 1, 0))


def fmt(rows, cols):
    cell = lambda v: "n/a" if v is None else f"{v:.1f}" if isinstance(v, float) else str(v)
    return "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n" + "".join(
        "| " + " | ".join(cell(r.get(c)) for c in cols) + " |\n" for r in rows)


def stream_quality(ss):
    """Share of the simulated stream the router sends to T2, and how often that is right."""
    pred, true = np.concatenate([s.pred for s in ss]), np.concatenate([s.true for s in ss])
    return dict(flagged_t2_pct=100 * float((pred == 2).mean()), t2_precision=float((true[pred == 2] == 2).mean()),
                t2_recall=float((pred[true == 2] == 2).mean()))


def main():
    import pandas as pd
    from pathlib import Path
    cal, sim = load_pool()
    out, csv = [], []

    def streams(true, pred, mix):
        return [make_stream(true, pred, mix, sd) for sd in SEEDS]

    def row(exp, label, base, aware, **kw):
        r = dict(exp=exp, label=label, base_seats=base["seats"], aware_seats=aware["seats"] if aware else None,
                 price_pct=100 * (aware["seats"] / base["seats"] - 1) if aware else None,
                 hidden_pct=aware["over_pct"] if aware else None, **kw)
        csv.append(r)
        return r

    t = true_tiers(sim, "wide")
    mix = (0.6, 0.3, 0.1)
    ss = streams(t, t, mix)
    base = find_seats(ss, "priority")
    out.append(f"## Baseline\n\nSeverity priority, mix 60/30/10, no cap, occupancy <= {OCC_MAX:.0%}: {base['seats']:.1f} seats on duty "
               f"on average = {base['fte']:.0f} FTE at {HOURS_PER_FTE_WEEK} h/week and {SHRINKAGE:.0%} shrinkage.\n")

    rows = []
    for cap in (math.inf, 60, 50, 45, 40, 35, 30):
        rs = [simulate(s, profile(base["k"]), "priority", report_cap=cap) for s in ss]
        over = 100 * sum(r["over"] for r in rs) / sum(r["seat_hours"] for r in rs)
        r = row("cap", "none" if cap == math.inf else cap, base, find_seats(ss, "aware", cap, cap) if cap < math.inf else base,
                priority_over_pct=over)
        if cap < math.inf:  # sensitivity: planning occupancy 95% instead of 85%
            b95 = find_seats(ss, "priority", occ_max=0.95)
            a95 = find_seats(ss, "aware", cap, cap, occ_max=0.95)
            r["price_pct_occ95"] = 100 * (a95["seats"] / b95["seats"] - 1)
            csv[-1]["price_pct_occ95"] = r["price_pct_occ95"]
        rows.append(r)
    out.append("## 1. What the cap costs (oracle tiers)\n\nCap = weighted exposure per rolling 60 min (T1=1, T2=3). "
               "`priority_over_pct` = share of seat-hours the unmanaged baseline spends over that cap. "
               f"`price_pct_occ95` repeats the price with a 95% occupancy ceiling.\n\n"
               + fmt(rows, ["label", "base_seats", "aware_seats", "price_pct", "priority_over_pct", "price_pct_occ95"]))

    k0 = find_seats(ss, "aware", CAP, CAP)
    rows_a, rows_b = [], []
    for model in ("oracle", "detoxify", "laya"):
        for rec in ((1.0,) if model == "oracle" else (0.5, 0.7, 0.8, 0.9, 0.95)):
            p = t if model == "oracle" else predicted_tiers(cal, sim, model, "wide", rec)
            sm = streams(t, p, mix)
            q = stream_quality(sm)
            rows_a.append(row("model_seats", f"{model}@{rec}", base, find_seats(sm, "aware", CAP, CAP), model=model, recall=rec, **q))
            rs = [simulate(s, profile(k0["k"]), "aware", CAP, CAP) for s in sm]
            att = sum(r["met"] for r in rs) / sum(r["counted"] for r in rs)
            rb = dict(label=f"{model}@{rec}", hidden_pct=100 * sum(r["over"] for r in rs) / sum(r["seat_hours"] for r in rs),
                      sla_t0=100 * att[0], sla_t1=100 * att[1], sla_t2=100 * att[2],
                      backlog_pct=100 * sum(r["backlog"] for r in rs) / sum(r["n"] for r in rs))
            rows_b.append(rb)
            csv.append(dict(exp="model_fixed_seats", **rb))
    out.append(f"## 2. Router error at cap {CAP} (wide policy)\n\n"
               "Threshold set so the model finds `recall` of true T2 on the calibration half; `flagged_t2_pct` and `t2_precision` "
               "are measured on the simulated stream (10% true T2).\n\n"
               f"### 2a. Seats needed to meet every SLA (n/a = more than 40 seats)\n\n"
               + fmt(rows_a, ["label", "aware_seats", "price_pct", "flagged_t2_pct", "t2_precision", "t2_recall"])
               + f"\n### 2b. Fixed headcount = the oracle's {k0['seats']:.1f} seats\n\n"
               "`hidden_pct` = share of seat-hours truly over the cap. SLA columns = % of items meeting their SLA by true tier.\n\n"
               + fmt(rows_b, ["label", "hidden_pct", "sla_t0", "sla_t1", "sla_t2", "backlog_pct"]))

    rows = []
    for t2 in (0.05, 0.10, 0.15):
        s2 = streams(t, t, (0.7 - t2, 0.3, t2))
        rows.append(row("mix", f"T2={t2:.0%}", find_seats(s2, "priority"), find_seats(s2, "aware", CAP, CAP)))
    out.append(f"## 3. Queue mix at cap {CAP} (oracle; T1 fixed at 30%)\n\n" + fmt(rows, ["label", "base_seats", "aware_seats", "price_pct"]))

    rows = []
    for pol in POLICIES:
        tp = true_tiers(sim, pol)
        t2 = 0.4 * float((tp == 2).sum() / (tp >= 1).sum())  # 40% of items are unsafe under every policy
        pmix = (0.6, 0.4 - t2, t2)
        b = find_seats(streams(tp, tp, pmix), "priority")
        for model in ("oracle", "detoxify", "laya"):
            p = tp if model == "oracle" else predicted_tiers(cal, sim, model, pol, 0.9)
            sm = streams(tp, p, pmix)
            rows.append(row("policy", f"{pol}/{model}", b, find_seats(sm, "aware", CAP, CAP), policy=pol, model=model,
                            t2_share_pct=100 * t2, **stream_quality(sm)))
    out.append(f"## 4. Policy to headcount at cap {CAP} (40% of items unsafe; models at 90% T2 recall on the calibration half)\n\n"
               + fmt(rows, ["label", "t2_share_pct", "base_seats", "aware_seats", "price_pct", "flagged_t2_pct", "t2_precision", "t2_recall"]))

    res = Path(__file__).resolve().parent.parent / "results"
    pd.DataFrame(csv).to_csv(res / "sweeps.csv", index=False)
    (res / "sweeps.md").write_text("# Sweeps\n\nSeats = average seats on duty (24/7, following the arrival shape); 3 seeds x 3 days pooled. "
                                   "Every ops number is an assumption.\n\n" + "\n".join(out))
    print((res / "sweeps.md").read_text())


if __name__ == "__main__":
    main()
