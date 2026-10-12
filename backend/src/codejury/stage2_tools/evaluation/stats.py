"""Clustered paired bootstrap. Seeds and variants are nested inside base problems.

Per base problem we first average over seeds; the resampling unit is the base problem, so
repeats are never treated as independent tasks. Pure Python and deterministic for a fixed seed.
"""

import math
import random


def per_problem(records: list[dict], method: str, regime: str | None, metric: str) -> dict:
    """task_id -> mean over seeds of the 0/1 metric (solved / incorrect_accepted / ...)."""
    sums: dict[str, list[float]] = {}
    for r in records:
        if r["method"] == method and r["regime"] == regime:
            sums.setdefault(r["task_id"], []).append(1.0 if r["category"] == metric else 0.0)
    return {task: sum(v) / len(v) for task, v in sums.items()}


def paired_bootstrap(
    a: dict, b: dict, *, resamples: int = 10000, seed: int = 0, confidence: float = 0.95
) -> dict:
    """Difference mean(a - b) over shared base problems with a percentile CI."""
    tasks = sorted(set(a) & set(b))
    if not tasks:
        return {
            "n_problems": 0,
            "difference": None,
            "ci": [None, None],
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "resamples": resamples,
        }
    diffs = [a[t] - b[t] for t in tasks]
    n = len(diffs)
    rng = random.Random(seed)
    means = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            total += diffs[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    alpha = (1 - confidence) / 2
    lo = means[max(0, math.floor(alpha * resamples))]
    hi = means[min(resamples - 1, math.ceil((1 - alpha) * resamples) - 1)]
    return {
        "n_problems": n,
        "difference": sum(diffs) / n,
        "ci": [lo, hi],
        "wins": sum(1 for d in diffs if d > 1e-12),
        "losses": sum(1 for d in diffs if d < -1e-12),
        "ties": sum(1 for d in diffs if abs(d) <= 1e-12),
        "resamples": resamples,
    }


def outcome(solved: dict, false_accept: dict, margin: float) -> str:
    """improved / inconclusive / worse from paired uncertainty and false acceptance.

    improved: the solved-rate CI excludes 0 on the positive side AND false acceptance is neither
    significantly higher (its CI includes <=0) nor higher by more than `margin` on average.
    worse: the solved-rate CI is entirely negative OR false acceptance is significantly higher.
    Anything else (including uncertainty that spans no gain) is inconclusive.
    """
    if solved["difference"] is None:
        return "not_measured"
    s_lo, s_hi = solved["ci"]
    f_diff = false_accept["difference"] or 0.0
    f_lo = false_accept["ci"][0] if false_accept["ci"][0] is not None else 0.0
    if s_hi < 0 or f_lo > 0:
        return "worse"
    if s_lo > 0 and f_lo <= 0 and f_diff <= margin:
        return "improved"
    return "inconclusive"
