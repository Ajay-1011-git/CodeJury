"""Authorized mixed-task corpus and independent native General training."""

import argparse
import json
from pathlib import Path

import yaml

from .registry import local_path
from .training.general import build
from .training.roles import train


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build", "train", "evaluate", "select", "audit"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--phase", choices=["pilot", "full"], default="pilot")
    parser.add_argument("--pilot-proof", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--training-report", type=Path)
    parser.add_argument("--selected-step", type=int)
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())
    if cfg["version"] != "stage2.general-learning.v1":
        raise ValueError("Unknown General learning configuration")
    if args.command == "build":
        result = build(args.config, args.out)
    elif args.command == "evaluate":
        if args.registry is None:
            parser.error("evaluate needs --registry")
        from .training.general.evaluate import evaluate

        result = evaluate(args.registry, cfg, args.out)
    elif args.command == "select":
        if args.training_report is None:
            parser.error("select needs --training-report")
        from .training.general.evaluate import select

        result = select(args.training_report, cfg, args.out)
    elif args.command == "audit":
        if args.registry is None or args.training_report is None:
            parser.error("audit needs --registry and --training-report")
        from .training.general.opportunity import audit

        result = audit(
            args.registry,
            args.training_report,
            local_path(cfg["judge_selection"]),
            args.out,
            relative_tolerance=cfg["opportunity_relative_tolerance"],
            general_step=args.selected_step,
        )
    else:
        if args.corpus is None:
            parser.error("train needs --corpus")
        result = train(
            "general",
            args.corpus,
            local_path(cfg["registry"]),
            local_path(cfg["runtime_config"]),
            cfg["recipe"],
            args.out,
            phase=args.phase,
            pilot=args.pilot_proof,
        )
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
