"""Frozen authorized exports, sequential native training and fresh runtime reload."""

import copy
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from threading import Event
from uuid import uuid4

import yaml
from jsonschema import ValidationError

from codejury.models.worker import file_hash

from ...budgets import CAPS
from ...contracts import checked, json_hash
from ...data import config, export_pools, final_pool_metadata, load_stage1, write_report
from ...factory import make_model_port
from ...registry import ADAPTER_FILES, Registry, hashes, local_path, role_config


def recipe(settings):
    value = settings.get("refresh")
    required = {
        "reference_proof",
        "pilot_steps",
        "steps",
        "save_every",
        "batch_size",
        "max_seq_length",
        "learning_rate",
        "grad_checkpoint",
        "seed",
    }
    if type(value) is not dict or set(value) != required:
        raise ValueError("Missing or unknown refresh recipe fields")
    for key, low, high in (
        ("pilot_steps", 10, 20),
        ("steps", 20, 2000),
        ("save_every", 1, 2000),
        ("batch_size", 1, 1),
        ("max_seq_length", 128, 4096),
        ("seed", 0, 2**32 - 1),
    ):
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise ValueError("Invalid refresh recipe: " + key)
    if (
        type(value["learning_rate"]) not in (int, float)
        or not math.isfinite(value["learning_rate"])
        or not 0 < value["learning_rate"] <= 0.001
        or value["grad_checkpoint"] is not True
        or value["steps"] < value["pilot_steps"]
        or value["steps"] % value["save_every"]
        or value["seed"] != settings["seed"]
    ):
        raise ValueError("Invalid refresh learning rate/checkpoint/seed policy")
    return value


def verify_pilot(path, identity, minimum_steps, *, role="fixer_a"):
    proof = json.loads(Path(path).read_text())
    if (
        proof.get("phase") != "pilot"
        or proof.get("status") != "pilot_verified"
        or proof.get("job_identity") != identity
        or type(proof.get("completed_steps")) is not int
        or proof["completed_steps"] < minimum_steps
        or proof.get("reload_verified") is not True
        or proof.get("updates_verified") is not True
    ):
        raise ValueError("Matching successful native pilot/save/reload required")
    registry = Registry(Path(proof["registry_path"]))
    if registry.identity(role)["adapter_hash"] != proof["adapter_hash"]:
        raise ValueError("Pilot adapter changed after verification")
    return proof


def checkpoint_registry(directory, weights, step, session, original, metrics):
    """Register actual trained bytes; quality status stays pilot-only until selection."""
    directory.mkdir()
    shutil.copyfile(weights, directory / "adapters.safetensors")
    shutil.copyfile(
        Path(session["native_output"]) / "adapter_config.json", directory / "adapter_config.json"
    )
    digest = file_hash(directory / "adapters.safetensors")
    role = session.get("role", "fixer_a")
    base = original.record["base"]
    write_report(
        directory / "freeze.json",
        {
            "adapter_sha256": digest,
            "model_id": base["model_id"],
            "model_revision": base["revision"],
            "training_steps": step,
            "data_manifest_sha256": session["data_manifest_hash"],
            "job_identity": session["job_identity"],
            "initial_adapter_hash": session["initial_adapter_hash"],
            "note": "Steps count this refresh; inherited initialization is recorded separately.",
        },
    )
    loss_points = []
    for row in metrics:
        if row["iteration"] <= step:
            loss_points.append(
                {
                    "step": row["iteration"],
                    "train_loss": row.get("train_loss"),
                    "validation_loss": row.get("val_loss"),
                }
            )
    card = checked(
        {
            "schema_version": "stage2.v1",
            "role": role,
            "status": "pilot_only",
            "adapter_hash": digest,
            **{
                key: base[key]
                for key in ("base_revision_hash", "tokenizer_hash", "quantization_hash")
            },
            "topology_hash": original.record["topology_hash"],
            "data_manifest_hash": session["data_manifest_hash"],
            "config_hash": role_config(base, original.record["topology_hash"], role, digest),
            "train_base_problems": session["train_base_problems"],
            "train_records": session["train_records"],
            "steps": step,
            "evaluation_summary": "Stage 2 refresh; executable checkpoint selection pending. "
            "Limited imported synthetic integer/list corpus.",
            "loss_points": loss_points,
        },
        "AdapterCard",
    )
    record = copy.deepcopy(original.record)
    record["adapters"] = {
        **(
            {"fixer_a": copy.deepcopy(original.record["adapters"]["fixer_a"])}
            if role == "fixer_b"
            else {}
        ),
        role: {
            "path": str(directory.resolve()),
            "files": hashes(directory, ADAPTER_FILES),
            "card": card,
        },
    }
    path = directory / "registry.json"
    write_report(path, record)
    Registry(path)
    return path


def reload_check(
    registry_path, runtime_config, prompt, seed, expected_parameter_hash=None, *, role="fixer_a"
):
    # The first native trainer has exited before this fresh runtime process starts.
    registry = Registry(registry_path)
    runtime = yaml.safe_load(Path(runtime_config).read_text())
    from ...model_worker import NativeModelPort

    with NativeModelPort(registry, runtime) as port:
        response = port.generate(
            {
                "schema_version": "stage2.v1",
                "request_id": "reload-" + uuid4().hex,
                "run_id": "a-refresh-reload",
                "role": role,
                "purpose": "reconstruct" if role == "fixer_b" else "repair",
                "prompt": prompt,
                "seed": seed,
                "max_new_tokens": 256,
                "remaining_budget": CAPS,
            },
            Event(),
        )
        if response["status"] != "ok" or not response["text"]:
            raise RuntimeError("Saved adapter could not generate after fresh runtime reload")
        inspection = port.inspect()
        if (
            expected_parameter_hash is not None
            and inspection["parameter_hash"] != expected_parameter_hash
        ):
            raise RuntimeError("Fresh reload parameters differ from trained parameters")
    from ...candidates import parse_draft

    try:
        parse_draft(response["text"])
        schema_valid = True
    except (ValueError, ValidationError):
        schema_valid = False
    return {
        "response": response,
        "inspection": inspection,
        "schema_valid": schema_valid,
        "note": "Reload/output check only; not executable quality selection.",
    }


def train(config_path, *, phase="pilot", out=None, pilot_proof=None):
    settings = config(config_path)
    cfg = recipe(settings)
    if not settings["training_enabled"]:
        raise ValueError("Training is disabled in this recipe")
    seal = final_pool_metadata(config_path)
    manifest, _ = load_stage1(local_path(settings["source_manifest"]))
    with make_model_port(local_path(settings["runtime_config"])) as port:
        registry = port.registry
    initial = registry.verify_adapter("fixer_a")
    identity = json_hash(
        {
            "recipe": cfg,
            "source_manifest_hash": json_hash(manifest),
            "reference_proof_hash": file_hash(local_path(cfg["reference_proof"])),
            "final_seal_hash": seal["manifest_hash"],
            "base_revision_hash": registry.base["base_revision_hash"],
            "topology_hash": registry.record["topology_hash"],
            "initial_adapter_hash": registry.identity("fixer_a")["adapter_hash"],
            "system": "json-system-user.v1",
            "target": "stage2.RepairDraft.v1",
        }
    )
    if phase not in {"pilot", "full"}:
        raise ValueError("Unknown training phase")
    if phase == "full":
        if pilot_proof is None:
            raise ValueError("Full training needs --pilot-proof")
        verify_pilot(pilot_proof, identity, cfg["pilot_steps"])
    directory = (
        Path(out).resolve()
        if out
        else (local_path(settings["report_directory"]) / (phase + "-" + uuid4().hex[:12]))
    )
    directory.mkdir(parents=True, exist_ok=False)
    pools = export_pools(
        config_path,
        directory / "pools",
        local_path(cfg["reference_proof"]),
        base_revision_hash=registry.base["base_revision_hash"],
    )
    data = directory / "sft"
    data.mkdir()
    for split, name in (("train", "train.jsonl"), ("validation", "valid.jsonl")):
        shutil.copyfile(directory / "pools" / split / "a-sft.jsonl", data / name)
    # The native loader only sees this freshly created local directory; no test.jsonl.
    pool_hash = json_hash(pools)
    steps = cfg["pilot_steps"] if phase == "pilot" else cfg["steps"]
    native_output = directory / "native"
    session = {
        "version": "stage2.a-refresh.v1",
        "phase": phase,
        "job_identity": identity,
        "registry_path": str(registry.path),
        "registry_hash": registry.manifest_hash,
        "initial_adapter_path": str(initial),
        "initial_adapter_hash": registry.identity("fixer_a")["adapter_hash"],
        "recipe": cfg,
        "steps": steps,
        "data_directory": str(data),
        "data_hashes": {name: file_hash(data / name) for name in ("train.jsonl", "valid.jsonl")},
        "data_manifest_hash": pool_hash,
        "native_output": str(native_output),
        "train_records": pools[0]["record_count"],
        "train_base_problems": pools[0]["base_problem_count"],
        "validation_records": pools[1]["record_count"],
        "final_pool": seal,
        "pilot_proof_hash": file_hash(pilot_proof) if pilot_proof else None,
        "source_manifest_hash": json_hash(manifest),
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
    environment = {**os.environ, "HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    with (directory / "native.log").open("x") as log:
        child = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=environment,
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
        write_report(
            directory / "failed.json",
            {
                "exit_code": code,
                "training_started": True,
                "note": "No promotion; native logs retained. Do not automatically replay.",
            },
        )
        raise RuntimeError("Native refresh failed; inspect retained logs")
    native = json.loads((directory / "native-result.json").read_text())
    if native["completed_steps"] != steps or not native["updates_verified"]:
        raise RuntimeError("Native job did not verify all intended updates")
    metrics = [json.loads(line) for line in (directory / "loss.jsonl").read_text().splitlines()]
    candidates = []
    for step in (
        [steps] if phase == "pilot" else range(cfg["save_every"], steps + 1, cfg["save_every"])
    ):
        weights = native_output / f"{step:07d}_adapters.safetensors"
        registered = checkpoint_registry(
            directory / f"checkpoint-{step}", weights, step, session, registry, metrics
        )
        candidates.append({"step": step, "registry_path": str(registered)})
    registered = Path(candidates[-1]["registry_path"])
    first = json.loads((directory / "pools/train/records.jsonl").read_text().splitlines()[0])
    reload = reload_check(
        registered,
        local_path(settings["runtime_config"]),
        first["a_prompt"],
        cfg["seed"],
        native["parameter_hash"],
    )
    write_report(directory / "reload.json", reload)
    result = {
        "status": "pilot_verified" if phase == "pilot" else "trained_selection_pending",
        "phase": phase,
        "job_identity": identity,
        "completed_steps": steps,
        "training_started": True,
        "updates_verified": True,
        "reload_verified": True,
        "adapter_hash": reload["response"]["adapter_hash"],
        "registry_path": str(registered),
        "candidates": candidates,
        "data_manifest_hash": pool_hash,
        "train_records": session["train_records"],
        "train_base_problems": session["train_base_problems"],
        "validation_records": session["validation_records"],
        "peak_memory_mb": native["peak_memory_mb"],
        "elapsed_seconds": time.monotonic() - started,
        "selected_adapter": None,
        "limitations": [
            "Limited synthetic integer/list pool; expanded corpus remains pending.",
            "Executable validation must select any released checkpoint.",
            "Final assessment contents never opened; no final benchmark.",
        ],
    }
    write_report(directory / "report.json", result)
    print(json.dumps(result), flush=True)
    return result
