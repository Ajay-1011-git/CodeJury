"""Record installed native MLX training interfaces without starting a learning job."""

import argparse
import inspect
import json
import platform
from importlib.metadata import version
from pathlib import Path
from threading import Event

from codejury.stage2_core.leases import ComputeLease


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with ComputeLease(
        owner="ajay", job_id="inspect-mlx-interfaces", kind="training", cancel=Event()
    ):
        import mlx.core as mx
        from mlx_lm import load
        from mlx_lm.lora import build_parser, train_model
        from mlx_lm.tuner.datasets import ChatDataset, load_dataset
        from mlx_lm.tuner.trainer import TrainingArgs, train
        from mlx_lm.tuner.utils import linear_to_lora_layers, load_adapters, remove_lora_layers

        functions = {
            name: str(inspect.signature(function))
            for name, function in {
                "mlx_lm.load": load,
                "train_model": train_model,
                "load_dataset": load_dataset,
                "ChatDataset": ChatDataset,
                "ChatDataset.process": ChatDataset.process,
                "TrainingArgs": TrainingArgs,
                "train": train,
                "linear_to_lora_layers": linear_to_lora_layers,
                "load_adapters": load_adapters,
                "remove_lora_layers": remove_lora_layers,
            }.items()
        }
        actual_flags = {
            flag for action in build_parser()._actions for flag in action.option_strings
        }
        required = {
            "--train",
            "--mask-prompt",
            "--num-layers",
            "--fine-tune-type",
            "--iters",
            "--max-seq-length",
            "--adapter-path",
            "--grad-checkpoint",
            "--seed",
        }
        if not required <= actual_flags:
            raise ValueError("Expected inspected training flags are missing")
        report = {
            "status": "inspected",
            "platform": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "versions": {name: version(name) for name in ("mlx", "mlx-lm", "transformers")},
            "metal_available": mx.metal.is_available(),
            "functions": functions,
            "verified_cli_flags": sorted(required),
            "model_loaded": False,
            "training_started": False,
            "limitation": "Interface inspection is not Critic/B/general "
            "trainer implementation or native pilot/reload acceptance.",
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "functions"}))


if __name__ == "__main__":
    main()
