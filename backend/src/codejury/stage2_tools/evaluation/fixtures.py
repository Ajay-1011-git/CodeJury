"""SYNTHETIC fixtures for harness checks only (runtime_mode fixture).

Nothing here executes code or measures anything. The scripted port returns canned MethodResults
and the fixture scorer looks correctness up by source hash. Results are labelled fixture and are
rejected by live/final mode; they prove harness logic, never learning or quality.
"""

from ..codec import sha256_text
from .tasks import EvalTask

LABEL = "FIXTURE (synthetic): harness check only, no quality evidence"
KINDS = [
    "natural",
    "natural",
    "synthetic",
    "synthetic",
    "heldout_family",
    "heldout_family",
    "synthetic",
    "natural",
]


def _run_create(i: int) -> dict:
    source = f"def f{i}(values):\n    return len(values)\n"
    return {
        "schema_version": "stage2.v1",
        "source": source,
        "function_name": f"f{i}",
        "contract_text": f"Return the sum of the integers (fixture task {i}).",
        "domain_schema": [
            {
                "name": "values",
                "domain": {
                    "kind": "list",
                    "min_length": 0,
                    "max_length": 6,
                    "item_domain": {"kind": "integer", "min": -5, "max": 5},
                },
            }
        ],
        "helper_interfaces": [],
        "requirements": [
            {
                "schema_version": "stage2.v1",
                "requirement_id": "sum",
                "description": "Sum of all values.",
                "source": "reviewed_contract",
                "approval_status": "approved",
                "property_template_id": "sum_ints",
                "parameters": {},
            }
        ],
        "supplied_tests": [
            {
                "schema_version": "stage2.v1",
                "test_id": "t0",
                "inputs": [[1, 2]],
                "expected": 3,
                "requirement_ids": ["sum"],
            }
        ],
        "allowed_dependencies": [],
        "resource_profile": "mac-standard-v1",
        "policy_mode": "learned",
        "seed": 0,
    }


def correct_source(i: int) -> str:
    return f"def f{i}(values):\n    return sum(values)\n"


def wrong_source(i: int) -> str:
    return f"def f{i}(values):\n    return sum(abs(v) for v in values)\n"


def tasks() -> list[EvalTask]:
    out = []
    for i, kind in enumerate(KINDS):
        out.append(
            EvalTask(
                task_id=f"fx-{i}",
                family_id=f"fam-{i % 4}",
                kind=kind,
                run_create=_run_create(i),
                hidden={
                    "reference_source": correct_source(i),
                    "tests": [{"inputs": [[-1, 2]], "expected": 1}],
                    "fixture_correct_hashes": [sha256_text(correct_source(i))],
                },
            )
        )
    return out


# Scripted outcome per (method, task index): a string for every seed, "s" = first seed variants.
S, W, U = "solved", "wrong", "unresolved"
SCRIPT = {
    "B0": [S, S, W, W, U, W, U, W],
    "B1": [S, S, W, S, W, U, W, W],
    "B2": [S, S, S, W, W, U, W, U],
    "B3": [S, S, S, S, W, U, W, W],
    "B4": [S, S, S, W, W, U, U, W],
    "CJ": [S, S, S, S, S, U, W, "wrong_pool_ok"],
}
DEFAULT = [S, W, U, W, U, W, U, W]


def _candidate(i: int, cid: str, origin: str, source: str, seq: int) -> dict:
    gen = {
        "original": "original",
        "fixer_a": "targeted_repair",
        "fixer_b": "independent_reconstruction",
    }[origin]
    return {
        "schema_version": "stage2.v1",
        "candidate_id": cid,
        "problem_id": f"fx-{i}",
        "parent_id": None if origin == "original" else "c-original",
        "origin": origin,
        "generation_view": gen,
        "source": source,
        "source_hash": sha256_text(source),
        "diagnosis": LABEL,
        "assumptions": [],
        "requirement_ids": ["sum"],
        "model_config_hash": None if origin == "original" else "a" * 64,
        "edits": [],
        "created_event_id": seq,
        "eligibility": "eligible",
        "rejection_reason": None,
        "verification_suite_hash": None,
    }


class FixtureBaselinePort:
    """Scripted BaselinePort. Reports runtime_mode=fixture; hidden data is never visible here."""

    mode = "fixture"

    def __init__(self):
        self.requests = []

    def run(self, request: dict, cancel) -> dict:
        self.requests.append(request)
        method = request["method"]
        task_id = request["request_id"].split("-fx-")[1].split("-")[0]
        i = int(task_id)
        seed = request["input"]["seed"]
        script = SCRIPT.get(method, DEFAULT)
        kind = script[i]
        if method == "CJ" and i == 2 and seed == 37:
            kind = W  # one seed flip so seed replication is non-trivial
        status, selected = "supported_patch", None
        pool = [_candidate(i, "c-original", "original", f"def f{i}(values):\n    return 0\n", 1)]
        if kind in (S, W, "wrong_pool_ok"):
            if kind == S:
                selected = correct_source(i)
            else:
                selected = wrong_source(i)
            pool.append(_candidate(i, "c-a", "fixer_a", wrong_source(i), 2))
            pool.append(
                _candidate(
                    i,
                    "c-b",
                    "fixer_b",
                    correct_source(i) if kind in (S, "wrong_pool_ok") else wrong_source(i),
                    3,
                )
            )
        elif kind == U:
            status = "unresolved"
        elif kind == "infra":
            status = "infrastructure_error"
        else:
            status = "cancelled"
        sel_hash = sha256_text(selected) if selected else None
        chosen = next((c["candidate_id"] for c in pool if c["source_hash"] == sel_hash), None)
        usage = {
            "schema_version": "stage2.v1",
            "output_tokens": 800,
            "input_tokens": 9000,
            "function_executions": 120,
            "elapsed_ms": 4000 + 100 * i,
            "learned_candidates": 2,
            "search_candidates": 0,
            "audit_mutants": 0,
            "judge_decisions": 0,
            "peak_memory_mb": None,
        }
        return {
            "schema_version": "stage2.v1",
            "request_id": request["request_id"],
            "method": method,
            "runtime_mode": "fixture",
            "final_result": {
                "schema_version": "stage2.v1",
                "run_id": f"run-{method}-{i}-{seed}",
                "status": status,
                "selected_candidate_id": chosen,
                "verification_scope": [LABEL],
                "unresolved_requirements": [],
                "evidence_ids": [],
                "resource_usage": usage,
                "termination_reason": None,
            },
            "selected_source": selected,
            "selected_source_hash": sel_hash,
            "candidate_pool": pool,
            "config_hash": request["config_hash"],
        }


class FixtureScorer:
    """Looks correctness up by hash. Runs no code. Labelled fixture."""

    mode = "fixture"

    def score(self, task: EvalTask, source: str) -> bool:
        return sha256_text(source) in task.hidden["fixture_correct_hashes"]
