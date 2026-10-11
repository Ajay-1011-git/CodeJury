"""Lazy native MLX imports; clean model reload and fresh KV state for every role."""

import gc
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..contracts import REPO_ROOT
from ..runner import Cancelled, DockerRunner, InfrastructureError
from .views import CRITIC_SYSTEM, REPAIR_SYSTEM

BACKEND = REPO_ROOT / "backend"


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        while block := file.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def settings(config=None):
    result = yaml.safe_load((Path(config) if config else BACKEND / "config/model.yaml").read_text())
    for key, variable in (
        ("model_dir", "CODEJURY_MODEL_DIR"),
        ("adapter_dir", "CODEJURY_ADAPTER_DIR"),
    ):
        value = os.getenv(variable) or result.get(key)
        result[key] = (
            (Path(value) if Path(value).is_absolute() else BACKEND / value).resolve()
            if value
            else None
        )
    if os.getenv("CODEJURY_ALLOW_RAW") is not None:
        result["allow_raw"] = os.getenv("CODEJURY_ALLOW_RAW") == "1"
    return result


def readiness(config=None):
    cfg = settings(config)
    sandbox = False
    try:
        DockerRunner().ready()
        sandbox = True
    except InfrastructureError:
        pass
    ready = False
    trained = False
    proof = (
        BACKEND
        / "artifacts/training"
        / ("model-smoke.json" if cfg["adapter_dir"] else "raw-smoke.json")
    )
    try:
        if (
            proof.exists()
            and cfg["model_dir"]
            and (cfg["model_dir"] / "model.safetensors").exists()
        ):
            record = json.loads(proof.read_text())
            raw = record.get("raw_loaded", False) and record.get("model_id") == cfg["model_id"]
            raw = raw and record.get("model_revision") == cfg["model_revision"]
            if (
                raw
                and cfg["adapter_dir"]
                and (cfg["adapter_dir"] / "adapters.safetensors").exists()
            ):
                freeze = json.loads((cfg["adapter_dir"] / "freeze.json").read_text())
                actual = file_hash(cfg["adapter_dir"] / "adapters.safetensors")
                trained = (
                    record.get("switch_verified", False) and record.get("adapter_sha256") == actual
                )
                trained = (
                    trained and freeze["adapter_sha256"] == actual and freeze["training_steps"] > 0
                )
            ready = trained or raw and cfg.get("allow_raw", False)
    except (OSError, ValueError, KeyError, TypeError):
        ready = trained = False
    return {"model_ready": bool(ready), "sandbox_ready": sandbox, "fixer_a_trained": bool(trained)}


@dataclass(frozen=True)
class Generation:
    text: str
    input_tokens: int
    output_tokens: int
    elapsed_ms: int
    peak_memory_mb: float


class ModelWorker:
    def __init__(self, config=None, *, force_raw=False, adapter_override=None):
        self.cfg = settings(config)
        self.force_raw = force_raw
        self.adapter = Path(adapter_override) if adapter_override else self.cfg["adapter_dir"]
        if not self.cfg["model_dir"] or not (self.cfg["model_dir"] / "model.safetensors").exists():
            raise InfrastructureError("Local model weights unavailable")
        if not force_raw and self.adapter is None and not self.cfg.get("allow_raw"):
            raise InfrastructureError("Trained adapter required; raw mode needs explicit override")
        self.model = self.tokenizer = None
        self.role = None
        self.last_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "elapsed_ms": 0,
            "peak_memory_mb": 0,
        }
        self.identity = {
            "model_id": self.cfg["model_id"],
            "model_revision": self.cfg["model_revision"],
            "adapter_role": "none" if force_raw or self.adapter is None else "fixer_a",
            "adapter_sha256": file_hash(self.adapter / "adapters.safetensors")
            if self.adapter and not force_raw
            else None,
        }

    def switch(self, role):
        import mlx.core as mx
        from mlx_lm import load

        if role not in {"fixer_a", "critic"}:
            raise ValueError("Unsupported Stage 1 role")
        # Entire previous object is destroyed; no adapter state is toggled in place.
        self.model = self.tokenizer = None
        gc.collect()
        mx.clear_cache()
        adapter = (
            str(self.adapter) if role == "fixer_a" and self.adapter and not self.force_raw else None
        )
        self.model, self.tokenizer = load(
            str(self.cfg["model_dir"]), adapter_path=adapter, trust_remote_code=False
        )
        self.role = role

    def parameter_hash(self):
        import mlx.core as mx
        import numpy as np
        from mlx.utils import tree_flatten

        digest = hashlib.sha256()
        for name, array in tree_flatten(self.model.parameters()):
            digest.update(name.encode())
            digest.update(str(array.dtype).encode())
            digest.update(
                np.array(
                    array.astype(mx.float32) if array.dtype == mx.bfloat16 else array
                ).tobytes()
            )
        return digest.hexdigest()

    def generate(self, role, view, *, max_tokens, cancel=None, deadline=None, format_retry=False):
        import mlx.core as mx
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler

        if cancel is not None and cancel.is_set():
            raise Cancelled("Cancelled before model operation")
        start = time.monotonic()
        self.last_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "elapsed_ms": 0,
            "peak_memory_mb": 0,
        }
        if self.role != role:
            self.switch(role)
        system = REPAIR_SYSTEM if role == "fixer_a" else CRITIC_SYSTEM
        if format_retry:
            system += (
                " The previous response was malformed. "
                "Emit a valid JSON object only, without Markdown."
            )
        prompt = self.tokenizer.apply_chat_template(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(view, separators=(",", ":"))},
            ],
            tokenize=True,
            add_generation_prompt=True,
        )
        if len(prompt) > 4096:
            raise ValueError("Model input exceeds 4096 token budget")
        cap = 1024 if role == "fixer_a" else 512
        if type(max_tokens) is not int or not 1 <= max_tokens <= cap:
            raise ValueError("Model output cap exceeds role budget")
        mx.random.seed(17)
        self.last_usage["input_tokens"] = len(prompt)
        text = ""
        final = None
        iterator = stream_generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=make_sampler(temp=0.0),
            prompt_cache=None,
        )
        try:
            for final in iterator:
                self.last_usage.update(
                    output_tokens=final.generation_tokens,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                    peak_memory_mb=final.peak_memory * 1000,
                )
                if cancel is not None and cancel.is_set():
                    raise Cancelled("Cancelled during inference")
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError("Episode deadline reached")
                text += final.text
                if len(text) > 24000:
                    raise ValueError("Generated output exceeds character limit")
        finally:
            iterator.close()
        return Generation(
            text,
            len(prompt),
            final.generation_tokens if final else 0,
            int((time.monotonic() - start) * 1000),
            final.peak_memory * 1000 if final else 0,
        )
