import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from sim import find_seats, make_stream, profile, simulate  # noqa: E402

POOL = np.repeat([0, 1, 2], 200)
MIX = (0.6, 0.3, 0.1)
CAP = 40


def stream(pred=None, seed=1):
    return make_stream(POOL, POOL if pred is None else pred, MIX, seed)


def test_every_item_handled_once_or_in_backlog():
    s = stream()
    r = simulate(s, profile(3), "aware", CAP, CAP)  # under-staffed on purpose, so a backlog exists
    assert r["backlog"] > 0
    assert r["started"].sum() + r["backlog"] == r["n"]


def test_cap_never_broken_with_oracle_tiers():
    r = simulate(stream(), profile(12), "aware", CAP, CAP)
    assert r["over"] == 0


def test_priority_without_cap_breaks_the_same_cap():
    r = simulate(stream(), profile(12), "priority", math.inf, CAP)
    assert r["over"] > 0


def test_missed_severe_items_are_hidden_breaches():
    blind = np.zeros_like(POOL)  # router believes everything is T0
    r = simulate(stream(blind), profile(12), "aware", CAP, CAP)
    assert r["over"] > 0


def test_same_seed_same_result():
    a = simulate(stream(seed=7), profile(8), "aware", CAP, CAP)
    b = simulate(stream(seed=7), profile(8), "aware", CAP, CAP)
    assert (a["met"] == b["met"]).all() and a["over"] == b["over"] and a["backlog"] == b["backlog"]


def test_cap_costs_headcount():
    ss = [stream(seed=1), stream(seed=2)]
    base = find_seats(ss, "priority")
    capped = find_seats(ss, "aware", CAP, CAP)
    assert base["seats"] < capped["seats"]


def test_occupancy_ceiling_adds_headcount():
    ss = [stream(seed=1), stream(seed=2)]
    assert find_seats(ss, "priority", occ_max=0.85)["seats"] > find_seats(ss, "priority", occ_max=1.0)["seats"]


def test_triage_budgets_hold_on_fresh_data():
    """Thresholds from a calibration draw keep each budget on a fresh draw in >= 90% of trials (target 95%)."""
    from triage import MIX as TMIX, SEVERE, close_tau, remove_hi
    rng = np.random.default_rng(0)
    draw = lambda n: np.repeat([0, 1, 2], n)
    score = lambda tc: rng.normal(np.array([0.0, 2.0, 2.5])[tc], 1.0)
    held = []
    for _ in range(200):
        tc = draw([570, 570, 380])
        g = score(tc)
        tt = draw((np.array(TMIX) * 20000).astype(int))
        gt = score(tt)
        tau, hi = close_tau(g, tc, 0.05), remove_hi(g, tc, 0.05)
        removed = gt >= hi
        held.append(((gt < tau) & (tt >= 1)).sum() / (tt >= 1).sum() <= 0.05
                    and ((gt < tau) & (tt == 2)).sum() / (tt == 2).sum() <= SEVERE
                    and (removed.sum() == 0 or (tt[removed] == 0).mean() <= 0.05))
    assert np.mean(held) >= 0.9
