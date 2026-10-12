"""Inspected MLX-LM training API; the global lease covers every native import/load."""

import json
import math
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from codejury.models.worker import file_hash

from ...data import write_report
from ...leases import ComputeLease
from ...registry import MODEL_SYSTEM, Registry


def main():
    path = Path(sys.argv[1])
    session = json.loads(path.read_text())
    with ComputeLease(owner="ajay", job_id="a-refresh-" + uuid4().hex, kind="training"):
        import mlx.core as mx
        import numpy as np
        from mlx.utils import tree_flatten
        from mlx_lm.lora import CONFIG_DEFAULTS, train_model
        from mlx_lm.tuner.callbacks import TrainingCallback
        from mlx_lm.tuner.datasets import load_dataset
        from mlx_lm.tuner.utils import remove_lora_layers

        from ...model_worker.native import MLXBackend, verify_tensors

        registry = Registry(Path(session["registry_path"]))
        if registry.manifest_hash != session["registry_hash"]:
            raise ValueError("Registry changed before native training")
        cfg = session["recipe"]
        data = Path(session["data_directory"])
        if {p.name for p in data.iterdir()} != {"train.jsonl", "valid.jsonl"}:
            raise ValueError("Only local allowlisted train/valid exports accepted")
        if any(file_hash(data / n) != h for n, h in session["data_hashes"].items()):
            raise ValueError("Export changed before native training")
        initial = registry.verify_adapter("fixer_a")
        if file_hash(initial / "adapters.safetensors") != session["initial_adapter_hash"]:
            raise ValueError("Initialization changed before native training")
        args = SimpleNamespace(
            **{
                **CONFIG_DEFAULTS,
                "model": str(registry.model_dir),
                "train": True,
                "test": False,
                "data": str(data),
                "mask_prompt": True,
                "fine_tune_type": "lora",
                "num_layers": registry.record["topology"]["num_layers"],
                "lora_parameters": registry.record["topology"]["lora_parameters"],
                "batch_size": cfg["batch_size"],
                "iters": session["steps"],
                "max_seq_length": cfg["max_seq_length"],
                "learning_rate": cfg["learning_rate"],
                "grad_checkpoint": cfg["grad_checkpoint"],
                "grad_accumulation_steps": 1,
                "seed": cfg["seed"],
                "adapter_path": session["native_output"],
                "resume_adapter_file": str(initial / "adapters.safetensors"),
                "steps_per_report": 1 if session["phase"] == "pilot" else 10,
                "steps_per_eval": session["steps"] if session["phase"] == "pilot" else 50,
                "val_batches": -1,
                "save_every": session["steps"]
                if session["phase"] == "pilot"
                else cfg["save_every"],
                "trust_remote_code": False,
            }
        )
        np.random.seed(args.seed)
        mx.random.seed(args.seed)
        backend = MLXBackend(registry)
        try:
            # Verify the complete resume tensor set with the exact runtime inserter.
            # Upstream train_model's partial resume load is used only after this check.
            backend.switch("fixer_a")
            initial_weights = mx.load(str(initial / "adapters.safetensors"))
            initial_parameter_hash = backend.inspect()["parameter_hash"]
            backend.model = remove_lora_layers(backend.model)
            train_set, valid_set, test_set = load_dataset(args, backend.tokenizer)
            if (
                len(train_set) != session["train_records"]
                or len(valid_set) != session["validation_records"]
                or len(test_set)
            ):
                raise ValueError("Native dataset counts/splits mismatch")
            masking = []
            for split, dataset in (("train", train_set), ("validation", valid_set)):
                for index in range(len(dataset)):
                    row = dataset[index]
                    messages = row["messages"]
                    if len(messages) != 3 or messages[0] != {
                        "role": "system",
                        "content": MODEL_SYSTEM,
                    }:
                        raise ValueError("Exported chat differs from the frozen runtime format")
                    tokens, offset = dataset.process(row)
                    runtime = backend.tokenizer.apply_chat_template(
                        messages[:-1],
                        tokenize=True,
                        add_generation_prompt=True,
                    )
                    if (
                        tokens[:offset] != runtime
                        or offset != len(runtime)
                        or not 0 < offset < len(tokens) <= args.max_seq_length
                    ):
                        raise ValueError("Mask/prefix/truncation mismatch in native dataset")
                    masking.append(
                        {
                            "split": split,
                            "index": index,
                            "prompt_tokens": offset,
                            "total_tokens": len(tokens),
                        }
                    )
            write_report(
                path.parent / "mask-audit.json",
                {
                    "processor": "mlx_lm.tuner.datasets.ChatDataset.process",
                    "mask_prompt": True,
                    "runtime_prefix_matches": True,
                    "rows": masking,
                    "max_tokens": max(r["total_tokens"] for r in masking),
                },
            )
            write_report(path.parent / "upstream-args.json", vars(args))
            metrics = []
            started = time.monotonic()

            class Metrics(TrainingCallback):
                def emit(self, kind, info):
                    if any(type(v) is float and not math.isfinite(v) for v in info.values()):
                        raise ValueError("Non-finite native training metric")
                    row = {
                        "kind": kind,
                        **info,
                        "elapsed_seconds": time.monotonic() - started,
                        "peak_memory_mb": mx.get_peak_memory() / 1e6,
                    }
                    metrics.append(row)
                    with (path.parent / "loss.jsonl").open("a") as stream:
                        stream.write(json.dumps(row) + "\n")
                    print(json.dumps(row), flush=True)

                def on_train_loss_report(self, info):
                    self.emit("train", info)

                def on_val_loss_report(self, info):
                    self.emit("validation", info)

            train_model(args, backend.model, train_set, valid_set, Metrics())
            backend.model.eval()
            mx.eval(backend.model.parameters())
            expected = {
                name: value
                for name, value in tree_flatten(backend.model.parameters())
                if name.rsplit(".", 1)[-1] in {"lora_a", "lora_b"}
            }
            weights = mx.load(str(Path(args.adapter_path) / "adapters.safetensors"))
            verify_tensors(weights, expected)
            verify_tensors(weights, initial_weights)
            if not all(bool(mx.all(mx.isfinite(value)).item()) for value in weights.values()):
                raise ValueError("Non-finite trained adapter")
            delta = sum(
                float(mx.sum(mx.abs(weights[n] - initial_weights[n])).item()) for n in weights
            )
            completed = max((r["iteration"] for r in metrics if r["kind"] == "train"), default=0)
            if completed != args.iters or not math.isfinite(delta) or delta <= 0:
                raise ValueError("Training did not verify actual gradient updates")
            write_report(
                path.parent / "native-result.json",
                {
                    "completed_steps": completed,
                    "updates_verified": True,
                    "adapter_delta_l1": delta,
                    "adapter_tensor_count": len(weights),
                    "initial_parameter_hash": initial_parameter_hash,
                    "parameter_hash": backend.inspect()["parameter_hash"],
                    "peak_memory_mb": mx.get_peak_memory() / 1e6,
                    "elapsed_seconds": time.monotonic() - started,
                },
            )
        finally:
            backend.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
