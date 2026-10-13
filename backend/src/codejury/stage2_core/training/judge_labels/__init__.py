"""Measured alternative-action labels. No simulated rewards or final assessment access."""

import copy
import json
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from codejury.models.worker import file_hash

from ...budgets import CAPS
from ...contracts import canonical_json, checked, json_hash
from ...data import write_report
from ...ledger import Ledger
from ...registry import MODEL_SYSTEM, local_path
from ...views import judge

ID_FIELDS = {
    "run_id",
    "problem_id",
    "requirement_id",
    "candidate_id",
    "parent_id",
    "test_id",
    "execution_id",
    "gap_id",
    "mutant_id",
    "state_id",
    "option_id",
    "action_id",
    "request_id",
    "proposal_id",
}
ID_LISTS = {
    "target_ids",
    "requirement_ids",
    "evidence_ids",
    "supplied_test_ids",
    "authoritative_counterexample_ids",
    "audit_gap_ids",
    "previous_action_ids",
    "mutant_ids",
    "target_candidate_ids",
}


def augment_ids(episode, target):
    """One bijection for every actual identifier/reference; never rename code or templates."""
    mapping = {}

    def gather(value):
        if type(value) is dict:
            for key, item in value.items():
                if key in ID_FIELDS and type(item) is str:
                    mapping.setdefault(item, "id-" + uuid4().hex)
                elif key in ID_LISTS:
                    for identifier in item:
                        mapping.setdefault(identifier, "id-" + uuid4().hex)
                gather(item)
        elif type(value) is list:
            for item in value:
                gather(item)

    gather(episode)

    def remap(value):
        if type(value) is dict:
            return {k: remap(v) for k, v in value.items()}
        if type(value) is list:
            return [remap(v) for v in value]
        return mapping.get(value, value) if type(value) is str else value

    augmented = remap(episode)
    augmented_target = remap(target)
    checked(augmented, "EpisodeBundle")
    checked(augmented_target, "JudgeDraft")
    return augmented, augmented_target


def utility(correct, status, usage, starting_budget, caps, coefficient=0.05):
    inherited = {
        k: caps[k] - starting_budget[k] - (128 if k == "function_executions" else 0) for k in CAPS
    }
    deltas = {k: max(0, usage[k] - inherited[k]) for k in CAPS}
    normalized = sum(deltas[k] / caps[k] for k in CAPS if caps[k]) / sum(
        bool(v) for v in caps.values()
    )
    reward = (
        1 if status == "supported_patch" and correct else -1 if status == "supported_patch" else 0
    )
    return reward - coefficient * normalized, deltas


def label(rollout_directory, out, *, minimum_margin=0.001):
    directory, out = Path(rollout_directory).resolve(), Path(out).resolve()
    if local_path("artifacts") not in out.parents or out.exists():
        raise ValueError("Immutable ignored Judge corpus output required")
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest["runtime_mode"] != "live" or manifest["contains_final_assessment"]:
        raise ValueError("Actual native learning rollouts required")
    for name, digest in manifest["files"].items():
        if (
            Path(name).name != name
            or (directory / name).is_symlink()
            or file_hash(directory / name) != digest
        ):
            raise ValueError("Changed rollout evidence")
    rows = [json.loads(line) for line in (directory / "scored.jsonl").read_text().splitlines()]
    commitments = [
        json.loads(line) for line in (directory / "commitments.jsonl").read_text().splitlines()
    ]
    if len(rows) != len(commitments) or len(rows) != manifest["continuations"]:
        raise ValueError("Every scored alternative must have its original frozen commitment")
    grouped = defaultdict(list)
    for row, commitment in zip(rows, commitments, strict=True):
        if any(row.get(key) != value for key, value in commitment.items()):
            raise ValueError("Private scoring changed an alternative commitment")
        if row["split"] not in {"train", "validation"}:
            raise ValueError("Final assessment cannot create Judge labels")
        checked(row["response"], "RolloutResult")
        if (
            row["episode_hash"] != json_hash(row["request"]["episode"])
            or row["request"]["remaining_budget"]
            != row["request"]["episode"]["state"]["remaining_budget"]
            or row["selected_source_hash"] != row["response"]["selected_source_hash"]
        ):
            raise ValueError("Score/commit/state identity mismatch")
        path = Path(row["fork_ledger"]).resolve()
        if local_path("artifacts") not in path.parents or not (path / "ledger.sqlite3").exists():
            raise ValueError("An actual immutable continuation ledger is required")
        fork = Ledger(path)
        final = row["response"]["final_result"]
        snapshot = fork.snapshot(final["run_id"])
        from ...rollouts import run_result

        if (
            json_hash(snapshot) != row["final_snapshot_hash"]
            or run_result(snapshot) != final
            or snapshot["model_manifest_hash"] != manifest["registry_hash"]
        ):
            raise ValueError("Private label no longer joins its committed native result")
        with fork.connection() as db:
            caps = json.loads(
                db.execute("SELECT limits FROM runs WHERE id=?", (final["run_id"],)).fetchone()[
                    "limits"
                ]
            )
        measured, deltas = utility(
            row["correct"],
            final["status"],
            final["resource_usage"],
            row["request"]["remaining_budget"],
            caps,
        )
        if abs(row["utility"] - measured) > 1e-12 or row["continuation_usage"] != deltas:
            raise ValueError("Action reward must be recomputed from the actual future cost")
        selected = next(
            (
                c
                for c in snapshot["candidates"]
                if c["candidate_id"] == final["selected_candidate_id"]
            ),
            None,
        )
        if (selected["source"] if selected else None) != row["response"]["selected_source"]:
            raise ValueError("Selected source differs from the immutable fork")
        proof = row["private_assessment"]
        if final["status"] == "supported_patch":
            if proof is None:
                raise ValueError("Selected candidate requires actual private assessment")
            request, result = (
                checked(proof["request"], "ToolRequest"),
                checked(proof["result"], "ToolResult"),
            )
            tests = request["parameters"]["tests"]
            executions = [
                e for e in result["executions"] if e["candidate_id"] == selected["candidate_id"]
            ]
            correct = (
                result["status"] == "ok"
                and result["request_id"] == request["request_id"]
                and bool(tests)
                and {e["test_id"] for e in executions} == {t["test_id"] for t in tests}
                and all(
                    e["outcome"] == "pass"
                    and e["exception"] is None
                    and all(
                        not i["mutated"] and i["before_hash"] == i["after_hash"]
                        for i in e["input_effects"]
                    )
                    for e in executions
                )
            )
            if type(row["correct"]) is not bool or correct != row["correct"]:
                raise ValueError(
                    "Correctness label differs from the selected candidate's real executions"
                )
            candidates = request["parameters"]["candidates"]
            if len(candidates) != 1 or candidates[0]["source"] != selected["source"]:
                raise ValueError("Private assessment scored a different source")
        elif row["correct"] is not False or proof is not None:
            raise ValueError("Abstention cannot receive selected-patch correctness")
        grouped[(row["split"], row["episode_hash"])].append(row)
    accepted, excluded = [], []
    for (split, digest), trials in grouped.items():
        episode = trials[0]["request"]["episode"]
        options = defaultdict(list)
        for trial in trials:
            options[trial["request"]["forced_option_id"]].append(trial)
        if (
            any(
                len(v) != len(manifest["seeds"])
                or {r["request"]["seed"] for r in v} != set(manifest["seeds"])
                for v in options.values()
            )
            or len(options) < 2
            or any(
                r["response"]["final_result"]["status"]
                in {"infrastructure_error", "cancelled", "invalid_input"}
                for r in trials
            )
        ):
            excluded.append(
                {"episode_hash": digest, "reason": "incomplete or infrastructure alternatives"}
            )
            continue
        means = {
            key: sum(r["utility"] for r in values) / len(values) for key, values in options.items()
        }
        ranked = sorted(means, key=lambda key: (-means[key], key))
        margin = means[ranked[0]] - means[ranked[1]]
        if margin < minimum_margin:
            excluded.append(
                {"episode_hash": digest, "reason": "uncertain action tie", "margin": margin}
            )
            continue
        selected = next(
            o for o in episode["state"]["available_actions"] if o["option_id"] == ranked[0]
        )
        target = checked(
            {
                "state_id": episode["state"]["state_id"],
                "action_option_id": ranked[0],
                "evidence_ids": [],
                "rationale": selected["prerequisite_summary"],
            },
            "JudgeDraft",
        )
        # Models see only the actually compared menu, never alternative private rewards.
        training_episode = copy.deepcopy(episode)
        training_episode["state"]["available_actions"] = [
            o for o in episode["state"]["available_actions"] if o["option_id"] in options
        ]
        for augmentation in range(2):
            transformed, answer = augment_ids(training_episode, target)
            ids = {c["candidate_id"] for c in transformed["candidates"]}
            visible = [e for e in transformed["executions"] if e["candidate_id"] in ids]
            prompt = judge(
                transformed["state"], transformed["tests"], transformed["candidates"], visible
            )
            accepted.append(
                {
                    "split": split,
                    "base_problem_id": trials[0]["base_problem_id"],
                    "record_id": trials[0]["record_id"],
                    "episode_hash": digest,
                    "prompt": prompt,
                    "target": answer,
                    "augmentation": augmentation,
                    "label_proof": {
                        "measured_option_means": means,
                        "margin": margin,
                        "seeds": manifest["seeds"],
                    },
                    "note": "ID-renamed training view; never an executed fork or independent base.",
                }
            )
    out.mkdir(parents=True)
    stats = {}
    for split, name in (("train", "train.jsonl"), ("validation", "valid.jsonl")):
        subset = [r for r in accepted if r["split"] == split]
        if not subset:
            raise ValueError("Nonempty train and disjoint validation labels required")
        stats[split] = {
            "records": len(subset),
            "base_problems": len({r["base_problem_id"] for r in subset}),
            "unique_states": len({r["episode_hash"] for r in subset}),
        }
        (out / name).write_bytes(
            b"".join(
                canonical_json(
                    {
                        "messages": [
                            {"role": "system", "content": MODEL_SYSTEM},
                            {"role": "user", "content": r["prompt"]},
                            {"role": "assistant", "content": canonical_json(r["target"]).decode()},
                        ]
                    }
                )
                + b"\n"
                for r in subset
            )
        )
    train_bases = {r["base_problem_id"] for r in accepted if r["split"] == "train"}
    validation_bases = {r["base_problem_id"] for r in accepted if r["split"] == "validation"}
    if train_bases & validation_bases:
        raise ValueError("Judge base-problem split contamination")
    (out / "records.jsonl").write_bytes(b"".join(canonical_json(r) + b"\n" for r in accepted))
    record = {
        "version": "stage2.judge-labels.v1",
        "role": "judge",
        "runtime_mode": "live",
        "contains_final_assessment": False,
        "rollout_manifest_hash": file_hash(directory / "manifest.json"),
        "splits": stats,
        "files": {n: file_hash(out / n) for n in ("train.jsonl", "valid.jsonl", "records.jsonl")},
        "excluded": excluded,
        "tie_policy": {"minimum_margin": minimum_margin, "action": "exclude"},
        "limitations": [
            "Limited genuine states; two ID variants are not independent observations.",
            "Greedy seeds are repeated real runs, not independent random samples.",
            "Missing state categories or base-count targets remain missing.",
        ],
    }
    write_report(out / "manifest.json", record)
    return record
