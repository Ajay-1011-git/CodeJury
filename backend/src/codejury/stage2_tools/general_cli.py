"""General comparator entrypoint. validate runs on CPU; train/evaluate need MLX and are pending."""

import argparse
import json
import sys
from pathlib import Path

import yaml

from .general_training.audit import audit
from .general_training.merge import ROLES, MergeError, merge

BACKEND = Path(__file__).resolve().parents[3]


def _validate(args) -> int:
    config = yaml.safe_load(Path(args.config).read_text())
    if config.get("schema") != "stage2-general-config.v1":
        print("unknown general config schema", file=sys.stderr)
        return 1
    directory = Path(args.manifests) if args.manifests else BACKEND / config["role_manifests_dir"]
    files = {r: directory / f"{r}.json" for r in ROLES}
    absent = [r for r, p in files.items() if not p.is_file()]
    if absent:
        print(
            json.dumps(
                {"status": "pending", "reason": "role datasets not frozen", "missing": absent}
            )
        )
        return 3
    try:
        merged = merge({r: json.loads(p.read_text()) for r, p in files.items()})
    except MergeError as exc:
        print(json.dumps({"status": "invalid", "reason": str(exc)}))
        return 1
    runs_path = directory / "runs.json"
    result = {"status": "ok", "examples": merged["examples"], "tokens": merged["tokens"]}
    if runs_path.is_file():
        runs = json.loads(runs_path.read_text())
        result["opportunity_audit"] = audit(
            runs["roles"], runs["general"], config["parity_tolerance"]
        )
    else:
        result["opportunity_audit"] = {"status": "not_measured", "missing": ["runs.json"]}
    print(json.dumps(result, indent=2))
    return 0


def _pending(name: str):
    def run(args) -> int:
        print(
            json.dumps(
                {
                    "status": "pending",
                    "command": name,
                    "reason": "needs native MLX hardware and frozen role datasets; nothing was run",
                }
            )
        )
        return 3

    return run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="general_cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("validate")
    p.add_argument("--config", required=True)
    p.add_argument("--manifests")
    p.set_defaults(fn=_validate)
    for name in ("train", "evaluate"):
        p = sub.add_parser(name)
        p.add_argument("--config")
        p.set_defaults(fn=_pending(name))
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
