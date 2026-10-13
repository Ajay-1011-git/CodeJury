"""Frozen, bounded learning-only continuation configuration."""

from pathlib import Path

import yaml


def load_config(path):
    value = yaml.safe_load(Path(path).read_text())
    fields = {
        "version",
        "source_manifest",
        "runtime_config",
        "registry",
        "ledger",
        "reports",
        "seeds",
        "states_per_base",
        "state_limits",
        "max_options",
        "minimum_margin",
        "recipe",
    }
    if (
        type(value) is not dict
        or set(value) != fields
        or value["version"] != "stage2.judge-learning.v1"
        or type(value["seeds"]) is not list
        or not 2 <= len(value["seeds"]) <= 3
        or len(set(value["seeds"])) != len(value["seeds"])
        or any(type(s) is not int or not 0 <= s < 2**32 for s in value["seeds"])
        or type(value["max_options"]) is not int
        or not 2 <= value["max_options"] <= 4
        or type(value["states_per_base"]) is not int
        or not 1 <= value["states_per_base"] <= 10
        or set(value["state_limits"]) != {"train", "validation"}
        or any(type(v) is not int or not 1 <= v <= 1000 for v in value["state_limits"].values())
        or not 0 < value["minimum_margin"] < 0.1
    ):
        raise ValueError("Invalid frozen Judge learning configuration")
    return value
