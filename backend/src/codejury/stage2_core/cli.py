"""Actual fixed-policy execution and training-only source collection."""

import argparse
import json
from pathlib import Path
from threading import Event

import yaml

from .contracts import checked, json_hash
from .controller import FixedController
from .controller.inputs import runtime_input
from .data import load_stage1
from .factory import make_model_port
from .intake import prepare
from .ledger import Ledger
from .registry import local_path


def collection(path):
    value = yaml.safe_load(Path(path).read_text())
    if (
        type(value) is not dict
        or set(value)
        != {
            "version",
            "runtime_config",
            "tool_config",
            "ledger_directory",
            "source_manifest",
            "seed",
            "policy",
        }
        or value["version"] != "stage2.fixed-collection.v1"
        or value["policy"] != "fixed-v1"
        or type(value["seed"]) is not int
        or value["seed"] < 0
    ):
        raise ValueError("Invalid frozen collection config")
    return value


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--request", type=Path, required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--record-id", action="append")
    collect.add_argument("--split", choices=["train", "validation"], default="train")
    for command in (run, collect):
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--policy", choices=["fixed"], default="fixed")
        command.add_argument("--critic-bootstrap", choices=["raw", "reviewed"], default="raw")
        command.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Collection reports cannot be overwritten")
    settings = collection(args.config)
    # Only the safe runtime projection crosses into the controller.
    inputs = []
    if args.command == "collect":
        manifest, rows = load_stage1(local_path(settings["source_manifest"]))
        by_id = {r["record_id"]: r for r in rows if r["split"] == args.split}
        args.record_id = args.record_id or sorted(by_id)
        if len(args.record_id) != len(set(args.record_id)) or any(
            i not in by_id for i in args.record_id
        ):
            raise ValueError("Only unique train record IDs may be collected")
        for record_id in args.record_id:
            row = by_id[record_id]
            problem, tests = runtime_input(row)
            inputs.append(
                (
                    problem,
                    tests,
                    {
                        "split": args.split,
                        "base_problem_id": row["base_problem_id"],
                        "record_id": record_id,
                        "source_manifest_hash": json_hash(manifest),
                        "runtime_input_hash": json_hash(problem),
                    },
                )
            )
        del rows, by_id, row  # reference targets/offline tests never enter the model/controller
    else:
        create = checked(json.loads(args.request.read_text()), "RunCreate")
        problem, tests = prepare(create)
        inputs.append((problem, tests, None))
    from codejury.stage2_tools.factory import make_tool_port

    model = make_model_port(local_path(settings["runtime_config"]))
    tool = make_tool_port(local_path(settings["tool_config"]))
    tool.sandbox.ready()
    ledger = Ledger(local_path(settings["ledger_directory"]))
    roles = ["raw", "fixer_a", "fixer_b"]
    if "critic" in model.registry.record["adapters"]:
        roles.append("critic")
    identities = {role: model.registry.identity(role) for role in roles}
    results, cancel = [], Event()
    try:
        for problem, tests, provenance in inputs:
            controller = FixedController(
                ledger,
                model,
                tool,
                identities,
                manifest_hash=model.registry.manifest_hash,
                runtime_hash=tool.sandbox.runtime_hash,
                mode="live",
                critic_bootstrap=args.critic_bootstrap,
            )
            result = controller.run(
                problem, tests, cancel=cancel, seed=settings["seed"], provenance=provenance
            )
            results.append(result)
            print(
                json.dumps(
                    {
                        "run_id": result["run_id"],
                        "status": result["status"],
                        "actions": [a["kind"] for a in result["actions"]],
                    }
                ),
                flush=True,
            )
    finally:
        model.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as stream:
        stream.write(
            json.dumps(
                {
                    "version": "stage2.fixed-collection-report.v1",
                    "base_revision_hash": model.registry.base["base_revision_hash"],
                    "model_manifest_hash": model.registry.manifest_hash,
                    "runs": results,
                },
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
