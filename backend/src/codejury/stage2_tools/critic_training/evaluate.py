"""Real role validation and immutable checkpoint promotion, with private labels."""

import copy
import json
from pathlib import Path
from threading import Event
from uuid import uuid4

from jsonschema import ValidationError

from codejury.models.worker import file_hash
from codejury.stage2_core.budgets import CAPS
from codejury.stage2_core.candidates import parse_draft
from codejury.stage2_core.contracts import CheckedToolPort, checked, json_hash
from codejury.stage2_core.data import write_report
from codejury.stage2_core.model_worker import NativeModelPort
from codejury.stage2_core.registry import Registry, local_path

from ..factory import make_tool_port
from .data import authorized_failure, investigation, validate


def scope(target, row):
    checked(target, "CriticDraft")
    if (
        target["mode"] != row["mode"]
        or not target["target_candidate_ids"]
        or not set(target["target_candidate_ids"]) <= set(row["target"]["target_candidate_ids"])
        or not set(target["requirement_ids"]) <= set(row["target"]["requirement_ids"])
        or (target["generator_spec"] is None) == (target["concrete_inputs"] is None)
    ):
        raise ValueError("Critic draft source/mode/scope mismatch")
    return target


def evaluate(registry_path, cfg, out, *, role="critic"):
    out = Path(out).resolve()
    if local_path("artifacts") not in out.parents or out.exists():
        raise ValueError("Immutable private validation output required")
    corpus = local_path(cfg["corpus"])
    audit = validate(corpus)
    rows = [
        json.loads(line)
        for line in (corpus / "records.jsonl").read_text().splitlines()
        if json.loads(line)["split"] == "validation"
    ]
    registry = Registry(Path(registry_path))
    if role not in {"critic", "raw"}:
        raise ValueError("Unknown Critic validation role")
    import yaml

    runtime = yaml.safe_load(local_path(cfg["runtime_config"]).read_text())
    tool = make_tool_port(local_path(cfg["tool_config"]))
    tool.sandbox.ready()
    out.mkdir(parents=True)
    cancel, results = Event(), []
    with NativeModelPort(registry, runtime) as model:
        for index, row in enumerate(rows):
            identifier = "critic-validation-" + uuid4().hex
            req = checked(
                {
                    "schema_version": "stage2.v1",
                    "request_id": identifier,
                    "run_id": identifier,
                    "role": role,
                    "purpose": "test_proposal" if role == "critic" else "baseline",
                    "prompt": row["prompt"],
                    "seed": cfg["seed"],
                    "max_new_tokens": 512,
                    "remaining_budget": CAPS,
                },
                "ModelRequest",
            )
            response = model.generate(req, cancel)
            valid, result, error = False, None, None
            if response["status"] == "ok":
                try:
                    target = scope(parse_draft(response["text"], "CriticDraft"), row)
                    episode = row["episode"]
                    candidates = [
                        c
                        for c in episode["candidates"]
                        if c["candidate_id"] in target["target_candidate_ids"]
                    ]
                    call = investigation(episode["problem"], episode["tests"], candidates, target)
                    result = CheckedToolPort(tool).call(call, cancel)
                    valid = (
                        result["status"] == "ok"
                        and bool(result["executions"])
                        and all(t["domain_valid"] for t in result["tests"])
                    )
                except (ValueError, ValidationError, RecursionError) as exc:
                    error = type(exc).__name__
            entry = {
                "record_id": row["record_id"],
                "base_problem_id": row["base_problem_id"],
                "mode": row["mode"],
                "correct_case": row["correct_case"],
                "invalid_context": row["invalid_context"],
                "prompt_hash": json_hash(row["prompt"]),
                "response": response,
                "tool_result": result,
                "format_domain_valid": valid,
                "authorized_failure": authorized_failure(result) if valid else False,
                "false_hard_rejection": row["correct_case"]
                and valid
                and authorized_failure(result),
                "error": error,
            }
            results.append(entry)
            with (out / "rows.jsonl").open("a") as stream:
                stream.write(json.dumps(entry) + "\n")
            print(json.dumps({"trial": index + 1, "total": len(rows), "valid": valid}), flush=True)
    summary = {
        "version": "stage2.critic-evaluation.v1",
        "role": role,
        "runtime_mode": "live",
        "registry_hash": registry.manifest_hash,
        "adapter_hash": registry.identity(role)["adapter_hash"],
        "data_manifest_hash": audit["manifest_hash"],
        "split": "validation",
        "records": len(results),
        "base_problems": len({r["base_problem_id"] for r in results}),
        "format_domain_valid": sum(r["format_domain_valid"] for r in results),
        "authorized_failure_yield": sum(r["authorized_failure"] for r in results),
        "correct_cases": sum(r["correct_case"] for r in results),
        "false_hard_rejections": sum(r["false_hard_rejection"] for r in results),
        "output_tokens": sum(r["response"]["usage"]["output_tokens"] for r in results),
        "input_tokens": sum(r["response"]["usage"]["input_tokens"] for r in results),
        "function_executions": sum(
            r["tool_result"]["usage"]["function_executions"]
            for r in results
            if r["tool_result"] is not None
        ),
        "rows_hash": file_hash(out / "rows.jsonl"),
        "contains_final_assessment": False,
    }
    write_report(out / "report.json", summary)
    return summary


def select(training_report, cfg, out):
    report = json.loads(Path(training_report).read_text())
    if (
        report["role"] != "critic"
        or report["status"] != "trained_selection_pending"
        or not report["reload_verified"]
        or not report["updates_verified"]
    ):
        raise ValueError("Actual full Critic training/reload required")
    directory = Path(out).resolve()
    if local_path("artifacts") not in directory.parents:
        raise ValueError("Private validation/adapter output required")
    directory.mkdir(parents=True, exist_ok=False)
    trials = []
    for candidate in report["candidates"]:
        measured = evaluate(
            candidate["registry_path"], cfg, directory / ("validation-" + str(candidate["step"]))
        )
        if measured["data_manifest_hash"] != report["data_manifest_hash"]:
            raise ValueError("Training/evaluation corpus identities differ")
        trials.append({**candidate, "evaluation": measured})
    best = max(
        trials,
        key=lambda c: (
            -c["evaluation"]["false_hard_rejections"],
            c["evaluation"]["format_domain_valid"],
            c["evaluation"]["authorized_failure_yield"],
            -c["evaluation"]["function_executions"],
            -c["step"],
        ),
    )
    measured = best["evaluation"]
    if (
        measured["records"] == 0
        or measured["format_domain_valid"] < 0.9 * measured["records"]
        or measured["false_hard_rejections"]
    ):
        write_report(
            directory / "selection-refused.json",
            {"trials": trials, "reason": "<90% format/domain validity or false hard rejection"},
        )
        raise ValueError("Measured Critic quality gate failed; no completed promotion")
    registry = Registry(Path(best["registry_path"]))
    record = copy.deepcopy(registry.record)
    card = record["adapters"]["critic"]["card"]
    card["status"] = "completed"
    card["evaluation_summary"] = (
        f"Real native validation: {measured['format_domain_valid']}/{measured['records']} "
        f"format/domain valid; {measured['false_hard_rejections']} false hard rejections; "
        f"{measured['authorized_failure_yield']} authorized failures. "
        "Limited synthetic learning corpus; no final benchmark claim."
    )
    checked(card, "AdapterCard")
    write_report(directory / "registry.json", record)
    Registry(directory / "registry.json")
    result = {
        "status": "completed_native_critic_selection",
        "selected": best,
        "trials": trials,
        "registry_path": str(directory / "registry.json"),
        "registry_hash": file_hash(directory / "registry.json"),
        "training_report_hash": file_hash(training_report),
        "contains_final_assessment": False,
    }
    write_report(directory / "selection.json", result)
    return result
