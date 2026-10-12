"""Separate B native jobs, using measured train failures and independent views."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from codejury.models.worker import file_hash

from ...contracts import canonical_json, checked, json_hash
from ...data import config as a_config
from ...data import export_pools, final_pool_metadata, learning_example, load_stage1, write_report
from ...registry import MODEL_SYSTEM, local_path
from ..fixer_a.refresh import checkpoint_registry, reload_check, verify_pilot
from . import ALPHAS, failure_fractions, sampling_plan
from .mining import selected_a, settings


def measurement(path, cfg, registry, manifest, records):
    """Rejoin measured outcomes to frozen train views/answers before sampling."""
    path = Path(path).resolve()
    report = json.loads(path.read_text())
    frozen = report["frozen"]
    rows = {
        r["base_problem_id"]: r
        for r in sorted(records, key=lambda r: r["record_id"], reverse=True)
        if r["split"] == "train"
    }
    samples = [
        json.loads(line) for line in (path.parent / "samples.jsonl").read_text().splitlines()
    ]
    if (
        report["status"] != "completed_native_mining"
        or frozen["runtime_mode"] != "live"
        or frozen["split"] != "train"
        or frozen["registry_hash"] != registry.manifest_hash
        or frozen["source_manifest_hash"] != json_hash(manifest)
        or frozen["selection_hash"] != file_hash(local_path(cfg["selected_a_manifest"]))
        or report["samples_hash"] != json_hash(samples)
        or report["base_problems"] != len(rows)
        or report["samples"] != len(rows) * 3
    ):
        raise ValueError("B needs complete genuine mining from its frozen selected A/train corpus")
    for sample in samples:
        base = sample["base_problem_id"]
        if base not in rows:
            raise ValueError("Non-training base in failure measurements")
        row = rows[base]
        trial = path.parent / (row["record_id"] + "-" + str(sample["seed"]))
        generation = json.loads((trial / "generation.json").read_text())
        answer = json.loads((trial / "answer.json").read_text())
        assessed = json.loads((trial / "assessment.json").read_text())
        prompt = learning_example(row)["a_prompt"]
        if (
            generation["response"] != sample["response"]
            or generation["request"]["prompt"] != prompt
            or generation["request"]["seed"] != sample["seed"]
            or generation["prompt_hash"] != json_hash(prompt)
            or sample["answer_hash"] != json_hash(answer)
            or assessed["answer_hash"] != sample["answer_hash"]
            or assessed["solved"] != sample["solved"]
        ):
            raise ValueError("Mining evidence no longer joins to its frozen generation/answer")
    measured = failure_fractions(
        samples,
        **{k: registry.identity("fixer_a")[k] for k in ("adapter_hash", "model_config_hash")},
    )
    if measured != report["measured"] or measured["retry_base_ids"]:
        raise ValueError("Invalid/unreplayed failure fractions")
    return measured


def chats(plan, *, view):
    return [
        {
            "messages": [
                {"role": "system", "content": MODEL_SYSTEM},
                {"role": "user", "content": p["prompt"]},
                {"role": "assistant", "content": canonical_json(p["target"]).decode()},
            ]
        }
        for p in plan
    ]


def train(
    config_path, mining_report, out, *, alpha=2, view="independent", phase="pilot", pilot_proof=None
):
    cfg = settings(config_path)
    if (
        not cfg["training_enabled"]
        or alpha not in ALPHAS
        or view not in {"independent", "same_as_a"}
    ):
        raise ValueError("Unknown/disabled B experiment")
    learning_path = local_path(cfg["a_config"])
    learning = a_config(learning_path)
    seal = final_pool_metadata(learning_path)
    manifest, records = load_stage1(local_path(learning["source_manifest"]))
    registry = selected_a(cfg)
    measured = measurement(mining_report, cfg, registry, manifest, records)
    train_rows = [r for r in records if r["split"] == "train"]
    planned = sampling_plan(
        train_rows,
        measured,
        alpha=alpha,
        broad_fraction=cfg["broad_fraction"],
        size=cfg["sample_count"],
        seed=cfg["refresh"]["seed"],
    )
    by_id = {r["record_id"]: r for r in records}
    plan = []
    for sample in planned["plan"]:
        target = dict(sample["target"])
        # B cannot diagnose a hidden corruption; its target rationale uses visible facts only.
        target["diagnosis"] = "Reconstruct the approved contract while preserving the interface."
        target = checked(target, "RepairDraft")
        prompt = (
            sample["b_prompt"]
            if view == "independent"
            else learning_example(by_id[sample["record_id"]])["a_prompt"]
        )
        plan.append({**sample, "target": target, "prompt": prompt, "view": view})
    valid_plan = []
    for row in records:
        if row["split"] == "validation":
            example = learning_example(row)
            target = {
                **example["target"],
                "diagnosis": "Reconstruct the approved contract while preserving the interface.",
            }
            valid_plan.append(
                {
                    "record_id": row["record_id"],
                    "base_problem_id": row["base_problem_id"],
                    "prompt": example["b_prompt"] if view == "independent" else example["a_prompt"],
                    "target": checked(target, "RepairDraft"),
                }
            )
    recipe = cfg["refresh"]
    identity = json_hash(
        {
            "version": "stage2.b-train.v1",
            "recipe": recipe,
            "selected_a": registry.manifest_hash,
            "measurement": measured,
            "train_plan_hash": json_hash(plan),
            "valid_plan_hash": json_hash(valid_plan),
            "alpha": alpha,
            "view": view,
            "final_seal": seal["manifest_hash"],
            "initialization": "fresh_seeded_lora_on_raw_base",
            "reference_proof": file_hash(local_path(recipe["reference_proof"])),
        }
    )
    if phase not in {"pilot", "full"}:
        raise ValueError("Unknown B training phase")
    if phase == "full":
        if pilot_proof is None:
            raise ValueError("B full training needs a matching --pilot-proof")
        verify_pilot(pilot_proof, identity, recipe["pilot_steps"], role="fixer_b")
    directory = Path(out).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    export_pools(
        learning_path,
        directory / "verified-pools",
        local_path(recipe["reference_proof"]),
        base_revision_hash=registry.base["base_revision_hash"],
    )
    write_report(
        directory / "sampling.json",
        {
            **planned,
            "view": view,
            "actual_unique_records": len({r["record_id"] for r in plan}),
            "actual_base_problems": len({r["base_problem_id"] for r in plan}),
        },
    )
    data = directory / "sft"
    data.mkdir()
    for name, values in (
        ("train.jsonl", chats(plan, view=view)),
        ("valid.jsonl", chats(valid_plan, view=view)),
    ):
        (data / name).write_bytes(b"".join(canonical_json(row) + b"\n" for row in values))
    write_report(directory / "plan.json", {"train": plan, "validation": valid_plan})
    pool_manifest = checked(
        {
            "schema_version": "stage2.v1",
            "exchange_id": f"b-{view}-alpha{alpha}",
            "owner": "ajay",
            "kind": "training_corpus",
            "base_revision_hash": registry.base["base_revision_hash"],
            "split": "train",
            "record_count": len(plan),
            "base_problem_count": len({r["base_problem_id"] for r in plan}),
            "contains_hidden_assessment": False,
            "files": [
                {
                    "relative_path": name,
                    "sha256": file_hash(data / name),
                    "size_bytes": (data / name).stat().st_size,
                }
                for name in ("train.jsonl",)
            ],
            "note": "Weighted repeated training records; unique counts recorded separately. "
            "No final contents. Same-view control is not independent B.",
        },
        "ArtifactManifest",
    )
    write_report(directory / "train-manifest.json", pool_manifest)
    valid_manifest = checked(
        {
            **pool_manifest,
            "exchange_id": f"b-{view}-validation",
            "split": "validation",
            "record_count": len(valid_plan),
            "base_problem_count": len({r["base_problem_id"] for r in valid_plan}),
            "files": [
                {
                    "relative_path": "valid.jsonl",
                    "sha256": file_hash(data / "valid.jsonl"),
                    "size_bytes": (data / "valid.jsonl").stat().st_size,
                }
            ],
        },
        "ArtifactManifest",
    )
    write_report(directory / "validation-manifest.json", valid_manifest)
    steps = recipe["pilot_steps"] if phase == "pilot" else recipe["steps"]
    session = {
        "version": "stage2.b-train.v1",
        "role": "fixer_b",
        "phase": phase,
        "alpha": alpha,
        "view": view,
        "job_identity": identity,
        "registry_path": str(registry.path),
        "registry_hash": registry.manifest_hash,
        "initial_adapter_hash": None,
        "recipe": recipe,
        "steps": steps,
        "data_directory": str(data),
        "data_hashes": {n: file_hash(data / n) for n in ("train.jsonl", "valid.jsonl")},
        "data_manifest_hash": json_hash([pool_manifest, valid_manifest]),
        "native_output": str(directory / "native"),
        "train_records": len(plan),
        "train_base_problems": pool_manifest["base_problem_count"],
        "validation_records": len(valid_plan),
        "final_pool": seal,
        "pilot_proof_hash": file_hash(pilot_proof) if pilot_proof else None,
        "mining_report_hash": file_hash(mining_report),
        "config_file_hash": file_hash(config_path),
    }
    session_path = directory / "session.json"
    command = [
        sys.executable,
        "-m",
        "codejury.stage2_core.training.fixer_a.native",
        str(session_path),
    ]
    session["actual_command"] = command
    write_report(session_path, session)
    started = time.monotonic()
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    with (directory / "native.log").open("x") as log:
        child = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env
        )
        try:
            for line in child.stdout:
                log.write(line)
                log.flush()
                print(line, end="", flush=True)
            code = child.wait()
        except BaseException:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            raise
    if code:
        write_report(directory / "failed.json", {"exit_code": code, "promotion": False})
        raise RuntimeError("Native B training failed; retain logs, no automatic replay")
    native = json.loads((directory / "native-result.json").read_text())
    if native["completed_steps"] != steps or not native["updates_verified"]:
        raise RuntimeError("B did not verify the intended real updates")
    metrics = [json.loads(line) for line in (directory / "loss.jsonl").read_text().splitlines()]
    candidates = []
    for step in (
        [steps]
        if phase == "pilot"
        else range(recipe["save_every"], steps + 1, recipe["save_every"])
    ):
        registered = checkpoint_registry(
            directory / f"checkpoint-{step}",
            directory / "native" / f"{step:07d}_adapters.safetensors",
            step,
            session,
            registry,
            metrics,
        )
        candidates.append({"step": step, "registry_path": str(registered)})
    registered = Path(candidates[-1]["registry_path"])
    reload = reload_check(
        registered,
        local_path(learning["runtime_config"]),
        plan[0]["prompt"],
        recipe["seed"],
        native["parameter_hash"],
        role="fixer_b",
    )
    write_report(directory / "reload.json", reload)
    result = {
        "status": "pilot_verified" if phase == "pilot" else "trained_selection_pending",
        "phase": phase,
        "role": "fixer_b",
        "alpha": alpha,
        "view": view,
        "job_identity": identity,
        "completed_steps": steps,
        "training_started": True,
        "updates_verified": True,
        "reload_verified": True,
        "adapter_hash": reload["response"]["adapter_hash"],
        "registry_path": str(registered),
        "candidates": candidates,
        "data_manifest_hash": session["data_manifest_hash"],
        "train_records": len(plan),
        "train_base_problems": session["train_base_problems"],
        "unique_train_records": len({r["record_id"] for r in plan}),
        "validation_records": len(valid_plan),
        "peak_memory_mb": native["peak_memory_mb"],
        "elapsed_seconds": time.monotonic() - started,
        "selected_adapter": None,
        "initialization": "Fresh seeded LoRA on the common raw base; A weights never loaded.",
    }
    write_report(directory / "report.json", result)
    print(json.dumps(result), flush=True)
    return result
