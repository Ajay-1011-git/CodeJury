"""Stage 2 A diagnostic and explicit, truthful learning prerequisites."""

import argparse
import json

from .training.fixer_a import evaluate, training_preconditions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["evaluate", "train"])
    parser.add_argument("--role", choices=["fixer_a"], required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.command == "evaluate":
        evaluate(args.config, args.out)
        return 0
    report = training_preconditions(args.config)
    print(json.dumps(report))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
