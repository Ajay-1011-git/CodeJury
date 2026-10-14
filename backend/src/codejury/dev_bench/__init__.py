"""Development-only benchmark. Runtime and scoring files have separate readers.

Never resolves the sealed assessment or imports the authoring catalogue.
"""

import hashlib
import json
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from codejury.stage2_core.contracts import checked
from codejury.stage2_core.intake import prepare
from codejury.stage2_tools.codec import typed_equal
from codejury.stage2_tools.domains import check_args
from codejury.stage2_tools.domains.source import check_bundle
from codejury.stage2_tools.oracles.gate import check_intake
from codejury.stage2_tools.runner.base import validate_envelope
from codejury.training.data import assert_disjoint, normalized

ROOT = Path(__file__).resolve().parents[3] / "data/dev_bench"
SEEDS = (17, 29, 43)
METHODS = ("B-base", "B-single", "J-current")


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_runtime(directory=ROOT):
    rows = read_jsonl(Path(directory) / "runtime.jsonl")
    bases = set()
    for row in rows:
        if set(row) != {
            "base_problem_id",
            "family_id",
            "tier",
            "split",
            "provenance",
            "run_create",
        }:
            raise ValueError("Runtime row contains unknown or scoring fields")
        if row["base_problem_id"] in bases or row["split"] != "development_benchmark":
            raise ValueError("Duplicate base or non-development split")
        bases.add(row["base_problem_id"])
        if row["tier"] not in {"T1", "T2", "T3"}:
            raise ValueError("Unknown tier")
        create = checked(row["run_create"], "RunCreate")
        check_intake(create)
        problem, _ = prepare(create)
        check_bundle(create["source"], problem)
    return rows


def load_scoring(directory=ROOT):
    rows = read_jsonl(Path(directory) / "private/scoring.jsonl")
    if len({r["base_problem_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate scoring base")
    return {r["base_problem_id"]: r for r in rows}


def execute_tests(sandbox, source, create, tests, cancel=None):
    "Candidate/reference execution stays in Docker; expectations stay in host scorer."
    problem, _ = prepare(create)
    check_bundle(source, problem)
    chunk_size = sandbox.limits["chunk_calls"]
    rows = []
    for start in range(0, len(tests), chunk_size):
        chunk = tests[start : start + chunk_size]
        calls = [{"inputs": t["inputs"], "trace_lines": []} for t in chunk]
        envelope = sandbox.run(
            {
                "source": source,
                "function_name": create["function_name"],
                "allowed_imports": create["allowed_dependencies"],
                "calls": calls,
            },
            cancel,
        )
        rows.extend(validate_envelope(envelope, len(chunk)))
    return rows


def passes(result, test):
    return (
        result["status"] == "ok"
        and not result["mutated"]
        and result["before_hash"] == result["after_hash"]
        and typed_equal(result["output"], test["expected"])
    )


def check_training_disjoint(runtime, scoring, training_manifest):
    """Read only declared train/validation assets. Assessment entries stay unopened.

    All current role collectors share this source manifest. Derived episodes/views
    do not introduce additional base problems. Hash-bind the inventory as proof.
"""
    path = Path(training_manifest)
    manifest = json.loads(path.read_text())
    pool, inventory = [], []
    for asset in manifest["assets"]:
        if asset["split"] not in {"train", "validation"}:
            continue
        target = path.parent.parent / asset["path"]
        if target.is_symlink() or path.parent.parent.resolve() not in target.resolve().parents:
            raise ValueError("Training asset leaves data directory")
        if file_hash(target) != asset["sha256"]:
            raise ValueError("Training asset hash mismatch")
        records = read_jsonl(target)
        if any(r["split"] != asset["split"] for r in records):
            raise ValueError("Training asset split mismatch")
        pool.extend(records)
        inventory.append(
            {"path": asset["path"], "sha256": asset["sha256"], "records": len(records)}
        )
    if not pool:
        raise ValueError("No training inventory")
    assert_disjoint(pool)
    dev = [scoring[r["base_problem_id"]] for r in runtime]
    assert_disjoint([*pool, *dev], identity_only=True)
    # Also forbid duplicates within development: one corruption per actual base.
    normalized_dev = [normalized(r["correct_source"]) for r in dev]
    if len(set(normalized_dev)) != len(dev):
        raise ValueError("Duplicate normalized development solution")
    near = []
    unique_pool = {r["base_problem_id"]: r for r in pool}.values()
    for row in dev:
        norm = normalized(row["correct_source"])
        for train in unique_pool:
            similarity = SequenceMatcher(
                None, norm, normalized(train["correct_source"]), autojunk=False
            ).ratio()
            if similarity >= 0.90:
                near.append(
                    {
                        "development": row["base_problem_id"],
                        "training": train["base_problem_id"],
                        "ast_similarity": round(similarity, 4),
                    }
                )
    if near:
        raise ValueError("Near-duplicate development/training solutions: " + json.dumps(near))
    return {
        "inventory": inventory,
        "training_base_problems": len({r["base_problem_id"] for r in pool}),
        "near_duplicate_threshold": 0.90,
        "near_duplicates": near,
        "sealed_assessment_read": False,
    }


def validate_benchmark(directory, sandbox, training_manifest):
    directory = Path(directory)
    runtime, scoring = load_runtime(directory), load_scoring(directory)
    if {r["base_problem_id"] for r in runtime} != scoring.keys():
        raise ValueError("Runtime/scoring populations differ")
    disjoint = check_training_disjoint(runtime, scoring, training_manifest)
    failures, executions = [], 0
    for index, row in enumerate(runtime):
        private = scoring[row["base_problem_id"]]
        create = row["run_create"]
        tests = create["supplied_tests"] + private["hidden_tests"]
        for test in tests:
            if check_args(create["domain_schema"], test["inputs"]):
                raise ValueError(f"{row['base_problem_id']}: scoring input outside domain")
        reference = execute_tests(sandbox, private["correct_source"], create, tests)
        buggy = execute_tests(sandbox, create["source"], create, tests)
        executions += len(reference) + len(buggy)
        if not all(passes(result, test) for result, test in zip(reference, tests)):
            failures.append(
                {
                    "base_problem_id": row["base_problem_id"],
                    "reason": "reference failed",
                    "tests": [t["test_id"] for r, t in zip(reference, tests) if not passes(r, t)],
                }
            )
        if all(passes(result, test) for result, test in zip(buggy, tests)):
            failures.append(
                {"base_problem_id": row["base_problem_id"], "reason": "corruption never fails"}
            )
        print(
            json.dumps({"validated": index + 1, "total": len(runtime), "rejected": len(failures)}),
            flush=True,
        )
    report = {
        "version": "codejury.dev-bench.validation.v1",
        "runtime_sha256": file_hash(directory / "runtime.jsonl"),
        "scoring_sha256": file_hash(directory / "private/scoring.jsonl"),
        "bases": len(runtime),
        "tiers": dict(Counter(r["tier"] for r in runtime)),
        "executions": executions,
        "runtime_hash": sandbox.runtime_hash,
        "disjointness": disjoint,
        "rejected": failures,
    }
    return report


def wilson(solved, total):
    if not total:
        return None
    z = 1.959963984540054
    p = solved / total
    center = (p + z * z / (2 * total)) / (1 + z * z / total)
    radius = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / (1 + z * z / total)
    return [max(0, center - radius), min(1, center + radius)]


def summarize(records):
    "Wilson intervals per seed: repeated seeds never enlarge the base denominator."
    results = []
    for method in sorted({r["method"] for r in records}):
        for seed in sorted({r["seed"] for r in records if r["method"] == method}):
            for tier in ("all", "T1", "T2", "T3"):
                subset = [
                    r
                    for r in records
                    if r["method"] == method
                    and r["seed"] == seed
                    and (tier == "all" or r["tier"] == tier)
                ]
                if not subset:
                    continue
                if len({r["base_problem_id"] for r in subset}) != len(subset):
                    raise ValueError("Repeated base in summary")
                solved = sum(r["outcome"] == "solved" for r in subset)
                results.append(
                    {
                        "method": method,
                        "seed": seed,
                        "tier": tier,
                        "bases": len(subset),
                        "solved": solved,
                        "solve_rate": solved / len(subset),
                        "wilson_95": wilson(solved, len(subset)),
                        "outcomes": dict(Counter(r["outcome"] for r in subset)),
                    }
                )
    return results
