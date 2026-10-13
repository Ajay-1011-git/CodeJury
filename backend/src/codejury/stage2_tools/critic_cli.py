"""Real Critic data, native pilot/full training, and validation-controlled selection."""

import argparse
import json
from pathlib import Path

import yaml

from codejury.stage2_core.ledger import Ledger
from codejury.stage2_core.registry import local_path


def settings(path):
    value = yaml.safe_load(Path(path).read_text())
    if (
        type(value) is not dict
        or set(value)
        != {
            "version",
            "runtime_config",
            "registry",
            "tool_config",
            "ledger",
            "reports",
            "corpus",
            "seed",
            "recipe",
        }
        or value["version"] != "stage2.critic-training.v1"
    ):
        raise ValueError("Unknown Critic configuration")
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["collect", "validate", "train", "evaluate", "select"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--phase", choices=["pilot", "full"], default="pilot")
    parser.add_argument("--pilot-proof", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--training-report", type=Path)
    args = parser.parse_args()
    cfg = settings(args.config)
    from .critic_training.data import collect, validate

    if args.command == "collect":
        from .factory import make_tool_port

        tool = make_tool_port(local_path(cfg["tool_config"]))
        tool.sandbox.ready()
        result = collect(
            Ledger(local_path(cfg["ledger"])),
            [local_path(p) for p in cfg["reports"]],
            tool,
            local_path(cfg["corpus"]),
            seed=cfg["seed"],
        )
    elif args.command == "validate":
        result = validate(local_path(cfg["corpus"]))
    elif args.command == "train":
        from codejury.stage2_core.training.roles import train

        if args.out is None:
            parser.error("train requires an immutable --out")
        audit = validate(local_path(cfg["corpus"]))
        if not audit["correct_mix_target_met"] or not audit["invalid_mix_target_met"]:
            raise ValueError("Required starting data mix targets were not met")
        result = train(
            "critic",
            local_path(cfg["corpus"]),
            local_path(cfg["registry"]),
            local_path(cfg["runtime_config"]),
            cfg["recipe"],
            args.out,
            phase=args.phase,
            pilot=args.pilot_proof,
        )
    else:
        from .critic_training.evaluate import evaluate, select

        if args.out is None:
            parser.error("evaluation/selection requires --out")
        if args.command == "evaluate":
            if args.registry is None:
                parser.error("evaluate requires --registry")
            result = evaluate(args.registry, cfg, args.out)
        else:
            if args.training_report is None:
                parser.error("select requires --training-report")
            result = select(args.training_report, cfg, args.out)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
