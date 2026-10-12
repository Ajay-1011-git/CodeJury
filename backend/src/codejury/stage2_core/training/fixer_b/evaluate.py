"""Paired executable A/B validation, assessed after each frozen visible answer."""

import json
from pathlib import Path
from threading import Event
from uuid import uuid4

import yaml

from codejury.models.worker import file_hash
from codejury.runner import DockerRunner

from ...budgets import CAPS
from ...contracts import json_hash
from ...data import config as a_config
from ...data import learning_example, load_stage1, runtime_example, write_report
from ...model_worker import NativeModelPort
from ...registry import Registry, local_path
from .mining import assess, selected_a, settings


def paired(rows):
    grouped = {}
    for row in rows:
        pair = grouped.setdefault(row["record_id"], {})
        if row["role"] in pair or row["role"] not in {"fixer_a", "fixer_b"}:
            raise ValueError("Duplicate/unknown role in paired validation")
        pair[row["role"]] = row
    if not grouped or any(set(p) != {"fixer_a", "fixer_b"} for p in grouped.values()):
        raise ValueError("Complete A/B pairs required")
    a = sum(p["fixer_a"]["solved"] for p in grouped.values())
    b = sum(p["fixer_b"]["solved"] for p in grouped.values())
    rescued = sum(not p["fixer_a"]["solved"] and p["fixer_b"]["solved"] for p in grouped.values())
    overlap = sum(p["fixer_a"]["solved"] and p["fixer_b"]["solved"] for p in grouped.values())
    total = len(grouped)
    return {
        "total": total,
        "a_solved": a,
        "b_solved": b,
        "union_solved": a + rescued,
        "rescued_a_failures": rescued,
        "a_failures": total - a,
        "rescue_rate": rescued / (total - a) if total > a else None,
        "joint_failures": total - a - rescued,
        "overlap_solved": overlap,
        "b_incorrect_accepted": sum(p["fixer_b"]["incorrect_accepted"] for p in grouped.values()),
        "b_malformed": sum(p["fixer_b"]["malformed"] for p in grouped.values()),
        "b_input_tokens": sum(p["fixer_b"]["usage"]["input_tokens"] for p in grouped.values()),
        "b_output_tokens": sum(p["fixer_b"]["usage"]["output_tokens"] for p in grouped.values()),
    }


def evaluate(config_path, registry_path, out, *, view="independent", baseline_path=None):
    cfg = settings(config_path)
    learning = a_config(local_path(cfg["a_config"]))
    manifest, records = load_stage1(local_path(learning["source_manifest"]))
    records = [r for r in records if r["split"] == "validation"]
    a_registry = selected_a(cfg)
    registry = Registry(Path(registry_path))
    job_path = registry.path.parent.parent / "session.json"
    job = json.loads(job_path.read_text())
    if (
        job.get("role") != "fixer_b"
        or job.get("view") != view
        or job.get("phase") != "full"
        or registry.record["adapters"]["fixer_b"]["card"]["data_manifest_hash"]
        != job["data_manifest_hash"]
    ):
        raise ValueError("Validation view/job does not match the actual full B training session")
    if (
        registry.identity("fixer_a") != a_registry.identity("fixer_a")
        or registry.identity("fixer_a")["adapter_hash"]
        == registry.identity("fixer_b")["adapter_hash"]
        or view not in {"independent", "same_as_a"}
    ):
        raise ValueError("B validation requires the frozen A and distinct compatible B")
    runtime = yaml.safe_load(local_path(learning["runtime_config"]).read_text())
    directory = Path(out).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    runner = DockerRunner()
    runner_info = runner.ready()
    rows, executions = [], 0
    roles = ("fixer_a", "fixer_b")
    if baseline_path is not None:
        # A's exact fixed one-shot outputs can be reused; B sees none of them.
        baseline = json.loads(Path(baseline_path).read_text())
        a_rows = [r for r in baseline["rows"] if r["role"] == "fixer_a"]
        if (
            baseline["status"] != "completed_diagnostic"
            or baseline["all_variants"] is not True
            or baseline["source_manifest_hash"] != json_hash(manifest)
            or baseline["seed"] != learning["seed"]
            or baseline["max_new_tokens"] != learning["max_new_tokens"]
            or len(a_rows) != len(records)
            or {r["record_id"] for r in a_rows} != {r["record_id"] for r in records}
            or any(
                r["response_status"] != "ok"
                or r["adapter_hash"] != registry.identity("fixer_a")["adapter_hash"]
                or r["model_config_hash"] != registry.identity("fixer_a")["model_config_hash"]
                for r in a_rows
            )
        ):
            raise ValueError("Reused A baseline does not match frozen validation/A/decoding")
        rows.extend(a_rows)
        roles = ("fixer_b",)
    with NativeModelPort(registry, runtime) as port:
        for record in records:
            example = learning_example(record)
            problem, tests = runtime_example(record)
            for role in roles:
                prompt = (
                    example["b_prompt"]
                    if role == "fixer_b" and view == "independent"
                    else example["a_prompt"]
                )
                request = {
                    "schema_version": "stage2.v1",
                    "request_id": "b-val-" + uuid4().hex,
                    "run_id": "b-paired-validation",
                    "role": role,
                    "purpose": "reconstruct" if role == "fixer_b" else "repair",
                    "prompt": prompt,
                    "seed": learning["seed"],
                    "max_new_tokens": learning["max_new_tokens"],
                    "remaining_budget": CAPS,
                }
                response = port.generate(request, Event())
                trial = directory / (record["record_id"] + "-" + role)
                trial.mkdir()
                write_report(
                    trial / "generation.json",
                    {"request": request, "response": response, "prompt_hash": json_hash(prompt)},
                )
                try:
                    result = assess(record, problem, tests, response, trial, runner)
                except Exception as exc:
                    write_report(
                        directory / "interrupted.json",
                        {
                            "exception": type(exc).__name__,
                            "completed_rows": len(rows),
                            "quality_conclusion": False,
                        },
                    )
                    raise
                row = {
                    "record_id": record["record_id"],
                    "base_problem_id": record["base_problem_id"],
                    "role": role,
                    **result,
                    "response_status": response["status"],
                    "adapter_hash": response["adapter_hash"],
                    "model_config_hash": response["model_config_hash"],
                    "usage": response["usage"],
                }
                rows.append(row)
                executions += result["function_executions"]
                print(
                    json.dumps(
                        {
                            "record": record["record_id"],
                            "role": role,
                            "solved": result["solved"],
                            "malformed": result["malformed"],
                        }
                    ),
                    flush=True,
                )
    report = {
        "status": "completed_paired_validation",
        "runtime_mode": "live",
        "view": view,
        "alpha": job["alpha"],
        "training_job_identity": job["job_identity"],
        "training_session_hash": file_hash(job_path),
        "registry_path": str(registry.path),
        "registry_hash": registry.manifest_hash,
        "source_manifest_hash": json_hash(manifest),
        "seed": learning["seed"],
        "max_new_tokens": learning["max_new_tokens"],
        "rows": rows,
        "summary": paired(rows),
        "runner": runner_info,
        "function_executions_new": executions,
        "a_baseline_reused": str(Path(baseline_path).resolve()) if baseline_path else None,
        "a_baseline_hash": file_hash(baseline_path) if baseline_path else None,
        "scope": "20 variants / 10 validation bases; no final assessment, no controller.",
        "note": "Union/rescue describes available one-shot candidates, not final selection.",
    }
    write_report(directory / "report.json", report)
    print(json.dumps(report["summary"]), flush=True)
    return report
