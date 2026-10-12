"""Private TRAINING assessment after immutable final answers; never fed back to a run."""

import json
from pathlib import Path
from uuid import uuid4

from ..budgets import CAPS
from ..contracts import CheckedToolPort, checked, json_hash
from ..controller import draft, records
from ..controller.inputs import training_input
from ..data import load_stage1
from ..registry import local_path


def training_labels(ledger, run_ids, tool_port, cancel, out):
    out = Path(out)
    private_root = local_path("artifacts/stage2_core")
    if private_root not in out.resolve().parents:
        raise ValueError("Private training labels must remain under artifacts/stage2_core")
    if out.exists():
        raise FileExistsError("Private training labels cannot be overwritten")
    if not run_ids or len(run_ids) != len(set(run_ids)):
        raise ValueError("Unique frozen training runs are required")
    manifest, train = None, None
    frozen = []
    for run_id in run_ids:
        snapshot = ledger.snapshot(run_id)
        metadata = records(ledger, run_id, "metadata")
        if (
            snapshot["runtime_mode"] != "live"
            or snapshot["status"] not in {"supported_patch", "unresolved"}
            or len(metadata) != 1
        ):
            raise ValueError("Private labels require frozen actual native training runs")
        provenance = metadata[0]["provenance"]
        if not provenance or provenance["split"] != "train":
            raise ValueError("Private labels exclude validation and final assessment")
        if train is None:
            manifest, rows = load_stage1(local_path("data/manifests/stage1.json"))
            train = {r["record_id"]: r for r in rows if r["split"] == "train"}
        row = train.get(provenance["record_id"])
        if (
            row is None
            or provenance["source_manifest_hash"] != json_hash(manifest)
            or training_input(row)[0] != snapshot["problem"]
        ):
            raise ValueError("Training source provenance mismatch")
        frozen.append((snapshot, row, json_hash(snapshot)))
    labels = []
    for snapshot, row, freeze_hash in frozen:
        request_id = "offline-" + uuid4().hex
        problem = snapshot["problem"]
        tests = [
            checked(
                {
                    "schema_version": "stage2.v1",
                    "test_id": request_id + "-t" + str(index),
                    "input_codec_version": "json.v1",
                    "inputs": t["args"],
                    "related_inputs": None,
                    "oracle_spec": {"kind": "literal", "expected": t["expected"]},
                    "oracle_status": "authoritative",
                    "oracle_source": "user",
                    "domain_valid": True,
                    "requirement_ids": [r["requirement_id"] for r in problem["requirements"]],
                    "provenance": "supplied",
                },
                "TestCase",
            )
            for index, t in enumerate(row["assessment_tests"])
        ]
        candidates = [c for c in snapshot["candidates"] if c["origin"] != "original"]
        request = checked(
            {
                "schema_version": "stage2.v1",
                "request_id": request_id,
                "id_prefix": request_id,
                "run_id": request_id,
                "problem": problem,
                "parameters": {
                    "operation": "evaluate",
                    "candidates": [draft(c) for c in candidates],
                    "tests": tests,
                    "stop_on_first_hard_failure": False,
                },
                "remaining_budget": CAPS,
            },
            "ToolRequest",
        )
        result = CheckedToolPort(tool_port).call(request, cancel)
        if result["status"] != "ok" or cancel.is_set():
            raise ValueError("Private assessment transport failed; no semantic labels published")
        candidate_labels = []
        for candidate in candidates:
            own = [
                e for e in result["executions"] if e["candidate_id"] == candidate["candidate_id"]
            ]
            complete = {e["test_id"] for e in own} == {t["test_id"] for t in tests} and bool(tests)
            solved = complete and all(
                e["outcome"] == "pass"
                and e["exception"] is None
                and all(
                    not effect["mutated"] and effect["before_hash"] == effect["after_hash"]
                    for effect in e["input_effects"]
                )
                for e in own
            )
            candidate_labels.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "source_hash": candidate["source_hash"],
                    "origin": candidate["origin"],
                    "complete": complete,
                    "training_assessment_solved": solved,
                }
            )
        selected = snapshot["decision"]["selected_candidate_id"]
        labels.append(
            {
                "run_id": snapshot["run_id"],
                "base_problem_id": row["base_problem_id"],
                "record_id": row["record_id"],
                "final_snapshot_hash": freeze_hash,
                "runtime_status": snapshot["status"],
                "selected_candidate_id": selected,
                "controller_solved": any(
                    c["candidate_id"] == selected and c["training_assessment_solved"]
                    for c in candidate_labels
                ),
                "candidate_labels": candidate_labels,
                "private_request": request,
                "private_result": result,
            }
        )
        if json_hash(ledger.snapshot(snapshot["run_id"])) != freeze_hash:
            raise ValueError("Private scoring altered a frozen runtime run")
    report = {
        "version": "stage2.private-training-labels.v1",
        "split": "train",
        "contains_training_assessment": True,
        "contains_final_assessment": False,
        "source_manifest_hash": json_hash(manifest),
        "runs": labels,
        "note": "Private post-freeze train assessment only. Not Judge action labels, "
        "not final benchmark accuracy; never import into runtime/exported episodes.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return {
        "runs": len(labels),
        "controller_solved": sum(label["controller_solved"] for label in labels),
        "candidate_solved": sum(
            c["training_assessment_solved"] for label in labels for c in label["candidate_labels"]
        ),
        "candidate_count": sum(len(label["candidate_labels"]) for label in labels),
        "actual_function_executions": sum(
            label["private_result"]["usage"]["function_executions"] for label in labels
        ),
    }
