"""Select checkpoints using validation repair execution, never sealed assessment."""

import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import yaml

from ..models.views import parse_repair
from ..models.worker import BACKEND, ModelWorker, file_hash
from ..properties import equal
from ..runner import DockerRunner
from .data import DATA, digest, prompt_view, request_view


def validation_records(manifest):
    seal = json.loads(Path(manifest).read_text())
    if seal["seal_sha256"] != digest(seal["assets"]):
        raise ValueError("Manifest seal mismatch")
    asset = next(a for a in seal["assets"] if a["split"] == "validation")
    content = (DATA / asset["path"]).read_bytes()
    if hashlib.sha256(content).hexdigest() != asset["sha256"]:
        raise ValueError("Validation asset changed")
    records = [json.loads(line) for line in content.decode().splitlines()]
    chosen = {}
    for row in records:
        chosen.setdefault(row["base_problem_id"], row)
    return list(chosen.values())


def select(config):
    cfg = yaml.safe_load(Path(config).read_text())
    output = BACKEND / cfg["output"]
    session = json.loads((output / "session.json").read_text())
    if not session["reload_verified"] or session["completed_steps"] < 300:
        raise ValueError("Full train/save/reload required before checkpoint selection")
    records = validation_records(BACKEND / cfg["dataset_manifest"])
    runner = DockerRunner()
    candidates = sorted(output.glob("*_adapters.safetensors"))
    if not candidates:
        raise ValueError("No validation checkpoints were saved")
    reports = []
    validation = BACKEND / "artifacts/training/checkpoint-validation"
    validation.mkdir(parents=True, exist_ok=True)
    for file in candidates:
        step = int(file.name.split("_")[0])
        directory = validation / f"step-{step}"
        directory.mkdir(exist_ok=True)
        shutil.copy2(output / "adapter_config.json", directory / "adapter_config.json")
        shutil.copy2(file, directory / "adapters.safetensors")
        worker = ModelWorker(BACKEND / cfg["model_config"], adapter_override=directory)
        rows = []
        for record in records:
            request = request_view(record)
            generations = []
            patch = None
            for attempt in range(2):
                result = worker.generate(
                    "fixer_a", prompt_view(record), max_tokens=1024, format_retry=attempt > 0
                )
                generations.append(asdict(result))
                try:
                    patch = parse_repair(result.text, request)
                    break
                except ValueError:
                    pass
            solved = False
            executions = []
            if patch:
                for test in record["visible_tests"] + record["assessment_tests"]:
                    actual = runner.execute(patch["source"], "solve", test["args"])
                    executions.append(
                        {
                            "test_id": test["test_id"],
                            **asdict(actual),
                            "correct": not actual.exception_type
                            and not actual.input_mutated
                            and equal(actual.actual_output, test["expected"]),
                        }
                    )
                solved = all(row["correct"] for row in executions)
            rows.append(
                {
                    "base_problem_id": record["base_problem_id"],
                    "solved": solved,
                    "malformed": patch is None,
                    "generations": generations,
                    "executions": executions,
                }
            )
            print(
                json.dumps(
                    {
                        "validation_step": step,
                        "problem": record["base_problem_id"],
                        "solved": solved,
                        "malformed": patch is None,
                    }
                ),
                flush=True,
            )
        summary = {
            "step": step,
            "solved": sum(row["solved"] for row in rows),
            "total": len(rows),
            "malformed": sum(row["malformed"] for row in rows),
            "adapter_sha256": file_hash(file),
            "rows": rows,
        }
        (directory / "validation.json").write_text(json.dumps(summary, indent=2) + "\n")
        reports.append(summary)
        # Release each checkpoint before loading another.
        worker.model = worker.tokenizer = None
        del worker
    best = sorted(reports, key=lambda row: (-row["solved"], row["malformed"], row["step"]))[0]
    frozen = BACKEND / "artifacts/training/fixer_a_selected"
    if frozen.exists():
        raise ValueError("Refusing to overwrite a frozen adapter")
    frozen.mkdir()
    selected = validation / f"step-{best['step']}"
    for name in ("adapter_config.json", "adapters.safetensors"):
        shutil.copy2(selected / name, frozen / name)
    freeze = {
        "selected_step": best["step"],
        "training_steps": session["completed_steps"],
        "adapter_sha256": file_hash(frozen / "adapters.safetensors"),
        "model_id": session["model_id"],
        "model_revision": session["model_revision"],
        "data_manifest_sha256": session["data_manifest_sha256"],
        "selection": (
            "Validation executable solved count, then malformed count, then earlier checkpoint"
        ),
        "validation": [{k: v for k, v in row.items() if k != "rows"} for row in reports],
    }
    (frozen / "freeze.json").write_text(json.dumps(freeze, indent=2) + "\n")
    print(json.dumps(freeze, indent=2))
    return freeze
