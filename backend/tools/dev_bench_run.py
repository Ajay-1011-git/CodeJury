#!/usr/bin/env python3
"""Development benchmark CLI. No sealed-set access, network, or downloads."""

import argparse
import json
import sys
from pathlib import Path

# Permit invocation from either repository root or backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codejury.dev_bench import METHODS, ROOT, SEEDS, read_jsonl, summarize, validate_benchmark
from codejury.dev_bench.runner import run_benchmark
from codejury.stage2_core.registry import local_path
from codejury.stage2_tools.factory import make_tool_port


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "run", "summarize"])
    parser.add_argument("--benchmark", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    parser.add_argument(
        "--ids", nargs="+", help="Explicit smoke subset, never full baseline evidence"
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not args.seeds or len(set(args.seeds)) != len(args.seeds) or any(s < 0 for s in args.seeds):
        parser.error("Seeds must be unique nonnegative integers")
    if len(set(args.methods)) != len(args.methods):
        parser.error("Methods must be unique")
    if args.command == "validate":
        sandbox = make_tool_port(local_path("../integration/stage2/tools.yaml")).sandbox
        sandbox.ready()
        report = validate_benchmark(
            args.benchmark, sandbox, local_path("data/manifests/stage1.json")
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 1 if report["rejected"] or report["bases"] < 60 else 0
    if args.command == "summarize":
        print(json.dumps(summarize(read_jsonl(args.out / "results.jsonl")), indent=2))
        return 0
    run_benchmark(
        args.benchmark,
        args.out,
        methods=tuple(args.methods),
        seeds=tuple(args.seeds),
        ids=args.ids,
        resume=args.resume,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
