"""MLX implementation, imported/constructed only inside the compute-lease owner."""

import gc

from ..registry import MODEL_SYSTEM


def verify_tensors(weights: dict, expected: dict) -> None:
    if set(weights) != set(expected):
        raise ValueError("Adapter tensor keys are incomplete or contain unexpected parameters")
    for name, value in weights.items():
        if tuple(value.shape) != tuple(expected[name].shape) or value.dtype != expected[name].dtype:
            raise ValueError("Adapter tensor shape/dtype mismatch: " + name)


class MLXBackend:
    def __init__(self, registry):
        import mlx.core as mx
        from mlx_lm import load

        self.mx = mx
        self.registry = registry
        self.model, self.tokenizer = load(str(registry.model_dir), trust_remote_code=False)
        self.model.eval()
        self.base_object_id = id(self.model)
        self.base_loads = 1
        self.role = "raw"
        self.faulted = False

    def reset(self):
        self.tokenizer.detokenizer.reset()
        gc.collect()
        self.mx.clear_cache()

    def switch(self, role):
        from mlx.utils import tree_flatten
        from mlx_lm.tuner.utils import linear_to_lora_layers, remove_lora_layers

        if self.faulted:
            raise ValueError("Adapter switch previously failed; close and audit the worker")
        directory = self.registry.verify_current(role)
        # remove_lora_layers retains each wrapper's original QuantizedLinear object.
        # No fusion, base reload or previous adapter arrays survive the switch.
        self.model = remove_lora_layers(self.model)
        if any(
            name.rsplit(".", 1)[-1] in {"lora_a", "lora_b", "m"}
            for name, _ in tree_flatten(self.model.parameters())
        ):
            self.faulted = True
            raise ValueError("Raw model still contains adapter leaves")
        self.reset()
        try:
            if role != "raw":
                layout = self.registry.record["topology"]
                linear_to_lora_layers(self.model, layout["num_layers"], layout["lora_parameters"])
                expected = {
                    name: value
                    for name, value in tree_flatten(self.model.parameters())
                    if name.rsplit(".", 1)[-1] in {"lora_a", "lora_b"}
                }
                weights = self.mx.load(str(directory / "adapters.safetensors"))
                verify_tensors(weights, expected)
                # Upstream's partial load is safe only after exact adapter-key validation.
                self.model.load_weights(list(weights.items()), strict=False)
                self.mx.eval(self.model.parameters())
            self.model.eval()
            self.role = role
        except Exception:
            self.model = remove_lora_layers(self.model)
            self.role = "raw"
            self.faulted = True
            self.reset()
            raise
        if id(self.model) != self.base_object_id:
            self.faulted = True
            raise ValueError("Base model object was replaced during adapter switch")

    def tokenize(self, prompt: str) -> list[int]:
        return self.tokenizer.apply_chat_template(
            [{"role": "system", "content": MODEL_SYSTEM}, {"role": "user", "content": prompt}],
            tokenize=True,
            add_generation_prompt=True,
        )

    def stream(self, tokens, max_tokens, seed, progress):
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler

        self.reset()
        self.mx.reset_peak_memory()
        self.mx.random.seed(seed)
        return stream_generate(
            self.model,
            self.tokenizer,
            prompt=tokens,
            max_tokens=max_tokens,
            sampler=make_sampler(temp=0.0),
            prompt_cache=None,
            prompt_progress_callback=progress,
        )

    def peak_memory_mb(self):
        return self.mx.get_peak_memory() / 1e6

    def inspect(self):
        from ...models.worker import ModelWorker

        return {
            "parameter_hash": ModelWorker.parameter_hash(self),
            "base_object_id": self.base_object_id,
            "base_loads": self.base_loads,
            "role": self.role,
        }

    def close(self):
        self.model = self.tokenizer = None
        gc.collect()
        self.mx.clear_cache()
