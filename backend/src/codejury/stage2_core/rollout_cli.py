"""Collect genuine alternative continuations, then private labels after frozen commits."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from threading import Event

import yaml

from codejury.models.worker import file_hash
from codejury.stage2_tools.critic_training.data import assess, rejoin
from codejury.stage2_tools.factory import make_tool_port

from .contracts import checked, json_hash
from .controller import records
from .data import load_stage1, write_report
from .ledger import Ledger
from .model_worker import NativeModelPort
from .registry import Registry, local_path
from .rollouts import RolloutPort
from .rollouts.config import load_config
from .training.judge_labels import label, utility


def states(cfg, ledger):
    source, rows = load_stage1(local_path(cfg["source_manifest"]))
    by_id = {r["record_id"]: r for r in rows}
    groups = defaultdict(list)
    seen = set()
    excluded = []
    for path in cfg["reports"]:
        report = json.loads(local_path(path).read_text())
        for result in report["runs"]:
            run_id = result["run_id"]
            if run_id in seen:
                raise ValueError("Duplicate source run")
            seen.add(run_id)
            with ledger.connection() as db:
                transports = list(
                    db.execute("SELECT status,response FROM requests WHERE run_id=?", (run_id,))
                )
            if any(
                t["status"] != "settled"
                or not t["response"]
                or json.loads(t["response"])["status"] != "ok"
                for t in transports
            ):
                excluded.append(
                    {
                        "run_id": run_id,
                        "status": result["status"],
                        "reason": "incomplete or unsuccessful source transport",
                    }
                )
                continue
            snapshot, episodes, row = rejoin(ledger, run_id, source, by_id)
            if any(e["model_manifest_hash"] != report["model_manifest_hash"] for e in episodes):
                raise ValueError("Report and episode model identities differ")
            for episode in episodes:
                groups[(row["split"], row["base_problem_id"])].append((episode, row))
    selected = []
    for (split, _), values in sorted(groups.items()):
        # Initial and latest states are genuinely different snapshots, not copied cases.
        ordered = [values[0], values[-1], *values[1:-1]] if len(values) > 1 else values
        unique = []
        for item in ordered:
            if len(item[0]["state"]["available_actions"]) < 2:
                continue
            if item[0]["state"]["state_id"] not in {v[0]["state"]["state_id"] for v in unique}:
                unique.append(item)
            if len(unique) == cfg["states_per_base"]:
                break
        limit = cfg["state_limits"][split]
        selected.extend(unique[: max(0, limit - sum(r[1]["split"] == split for r in selected))])
    return selected, {"source_runs": len(seen), "excluded_runs": excluded}


def collect(cfg, out):
    out = Path(out).resolve()
    if local_path("artifacts") not in out.parents or out.exists():
        raise ValueError("Immutable ignored rollout directory required")
    parent = Ledger(local_path(cfg["ledger"]))
    selected, source_audit = states(cfg, parent)
    registry = Registry(local_path(cfg["registry"]))
    if registry.record["adapters"].get("critic", {}).get("card", {}).get("status") != "completed":
        raise ValueError("Freeze a measured completed Critic before learning rollouts")
    runtime = yaml.safe_load(local_path(cfg["runtime_config"]).read_text())
    tool = make_tool_port(local_path("../integration/stage2/tools.yaml"))
    tool.sandbox.ready()
    identities = {r: registry.identity(r) for r in ["raw", *registry.record["adapters"]]}
    out.mkdir(parents=True)
    commitments, scored, cancel = [], [], Event()
    with NativeModelPort(registry, runtime) as model:
        port = RolloutPort(
            parent,
            out / "forks",
            model,
            tool,
            identities,
            manifest_hash=registry.manifest_hash,
            runtime_hash=tool.sandbox.runtime_hash,
        )
        for index, (episode, source_row) in enumerate(selected):
            options = episode["state"]["available_actions"]
            safe = next(o for o in options if o["action"]["kind"] == "abstain")
            compared = [o for o in options if o != safe][: cfg["max_options"] - 1] + [safe]
            for option in compared:
                for seed in cfg["seeds"]:
                    request = checked(
                        {
                            "schema_version": "stage2.v1",
                            "request_id": "rollout-" + str(len(commitments)),
                            "episode": episode,
                            "forced_option_id": option["option_id"],
                            "seed": seed,
                            "continuation_policy": "fixed-v1",
                            "remaining_budget": episode["state"]["remaining_budget"],
                        },
                        "RolloutRequest",
                    )
                    response = port.continue_episode(request, cancel)
                    commitment = {
                        "split": source_row["split"],
                        "record_id": source_row["record_id"],
                        "base_problem_id": source_row["base_problem_id"],
                        "episode_hash": json_hash(episode),
                        "request": request,
                        "response": response,
                        "fork_ledger": str(port.last_ledger_directory),
                        "selected_source_hash": response["selected_source_hash"],
                    }
                    commitments.append(commitment)
                    with (out / "commitments.jsonl").open("a") as stream:
                        stream.write(json.dumps(commitment) + "\n")
            print(
                json.dumps(
                    {
                        "states_committed": index + 1,
                        "total_states": len(selected),
                        "actual_continuations": len(commitments),
                    }
                ),
                flush=True,
            )
    # All alternative final commitments exist before any private score is computed.
    _, source_rows = load_stage1(local_path(cfg["source_manifest"]))
    source_rows = {r["record_id"]: r for r in source_rows}
    for commitment in commitments:
        response = commitment["response"]
        final = response["final_result"]
        correct, proof = False, None
        fork = Ledger(Path(commitment["fork_ledger"]))
        snapshot = fork.snapshot(final["run_id"])
        frozen_hash = json_hash(snapshot)
        if final["status"] == "supported_patch":
            candidate = next(
                c
                for c in snapshot["candidates"]
                if c["candidate_id"] == final["selected_candidate_id"]
            )
            if candidate["source_hash"] != response["selected_source_hash"]:
                raise ValueError("Selected source changed after commitment")
            labels, proof = assess(
                snapshot["problem"], [candidate], source_rows[commitment["record_id"]], tool, cancel
            )
            correct = labels[candidate["candidate_id"]]
        metadata = records(parent, commitment["request"]["episode"]["run_id"], "metadata")[0]
        value, deltas = utility(
            correct,
            final["status"],
            final["resource_usage"],
            commitment["request"]["remaining_budget"],
            metadata["profile"]["caps"],
        )
        if frozen_hash != json_hash(fork.snapshot(final["run_id"])):
            raise ValueError("Private score changed a committed alternative")
        scored.append(
            {
                **commitment,
                "correct": correct,
                "utility": value,
                "continuation_usage": deltas,
                "final_snapshot_hash": frozen_hash,
                "private_assessment": proof,
            }
        )
        with (out / "scored.jsonl").open("a") as stream:
            stream.write(json.dumps(scored[-1]) + "\n")
    summary = {
        "version": "stage2.judge-rollouts.v1",
        "runtime_mode": "live",
        "contains_final_assessment": False,
        "registry_hash": registry.manifest_hash,
        "seeds": cfg["seeds"],
        "states": len(selected),
        "source_audit": source_audit,
        "learning_config_hash": json_hash(cfg),
        "continuations": len(commitments),
        "train_base_problems": len(
            {r["base_problem_id"] for r in commitments if r["split"] == "train"}
        ),
        "validation_base_problems": len(
            {r["base_problem_id"] for r in commitments if r["split"] == "validation"}
        ),
        "utility": "correct_selection - incorrect_selection "
        "- .05 * mean(normalized_future_resource_usage)",
        "files": {n: file_hash(out / n) for n in ("commitments.jsonl", "scored.jsonl")},
        "limitations": [
            "Below the 200-state/60-train-base target; source pool has only 40 train bases.",
            "Greedy seeds are repeated actual continuations, not independent stochastic samples.",
        ],
    }
    write_report(out / "manifest.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["collect", "label", "train", "select"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rollouts", type=Path)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--phase", choices=["pilot", "full"], default="pilot")
    parser.add_argument("--pilot-proof", type=Path)
    parser.add_argument("--training-report", type=Path)
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.command == "collect":
        result = collect(cfg, args.out)
    elif args.command == "label":
        if args.rollouts is None:
            parser.error("label needs --rollouts")
        result = label(args.rollouts, args.out, minimum_margin=cfg["minimum_margin"])
    elif args.command == "select":
        if args.corpus is None or args.training_report is None:
            parser.error("select needs --corpus and --training-report")
        from .training.judge_labels.evaluate import select

        result = select(
            args.training_report,
            {
                "corpus": str(args.corpus),
                "runtime_config": cfg["runtime_config"],
                "seed": cfg["recipe"]["seed"],
            },
            args.out,
        )
    else:
        if args.corpus is None:
            parser.error("train needs --corpus")
        from .training.roles import train

        result = train(
            "judge",
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
