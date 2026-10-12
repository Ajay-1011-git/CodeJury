"""Fairness audit: identical visible inputs, caps and tool access across methods."""

from collections import defaultdict


def audit(config: dict, records: list[dict]) -> dict:
    problems = []
    visible = defaultdict(set)
    for r in records:
        visible[(r["task_id"], r["seed"])].add(r["request_hash"])
    differing = [k for k, v in visible.items() if len(v) > 1]
    if differing:
        problems.append(f"{len(differing)} task/seed pairs gave methods different visible inputs")
    full = set(config["tools_full"])
    for method in ("B3", "B4", "CJ"):
        if set(config["methods"][method]["tools"]) != full:
            problems.append(f"{method} lacks the full tool set")
    caps = {name: reg["caps"] for name, reg in config["regimes"].items()}
    for method, spec in config["methods"].items():
        regime = spec["regime"]
        if (
            regime
            and caps[regime] != config["regimes"]["token_matched"]["caps"]
            and (regime == "token_matched")
        ):
            problems.append(f"{method} has non-common token-matched caps")
    tm = [m for m, s in config["methods"].items() if s["budget"] == "token_matched"]
    return {
        "ok": not problems,
        "problems": problems,
        "token_matched_methods": tm,
        "reference_only": [m for m, s in config["methods"].items() if s["budget"] == "reference"],
    }
