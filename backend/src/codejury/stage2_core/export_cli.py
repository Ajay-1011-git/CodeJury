"""Export genuine fixed-controller TRAIN states through the frozen exchange contract."""

import argparse
import json
from pathlib import Path
from threading import Event

from .episode_export import export
from .ledger import Ledger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["episodes", "score-training"])
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--ledger", type=Path, default=Path("artifacts/stage2_core/fixed-collection")
    )
    parser.add_argument("--split", choices=["train"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--tool-config", type=Path, default=Path("../integration/stage2/tools.yaml")
    )
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    if args.command == "score-training":
        from codejury.stage2_tools.factory import make_tool_port

        from .episode_export.offline import training_labels

        tool = make_tool_port(args.tool_config)
        tool.sandbox.ready()
        result = training_labels(
            Ledger(args.ledger), [r["run_id"] for r in report["runs"]], tool, Event(), args.out
        )
        print(json.dumps(result))
        return
    manifest = export(
        Ledger(args.ledger),
        [r["run_id"] for r in report["runs"]],
        args.out,
        base_revision_hash=report["base_revision_hash"],
        split=args.split,
    )
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
