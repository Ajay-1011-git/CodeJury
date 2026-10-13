"""Native training for new roles, with immutable data and mandatory pilot/reload proof."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from codejury.models.worker import file_hash

from ...contracts import json_hash
from ...data import write_report
from ...registry import Registry, local_path
from ..fixer_a.refresh import checkpoint_registry, reload_check, verify_pilot


def train(role, corpus, registry_path, runtime_config, recipe, out, *, phase="pilot", pilot=None):
    if role not in {"fixer_a", "critic", "judge", "general"} or phase not in {"pilot", "full"}:
        raise ValueError("Unsupported new role or training phase")
    required = {
        "pilot_steps",
        "steps",
        "save_every",
        "batch_size",
        "max_seq_length",
        "learning_rate",
        "grad_checkpoint",
        "seed",
    }
    if set(recipe) not in (required, required | {"validation_loss_batches"}) or any(
        type(recipe[k]) is not int
        for k in ("pilot_steps", "steps", "save_every", "batch_size", "max_seq_length", "seed")
    ):
        raise ValueError("Unknown or incorrectly typed training recipe")
    if "validation_loss_batches" in recipe and (
        type(recipe["validation_loss_batches"]) is not int
        or not 4 <= recipe["validation_loss_batches"] <= 64
    ):
        raise ValueError("Declare 4–64 loss batches; quality selection still needs full execution")
    if not (
        10 <= recipe["pilot_steps"] <= 20 <= recipe["steps"] <= 2000
        and 1 <= recipe["save_every"] <= recipe["steps"]
        and recipe["steps"] % recipe["save_every"] == 0
        and recipe["batch_size"] == 1
        and 128 <= recipe["max_seq_length"] <= 4096
        and recipe["grad_checkpoint"] is True
        and recipe["seed"] >= 0
        and type(recipe["learning_rate"]) in {int, float}
        and 0 < recipe["learning_rate"] <= 0.001
    ):
        raise ValueError("Invalid bounded native recipe")
    corpus = Path(corpus).resolve()
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest["role"] != role
        or manifest["runtime_mode"] != "live"
        or manifest["contains_final_assessment"] is not False
    ):
        raise ValueError("Real execution-filtered, final-free role corpus required")
    for name in ("train.jsonl", "valid.jsonl"):
        source = corpus / name
        if source.is_symlink() or file_hash(source) != manifest["files"][name]:
            raise ValueError("Corpus file identity mismatch")
    registry = Registry(Path(registry_path))
    initial_hash = None
    if role == "fixer_a":
        registry.verify_adapter(role)
        initial_hash = registry.identity(role)["adapter_hash"]
    training_root = Path(__file__).resolve().parents[1]
    trainer_sources = {
        str(p.relative_to(local_path("."))): file_hash(p)
        for p in (
            Path(__file__).resolve(),
            training_root / "fixer_a/native.py",
            training_root / "fixer_a/refresh.py",
        )
    }
    identity = json_hash(
        {
            "role": role,
            "recipe": recipe,
            "data_manifest_hash": file_hash(manifest_path),
            "base_revision_hash": registry.base["base_revision_hash"],
            "topology_hash": registry.record["topology_hash"],
            "initial_adapter_hash": initial_hash,
            "trainer_sources": trainer_sources,
        }
    )
    if phase == "full":
        if pilot is None:
            raise ValueError("Full training requires matching native pilot proof")
        verify_pilot(pilot, identity, recipe["pilot_steps"], role=role)
    directory = Path(out).resolve()
    private_root = local_path("artifacts")
    if private_root not in directory.parents:
        raise ValueError("Training weights and private data must stay in ignored artifacts")
    directory.mkdir(parents=True, exist_ok=False)
    data = directory / "sft"
    data.mkdir()
    for name in ("train.jsonl", "valid.jsonl"):
        shutil.copyfile(corpus / name, data / name)
    steps = recipe["pilot_steps"] if phase == "pilot" else recipe["steps"]
    session = {
        "version": "stage2.role-training.v1",
        "role": role,
        "phase": phase,
        "job_identity": identity,
        "registry_path": str(registry.path),
        "registry_hash": registry.manifest_hash,
        "initial_adapter_hash": initial_hash,
        "recipe": recipe,
        "steps": steps,
        "data_directory": str(data),
        "data_hashes": {n: file_hash(data / n) for n in ("train.jsonl", "valid.jsonl")},
        "data_manifest_hash": file_hash(manifest_path),
        "native_output": str(directory / "native"),
        "train_records": manifest["splits"]["train"]["records"],
        "train_base_problems": manifest["splits"]["train"]["base_problems"],
        "validation_records": manifest["splits"]["validation"]["records"],
        "pilot_proof_hash": file_hash(pilot) if pilot else None,
        "trainer_sources": trainer_sources,
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
    with (directory / "native.log").open("x") as log:
        child = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={
                **{
                    key: value
                    for key, value in os.environ.items()
                    if key not in {"GROQ_API_KEY", "groq_api_1", "groq_api_2", "groq_api_3"}
                },
                "HF_HUB_OFFLINE": "1",
                "TOKENIZERS_PARALLELISM": "false",
            },
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
        write_report(directory / "failed.json", {"exit_code": code, "promoted": False})
        raise RuntimeError("Native role training failed; retained logs require inspection")
    native = json.loads((directory / "native-result.json").read_text())
    if native["completed_steps"] != steps or native["updates_verified"] is not True:
        raise RuntimeError("Actual native updates were not verified")
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
    first = json.loads((data / "train.jsonl").read_text().splitlines()[0])
    reload = reload_check(
        candidates[-1]["registry_path"],
        runtime_config,
        first["messages"][1]["content"],
        recipe["seed"],
        native["parameter_hash"],
        role=role,
    )
    write_report(directory / "reload.json", reload)
    result = {
        "role": role,
        "phase": phase,
        "job_identity": identity,
        "status": "pilot_verified" if phase == "pilot" else "trained_selection_pending",
        "completed_steps": steps,
        "updates_verified": True,
        "reload_verified": True,
        "adapter_hash": reload["response"]["adapter_hash"],
        "registry_path": candidates[-1]["registry_path"],
        "candidates": candidates,
        "data_manifest_hash": session["data_manifest_hash"],
        "train_records": session["train_records"],
        "train_base_problems": session["train_base_problems"],
        "validation_records": session["validation_records"],
        "peak_memory_mb": native["peak_memory_mb"],
        "elapsed_seconds": time.monotonic() - started,
        "selected_adapter": None,
    }
    write_report(directory / "report.json", result)
    print(json.dumps(result), flush=True)
    return result
