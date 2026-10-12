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
