"""Native held-out menu validation. End-to-end repair quality is evaluated separately."""

import copy
import json
from pathlib import Path
from threading import Event
from uuid import uuid4

import yaml
from jsonschema import ValidationError

from codejury.models.worker import file_hash

from ...budgets import CAPS
from ...candidates import parse_draft
from ...contracts import checked, json_hash
from ...data import write_report
from ...model_worker import NativeModelPort
from ...registry import Registry, local_path


def menu(prompt):
    payload = json.JSONDecoder().raw_decode(prompt.split("Runtime-visible facts:\n", 1)[1])[0]
    if payload["view_format"] != "judge-summary.v2":
        raise ValueError("Validation must use the actual bounded runtime menu")
    return payload


def valid_choice(draft, payload):
    state = payload["state"]
    ids = set(state["authoritative_counterexample_ids"]) | set(state["audit_gap_ids"])
    ids.update(e["execution_id"] for e in payload["visible_evidence"])
    if (
        draft["state_id"] != state["state_id"]
        or not set(draft["evidence_ids"]) <= ids
        or draft["action_option_id"] not in {o["option_id"] for o in state["available_actions"]}
    ):
        raise ValueError("Choice references an unoffered action, stale state or hidden evidence")


def evaluate(registry_path, cfg, out):
    corpus = local_path(cfg["corpus"])
    manifest = json.loads((corpus / "manifest.json").read_text())
    if (
        manifest["role"] != "judge"
        or manifest["runtime_mode"] != "live"
        or manifest["contains_final_assessment"]
    ):
        raise ValueError("Genuine final-free Judge corpus required")
    for name, digest in manifest["files"].items():
        if Path(name).name != name or file_hash(corpus / name) != digest:
            raise ValueError("Changed Judge corpus")
    rows = [json.loads(line) for line in (corpus / "records.jsonl").read_text().splitlines()]
    if any(r["split"] not in {"train", "validation"} for r in rows):
        raise ValueError("Final data forbidden in Judge selection")
    rows = [r for r in rows if r["split"] == "validation"]
    if not rows:
        raise ValueError("Held-out empirical action labels are required")
    out = Path(out).resolve()
    if local_path("artifacts") not in out.parents or out.exists():
        raise ValueError("Immutable ignored Judge validation output required")
    registry = Registry(Path(registry_path))
    runtime = yaml.safe_load(local_path(cfg["runtime_config"]).read_text())
    out.mkdir(parents=True)
    results, cancel = [], Event()
    with NativeModelPort(registry, runtime) as model:
        for index, row in enumerate(rows):
            payload = menu(row["prompt"])
            valid_choice(checked(row["target"], "JudgeDraft"), payload)
            req = checked(
                {
                    "schema_version": "stage2.v1",
                    "request_id": "judge-val-" + uuid4().hex,
                    "run_id": "validation",
                    "role": "judge",
                    "purpose": "action_choice",
                    "prompt": row["prompt"],
                    "seed": cfg["seed"],
                    "max_new_tokens": 192,
                    "remaining_budget": CAPS,
                },
                "ModelRequest",
            )
            response = model.generate(req, cancel)
            valid, match, error = False, False, None
            if response["status"] == "ok":
                try:
                    answer = parse_draft(response["text"], "JudgeDraft")
                    valid_choice(answer, payload)
                    valid = True
                    match = answer["action_option_id"] == row["target"]["action_option_id"]
                except (ValueError, ValidationError, RecursionError) as exc:
                    error = type(exc).__name__
            entry = {
                "record_id": row["record_id"],
                "base_problem_id": row["base_problem_id"],
                "episode_hash": row["episode_hash"],
                "prompt_hash": json_hash(row["prompt"]),
                "response": response,
                "valid_choice": valid,
                "matches_empirical_label": match,
                "error": error,
            }
            results.append(entry)
            with (out / "rows.jsonl").open("a") as stream:
                stream.write(json.dumps(entry) + "\n")
            print(json.dumps({"trial": index + 1, "total": len(rows), "valid": valid}), flush=True)
    result = {
        "version": "stage2.judge-validation.v1",
        "runtime_mode": "live",
        "split": "validation",
        "registry_hash": registry.manifest_hash,
        "adapter_hash": registry.identity("judge")["adapter_hash"],
        "data_manifest_hash": file_hash(corpus / "manifest.json"),
        "records": len(results),
        "base_problems": len({r["base_problem_id"] for r in results}),
        "unique_states": len({r["episode_hash"] for r in results}),
        "valid_choices": sum(r["valid_choice"] for r in results),
        "empirical_label_matches": sum(r["matches_empirical_label"] for r in results),
        "output_tokens": sum(r["response"]["usage"]["output_tokens"] for r in results),
        "input_tokens": sum(r["response"]["usage"]["input_tokens"] for r in results),
        "rows_hash": file_hash(out / "rows.jsonl"),
        "contains_final_assessment": False,
        "limitation": "Menu-label agreement is not end-to-end repair improvement.",
    }
    write_report(out / "report.json", result)
    return result


def select(training_report, cfg, out):
    report = json.loads(Path(training_report).read_text())
    if (
        report["role"] != "judge"
        or report["status"] != "trained_selection_pending"
        or not report["reload_verified"]
        or not report["updates_verified"]
    ):
        raise ValueError("Actual full Judge updates/reload required")
    out = Path(out).resolve()
    if local_path("artifacts") not in out.parents or out.exists():
        raise ValueError("Immutable ignored Judge selection output required")
    out.mkdir(parents=True)
    trials = []
    for candidate in report["candidates"]:
        measured = evaluate(
            candidate["registry_path"], cfg, out / ("validation-" + str(candidate["step"]))
        )
        if measured["data_manifest_hash"] != report["data_manifest_hash"]:
            raise ValueError("Training/selection corpus identity differs")
        trials.append({**candidate, "evaluation": measured})
    best = max(
        trials,
        key=lambda c: (
            c["evaluation"]["valid_choices"],
            c["evaluation"]["empirical_label_matches"],
            -c["step"],
        ),
    )
    measured = best["evaluation"]
    if measured["valid_choices"] < 0.9 * measured["records"]:
        write_report(
            out / "selection-refused.json", {"trials": trials, "reason": "<90% valid choices"}
        )
        raise ValueError("Measured Judge format/menu gate failed; no promotion")
    registry = Registry(Path(best["registry_path"]))
    record = copy.deepcopy(registry.record)
    card = record["adapters"]["judge"]["card"]
    card["status"] = "completed"
    card["evaluation_summary"] = (
        f"Actual held-out menus: {measured['valid_choices']}/{measured['records']} valid; "
        f"{measured['empirical_label_matches']} empirical-label matches. "
        "Limited genuine continuations; no final benchmark claim."
    )
    checked(card, "AdapterCard")
    write_report(out / "registry.json", record)
    Registry(out / "registry.json")
    result = {
        "status": "completed_native_judge_selection",
        "selected": best,
        "trials": trials,
        "training_report_hash": file_hash(training_report),
        "training_report_path": str(Path(training_report).resolve()),
        "registry_path": str(out / "registry.json"),
        "registry_hash": file_hash(out / "registry.json"),
        "contains_final_assessment": False,
    }
    write_report(out / "selection.json", result)
    return result
