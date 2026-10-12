"""Public BenchmarkReport (aggregates only) and the private per-seed analysis."""

import json
from collections import defaultdict
from pathlib import Path

from ..codec import errors
from . import config as cfg
from .harness import SIX
from .stats import outcome, paired_bootstrap, per_problem


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _row(config, records, entry, public_seed):
    method, regime = entry["method"], entry["regime"]
    mine = [r for r in records if r["method"] == method and r["regime"] == regime]
    first = [r for r in mine if r["seed"] == public_seed]
    counts = {name: sum(1 for r in first if r["category"] == name) for name in SIX}
    accepted = counts["solved"] + counts["incorrect_accepted"]
    usage = [r["usage"] for r in mine if r["usage"]]
    peak = [u["peak_memory_mb"] for u in usage]
    note = (
        f"Counts use the public seed {public_seed} only; {len({r['seed'] for r in mine})} seeds "
        "were run and analysed with base-problem clustering. "
    )
    if entry["budget"] == "reference":
        note += "Unmatched one-shot reference, not a budget-matched comparison. "
    if any(r["runtime_mode"] == "fixture" for r in mine):
        note += "SYNTHETIC FIXTURE RESULTS: not evidence of any learning or quality."
    return {
        "schema_version": "stage2.v1",
        "method": method,
        "total_base_problems": len({r["task_id"] for r in first}),
        "seed_count": len({r["seed"] for r in mine}),
        **counts,
        "acceptance_precision": counts["solved"] / accepted if accepted else None,
        "mean_input_tokens": _mean(u["input_tokens"] for u in usage),
        "mean_output_tokens": _mean(u["output_tokens"] for u in usage),
        "mean_executions": _mean(u["function_executions"] for u in usage),
        "mean_elapsed_ms": _mean(u["elapsed_ms"] for u in usage),
        "mean_peak_memory_mb": _mean(peak) if any(p is not None for p in peak) else None,
        "inference_config_hash": mine[0]["config_hash"]
        if mine
        else cfg.config_hash(config, method, regime),
        "training_token_opportunity": int(
            config["methods"].get(method, {}).get("training_token_opportunity", 0)
        ),
        "budget_comparison": entry["budget"]
        if entry["budget"] in ("reference", "token_matched", "time_matched")
        else "token_matched",
        "note": note.strip(),
    }


def secondary(records: list[dict]) -> dict:
    """Pool diagnostics, computed only after commitments: never oracle-best selection."""
    out = {}
    groups = defaultdict(list)
    for r in records:
        groups[(r["method"], r["regime"])].append(r)
    for (method, regime), rs in groups.items():
        with_pool = [r for r in rs if r["pool"]]
        has = [r for r in with_pool if r.get("pool_has_correct")]
        a_fail = [
            r
            for r in with_pool
            if not any(
                f["correct"] for f in r["pool_scores"].values() if f["origin"].startswith("fixer_a")
            )
            and any(f["origin"].startswith("fixer_a") for f in r["pool_scores"].values())
        ]
        rescued = [
            r
            for r in a_fail
            if any(
                f["correct"] for f in r["pool_scores"].values() if f["origin"].startswith("fixer_b")
            )
        ]
        joint = [r for r in a_fail if r not in rescued]
        out[f"{method}|{regime}"] = {
            "runs_with_pool": len(with_pool),
            "pool_contains_correct": len(has),
            "selected_correct_given_pool_correct": (
                sum(1 for r in has if r["category"] == "solved") / len(has) if has else None
            ),
            "b_rescue_rate_among_a_failed": len(rescued) / len(a_fail) if a_fail else None,
            "joint_failure_rate_among_a_failed": len(joint) / len(a_fail) if a_fail else None,
            "critic_authorized_yield": None,
            "critic_false_rejection": None,
            "judge_vs_fixed": None,
            "note": "Critic/Judge event-level metrics need the runtime event export; null here.",
        }
    return out


def analyze(
    config: dict,
    records: list[dict],
    *,
    manifest_hash: str | None,
    dataset_id: str | None,
    mode: str,
    declared_runs: int | None = None,
) -> dict:
    plan = cfg.plan(config)
    rows = [
        _row(config, records, e, config["public_seed"])
        for e in plan
        if any(r["method"] == e["method"] and r["regime"] == e["regime"] for r in records)
    ]
    boot = config["bootstrap"]
    primary = config["primary_comparison"]
    regime = primary["regime"]
    ours = (primary["method"], regime)
    base = (primary["baseline"], regime)
    comparisons = {}
    for metric in ("solved", "incorrect_accepted"):
        a = per_problem(records, ours[0], ours[1], metric)
        b = per_problem(records, base[0], base[1], metric)
        comparisons[metric] = paired_bootstrap(
            a, b, resamples=boot["resamples"], seed=boot["seed"], confidence=boot["confidence"]
        )
    for kind in sorted({r["kind"] for r in records}):
        subset = [r for r in records if r["kind"] == kind]
        a = per_problem(subset, ours[0], ours[1], "solved")
        b = per_problem(subset, base[0], base[1], "solved")
        comparisons[f"solved[{kind}]"] = paired_bootstrap(
            a, b, resamples=boot["resamples"], seed=boot["seed"], confidence=boot["confidence"]
        )
    verdict = outcome(
        comparisons["solved"], comparisons["incorrect_accepted"], config["false_acceptance_margin"]
    )
    expected = sum(1 for e in plan)
    seen = len({(r["method"], r["regime"]) for r in records})
    if not records:
        status = "not_run"
    elif seen < expected or (declared_runs is not None and len(records) < declared_runs):
        status = "partial"
    else:
        status = "completed"
    if status != "completed" and verdict != "not_measured":
        verdict = "inconclusive" if verdict == "improved" else verdict
    limitations = [
        "Selected-patch correctness uses finite hidden tests, not proof of correctness.",
        "Counts are for the public seed; all seeds are analysed in the private table, clustered "
        "by base problem.",
        "Candidate-pool metrics are secondary diagnostics computed after all commitments.",
        "Critic yield/false-rejection and Judge-vs-fixed event metrics are not in this report.",
    ]
    if mode == "fixture":
        limitations.insert(0, "SYNTHETIC FIXTURE RUN: harness check only, no quality evidence.")
    n = comparisons["solved"]["n_problems"]
    note = (
        f"{primary['method']} vs {primary['baseline']} ({regime}), paired clustered bootstrap over "
        f"{n} base problems, {boot['resamples']} resamples, {int(boot['confidence'] * 100)}% CI. "
    )
    if comparisons["solved"]["difference"] is not None:
        d, (lo, hi) = comparisons["solved"]["difference"], comparisons["solved"]["ci"]
        note += (
            f"solved difference {d:+.3f} [{lo:+.3f}, {hi:+.3f}]; wins "
            f"{comparisons['solved']['wins']}, losses {comparisons['solved']['losses']}, "
            f"ties {comparisons['solved']['ties']}. "
        )
    if (primary["baseline"], regime) not in {(r["method"], r["regime"]) for r in records}:
        note += "The fair baseline was not run: comparison incomplete."
        verdict = "not_measured"
    report = {
        "schema_version": "stage2.v1",
        "runtime_mode": mode,
        "status": status,
        "dataset_id": dataset_id,
        "dataset_manifest_hash": manifest_hash,
        "rows": rows,
        "paired_analysis_note": note.strip(),
        "limitations": limitations,
        "research_outcome": verdict if status != "not_run" else "not_measured",
    }
    problems = errors(report, "BenchmarkReport")
    if problems:
        raise ValueError(f"BenchmarkReport invalid: {problems[0]}")
    for row in report["rows"]:
        if sum(row[k] for k in SIX) != row["total_base_problems"]:
            raise ValueError(f"{row['method']}: six outcome counts do not partition the problems")
    return {"report": report, "comparisons": comparisons, "secondary": secondary(records)}


def write_analysis(result: dict, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(result["report"], indent=2, sort_keys=True))
    private = Path(path).with_name(Path(path).stem + ".private.json")
    private.write_text(
        json.dumps(
            {"comparisons": result["comparisons"], "secondary": result["secondary"]},
            indent=2,
            sort_keys=True,
        )
    )
