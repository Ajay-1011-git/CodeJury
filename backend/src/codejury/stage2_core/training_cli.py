"""Stage 2 A native pilot/refresh and executable validation/selection."""

import argparse
import json

from .training.fixer_a import evaluate, training_preconditions
from .training.fixer_a.refresh import train
from .training.fixer_a.select import select


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["evaluate", "train", "preflight", "select"])
    parser.add_argument("--role", choices=["fixer_a"], required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out")
    parser.add_argument("--phase", choices=["pilot", "full"], default="pilot")
    parser.add_argument("--pilot-proof")
    parser.add_argument("--registry")
    parser.add_argument("--all-variants", action="store_true")
    parser.add_argument("--a-only", action="store_true")
    parser.add_argument("--baseline")
    parser.add_argument("--candidate", action="append", default=[])
    args = parser.parse_args()
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
