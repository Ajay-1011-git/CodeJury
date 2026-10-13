"""Matched executable validation, strict improvement gate and explicit downstream staleness."""

import json
from pathlib import Path

from codejury.models.worker import file_hash

from ..contracts import json_hash
from ..data import write_report
from ..registry import Registry, local_path
from ..training.fixer_a import evaluate
from .collect import source


def summary(rows):
    return {
        name: sum(r[name] for r in rows)
        for name in ["solved", "incorrect_accepted", "malformed", "accepted"]
    }


def decision(baseline, candidates):
    old = summary(baseline)
    eligible = [
        (name, rows)
        for name, rows in candidates.items()
        if summary(rows)["solved"] > old["solved"]
        and summary(rows)["incorrect_accepted"] <= old["incorrect_accepted"]
        and summary(rows)["malformed"] <= old["malformed"]
    ]
    if not eligible:
        return {
            "status": "no_gain_retain_current",
            "baseline": old,
            "selected": None,
            "candidates": {name: summary(rows) for name, rows in candidates.items()},
        }
    name, rows = min(
        eligible,
        key=lambda item: (
            -summary(item[1])["solved"],
            summary(item[1])["incorrect_accepted"],
            summary(item[1])["malformed"],
            item[0],
        ),
    )
    before = {r["record_id"]: r for r in baseline}
    wins = [r["record_id"] for r in rows if r["solved"] and not before[r["record_id"]]["solved"]]
    losses = [r["record_id"] for r in rows if not r["solved"] and before[r["record_id"]]["solved"]]
    return {
        "status": "candidate_improved_dependencies_pending",
        "baseline": old,
        "selected": name,
        "selected_summary": summary(rows),
        "paired_wins": wins,
        "paired_losses": losses,
        "candidates": {name: summary(rows) for name, rows in candidates.items()},
        "limitations": "20 variants / 10 independent bases; tentative local evidence, not final.",
    }


def checked_rows(path, role, manifest, expected, *, adapter_hash=None):
    report = json.loads(Path(path).read_text())
    registry = Registry(Path(report["registry_path"]))
    rows = [r for r in report["rows"] if r["role"] == role]
    if (
        report["status"] != "completed_diagnostic"
        or report["all_variants"] is not True
        or report["source_manifest_hash"] != json_hash(manifest)
        or report["seed"] != 17
        or report["max_new_tokens"] != 1024
        or len(rows) != len(expected)
        or {r["record_id"] for r in rows} != expected
        or report["model_manifest_hash"] != registry.manifest_hash
        or any(
            r["response_status"] != "ok"
            or r["adapter_hash"] != registry.identity(role)["adapter_hash"]
            for r in rows
        )
    ):
        raise ValueError("Unmatched validation report")
    if adapter_hash is not None and registry.identity(role)["adapter_hash"] != adapter_hash:
        raise ValueError("Baseline is not the current initial adapter")
    return rows


def compare(cfg):
    root = local_path(cfg["artifact_root"])
    result_path = root / "comparison-v1.json"
    if result_path.exists():
        return json.loads(result_path.read_text())
    manifest, rows, _ = source(cfg)
    expected = {r["record_id"] for r in rows if r["split"] == "validation"}
    original = Registry(root / "baseline-registry.json")
    baseline_path = local_path(
        "artifacts/stage2_core/fixer-a-refresh/validation-step100/report.json"
    )
    raw_path = local_path("artifacts/stage2_core/fixer-a-refresh/validation-retained/report.json")
    baseline = checked_rows(
        baseline_path,
        "fixer_a",
        manifest,
        expected,
        adapter_hash=original.identity("fixer_a")["adapter_hash"],
    )
    raw = checked_rows(raw_path, "raw", manifest, expected)
    training = json.loads((root / "student-full-v1/report.json").read_text())
    if training["updates_verified"] is not True or training["reload_verified"] is not True:
        raise ValueError("Saved native candidate has not passed update/reload checks")
    comparisons = {}
    artifacts = {}
    for candidate in training["candidates"]:
        name = f"step-{candidate['step']}"
        out = root / ("validation-" + name)
        path = out / "report.json"
        if not path.exists():
            evaluate(
                local_path(cfg["source_config"]),
                out,
                registry_path=candidate["registry_path"],
                all_variants=True,
                roles=("fixer_a",),
            )
        comparisons[name] = checked_rows(path, "fixer_a", manifest, expected)
        artifacts[name] = {
            "path": str(path),
            "sha256": file_hash(path),
            "registry_path": candidate["registry_path"],
        }
    result = decision(baseline, comparisons)
    result.update(
        raw=summary(raw),
        baseline_report_hash=file_hash(baseline_path),
        raw_report_hash=file_hash(raw_path),
        reports=artifacts,
        training_report_hash=file_hash(root / "student-full-v1/report.json"),
        promoted_to_runtime=False,
        final_contents_opened=False,
        decoding="Identical greedy temp=0, seed 17; duplicate seeds add no sampling evidence.",
    )
    if result["selected"]:
        result["candidate_registry"] = artifacts[result["selected"]]["registry_path"]
        result["required_before_activation"] = [
            "Remine B against new A and paired rescue validation",
            "Validate Critic on current candidate distribution",
            "Refresh affected executed Judge continuation labels and retrain/validate",
            "General teacher opportunity and completion-token parity",
            "All-role local validation and live acceptance",
        ]
    write_report(result_path, result)
    return result


def lineage_check(cfg):
    root = local_path(cfg["artifact_root"])
    path = root / "comparison-v1.json"
    if not path.exists():
        return {"status": "pending_student_comparison", "final_allowed": False}
    result = json.loads(path.read_text())
    return {
        "status": result["status"],
        "upstream_changed": False,
        "candidate_upstream_changed": result["selected"] is not None,
        "affected_labels": "stale_for_candidate" if result["selected"] else "original_preserved",
        "final_allowed": False,
        "pending": result.get(
            "required_before_activation",
            ["General selection", "Live acceptance", "Clean release freeze"],
        ),
    }
