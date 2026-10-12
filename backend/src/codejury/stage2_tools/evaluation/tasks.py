"""Private evaluation tasks and hidden scoring. Hidden references/tests never enter requests."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ..domains import SourceError, analyze_source, check_args
from ..oracles import OracleError, build_supplied_tests, check_intake

KINDS = ("natural", "synthetic", "heldout_family", "external")


@dataclass(frozen=True)
class EvalTask:
    task_id: str
    family_id: str
    kind: str
    run_create: dict
    hidden: dict  # {"reference_source": str, "tests": [{"inputs":..., "expected":...}]}


def load_tasks(path: Path) -> list[EvalTask]:
    tasks = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["kind"] not in KINDS:
            raise ValueError(f"Unknown task kind {row['kind']!r}")
        tasks.append(
            EvalTask(
                row["task_id"], row["family_id"], row["kind"], row["run_create"], row["hidden"]
            )
        )
    if len({t.task_id for t in tasks}) != len(tasks):
        raise ValueError("Duplicate base problem ids: variants are not independent tasks")
    return tasks


def visible_hash(task: EvalTask) -> str:
    return hashlib.sha256(json.dumps(task.run_create, sort_keys=True).encode()).hexdigest()


def problem_stub(run_create: dict) -> dict:
    """The minimum Problem fields the sandbox evaluator needs to run a bundle."""
    info = analyze_source(
        run_create["source"],
        run_create["function_name"],
        run_create["helper_interfaces"],
        run_create["allowed_dependencies"],
    )
    return {
        "problem_id": "scoring",
        "function_name": run_create["function_name"],
        "signature": info.signature,
        "helper_interfaces": run_create["helper_interfaces"],
        "allowed_dependencies": run_create["allowed_dependencies"],
        "domain_schema": run_create["domain_schema"],
        "requirements": run_create["requirements"],
    }


def hidden_tests(task: EvalTask) -> list[dict]:
    return [
        {
            "schema_version": "stage2.v1",
            "test_id": f"hidden-{i}",
            "input_codec_version": "json.v1",
            "inputs": t["inputs"],
            "related_inputs": None,
            "oracle_spec": {"kind": "literal", "expected": t["expected"]},
            "oracle_status": "authoritative",
            "oracle_source": "reviewed_contract",
            "domain_valid": True,
            "requirement_ids": [],
            "provenance": "supplied",
        }
        for i, t in enumerate(task.hidden["tests"])
    ]


def static_eligibility(task: EvalTask) -> str | None:
    """Reason a task is excluded before any method runs (frozen preflight), else None."""
    try:
        check_intake(task.run_create)
        build_supplied_tests(task.run_create)
        problem_stub(task.run_create)
        for t in task.hidden["tests"]:
            reason = check_args(task.run_create["domain_schema"], t["inputs"])
            if reason:
                return f"hidden test outside the supported domain: {reason}"
        analyze_source(
            task.hidden["reference_source"],
            task.run_create["function_name"],
            task.run_create["helper_interfaces"],
            task.run_create["allowed_dependencies"],
        )
    except (OracleError, SourceError, ValueError, KeyError) as exc:
        return f"unsupported by the frozen preflight: {exc}"
    return None


class SandboxScorer:
    """Scores a source on the hidden tests inside the sandbox. Used once per committed run."""

    mode = "sandbox"

    def __init__(self, sandbox, max_executions: int = 100000):
        self.sandbox = sandbox
        self.max_executions = max_executions

    def score(self, task: EvalTask, source: str) -> bool:
        from ..runner import Evaluator, hard_rejection

        problem = problem_stub(task.run_create)
        ev = Evaluator(self.sandbox, problem, id_prefix="hs", max_executions=self.max_executions)
        tests = hidden_tests(task)
        rows = ev.evaluate({"candidate_id": "scored", "source": source}, tests)
        if len(rows) != len(tests):
            return False
        return not any(hard_rejection(r, t) for r, t in zip(rows, tests))

    def reference_ok(self, task: EvalTask) -> bool:
        return self.score(task, task.hidden["reference_source"])
