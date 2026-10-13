"""Explicit offline entry point; never reached from a live repair."""

import argparse
import json
from pathlib import Path

from ..registry import local_path
from .budget import Halt, Ledger
from .collect import collect, settings
from .redaction import credentials


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "preflight",
            "smoke",
            "collect",
            "validate",
            "train-student",
            "compare",
            "lineage-check",
            "handoff",
            "complete-training",
        ],
    )
    parser.add_argument("--config", default="config/stage2_core/teacher.yaml")
    parser.add_argument("--stage", choices=["pilot"], default="pilot")
    parser.add_argument("--max-attempts", type=int, choices=[1], default=1)
    parser.add_argument("--phase", choices=["pilot", "full"], default="pilot")
    parser.add_argument("--role", choices=["fixer_a"], default="fixer_a")
    parser.add_argument("--split", choices=["validation"], default="validation")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    cfg = settings(args.config)
    if args.command == "complete-training":
        from .continue_training import complete

        result = complete(cfg)
    elif args.command == "handoff":
        from .handoff import handoff

        if args.out is None:
            parser.error("handoff requires --out")
        result = handoff(cfg, args.out)
    elif args.command == "train-student":
        from .student_train import train_student

        result = train_student(cfg, phase=args.phase)
    elif args.command == "compare":
        from .compare import compare

        result = compare(cfg)
    elif args.command == "lineage-check":
        from .compare import lineage_check

        result = lineage_check(cfg)
    elif args.command == "validate":
        from .validate import validate_all

        result = validate_all(cfg)
    else:
        from .client import Teacher

        ledger = Ledger(local_path(cfg["ledger"]))
        keys = credentials(Path(__file__).resolve().parents[5] / ".env")
        teacher = Teacher(keys, ledger)
        try:
            result = (
                teacher.preflight()
                if args.command == "preflight"
                else collect(cfg, teacher, smoke=args.command == "smoke")
            )
        except Halt as error:
            print(json.dumps({"status": "stopped", "reason": str(error), **ledger.summary()}))
            return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
