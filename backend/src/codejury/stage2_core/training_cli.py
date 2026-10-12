"""Stage 2 A native pilot/refresh and executable validation/selection."""

import argparse
import json

from .training.fixer_a import evaluate, training_preconditions
from .training.fixer_a.refresh import train
from .training.fixer_a.select import select


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "evaluate",
            "train",
            "preflight",
            "select",
            "mine-b",
            "experiment-b",
            "export-fixers",
            "finalize-b",
        ],
    )
    parser.add_argument("--role", choices=["fixer_a", "fixer_b"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--out")
    parser.add_argument("--phase", choices=["pilot", "full"], default="pilot")
    parser.add_argument("--pilot-proof")
    parser.add_argument("--registry")
    parser.add_argument("--all-variants", action="store_true")
    parser.add_argument("--a-only", action="store_true")
    parser.add_argument("--baseline")
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--control", action="append", default=[])
    parser.add_argument("--mining-report")
    parser.add_argument("--alpha", type=int, choices=[0, 1, 2, 4], default=2)
    parser.add_argument("--view", choices=["independent", "same_as_a"], default="independent")
    args = parser.parse_args()
    if args.command == "finalize-b":
        from .training.fixer_b.experiments import finalize

        if not args.out:
            parser.error("finalize-b requires the experiment --out directory")
        print(json.dumps(finalize(args.config, args.out)))
        return 0
    if args.command == "export-fixers":
        from .training.fixer_b.select import export_fixers

        if not args.out:
            parser.error("export-fixers requires a selected --out directory")
        print(json.dumps(export_fixers(args.out)))
        return 0
    if args.command == "mine-b":
        from .training.fixer_b.mining import mine

        if not args.out:
            parser.error("mine-b requires --out")
        mine(args.config, args.out)
        return 0
    if args.command == "experiment-b":
        from .training.fixer_b.experiments import run

        if not args.out or not args.mining_report or not args.baseline:
            parser.error("experiment-b requires --out, --mining-report and --baseline")
        run(args.config, args.mining_report, args.out, args.baseline)
        return 0
    if args.role == "fixer_b" and args.command == "train":
        from .training.fixer_b.train import train as train_b

        if not args.out or not args.mining_report:
            parser.error("B training requires --out and --mining-report")
        train_b(
            args.config,
            args.mining_report,
            args.out,
            alpha=args.alpha,
            view=args.view,
            phase=args.phase,
            pilot_proof=args.pilot_proof,
        )
        return 0
    if args.role == "fixer_b" and args.command == "evaluate":
        from .training.fixer_b.evaluate import evaluate as evaluate_b

        if not args.registry or not args.out:
            parser.error("B evaluation requires --registry and --out")
        evaluate_b(
            args.config, args.registry, args.out, view=args.view, baseline_path=args.baseline
        )
        return 0
    if args.role == "fixer_b" and args.command == "select":
        from .training.fixer_b.select import select as select_b

        if not args.out or not args.candidate or not args.control:
            parser.error("B selection requires --out, --candidate and --control")
        print(
            json.dumps(select_b(args.config, args.candidate, args.out, control_paths=args.control))
        )
        return 0
    if args.role != "fixer_a":
        parser.error("This command currently requires --role fixer_a")
    if args.command == "evaluate":
        evaluate(
            args.config,
            args.out,
            registry_path=args.registry,
            all_variants=args.all_variants,
            roles=("fixer_a",) if args.a_only else ("raw", "fixer_a"),
        )
        return 0
    if args.command == "train":
        train(args.config, phase=args.phase, out=args.out, pilot_proof=args.pilot_proof)
        return 0
    if args.command == "select":
        if not args.baseline or not args.candidate or not args.out:
            parser.error("select needs --baseline, --candidate and --out")
        print(json.dumps(select(args.config, args.baseline, args.candidate, args.out)))
        return 0
    report = training_preconditions(args.config)
    print(json.dumps(report))
    return 0 if report["status"] == "ready_for_pilot" else 2


if __name__ == "__main__":
    raise SystemExit(main())
