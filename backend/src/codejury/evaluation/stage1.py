"""Freeze visible-only final answers before independent sealed assessment execution."""

import copy
import importlib.metadata
import json
import subprocess
import threading
import time
from dataclasses import asdict
from pathlib import Path

from ..api.repository import Repository
from ..contracts import validate
from ..controller.loop import run
from ..models.views import parse_repair, repair_view
from ..models.worker import BACKEND, ModelWorker, file_hash
from ..properties import equal
from ..runner import DockerRunner
from ..storage import Store
from ..training.data import digest, load_records, request_view

METHODS = ("raw_single", "trained_a_single", "stage1_loop")


def correct(result, test):
    return (
        result.exception_type is None
        and not result.input_mutated
        and equal(result.actual_output, test["expected"])
    )


def single(request, model, runner):
    start = time.monotonic()
    baseline = []
    executions = []
    for test in request["supplied_tests"]:
        result = runner.execute(request["source"], request["function_name"], test["args"])
        executions.append({"test_id": test["test_id"], "phase": "baseline", **asdict(result)})
        if not correct(result, test):
            baseline.append(
                {"test_id": test["test_id"], "args": test["args"], "result": asdict(result)}
            )
    generated = model.generate(
        "fixer_a", repair_view(request, baseline), max_tokens=1024, deadline=start + 600
    )
    patch = None
    error = None
    try:
        patch = parse_repair(generated.text, request)
    except ValueError as exc:
        error = str(exc)
    accepted = False
    if patch:
        rows = []
        for test in request["supplied_tests"]:
            result = runner.execute(patch["source"], request["function_name"], test["args"])
            executions.append({"test_id": test["test_id"], "phase": "candidate", **asdict(result)})
            rows.append(correct(result, test))
        accepted = all(rows)
    return {
        "accepted": accepted,
        "source": patch["source"] if patch else None,
        "malformed": patch is None,
        "format_error": error,
        "generations": [asdict(generated)],
        "visible_executions": executions,
        "usage": {
            "input_tokens": generated.input_tokens,
            "output_tokens": generated.output_tokens,
            "function_executions": len(executions),
            "elapsed_ms": int((time.monotonic() - start) * 1000),
            "peak_memory_mb": generated.peak_memory_mb,
        },
    }


def loop_answer(request, model, runner, directory):
    store = Store(directory)
    snapshot = Repository(store).claim(request, "live")
    result = run(request, store, snapshot["run_id"], threading.Event(), model=model, runner=runner)
    selected = result["decision"]["selected_candidate_id"]
    candidate = next((c for c in result["candidates"] if c["candidate_id"] == selected), None)
    return {
        "accepted": result["status"] == "supported_patch",
        "source": candidate["source"] if candidate else None,
        "malformed": False,
        "usage": result["usage"],
        "snapshot": result,
        "episode_file": str(store.directory / (snapshot["run_id"] + "-episode.json")),
    }


def freeze_then_assess(answer, request, tests, runner, path):
    # No model/controller call is possible after this immutable final-answer boundary.
    with Path(path).open("x") as file:
        file.write(json.dumps(answer, indent=2) + "\n")
    frozen_sha256 = file_hash(path)
    assessed = []
    if answer["accepted"]:
        for test in tests:
            result = runner.execute(answer["source"], request["function_name"], test["args"])
            assessed.append(
                {"test_id": test["test_id"], "correct": correct(result, test), **asdict(result)}
            )
    solved = answer["accepted"] and bool(assessed) and all(row["correct"] for row in assessed)
    return {
        "accepted": answer["accepted"],
        "solved": bool(solved),
        "incorrect_accepted": answer["accepted"] and not solved,
        "unresolved": not answer["accepted"],
        "final_answer_sha256": frozen_sha256,
        "assessment_executions": assessed,
        "usage": answer["usage"],
        "malformed": answer["malformed"],
    }


def aggregate(method, rows):
    count = len(rows)
    return {
        "method": method,
        "total": count,
        "solved": sum(row["solved"] for row in rows),
        "unresolved": sum(row["unresolved"] for row in rows),
        "incorrect_accepted": sum(row["incorrect_accepted"] for row in rows),
        "mean_elapsed_ms": round(sum(row["usage"]["elapsed_ms"] for row in rows) / count)
        if count
        else None,
        "mean_output_tokens": round(sum(row["usage"]["output_tokens"] for row in rows) / count)
        if count
        else None,
    }


def stage1(manifest, config, out):
    out = Path(out)
    if out.exists():
        raise ValueError("Refusing to overwrite measured evaluation")
    seal, records = load_records(manifest)
    counts = {a["split"]: {k: a[k] for k in ("base_problems", "records")} for a in seal["assets"]}
    chosen = {}
    for record in records:
        if record["split"] == "assessment":
            chosen.setdefault(record["base_problem_id"], record)
    if len(chosen) != counts["assessment"]["base_problems"]:
        raise ValueError("Assessment base count mismatch")
    work = out.parent / (out.stem + "-evidence")
    work.mkdir(parents=True, exist_ok=False)
    runner = DockerRunner()
    runner.ready()
    worker = ModelWorker(config)
    freeze = json.loads((worker.adapter / "freeze.json").read_text())
    if worker.identity["adapter_sha256"] != freeze["adapter_sha256"]:
        raise ValueError("Selected adapter changed before evaluation")
    all_rows = []
    summaries = []
    identity = copy.deepcopy(worker.identity)
    worker.model = worker.tokenizer = None
    del worker
    for method in METHODS:
        model = ModelWorker(config, force_raw=method == "raw_single")
        rows = []
        for record in chosen.values():
            request = request_view(record)
            directory = work / method / record["base_problem_id"]
            directory.mkdir(parents=True)
            start = time.monotonic()
            answer = (
                loop_answer(request, model, runner, directory / "visible-runtime")
                if method == "stage1_loop"
                else single(request, model, runner)
            )
            row = freeze_then_assess(
                answer, request, record["assessment_tests"], runner, directory / "final-answer.json"
            )
            row.update(
                method=method,
                base_problem_id=record["base_problem_id"],
                visible_input_sha256=digest(request),
                total_elapsed_ms=int((time.monotonic() - start) * 1000),
            )
            rows.append(row)
            (directory / "assessment.json").write_text(json.dumps(row, indent=2) + "\n")
            print(
                json.dumps(
                    {
                        "method": method,
                        "base_problem_id": record["base_problem_id"],
                        "solved": row["solved"],
                        "accepted": row["accepted"],
                        "tokens": row["usage"]["output_tokens"],
                    }
                ),
                flush=True,
            )
        summaries.append(aggregate(method, rows))
        all_rows.extend(rows)
        model.model = model.tokenizer = None
        del model
    results = {
        "runtime_mode": "live",
        "evaluation": summaries,
        "rows": all_rows,
        "identity": identity,
        "freeze": freeze,
        "counts": counts,
        "reproducibility": {
            "dataset_manifest_sha256": file_hash(manifest),
            "split_seal_sha256": seal["seal_sha256"],
            "assessment_assets": [
                {"sha256": a["sha256"]} for a in seal["assets"] if a["split"] == "assessment"
            ],
            "config_sha256": file_hash(config),
            "profile_sha256": file_hash(BACKEND / "config/stage1-demo.yaml"),
            "uv_lock_sha256": file_hash(BACKEND / "uv.lock"),
            "model_weight_sha256": file_hash(model_path(config) / "model.safetensors"),
            "tokenizer_sha256": file_hash(model_path(config) / "tokenizer.json"),
            "commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip(),
            "versions": {
                p: importlib.metadata.version(p)
                for p in ["mlx", "mlx-lm", "hypothesis", "jsonschema"]
            },
            "seed": 17,
            "assessment_variant_selection": "first sealed variant per base, predeclared",
            "single_budget": "one generation <=1024 tokens, no format retry",
            "loop_budget": (
                "<=4096 tokens, Critic, optional format retry, one revision, "
                "<=400 executions, <=600 seconds"
            ),
        },
        "note": (
            "Synthetic internal assessment; runtime receives no private tests "
            "or reference sources. "
            "Loop has a greater tool/token budget; no fair superiority claim. "
            "Stage 2 requires matched-budget baselines."
        ),
    }
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(summaries, indent=2))
    return results


def model_path(config):
    from ..models.worker import settings

    return settings(config)["model_dir"]


def export_report(results_path, out):
    config = BACKEND / "config/training/fixer_a.yaml"
    import yaml

    cfg = yaml.safe_load(config.read_text())
    session = json.loads((BACKEND / cfg["output"] / "session.json").read_text())
    if results_path is None:
        # Offline metadata only; no private data is read to build the pending-evaluation report.
        manifest = BACKEND / cfg["dataset_manifest"]
        seal = json.loads(manifest.read_text())
        frozen = BACKEND / "artifacts/training/fixer_a_selected"
        freeze = json.loads((frozen / "freeze.json").read_text())
        if file_hash(frozen / "adapters.safetensors") != freeze["adapter_sha256"]:
            raise ValueError("Frozen adapter changed")
        results = {
            "runtime_mode": "live",
            "identity": freeze,
            "freeze": freeze,
            "counts": {a["split"]: a for a in seal["assets"]},
            "reproducibility": {"dataset_manifest_sha256": file_hash(manifest)},
            "evaluation": [],
            "note": "Real adapter training completed; measured evaluation pending.",
        }
    else:
        results = json.loads(Path(results_path).read_text())
    if results["runtime_mode"] != "live":
        raise ValueError("Fixture evaluation cannot produce a live training report")
    if not session["reload_verified"] or session["completed_steps"] < 1:
        raise ValueError("Actual adapter training required")
    if session["data_manifest_sha256"] != results["reproducibility"]["dataset_manifest_sha256"]:
        raise ValueError("Evaluation/training data mismatch")
    if results["freeze"]["adapter_sha256"] != results["identity"]["adapter_sha256"]:
        raise ValueError("Evaluation adapter mismatch")
    losses = {}
    for line in Path(session["loss_path"]).read_text().splitlines():
        point = json.loads(line)
        step = point["iteration"]
        value = losses.setdefault(step, {"step": step, "train_loss": None, "validation_loss": None})
        if point["kind"] == "train":
            value["train_loss"] = point["train_loss"]
        else:
            value["validation_loss"] = point["val_loss"]
    report = {
        "schema_version": "stage1.v1",
        "runtime_mode": "live",
        "status": "completed" if results_path is not None else "pilot_only",
        "model_id": results["identity"]["model_id"],
        "model_revision": results["identity"]["model_revision"],
        "adapter_sha256": results["identity"]["adapter_sha256"],
        "train_base_problems": results["counts"]["train"]["base_problems"],
        "validation_base_problems": results["counts"]["validation"]["base_problems"],
        "evaluation_base_problems": (
            results["counts"]["assessment"]["base_problems"] if results_path is not None else 0
        ),
        "train_records": results["counts"]["train"]["records"],
        "steps": session["completed_steps"],
        "loss_points": sorted(losses.values(), key=lambda x: x["step"]),
        "evaluation": results["evaluation"],
        "provenance_note": results["note"],
    }
    validate(report, "TrainingReport")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(out)
    print(json.dumps(report, indent=2))
    return report
