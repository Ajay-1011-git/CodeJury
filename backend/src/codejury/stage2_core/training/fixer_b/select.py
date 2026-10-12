"""Validation selects independent B and retains genuine alpha/view controls."""

import copy
import json
import shutil
from pathlib import Path

from codejury.models.worker import file_hash

from ...contracts import checked, json_hash
from ...data import config as a_config
from ...data import load_stage1, write_report
from ...registry import ADAPTER_FILES, Registry, hashes, local_path
from . import ALPHAS
from .evaluate import paired
from .mining import selected_a, settings


def rank(summary):
    return (
        summary["b_incorrect_accepted"],
        -summary["union_solved"],
        -summary["b_solved"],
        summary["b_malformed"],
        summary["b_input_tokens"] + summary["b_output_tokens"],
    )


def inspect_reports(config_path, paths):
    cfg = settings(config_path)
    learning = a_config(local_path(cfg["a_config"]))
    source, records = load_stage1(local_path(learning["source_manifest"]))
    expected = {r["record_id"] for r in records if r["split"] == "validation"}
    a = selected_a(cfg)
    entries = []
    for path in paths:
        path = Path(path).resolve()
        report = json.loads(path.read_text())
        registry = Registry(Path(report["registry_path"]))
        job_path = registry.path.parent.parent / "session.json"
        job = json.loads(job_path.read_text())
        summary = paired(report["rows"])
        if (
            report["status"] != "completed_paired_validation"
            or report["runtime_mode"] != "live"
            or report["source_manifest_hash"] != json_hash(source)
            or report["seed"] != learning["seed"]
            or report["max_new_tokens"] != learning["max_new_tokens"]
            or report["registry_hash"] != registry.manifest_hash
            or registry.identity("fixer_a") != a.identity("fixer_a")
            or {r["record_id"] for r in report["rows"]} != expected
            or len(report["rows"]) != 2 * len(expected)
            or report["summary"] != summary
            or report["training_session_hash"] != file_hash(job_path)
            or report["training_job_identity"] != job["job_identity"]
            or job["config_file_hash"] != file_hash(config_path)
            or job["registry_hash"] != a.manifest_hash
            or job["phase"] != "full"
            or job["view"] != report["view"]
            or job["alpha"] != report["alpha"]
            or any(
                r["response_status"] != "ok"
                or r["adapter_hash"] != registry.identity(r["role"])["adapter_hash"]
                or r["model_config_hash"] != registry.identity(r["role"])["model_config_hash"]
                for r in report["rows"]
            )
        ):
            raise ValueError("Incomplete/incompatible actual paired B validation")
        proof_path = job_path.parent / "report.json"
        proof = json.loads(proof_path.read_text())
        if (
            proof["status"] != "trained_selection_pending"
            or proof["reload_verified"] is not True
            or proof["updates_verified"] is not True
            or proof["job_identity"] != job["job_identity"]
            or proof["completed_steps"] != job["steps"]
        ):
            raise ValueError("B job lacks actual train/save/reload proof")
        entries.append(
            {
                "path": str(path),
                "sha256": file_hash(path),
                "report": report,
                "registry": registry,
                "summary": summary,
                "job": job,
            }
        )
    return entries


def select(config_path, candidate_paths, out, *, control_paths=()):
    candidates = inspect_reports(config_path, candidate_paths)
    if (
        not candidates
        or any(r["report"]["view"] != "independent" for r in candidates)
        or {r["report"]["alpha"] for r in candidates} != set(ALPHAS)
    ):
        raise ValueError("Selection requires actual independent-view alpha0/1/2/4 validation")
    chosen = min(candidates, key=lambda r: rank(r["summary"]))
    controls = inspect_reports(config_path, control_paths) if control_paths else []
    matching = [
        r
        for r in controls
        if r["report"]["view"] == "same_as_a" and r["report"]["alpha"] == chosen["report"]["alpha"]
    ]
    if not matching:
        raise ValueError("Selected weighting also needs a genuinely trained same-view control")
    directory = Path(out).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    registry = chosen["registry"]
    adapter = registry.verify_adapter("fixer_b")
    for name in ADAPTER_FILES:
        shutil.copyfile(adapter / name, directory / name)
    record = copy.deepcopy(registry.record)
    entry = record["adapters"]["fixer_b"]
    entry["path"] = str(directory)
    entry["files"] = hashes(directory, ADAPTER_FILES)
    entry["card"]["status"] = "completed"
    s = chosen["summary"]
    entry["card"]["evaluation_summary"] = (
        f"Limited 20-variant/10-base validation: B{s['b_solved']}/20, union{s['union_solved']}/20, "
        f"rescues{s['rescued_a_failures']}/{s['a_failures']}, "
        f"incorrect-accepted{s['b_incorrect_accepted']}. "
        f"Independent-view alpha{chosen['report']['alpha']}; "
        "actual alpha0/1/2/4 and same-view controls. "
        "One-shot candidates only; final controller selection and final benchmark not measured."
    )
    checked(entry["card"], "AdapterCard")
    write_report(directory / "registry.json", record)
    selected = Registry(directory / "registry.json")
    result = {
        "status": "selected_limited_validation",
        "role": "fixer_b",
        "registry_path": str(selected.path),
        "adapter_hash": selected.identity("fixer_b")["adapter_hash"],
        "a_adapter_hash": selected.identity("fixer_a")["adapter_hash"],
        "selected_report": chosen["path"],
        "alpha": chosen["report"]["alpha"],
        "selected_summary": s,
        "comparisons": [
            {
                "path": r["path"],
                "sha256": r["sha256"],
                "summary": r["summary"],
                "alpha": r["report"]["alpha"],
                "view": r["report"]["view"],
                "steps": r["registry"].record["adapters"]["fixer_b"]["card"]["steps"],
            }
            for r in [*candidates, *controls]
        ],
        "policy": "Incorrect acceptance ascending, union solved descending, B solved descending, "
        "malformed ascending, token cost ascending. No loss/disagreement reward.",
        "limitations": [
            "Small synthetic corpus; weighted repeats are not new bases.",
            "Union/rescue is candidate availability, not controller final-answer quality.",
            "20 variants share 10 validation bases; final assessment remains sealed.",
        ],
    }
    write_report(directory / "selection.json", result)
    export_fixers(directory)
    return result


def export_fixers(directory):
    """Complete/recover only the private handoff after verified checkpoint selection."""
    directory = Path(directory).resolve()
    result = json.loads((directory / "selection.json").read_text())
    selected = Registry(directory / "registry.json")
    if (
        result["status"] != "selected_limited_validation"
        or result["role"] != "fixer_b"
        or result["adapter_hash"] != selected.identity("fixer_b")["adapter_hash"]
        or result["a_adapter_hash"] != selected.identity("fixer_a")["adapter_hash"]
    ):
        raise ValueError("Handoff requires actual matching selected A/B bytes")
    if (directory / "exchange/manifest.json").exists():
        raise FileExistsError("Adapter handoff refuses overwrite")
    handoff_files = []
    for role in ("fixer_a", "fixer_b"):
        destination = directory / "exchange" / role
        destination.mkdir(parents=True, exist_ok=True)
        source = selected.verify_adapter(role)
        for name in ADAPTER_FILES:
            target = destination / name
            if target.exists():
                if file_hash(target) != file_hash(source / name):
                    raise ValueError("Partial handoff bytes differ from selected adapter")
            else:
                shutil.copyfile(source / name, target)
            handoff_files.append(
                {
                    "relative_path": role + "/" + name,
                    "sha256": file_hash(destination / name),
                    "size_bytes": (destination / name).stat().st_size,
                }
            )
    artifact = checked(
        {
            "schema_version": "stage2.v1",
            "exchange_id": "ajay-selected-fixers",
            "owner": "ajay",
            "kind": "fixer_adapters",
            "split": "none",
            "base_revision_hash": selected.base["base_revision_hash"],
            "files": handoff_files,
            "record_count": 2,
            "base_problem_count": 0,
            "contains_hidden_assessment": False,
            "note": "Actual selected A/B adapters; small synthetic validation. "
            "Private local handoff, not committed weight bytes.",
        },
        "ArtifactManifest",
    )
    write_report(directory / "exchange/manifest.json", artifact)
    return artifact
