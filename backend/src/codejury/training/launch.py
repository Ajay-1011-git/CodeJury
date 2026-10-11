"""Build verified MLX argv, record actual commands, and run the native pilot/full job."""

import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

from ..models.worker import BACKEND, file_hash, settings
from .data import export_sft, load_records


def launch(config, pilot=False):
    cfg = yaml.safe_load(Path(config).read_text())
    model_cfg = settings(BACKEND / cfg["model_config"])
    if not model_cfg["model_dir"]:
        raise ValueError("Set absolute CODEJURY_MODEL_DIR to the downloaded checkpoint")
    manifest = BACKEND / cfg["dataset_manifest"]
    load_records(manifest)
    export_sft(manifest, BACKEND / cfg["data"])
    if not pilot:
        proof = json.loads((BACKEND / cfg["pilot_output"] / "session.json").read_text())
        if proof.get("completed_steps", 0) < 10 or not proof.get("reload_verified"):
            raise ValueError("Successful real pilot/save/reload required before the full job")
    output = BACKEND / (cfg["pilot_output"] if pilot else cfg["output"])
    output.mkdir(parents=True, exist_ok=True)
    if (output / "session.json").exists():
        raise ValueError("Refusing to overwrite a training session; choose a new output directory")
    steps = cfg["pilot_steps"] if pilot else cfg["steps"]
    upstream_config = output / "mlx-config.yaml"
    upstream_config.write_text(yaml.safe_dump({"lora_parameters": cfg["lora_parameters"]}))
    upstream = [
        "--model",
        str(model_cfg["model_dir"]),
        "--train",
        "--data",
        str(BACKEND / cfg["data"]),
        "--fine-tune-type",
        "lora",
        "--mask-prompt",
        "--batch-size",
        str(cfg["batch_size"]),
        "--num-layers",
        str(cfg["num_layers"]),
        "--iters",
        str(steps),
        "--learning-rate",
        str(cfg["learning_rate"]),
        "--max-seq-length",
        str(cfg["max_seq_length"]),
        "--grad-accumulation-steps",
        str(cfg["grad_accumulation_steps"]),
        "--adapter-path",
        str(output),
        "--seed",
        str(cfg["seed"]),
        "--steps-per-report",
        "1" if pilot else "10",
        "--steps-per-eval",
        "10" if pilot else "50",
        "--val-batches",
        "4",
        "--save-every",
        "10" if pilot else "100",
        "--config",
        str(upstream_config),
    ]
    if cfg["grad_checkpoint"]:
        upstream.append("--grad-checkpoint")
    session_path = output / "session.json"
    actual = [sys.executable, "-m", "codejury.training.native", str(session_path)]
    session = {
        "kind": "pilot" if pilot else "full",
        "model_id": model_cfg["model_id"],
        "model_revision": model_cfg["model_revision"],
        "config_sha256": file_hash(config),
        "data_manifest_sha256": file_hash(manifest),
        "sft_sha256": {
            name: file_hash(BACKEND / cfg["data"] / name) for name in ("train.jsonl", "valid.jsonl")
        },
        "upstream_config_sha256": file_hash(upstream_config),
        "seed": cfg["seed"],
        "upstream_args": upstream,
        "actual_command": actual,
        "inspected_equivalent_cli": [sys.executable, "-m", "mlx_lm", "lora", *upstream],
        "loss_path": str(output / "loss.jsonl"),
        "completed_steps": 0,
        "reload_verified": False,
    }
    session_path.write_text(json.dumps(session, indent=2))
    start = time.monotonic()
    with (output / "native.log").open("w") as log:
        child = subprocess.Popen(
            actual, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        for line in child.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
        code = child.wait()
    session = json.loads(session_path.read_text())
    session["elapsed_seconds"] = time.monotonic() - start
    session["exit_code"] = code
    metrics = (
        [json.loads(line) for line in (output / "loss.jsonl").read_text().splitlines()]
        if (output / "loss.jsonl").exists()
        else []
    )
    session["completed_steps"] = max(
        (row["iteration"] for row in metrics if row["kind"] == "train"), default=0
    )
    if (
        code == 0
        and session["completed_steps"] == steps
        and (output / "adapters.safetensors").exists()
    ):
        session["adapter_sha256"] = file_hash(output / "adapters.safetensors")
        from ..models.worker import ModelWorker

        worker = ModelWorker(BACKEND / cfg["model_config"], adapter_override=output)
        worker.switch("fixer_a")
        session["reload_parameter_sha256"] = worker.parameter_hash()
        session["reload_verified"] = True
    session_path.write_text(json.dumps(session, indent=2) + "\n")
    if code or not session["reload_verified"]:
        raise RuntimeError("Native training/save/reload failed; retain session/logs for diagnosis")
    print(json.dumps(session, indent=2))
    return session
