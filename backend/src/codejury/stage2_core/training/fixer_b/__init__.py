"""Train-only A failure weighting and deterministic broad/focused sampling.

This module prepares controls; it neither manufactures failures nor trains an adapter.
"""

import math
import random
from collections import defaultdict

from ...contracts import checked, json_hash
from ...data import learning_example

SEEDS = (17, 29, 41)
ALPHAS = (0, 1, 2, 4)


def failure_fractions(samples, *, adapter_hash, model_config_hash, runtime_mode="live"):
    grouped = defaultdict(dict)
    fields = {
        "runtime_mode",
        "split",
        "base_problem_id",
        "seed",
        "response",
        "solved",
        "infrastructure_error",
        "answer_hash",
    }
    for sample in samples:
        if set(sample) != fields or sample["split"] != "train":
            raise ValueError("Failure mining accepts strictly shaped training samples only")
        if sample["runtime_mode"] != runtime_mode or runtime_mode not in {"live", "fixture"}:
            raise ValueError("Fixture/native evidence cannot be mixed")
        response = checked(sample["response"], "ModelResponse")
        if (
            response["role"] != "fixer_a"
            or response["adapter_hash"] != adapter_hash
            or response["model_config_hash"] != model_config_hash
            or sample["seed"] not in SEEDS
            or type(sample["seed"]) is not int
            or type(sample["solved"]) is not bool
            or type(sample["infrastructure_error"]) is not bool
            or not isinstance(sample["base_problem_id"], str)
            or not sample["base_problem_id"]
            or type(sample["answer_hash"]) is not str
            or len(sample["answer_hash"]) != 64
            or any(c not in "0123456789abcdef" for c in sample["answer_hash"])
        ):
            raise ValueError("Failure sample lacks frozen A/answer/seed provenance")
        if response["status"] != "ok" and not sample["infrastructure_error"]:
            raise ValueError("Native transport failure must be separate from student failure")
        base = grouped[sample["base_problem_id"]]
        if sample["seed"] in base:
            raise ValueError("Duplicate base/seed measurement")
        base[sample["seed"]] = sample
    result, retry = {}, []
    for base_id, seeds in sorted(grouped.items()):
        if set(seeds) != set(SEEDS):
            raise ValueError("Exactly three frozen A generations per training base required")
        if any(s["infrastructure_error"] for s in seeds.values()):
            retry.append(base_id)
            continue
        result[base_id] = sum(not s["solved"] for s in seeds.values()) / len(SEEDS)
    return {
        "runtime_mode": runtime_mode,
        "fractions": result,
        "retry_base_ids": retry,
        "adapter_hash": adapter_hash,
        "model_config_hash": model_config_hash,
        "seeds": list(SEEDS),
        "sample_hash": json_hash(samples),
    }


def sampling_plan(rows, measured, *, alpha=2, broad_fraction=0.25, size=100, seed=17):
    if (
        alpha not in ALPHAS
        or type(alpha) is not int
        or type(size) is not int
        or size < 4
        or type(broad_fraction) not in (int, float)
        or not 0.25 <= broad_fraction <= 0.5
    ):
        raise ValueError("Use alpha 0/1/2/4 and a 25–50% broad general mixture")
    if measured["runtime_mode"] != "live":
        raise ValueError("CPU fixture weights cannot produce a native training plan")
    if measured["retry_base_ids"]:
        raise ValueError("Infrastructure failures need replay before weighting")
    if not rows or any(row["split"] != "train" for row in rows):
        raise ValueError("Only training rows belong in B's learning plan")
    if len({row["record_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate corpus record identity")
    bases = {row["base_problem_id"] for row in rows}
    if set(measured["fractions"]) != bases:
        raise ValueError("Every training base requires measured A failures")
    fractions = measured["fractions"]
    if any(type(f) not in (int, float) or not 0 <= f <= 1 for f in fractions.values()):
        raise ValueError("Failure fraction must be in [0,1]")
    rng = random.Random(seed)
    # Sample bases first so variant counts cannot accidentally weight a family twice.
    groups = defaultdict(list)
    for row in sorted(rows, key=lambda r: r["record_id"]):
        groups[row["base_problem_id"]].append(row)
    base_ids = sorted(groups)
    weights = {b: 1 + alpha * fractions[b] for b in base_ids}
    broad_count = max(
        math.ceil(size * 0.25), min(math.floor(size * 0.5), round(size * broad_fraction))
    )
    plan = []
    for index in range(size):
        broad = index < broad_count
        base = rng.choices(base_ids, weights=None if broad else [weights[b] for b in base_ids])[0]
        row = rng.choice(groups[base])
        # The original/helper bodies and A outputs are absent from this B view.
        example = learning_example(row)
        plan.append(
            {
                "record_id": row["record_id"],
                "base_problem_id": base,
                "stratum": "broad" if broad else "failure_weighted",
                "b_prompt": example["b_prompt"],
                "target": example["target"],
            }
        )
    return {
        "runtime_mode": "live",
        "training_started": False,
        "alpha": alpha,
        "alpha_trials_required": list(ALPHAS),
        "broad_count": broad_count,
        "sample_count": size,
        "actual_broad_fraction": broad_count / size,
        "weights": weights,
        "seed": seed,
        "plan": plan,
        "unweighted_control": "alpha=0; a real separate job remains required",
        "same_view_control": "Separate A-view training job remains required",
        "measurement_hash": measured["sample_hash"],
    }
