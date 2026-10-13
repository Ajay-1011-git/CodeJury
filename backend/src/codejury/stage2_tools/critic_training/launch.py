"""Build the verified mlx-lm argv, record the actual command and run the native job."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

from .data.config import config_hash
from .sft import export


def _hash(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def launch(config: dict, backend: Path, data_dir: Path, name: str, *, pilot: bool, fixture: bool):
    t = config["training"]
    model_dir = os.environ.get(t["model_dir_env"], "")
    if not model_dir or not Path(model_dir).is_absolute() or not Path(model_dir).is_dir():
        raise ValueError(f"Set {t['model_dir_env']} to the absolute local checkpoint directory")
    out = backend / t["out_root"] / name
    if (out / "session.json").exists():
        raise ValueError("Refusing to overwrite a training session; choose a new name")
    out.mkdir(parents=True, exist_ok=True)
    sft = export(
        data_dir, out / "sft", validation_fraction=t["validation_fraction"], seed=t["seed"]
    )
    if sft["fixture"] != fixture:
        raise ValueError("fixture flag does not match the data manifest")
    steps = t["pilot_steps"] if pilot else t["steps"]
    if not pilot:
        proof = json.loads((backend / t["out_root"] / "pilot" / "session.json").read_text())
        if proof.get("completed_steps", 0) < t["pilot_steps"] or not proof.get("reload_verified"):
            raise ValueError("A successful real pilot with verified reload is required first")
        if proof.get("fixture") or fixture:
            raise ValueError("Full training needs real data; fixture pilots cannot unlock it")
    upstream_cfg = out / "mlx-config.yaml"
    upstream_cfg.write_text(yaml.safe_dump({"lora_parameters": t["lora_parameters"]}))
    argv = [
        "--model", model_dir, "--train", "--data", str(out / "sft"), "--fine-tune-type", "lora",
        "--mask-prompt", "--batch-size", str(t["batch_size"]), "--num-layers", str(t["num_layers"]),
        "--iters", str(steps), "--learning-rate", str(t["learning_rate"]),
        "--max-seq-length", str(t["max_seq_length"]),
        "--grad-accumulation-steps", str(t["grad_accumulation_steps"]),
        "--adapter-path", str(out), "--seed", str(t["seed"]),
        "--steps-per-report", "1" if pilot else "10", "--steps-per-eval", "5" if pilot else "50",
        "--val-batches", "2", "--save-every", str(steps if pilot else 100),
        "--config", str(upstream_cfg),
    ]  # fmt: skip
    if t["grad_checkpoint"]:
        argv.append("--grad-checkpoint")
    session_path = out / "session.json"
    actual = [os.environ.get("CODEJURY_MLX_PYTHON", sys.executable), "-m",
              "codejury.stage2_tools.critic_training.native", str(session_path)]  # fmt: skip
    session = {
        "kind": "pilot" if pilot else "full",
        "fixture": fixture,
        "model_id": t["model_id"],
        "model_revision": t["model_revision"],
        "config_hash": config_hash(config),
        "sft": sft,
        "seed": t["seed"],
        "steps_requested": steps,
        "upstream_args": argv,
        "actual_command": actual,
        "loss_path": str(out / "loss.jsonl"),
        "completed_steps": 0,
        "reload_verified": False,
    }
    session_path.write_text(json.dumps(session, indent=2))
    start = time.monotonic()
    env = {**os.environ, "PYTHONPATH": str(backend / "src")}
    with (out / "native.log").open("w") as log:
        child = subprocess.Popen(actual, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1, env=env)  # fmt: skip
        for line in child.stdout:
            log.write(line)
        code = child.wait()
    session = json.loads(session_path.read_text())
    session["elapsed_seconds"] = time.monotonic() - start
    session["exit_code"] = code
    rows = [json.loads(x) for x in (out / "loss.jsonl").read_text().splitlines()] if (
        out / "loss.jsonl").exists() else []  # fmt: skip
    session["completed_steps"] = max(
        (r["iteration"] for r in rows if r["kind"] == "train"), default=0
    )
    session["peak_memory_mb"] = max((r["peak_memory_mb"] for r in rows), default=None)
    weights = out / "adapters.safetensors"
    if weights.exists():
        session["adapter_sha256"] = _hash(weights)
    session_path.write_text(json.dumps(session, indent=2) + "\n")
    if code or not session["reload_verified"] or session["completed_steps"] != steps:
        raise RuntimeError("Native training/reload failed; session and logs retained")
    return session
