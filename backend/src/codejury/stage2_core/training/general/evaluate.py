"""Real single-agent validation and measured comparable-opportunity selection."""

import copy
import json
from pathlib import Path
from threading import Event

import yaml

from codejury.models.worker import file_hash
from codejury.stage2_tools.critic_training.data import assess
from codejury.stage2_tools.factory import make_tool_port
from codejury.stage2_tools.port import ToolPortImpl

from ...baselines.controllers import GeneralController
from ...contracts import checked, json_hash
from ...controller import records
from ...controller.inputs import runtime_input
from ...data import load_stage1, write_report
from ...ledger import Ledger
from ...model_worker import NativeModelPort
from ...registry import Registry, local_path
from .opportunity import audit


def evaluate(registry_path, cfg, out):
    _, rows = load_stage1(local_path(cfg["source_manifest"]))
    rows = [r for r in rows if r["split"] == "validation"]
    out = Path(out).resolve()
    if local_path("artifacts") not in out.parents or out.exists():
        raise ValueError("Immutable ignored General validation output required")
    registry = Registry(Path(registry_path))
    if "general" not in registry.record["adapters"]:
        raise ValueError("Actual trained General adapter required")
    runtime = yaml.safe_load(local_path(cfg["runtime_config"]).read_text())
    tool = make_tool_port(local_path("../integration/stage2/tools.yaml"))
    tool.sandbox.ready()
    out.mkdir(parents=True)
    identities = {r: registry.identity(r) for r in ["raw", *registry.record["adapters"]]}
    frozen, results, cancel = [], [], Event()
    # All visible-input runs commit before any private validation score.
    with NativeModelPort(registry, runtime) as model:
        for index, row in enumerate(rows):
            ledger = Ledger(out / "runs" / row["record_id"])
            control = GeneralController(
                ledger,
                model,
                ToolPortImpl(tool.sandbox, contracts=tool.contracts),
                identities,
                manifest_hash=registry.manifest_hash,
                runtime_hash=tool.sandbox.runtime_hash,
                mode="live",
                model_roles={"fixer_a": "general", "fixer_b": "general"},
                critic_role="general",
            )
            problem, tests = runtime_input(row)
            snapshot = control.run(problem, tests, cancel=cancel, seed=cfg["seed"])
            selected = next(
                (
                    c
                    for c in snapshot["candidates"]
                    if c["candidate_id"] == snapshot["decision"]["selected_candidate_id"]
                ),
                None,
            )
            commitment = {
                "record_id": row["record_id"],
                "base_problem_id": row["base_problem_id"],
                "run_id": snapshot["run_id"],
                "ledger": str(ledger.directory),
                "snapshot_hash": json_hash(snapshot),
                "status": snapshot["status"],
                "selected_source_hash": selected["source_hash"] if selected else None,
                "usage": snapshot["resource_usage"],
                "valid_decisions": sum(
                    r["mode"] == "learned"
                    for r in records(ledger, snapshot["run_id"], "judge_choice")
                ),
                "fixed_fallbacks": sum(
                    r["mode"] == "fixed_fallback"
                    for r in records(ledger, snapshot["run_id"], "judge_choice")
                ),
                "state_id_filled": sum(
                    bool(r.get("state_id_filled"))
                    for r in records(ledger, snapshot["run_id"], "judge_choice")
                ),
            }
            frozen.append((row, snapshot, selected, ledger, commitment))
            with (out / "commitments.jsonl").open("a") as stream:
                stream.write(json.dumps(commitment) + "\n")
            print(
                json.dumps(
                    {"committed": index + 1, "total": len(rows), "status": snapshot["status"]}
                ),
                flush=True,
            )
    for row, snapshot, selected, ledger, commitment in frozen:
        correct, proof = False, None
        if snapshot["status"] == "supported_patch":
            labels, proof = assess(snapshot["problem"], [selected], row, tool, cancel)
            correct = labels[selected["candidate_id"]]
        if json_hash(ledger.snapshot(snapshot["run_id"])) != commitment["snapshot_hash"]:
            raise ValueError("Private General validation altered a frozen result")
        result = {**commitment, "correct": correct, "private_assessment": proof}
        results.append(result)
        with (out / "rows.jsonl").open("a") as stream:
            stream.write(json.dumps(result) + "\n")
    summary = {
        "version": "stage2.general-validation.v1",
        "runtime_mode": "live",
        "split": "validation",
        "registry_hash": registry.manifest_hash,
        "adapter_hash": registry.identity("general")["adapter_hash"],
        "records": len(results),
        "base_problems": len({r["base_problem_id"] for r in results}),
        "solved": sum(r["correct"] for r in results),
        "incorrect_accepted": sum(
            r["status"] == "supported_patch" and not r["correct"] for r in results
        ),
        "unresolved": sum(r["status"] == "unresolved" for r in results),
        "valid_decisions": sum(r["valid_decisions"] for r in results),
        "decision_attempts": sum(r["usage"]["judge_decisions"] for r in results),
        "fixed_fallbacks": sum(r["fixed_fallbacks"] for r in results),
        "state_id_filled": sum(r.get("state_id_filled", 0) for r in results),
        "output_tokens": sum(r["usage"]["output_tokens"] for r in results),
        "input_tokens": sum(r["usage"]["input_tokens"] for r in results),
        "function_executions": sum(r["usage"]["function_executions"] for r in results),
        "rows_hash": file_hash(out / "rows.jsonl"),
        "contains_final_assessment": False,
        "limitations": [
            "Synthetic variants are clustered into ten validation bases.",
            "Explicit fixed fallbacks remain in the outcome and cost.",
        ],
    }
    write_report(out / "report.json", summary)
    return summary


def select(training_report, cfg, out):
    report = json.loads(Path(training_report).read_text())
    if (
        report["role"] != "general"
        or report["status"] != "trained_selection_pending"
        or not report["updates_verified"]
        or not report["reload_verified"]
    ):
        raise ValueError("Real full General training and reload required")
    out = Path(out).resolve()
    if local_path("artifacts") not in out.parents or out.exists():
        raise ValueError("Immutable ignored General selection output required")
    out.mkdir(parents=True)
    trials, excluded = [], []
    for candidate in report["candidates"]:
        opportunity = audit(
            candidate["registry_path"],
            training_report,
            local_path(cfg["judge_selection"]),
            out / ("opportunity-" + str(candidate["step"]) + ".json"),
            relative_tolerance=cfg["opportunity_relative_tolerance"],
            general_step=candidate["step"],
            teacher_training=cfg.get("teacher_training"),
        )
        if not opportunity["comparable"]:
            excluded.append(
                {
                    **candidate,
                    "reason": "completion exposure outside frozen tolerance",
                    "opportunity": opportunity,
                }
            )
            continue
        measured = evaluate(
            candidate["registry_path"],
            {**cfg, "seed": cfg["seed"]},
            out / ("validation-" + str(candidate["step"])),
        )
        trials.append({**candidate, "evaluation": measured, "opportunity": opportunity})
    if not trials:
        write_report(
            out / "selection-refused.json",
            {"excluded": excluded, "reason": "no comparable actual exposure"},
        )
        raise ValueError("No comparably trained General checkpoint; research remains incomplete")
    best = max(
        trials,
        key=lambda c: (
            -c["evaluation"]["incorrect_accepted"],
            c["evaluation"]["solved"],
            c["evaluation"]["valid_decisions"],
            -c["evaluation"]["output_tokens"],
            -c["step"],
        ),
    )
    measured = best["evaluation"]
    if (
        not measured["decision_attempts"]
        or measured["valid_decisions"] < 0.9 * measured["decision_attempts"]
    ):
        write_report(
            out / "selection-refused.json",
            {"trials": trials, "excluded": excluded, "reason": "<90% valid menu choices"},
        )
        raise ValueError("General native action validity gate failed; no completed promotion")
    registry = Registry(Path(best["registry_path"]))
    record = copy.deepcopy(registry.record)
    card = record["adapters"]["general"]["card"]
    card["status"] = "completed"
    card["evaluation_summary"] = (
        f"Real validation: {measured['solved']}/{measured['records']} solved; "
        f"{measured['incorrect_accepted']} incorrect accepted; "
        f"{measured['valid_decisions']}/{measured['decision_attempts']} valid choices. "
        "Comparable measured completion exposure; no final claim."
    )
    checked(card, "AdapterCard")
    write_report(out / "registry.json", record)
    Registry(out / "registry.json")
    final_audit = audit(
        out / "registry.json",
        training_report,
        local_path(cfg["judge_selection"]),
        out / "opportunity.json",
        relative_tolerance=cfg["opportunity_relative_tolerance"],
        general_step=best["step"],
        teacher_training=cfg.get("teacher_training"),
    )
    result = {
        "status": "completed_native_general_selection",
        "selected": best,
        "trials": trials,
        "excluded": excluded,
        "opportunity": final_audit,
        "training_report_hash": file_hash(training_report),
        "training_report_path": str(Path(training_report).resolve()),
        "registry_path": str(out / "registry.json"),
        "contains_final_assessment": False,
    }
    write_report(out / "selection.json", result)
    return result
