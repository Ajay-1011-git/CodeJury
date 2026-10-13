"""Critic data/training configuration loading and hashing."""

import hashlib
import json
from pathlib import Path

import yaml

MODES = ("discriminate", "challenge_agreement", "audit_gap", "validate_revision")
SCHEMA = "stage2-critic-config.v1"


class ConfigError(ValueError):
    pass


def load(path: Path | str) -> dict:
    config = yaml.safe_load(Path(path).read_text())
    if config.get("schema") != SCHEMA:
        raise ConfigError("Unknown critic config schema")
    mix = config["data"]["mix_targets"]
    if not 0 <= mix["correct_candidate_min"] <= 1 or not 0 <= mix["invalid_proposal_min"] <= 1:
        raise ConfigError("Mix targets must be fractions")
    if config["data"]["split"] not in ("train", "validation"):
        raise ConfigError("Critic data may only be collected from train or validation splits")
    if set(config["data"]["mode_priority"]) != set(MODES):
        raise ConfigError("mode_priority must list the four Critic modes")
    return config


def config_hash(config: dict) -> str:
    blob = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()
