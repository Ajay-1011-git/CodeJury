"""Measure the learned Judge's format validity inside the real validation loop.

Mirrors the General validation (same 20 validation records, seed, tools and scoring) but runs the
council controller with the selected learned Judge. Reports valid vs attempted Judge decisions so
the figure can be compared with the General adapter's 81-89% on identical states.

Usage (from backend, with the usual environment exports):
  .venv/bin/python tools/stage2_core/judge_loop_check.py \
      --registry artifacts/stage2_core/teacher/current-judge-selected-v1/registry.json \
      --config artifacts/stage2_core/teacher/current-general-config-v2.yaml \
      --out artifacts/stage2_core/teacher/judge-loop-check-v1
"""

import argparse
import json
import sys
from pathlib import Path
from threading import Event

import yaml

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND / "src"))

from codejury.models.worker import file_hash  # noqa: E402
from codejury.stage2_core.contracts import json_hash  # noqa: E402
from codejury.stage2_core.controller import records  # noqa: E402
from codejury.stage2_core.controller.inputs import runtime_input  # noqa: E402
from codejury.stage2_core.controller.learned import LearnedController  # noqa: E402
from codejury.stage2_core.data import load_stage1, write_report  # noqa: E402
from codejury.stage2_core.ledger import Ledger  # noqa: E402
from codejury.stage2_core.model_worker import NativeModelPort  # noqa: E402
from codejury.stage2_core.registry import Registry, local_path  # noqa: E402
from codejury.stage2_tools.critic_training.data import assess  # noqa: E402
from codejury.stage2_tools.factory import make_tool_port  # noqa: E402
from codejury.stage2_tools.port import ToolPortImpl  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())
    _, rows = load_stage1(local_path(cfg["source_manifest"]))
    rows = [r for r in rows if r["split"] == "validation"]
    out = args.out.resolve()
    if local_path("artifacts") not in out.parents or out.exists():
        raise ValueError("Immutable ignored output directory required")
    registry = Registry(args.registry.resolve())
    if "judge" not in registry.record["adapters"]:
        raise ValueError("A trained Judge adapter is required")
    runtime = yaml.safe_load(local_path(cfg["runtime_config"]).read_text())
    tool = make_tool_port(local_path("../integration/stage2/tools.yaml"))
    tool.sandbox.ready()
    out.mkdir(parents=True)
    identities = {r: registry.identity(r) for r in ["raw", *registry.record["adapters"]]}
    frozen, cancel = [], Event()
    with NativeModelPort(registry, runtime) as model:
        for index, row in enumerate(rows):
            ledger = Ledger(out / "runs" / row["record_id"])
            control = LearnedController(
                ledger,
                model,
                ToolPortImpl(tool.sandbox, contracts=tool.contracts),
                identities,
                manifest_hash=registry.manifest_hash,
                runtime_hash=tool.sandbox.runtime_hash,
                mode="live",
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
            judge = records(ledger, snapshot["run_id"], "judge_choice")
            commitment = {
                "record_id": row["record_id"],
                "base_problem_id": row["base_problem_id"],
                "run_id": snapshot["run_id"],
                "snapshot_hash": json_hash(snapshot),
                "status": snapshot["status"],
                "usage": snapshot["resource_usage"],
                "valid_decisions": sum(r["mode"] == "learned" for r in judge),
                "fixed_fallbacks": sum(r["mode"] == "fixed_fallback" for r in judge),
                "state_id_filled": sum(bool(r.get("state_id_filled")) for r in judge),
            }
            frozen.append((row, snapshot, selected, ledger, commitment))
            with (out / "commitments.jsonl").open("a") as stream:
                stream.write(json.dumps(commitment) + "\n")
            print(json.dumps({"committed": index + 1, "total": len(rows)}), flush=True)
    results = []
    for row, snapshot, selected, ledger, commitment in frozen:
        correct = False
        if snapshot["status"] == "supported_patch":
            labels, _ = assess(snapshot["problem"], [selected], row, tool, cancel)
            correct = labels[selected["candidate_id"]]
        if json_hash(ledger.snapshot(snapshot["run_id"])) != commitment["snapshot_hash"]:
            raise ValueError("Private scoring altered a frozen result")
        results.append({**commitment, "correct": correct})
    attempts = sum(r["usage"]["judge_decisions"] for r in results)
    valid = sum(r["valid_decisions"] for r in results)
    summary = {
        "version": "stage2.judge-loop-check.v1",
        "runtime_mode": "live",
        "split": "validation",
        "registry_hash": registry.manifest_hash,
        "judge_adapter_hash": registry.identity("judge")["adapter_hash"],
        "records": len(results),
        "base_problems": len({r["base_problem_id"] for r in results}),
        "solved": sum(r["correct"] for r in results),
        "incorrect_accepted": sum(
            r["status"] == "supported_patch" and not r["correct"] for r in results
        ),
        "unresolved": sum(r["status"] == "unresolved" for r in results),
        "valid_decisions": valid,
        "decision_attempts": attempts,
        "valid_fraction": round(valid / attempts, 4) if attempts else None,
        "fixed_fallbacks": sum(r["fixed_fallbacks"] for r in results),
        "state_id_filled": sum(r["state_id_filled"] for r in results),
        "rows_hash": file_hash(out / "commitments.jsonl"),
        "contains_final_assessment": False,
        "limitations": [
            "Twenty runs share ten validation bases; this is a format-validity probe only.",
            "Compared against General on the same records and seed, not a research claim.",
        ],
    }
    write_report(out / "report.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
