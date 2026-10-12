"""Runtime-visible episode export and training-only Stage 2 research hooks."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from codejury.contracts import REPO_ROOT, validate
from codejury.contracts.intake import source_hash, validate_args, validate_request, validate_test
from codejury.models.worker import file_hash
from codejury.properties import equal, expected
from codejury.training.data import DATA, digest, request_view


def visible_episode(body):
    request = copy.deepcopy(body["request"])
    snapshot = copy.deepcopy(body["snapshot"])
    validate_request(request)
    validate(snapshot, "RunSnapshot")
    candidate_ids = {c["candidate_id"] for c in snapshot["candidates"]}
    test_ids = {t["test_id"] for t in snapshot["tests"]}
    for candidate in snapshot["candidates"]:
        if candidate["source_sha256"] != source_hash(candidate["source"]):
            raise ValueError("Candidate hash mismatch")
        if candidate["parent_id"] is not None and candidate["parent_id"] not in candidate_ids:
            raise ValueError("Unknown candidate parent")
    for test in snapshot["tests"]:
        validate_test(test, request)  # A hidden authoritative literal cannot be added here.
    for row in snapshot["executions"]:
        if row["candidate_id"] not in candidate_ids or row["test_id"] not in test_ids:
            raise ValueError("Unknown execution evidence ID")
    actions = []
    for index, action in enumerate(body.get("actions", []), 1):
        allowed = {
            "action",
            "source",
            "role",
            "property_id",
            "family",
            "reason",
            "inputs",
            "shrink_limited",
            "authority",
            "counterexample",
        }
        row = {k: copy.deepcopy(v) for k, v in action.items() if k in allowed}
        if row.get("source") not in {
            "fixed_stage1_policy",
            "raw_critic",
            "deterministic_fallback",
            "property_engine",
        }:
            raise ValueError("Unknown action source")
        case = row.get("counterexample")
        if case is not None:
            if set(case) != {"args", "actual_output", "expected", "property_id", "oracle_status"}:
                raise ValueError("Unexpected counterexample fields")
            validate_args(case["args"], request["input_domain"])
            prop = request["approved_property"]
            if not prop or case["property_id"] != prop or case["oracle_status"] != "authoritative":
                raise ValueError("Only approved runtime counterexamples may be exported")
            if not equal(case["expected"], expected(prop, case["args"][0])):
                raise ValueError("Counterexample oracle mismatch")
        row["action_id"] = f"{snapshot['run_id']}:action-{index}"
        actions.append(row)
    return {
        "schema_version": "episode.v1",
        "runtime_mode": snapshot["runtime_mode"],
        "problem_id": "visible-" + digest(request),
        "run_id": snapshot["run_id"],
        "request": request,
        "candidates": snapshot["candidates"],
        "tests": snapshot["tests"],
        "outcomes": [
            {"outcome_id": f"{snapshot['run_id']}:{r['execution_id']}", **r}
            for r in snapshot["executions"]
        ],
        "actions": actions,
        "decision": snapshot["decision"],
        "status": snapshot["status"],
        "usage": snapshot["usage"],
    }


def export_runtime(directory, out):
    rows = []
    for path in sorted(Path(directory).glob("*-episode.json")):
        if path.is_symlink() or path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Invalid episode file")
        rows.append(visible_episode(json.loads(path.read_text())))
    write_jsonl(out, rows)
    return {
        "episodes": len(rows),
        "runtime_modes": sorted({r["runtime_mode"] for r in rows}),
        "hidden_join": False,
    }


def write_jsonl(out, rows):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as file:
        for row in rows:
            file.write(json.dumps(row, separators=(",", ":")) + "\n")


def train_records(manifest):
    # Read only the sealed train asset; validation/assessment/Stage2 paths are never opened.
    seal = json.loads(Path(manifest).read_text())
    if seal["seal_sha256"] != digest(seal["assets"]):
        raise ValueError("Split seal mismatch")
    assets = [a for a in seal["assets"] if a["split"] == "train"]
    if len(assets) != 1:
        raise ValueError("Exactly one train asset required")
    asset = assets[0]
    path = (DATA / asset["path"]).resolve()
    if DATA.resolve() not in path.parents or (DATA / asset["path"]).is_symlink():
        raise ValueError("Invalid train asset path")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != asset["sha256"]:
        raise ValueError("Train asset changed")
    rows = [json.loads(line) for line in content.decode().splitlines()]
    if any(r["split"] != "train" for r in rows):
        raise ValueError("Non-training record rejected")
    return rows


def join_training_ids(episodes, records):
    if any(r["split"] != "train" for r in records):
        raise ValueError("Offline joins accept training IDs only")
    by_request = {digest(request_view(r)): r for r in records}
    joined = []
    for episode in episodes:
        row = by_request.get(digest(episode["request"]))
        if row is None:
            raise ValueError("Episode does not match a training-only problem")
        joined.append(
            {
                "run_id": episode["run_id"],
                "problem_id": episode["problem_id"],
                "base_problem_id": row["base_problem_id"],
                "family_id": row["family_id"],
                "split": "train",
                "source_sha256": source_hash(row["buggy_source"]),
                "training_assessment_ids": [t["test_id"] for t in row["assessment_tests"]],
            }
        )
    return joined


def mine_train(manifest, config, out, *, bases=5, repeats=2, model=None, runner=None, mode="live"):
    from codejury.evaluation.stage1 import freeze_then_assess, single
    from codejury.models.worker import ModelWorker
    from codejury.runner import DockerRunner

    if mode not in {"live", "fixture"}:
        raise ValueError("Explicit live/fixture mode required")
    if not 1 <= bases <= 40 or not 2 <= repeats <= 4:
        raise ValueError("Mining limits: 1–40 bases, 2–4 repeats")
    if mode == "live" and (model is not None or runner is not None):
        raise ValueError("Injected dependencies must be labelled fixture")
    records = train_records(manifest)
    chosen = {}
    for record in records:
        chosen.setdefault(record["base_problem_id"], record)
    chosen = list(chosen.values())[:bases]
    model = model or ModelWorker(config)
    runner = runner or DockerRunner()
    if mode == "live":
        if model.identity["adapter_role"] != "fixer_a":
            raise ValueError("Failure mining requires trained Fixer A")
        freeze = json.loads((model.adapter / "freeze.json").read_text())
        if (
            freeze["training_steps"] < 1
            or freeze["adapter_sha256"] != model.identity["adapter_sha256"]
        ):
            raise ValueError("Failure mining requires verified training metadata")
    out = Path(out)
    work = out.parent / (out.stem + "-evidence")
    work.mkdir(parents=True, exist_ok=False)
    failures = []
    joins = []
    failed_trials = 0
    for record in chosen:
        request = request_view(record)
        trials = []
        for trial in range(repeats):
            answer = single(request, model, runner)
            trial_id = f"{record['base_problem_id']}:{trial + 1}"
            row = freeze_then_assess(
                answer,
                request,
                record["assessment_tests"],
                runner,
                work / (trial_id.replace(":", "-") + "-final.json"),
            )
            failed_trials += int(not row["solved"])
            trials.append(
                {
                    "trial_id": trial_id,
                    "raw_outcome": answer["generations"][0]["text"],
                    "source": answer["source"],
                    "usage": answer["usage"],
                    "accepted": row["accepted"],
                    "solved": row["solved"],
                    "malformed": row["malformed"],
                }
            )
            joins.append(
                {
                    "trial_id": trial_id,
                    "base_problem_id": record["base_problem_id"],
                    "split": "train",
                    "frozen_answer_sha256": row["final_answer_sha256"],
                    "assessment_outcomes": row["assessment_executions"],
                }
            )
        if any(not t["solved"] for t in trials):
            failures.append(
                {
                    "schema_version": "stage2-mining.v1",
                    "runtime_mode": mode,
                    "base_problem_id": record["base_problem_id"],
                    "family_id": record["family_id"],
                    "split": "train",
                    "source_sha256": source_hash(record["buggy_source"]),
                    "manifest_sha256": file_hash(manifest),
                    "model": model.identity,
                    "request": request,
                    "trials": trials,
                    "provenance": "Actual repeated A outputs; train-only; no Stage2 role trained",
                }
            )
        print(
            json.dumps(
                {
                    "mined_train_base": record["base_problem_id"],
                    "failed_trials": sum(not t["solved"] for t in trials),
                }
            ),
            flush=True,
        )
    write_jsonl(out, failures)
    write_jsonl(work / "offline-training-join.jsonl", joins)
    summary = {
        "runtime_mode": mode,
        "bases": len(chosen),
        "trials": len(joins),
        "failed_trials": failed_trials,
        "failure_base_records": len(failures),
        "split": "train",
        "repeats": repeats,
        "seed": 17,
        "note": "Deterministic repeated outcomes are not additional independent problems.",
    }
    (work / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("runtime")
    export.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "backend/artifacts/runs")
    export.add_argument("--out", type=Path, required=True)
    join = sub.add_parser("join-train")
    join.add_argument("--episodes", type=Path, required=True)
    join.add_argument("--manifest", type=Path, required=True)
    join.add_argument("--out", type=Path, required=True)
    mine = sub.add_parser("mine-train")
    mine.add_argument("--manifest", type=Path, required=True)
    mine.add_argument("--config", type=Path, required=True)
    mine.add_argument("--out", type=Path, required=True)
    mine.add_argument("--bases", type=int, default=5)
    mine.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    if args.command == "runtime":
        result = export_runtime(args.runs_dir, args.out)
    elif args.command == "join-train":
        episodes = [json.loads(line) for line in args.episodes.read_text().splitlines()]
        rows = join_training_ids(episodes, train_records(args.manifest))
        write_jsonl(args.out, rows)
        result = {"joined_train_episodes": len(rows)}
    else:
        result = mine_train(
            args.manifest, args.config, args.out, bases=args.bases, repeats=args.repeats
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
