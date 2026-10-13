"""MLX-LM native bridge (mirrors the interface inspected on mlx-lm 0.32.0).

Runs as a subprocess: `python -m codejury.stage2_tools.critic_training.native session.json`.
Verifies assistant-completion masking and LoRA targets on the real model before any step, trains
with local metric callbacks, then reloads the saved adapter and checks every saved tensor equals
the freshly loaded model's tensor.
"""

import json
import sys
import time
import types
from pathlib import Path

import yaml


def main() -> int:
    import mlx.core as mx
    import numpy as np
    from mlx.utils import tree_flatten
    from mlx_lm import load
    from mlx_lm.lora import CONFIG_DEFAULTS, build_parser, train_model
    from mlx_lm.tuner.callbacks import TrainingCallback
    from mlx_lm.tuner.datasets import load_dataset

    path = Path(sys.argv[1])
    session = json.loads(path.read_text())
    parsed = vars(build_parser().parse_args(session["upstream_args"]))
    config = yaml.safe_load(Path(parsed["config"]).read_text())
    for key, value in config.items():
        if parsed.get(key) is None:
            parsed[key] = value
    for key, value in CONFIG_DEFAULTS.items():
        if parsed.get(key) is None:
            parsed[key] = value
    args = types.SimpleNamespace(**parsed)
    np.random.seed(args.seed)
    mx.random.seed(args.seed)
    session["random_seeds"] = {"numpy": args.seed, "mlx": args.seed}
    if args.trust_remote_code:
        raise ValueError("Remote code is disabled")
    model, tokenizer = load(args.model, trust_remote_code=False)
    actual = {name for name, _ in model.layers[-1].named_modules()}
    requested = set(args.lora_parameters["keys"])
    if not requested <= actual:
        raise ValueError(f"LoRA targets unavailable: {requested - actual}")
    train, valid, _ = load_dataset(args, tokenizer)
    train_tokens = 0
    for dataset in (train, valid):
        for row in dataset._data:
            tokens, offset = dataset.process(row)
            if not 0 < offset < len(tokens) <= args.max_seq_length:
                raise ValueError("SFT masking/truncation would omit part of the completion")
            if dataset is train:
                train_tokens += len(tokens)
    session["mask_verified"] = True
    session["projection_targets"] = sorted(requested)
    session["train_tokens_per_epoch"] = train_tokens
    session["max_train_tokens"] = max(len(train.process(row)[0]) for row in train._data)
    path.write_text(json.dumps(session, indent=2))
    loss_path = Path(session["loss_path"])
    start = time.monotonic()

    class LocalMetrics(TrainingCallback):
        def emit(self, kind, info):
            record = {
                "kind": kind,
                **info,
                "elapsed_seconds": time.monotonic() - start,
                "peak_memory_mb": mx.get_peak_memory() / 1e6,
            }
            with loss_path.open("a") as file:
                file.write(json.dumps(record) + "\n")
            print(json.dumps(record), flush=True)

        def on_train_loss_report(self, info):
            self.emit("train", info)

        def on_val_loss_report(self, info):
            self.emit("validation", info)

    train_model(args, model, train, valid, LocalMetrics())
    # Genuine reload: fresh model + saved adapter; every saved tensor must match exactly.
    del model
    saved = mx.load(str(Path(args.adapter_path) / "adapters.safetensors"))
    reloaded, _ = load(args.model, adapter_path=args.adapter_path, trust_remote_code=False)
    live = dict(tree_flatten(reloaded.parameters()))
    missing = [k for k in saved if k not in live]
    mismatched = [k for k in saved if k in live and not bool(mx.array_equal(saved[k], live[k]))]
    session["reload_tensors_checked"] = len(saved)
    session["reload_missing"] = missing
    session["reload_mismatched"] = mismatched
    session["reload_verified"] = bool(saved) and not missing and not mismatched
    path.write_text(json.dumps(session, indent=2))
    return 0 if session["reload_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
