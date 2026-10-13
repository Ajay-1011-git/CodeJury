"""Evaluation config loading and frozen per-method configuration hashes."""

import hashlib
import json
from pathlib import Path

import yaml

ABLATIONS = (
    "B-unweighted",
    "B-same-view",
    "Generic-Critic",
    "No-search",
    "No-gap-feedback",
    "Audit-at-end",
    "Fixed-Judge",
)
CORE = ("B0", "B1", "B2", "B3", "B4", "CJ")
BUDGET_KEYS = (
    "output_tokens",
    "input_tokens",
    "function_executions",
    "elapsed_ms",
    "learned_candidates",
    "search_candidates",
    "audit_mutants",
    "judge_decisions",
)


class ConfigError(ValueError):
    pass


def load(path: Path | str) -> dict:
    config = yaml.safe_load(Path(path).read_text())
    if config.get("schema") != "stage2-eval-config.v1":
        raise ConfigError("Unknown evaluation config schema")
    if len(config["seeds"]) < 3 or len(set(config["seeds"])) != len(config["seeds"]):
        raise ConfigError("At least 3 distinct declared seeds are required")
    if config["public_seed"] != config["seeds"][0]:
        raise ConfigError("The public seed must be the first fixed seed")
    if config["profile"] == "final" and config["split"] != "final_assessment":
        raise ConfigError("The final profile must target final_assessment")
    if config["profile"] == "validation" and config["split"] == "final_assessment":
        raise ConfigError("Validation experiments can never use the sealed final split")
    for regime in config["regimes"].values():
        if set(regime["caps"]) != set(BUDGET_KEYS):
            raise ConfigError("Regime caps must define every Budget field")
    if not set(config["methods"]) >= set(CORE):
        raise ConfigError("Every core method B0-B4 and CJ must be declared")
    return config


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def config_hash(config: dict, method: str, regime: str | None) -> str:
    """Hash over the exact method block, regime caps and sampling seeds that define a run."""
    block = config["methods"].get(method, {"ablation_of": "CJ"})
    caps = config["regimes"][regime]["caps"] if regime else None
    payload = {
        "method": method,
        "block": block,
        "regime": regime,
        "caps": caps,
        "profile": config["profile"],
        "seeds": config["seeds"],
        "public_seed": config["public_seed"],
    }
    return hashlib.sha256(canonical(payload)).hexdigest()


def plan(config: dict) -> list[dict]:
    """Every (method, regime) combination declared for the experiment."""
    rows = []
    for method in CORE:
        m = config["methods"][method]
        rows.append({"method": method, "regime": m["regime"], "budget": m["budget"]})
    for method in config.get("time_matched_methods", []):
        rows.append({"method": method, "regime": "time_matched", "budget": "time_matched"})
    for method in config.get("ablations", []):
        rows.append({"method": method, "regime": "token_matched", "budget": "token_matched"})
    return rows


def resource_caps(config: dict, regime: str | None) -> dict:
    regime = regime or "token_matched"  # B0 receives the common ceiling but is reported unmatched
    return dict(config["regimes"][regime]["caps"])
