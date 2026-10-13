"""Live factories. Imports do not load weights, acquire leases or launch workers."""

import os
from pathlib import Path

import yaml

from .model_worker import NativeModelPort
from .registry import Registry, local_path


def make_model_port(config_path: Path) -> NativeModelPort:
    config = yaml.safe_load(Path(config_path).read_text())
    expected = {
        "profile",
        "model_manifest",
        "startup_timeout_s",
        "shutdown_grace_s",
        "poll_interval_s",
    }
    if (
        type(config) is not dict
        or set(config) != expected
        or config["profile"] != "mac-standard-v1"
    ):
        raise ValueError("Unknown or missing native runtime settings")
    for name, lower, upper in (
        ("startup_timeout_s", 1, 120),
        ("shutdown_grace_s", 0.1, 10),
        ("poll_interval_s", 0.01, 0.2),
    ):
        if type(config[name]) not in (int, float) or not lower <= config[name] <= upper:
            raise ValueError("Invalid worker timeout: " + name)
    manifest = os.getenv("CODEJURY_STAGE2_MODEL_MANIFEST") or config["model_manifest"]
    return NativeModelPort(Registry(local_path(manifest)), config)


def make_rollout_port(config_path, model_port, tool_port):
    from .ledger import Ledger
    from .rollouts import RolloutPort
    from .rollouts.config import load_config

    settings = load_config(config_path)
    if (
        model_port.registry.manifest_hash
        != Registry(local_path(settings["registry"])).manifest_hash
    ):
        raise ValueError("Rollout model differs from the frozen E3 registry")
    identities = {
        r: model_port.registry.identity(r) for r in ["raw", *model_port.registry.record["adapters"]]
    }
    return RolloutPort(
        Ledger(local_path(settings["ledger"])),
        local_path("artifacts/stage2_core/judge-continuations"),
        model_port,
        tool_port,
        identities,
        manifest_hash=model_port.registry.manifest_hash,
        runtime_hash=tool_port.sandbox.runtime_hash,
    )


def make_baseline_port(config_path, model_port, tool_port, *, evaluation_config=None):
    from uuid import uuid4

    from codejury.stage2_tools.evaluation.config import load

    from .baselines import BaselinePort, control_registries

    settings = yaml.safe_load(Path(config_path).with_name("methods.yaml").read_text())
    if (
        type(settings) is not dict
        or set(settings)
        != {
            "version",
            "evaluation_config",
            "ledger_directory",
            "control_registry_directory",
            "controls",
        }
        or settings["version"] != "stage2.live-methods.v1"
    ):
        raise ValueError("Invalid live method registry")
    config = evaluation_config or load(local_path(settings["evaluation_config"]))
    controls = control_registries(
        model_port.registry,
        settings["controls"],
        local_path(settings["control_registry_directory"]) / uuid4().hex,
    )
    return BaselinePort(
        config, model_port, tool_port, local_path(settings["ledger_directory"]), variants=controls
    )
