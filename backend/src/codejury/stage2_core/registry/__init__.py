"""Frozen local model/adapter registry, verified from bytes before native loading."""

import json
import os
from pathlib import Path

from ...models.worker import file_hash
from ..contract_check import REPO_ROOT
from ..contracts import checked, json_hash

BACKEND = REPO_ROOT / "backend"
ROLES = {"fixer_a", "fixer_b", "critic", "judge", "general"}
REQUIRED = {"fixer_a", "fixer_b", "critic", "judge"}
TOKENIZER_FILES = {"tokenizer.json", "tokenizer_config.json", "chat_template.jinja"}
BASE_FILES = TOKENIZER_FILES | {"config.json", "model.safetensors", "model.safetensors.index.json"}
ADAPTER_FILES = {"adapter_config.json", "adapters.safetensors", "freeze.json"}
MODEL_SYSTEM = (
    "Follow the supplied task, output schema, contract and function interfaces exactly. "
    "Return only the requested JSON object, without Markdown or explanatory prose. "
    "Never invent authoritative test expectations or claim execution that did not occur."
)


class RegistryError(ValueError):
    pass


def unresolved_local_path(value: str) -> Path:
    path = Path(value)
    # Resolve archived machine paths without editing hash-bound provenance files.
    original = os.getenv("CODEJURY_STAGE2_ORIGINAL_ROOT")
    if original and path.is_absolute():
        original_root = Path(original)
        if not original_root.is_absolute() or original_root == Path("/"):
            raise RegistryError("Original checkout root must be an absolute non-root directory")
        try:
            relative = path.relative_to(original_root)
        except ValueError:
            pass
        else:
            path = REPO_ROOT / relative
    return path if path.is_absolute() else BACKEND / path


def local_path(value: str) -> Path:
    return unresolved_local_path(value).resolve()


def exact_keys(value: dict, keys: set[str]) -> None:
    if type(value) is not dict or set(value) != keys:
        raise RegistryError("Registry fields are missing or unknown")


def hashes(directory: Path, names: set[str]) -> dict:
    result = {}
    for name in sorted(names):
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise RegistryError("Missing or symlink model/adapter file: " + name)
        result[name] = file_hash(path)
    return result


def topology(config: dict) -> dict:
    if config.get("fine_tune_type") != "lora" or type(config.get("num_layers")) is not int:
        raise RegistryError("Only inspected removable linear LoRA topology is supported")
    parameters = config.get("lora_parameters", {})
    exact_keys(parameters, {"rank", "scale", "dropout", "keys"})
    if (
        type(parameters["rank"]) is not int
        or not 1 <= parameters["rank"] <= 64
        or not 1 <= config["num_layers"] <= 32
        or parameters["dropout"] != 0
        or parameters["keys"] != ["self_attn.qkv_proj", "self_attn.o_proj"]
        or type(parameters["scale"]) not in (int, float)
        or parameters["scale"] <= 0
    ):
        raise RegistryError("Unsupported Phi linear LoRA topology")
    # These are the actual targets inspected in Phi3 and the genuine Stage 1 checkpoint.
    return {
        "fine_tune_type": "lora",
        "num_layers": config["num_layers"],
        "lora_parameters": parameters,
    }


def role_config(base: dict, topology_hash: str, role: str, adapter_hash: str | None) -> str:
    cap = 192 if role == "judge" else 512 if role == "critic" else 1024
    return json_hash(
        {
            "base_revision_hash": base["base_revision_hash"],
            "tokenizer_hash": base["tokenizer_hash"],
            "quantization_hash": base["quantization_hash"],
            "topology_hash": topology_hash,
            "role": role,
            "adapter_hash": adapter_hash,
            "decoding": {
                "sampler": "greedy",
                "context_tokens": 4096,
                "role_output_cap": cap,
                "chat": "json-system-user.v1",
                "system_hash": json_hash(MODEL_SYSTEM),
            },
        }
    )


class Registry:
    def __init__(self, path: Path):
        unresolved = unresolved_local_path(path)
        self.path = unresolved.resolve()
        if unresolved.is_symlink():
            raise RegistryError("Registry must not be a symlink")
        self.record = json.loads(self.path.read_text())
        exact_keys(
            self.record,
            {"version", "runtime_mode", "base", "topology", "topology_hash", "adapters"},
        )
        if self.record["version"] != "stage2.registry.v1" or self.record["runtime_mode"] != "live":
            raise RegistryError("Live factory requires a genuine live registry")
        self.base = self.record["base"]
        exact_keys(
            self.base,
            {
                "path",
                "model_id",
                "revision",
                "files",
                "base_revision_hash",
                "tokenizer_hash",
                "quantization_hash",
            },
        )
        self.model_dir = local_path(os.getenv("CODEJURY_MODEL_DIR") or self.base["path"])
        actual = hashes(self.model_dir, BASE_FILES)
        if actual != self.base["files"]:
            raise RegistryError("Frozen base/tokenizer file hash mismatch")
        base_config = json.loads((self.model_dir / "config.json").read_text())
        if (
            base_config.get("model_type") != "phi3"
            or base_config.get("num_hidden_layers") != 32
            or base_config.get("quantization") != {"group_size": 64, "bits": 4, "mode": "affine"}
        ):
            raise RegistryError("Registry requires the inspected 32-layer 4-bit Phi3 conversion")
        expected_base = json_hash(
            {
                "model_id": self.base["model_id"],
                "revision": self.base["revision"],
                "files": {k: v for k, v in actual.items() if k not in TOKENIZER_FILES},
            }
        )
        if (
            self.base["base_revision_hash"] != expected_base
            or self.base["tokenizer_hash"] != json_hash({k: actual[k] for k in TOKENIZER_FILES})
            or self.base["quantization_hash"] != json_hash(base_config["quantization"])
        ):
            raise RegistryError("Base/tokenizer/quantization identity mismatch")
        if (
            topology(self.record["topology"]) != self.record["topology"]
            or json_hash(self.record["topology"]) != self.record["topology_hash"]
        ):
            raise RegistryError("Frozen topology mismatch")
        if type(self.record["adapters"]) is not dict or not set(self.record["adapters"]) <= ROLES:
            raise RegistryError("Unsupported adapter role")
        for role, entry in self.record["adapters"].items():
            exact_keys(entry, {"path", "files", "card"})
            card = checked(entry["card"], "AdapterCard")
            if (
                card["role"] != role
                or card["status"] == "not_started"
                or card["steps"] < 1
                or card["adapter_hash"] is None
            ):
                raise RegistryError("Adapter card does not describe a trained role")
            for key in ("base_revision_hash", "tokenizer_hash", "quantization_hash"):
                if card[key] != self.base[key]:
                    raise RegistryError("Adapter card base compatibility mismatch")
            if card["topology_hash"] != self.record["topology_hash"] or card["config_hash"] != (
                role_config(self.base, self.record["topology_hash"], role, card["adapter_hash"])
            ):
                raise RegistryError("Adapter role configuration mismatch")
            self.verify_adapter(role)
        adapter_hashes = [
            entry["card"]["adapter_hash"] for entry in self.record["adapters"].values()
        ]
        if len(adapter_hashes) != len(set(adapter_hashes)):
            raise RegistryError("Distinct trained roles must not alias the same adapter bytes")
        self.base_stats = {name: self._stat(self.model_dir / name) for name in BASE_FILES}
        self.manifest_hash = json_hash(
            {
                **self.record,
                "base": {k: v for k, v in self.base.items() if k != "path"},
                "adapters": {
                    r: {k: v for k, v in e.items() if k != "path"}
                    for r, e in self.record["adapters"].items()
                },
            }
        )

    @staticmethod
    def _stat(path):
        value = path.stat()
        return value.st_ino, value.st_size, value.st_mtime_ns

    def verify_adapter(self, role: str) -> Path:
        entry = self.record["adapters"].get(role)
        if entry is None:
            raise RegistryError("Trained adapter unavailable for " + role)
        directory = local_path(entry["path"])
        actual = hashes(directory, ADAPTER_FILES)
        if (
            actual != entry["files"]
            or actual["adapters.safetensors"] != entry["card"]["adapter_hash"]
        ):
            raise RegistryError("Adapter/config/freeze file hash mismatch")
        config = json.loads((directory / "adapter_config.json").read_text())
        freeze = json.loads((directory / "freeze.json").read_text())
        if topology(config) != self.record["topology"]:
            raise RegistryError("Adapter insertion topology mismatch")
        if (
            freeze["adapter_sha256"] != entry["card"]["adapter_hash"]
            or freeze["model_id"] != self.base["model_id"]
            or freeze["model_revision"] != self.base["revision"]
            or freeze["training_steps"] != entry["card"]["steps"]
            or freeze["data_manifest_sha256"] != entry["card"]["data_manifest_hash"]
        ):
            raise RegistryError("Training freeze provenance mismatch")
        return directory

    def verify_current(self, role: str) -> Path | None:
        if any(self._stat(self.model_dir / name) != self.base_stats[name] for name in BASE_FILES):
            raise RegistryError("Base/tokenizer changed after registry verification")
        return self.verify_adapter(role) if role != "raw" else None

    def identity(self, role: str) -> dict:
        card = self.record["adapters"].get(role, {}).get("card")
        adapter = card["adapter_hash"] if card else None
        return {
            "model_revision_hash": self.base["base_revision_hash"],
            "adapter_hash": adapter,
            "model_config_hash": role_config(
                self.base, self.record["topology_hash"], role, adapter
            ),
        }

    def readiness(self) -> dict:
        available = sorted(self.record["adapters"])
        missing = sorted(REQUIRED - set(available))
        incomplete = sorted(
            role
            for role in REQUIRED & set(available)
            if self.record["adapters"][role]["card"]["status"] != "completed"
        )
        return {
            "ready": not missing and not incomplete,
            "available_roles": ["raw", *available],
            "missing_roles": missing,
            "incomplete_roles": incomplete,
            "manifest_hash": self.manifest_hash,
        }


def register_stage1(
    model_dir: Path, adapter_dir: Path, training_report: Path, out: Path
) -> Registry:
    model_dir, adapter_dir = model_dir.resolve(), adapter_dir.resolve()
    # Reuse actual frozen Stage 1 metadata, never synthesize a new role/checkpoint.
    model_files = hashes(model_dir, BASE_FILES)
    adapter_files = hashes(adapter_dir, ADAPTER_FILES)
    config = json.loads((model_dir / "config.json").read_text())
    freeze = json.loads((adapter_dir / "freeze.json").read_text())
    report = json.loads(training_report.read_text())
    if (
        report.get("runtime_mode") != "live"
        or report.get("adapter_sha256") != freeze["adapter_sha256"]
    ):
        raise RegistryError("Stage 1 report is missing genuine adapter provenance")
    base = {
        "path": str(model_dir),
        "model_id": freeze["model_id"],
        "revision": freeze["model_revision"],
        "files": model_files,
        "tokenizer_hash": json_hash({k: model_files[k] for k in TOKENIZER_FILES}),
        "quantization_hash": json_hash(config["quantization"]),
    }
    base["base_revision_hash"] = json_hash(
        {
            "model_id": base["model_id"],
            "revision": base["revision"],
            "files": {k: v for k, v in model_files.items() if k not in TOKENIZER_FILES},
        }
    )
    layout = topology(json.loads((adapter_dir / "adapter_config.json").read_text()))
    layout_hash = json_hash(layout)
    card = checked(
        {
            "schema_version": "stage2.v1",
            "role": "fixer_a",
            "status": "pilot_only",
            "adapter_hash": adapter_files["adapters.safetensors"],
            "base_revision_hash": base["base_revision_hash"],
            "tokenizer_hash": base["tokenizer_hash"],
            "quantization_hash": base["quantization_hash"],
            "topology_hash": layout_hash,
            "data_manifest_hash": freeze["data_manifest_sha256"],
            "config_hash": role_config(
                base, layout_hash, "fixer_a", adapter_files["adapters.safetensors"]
            ),
            "train_base_problems": report["train_base_problems"],
            "train_records": report["train_records"],
            "steps": freeze["training_steps"],
            "evaluation_summary": "Retained Stage 1 adapter, selected "
            "step 100; recorded assessment 1/10 solved. Stage 2 refresh/validation pending A2.05.",
            "loss_points": report["loss_points"],
        },
        "AdapterCard",
    )
    record = {
        "version": "stage2.registry.v1",
        "runtime_mode": "live",
        "base": base,
        "topology": layout,
        "topology_hash": layout_hash,
        "adapters": {"fixer_a": {"path": str(adapter_dir), "files": adapter_files, "card": card}},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(record, indent=2) + "\n")
    return Registry(out)
