"""Private label-side assessment and reviewed experiments on genuine frozen episodes."""

import json
from collections import Counter
from pathlib import Path
from threading import Event
from uuid import uuid4

from codejury.models.worker import file_hash
from codejury.stage2_core.budgets import CAPS
from codejury.stage2_core.contracts import CheckedToolPort, canonical_json, checked, json_hash
from codejury.stage2_core.controller import draft, records
from codejury.stage2_core.controller.bootstrap import critic_input_prompt, reviewed_proposal
from codejury.stage2_core.controller.inputs import runtime_input
from codejury.stage2_core.data import load_stage1, write_report
from codejury.stage2_core.registry import MODEL_SYSTEM, local_path

MODES = ("discriminate", "challenge_agreement", "audit_gap", "validate_revision")


def authorized_failure(result):
    hard_ids = {
        t["test_id"]
        for t in result["tests"]
        if t["domain_valid"] and t["oracle_status"] == "authoritative"
    }
    return any(
        e["test_id"] in hard_ids and e["outcome"] in {"fail", "error", "timeout"}
        for e in result["executions"]
    )


def request(problem, parameters):
    identifier = "critic-label-" + uuid4().hex
    return checked(
        {
            "schema_version": "stage2.v1",
            "request_id": identifier,
            "id_prefix": identifier,
            "run_id": identifier,
            "problem": problem,
            "parameters": parameters,
            "remaining_budget": CAPS,
        },
        "ToolRequest",
    )


def investigation(problem, tests, candidates, target):
    return request(
        problem,
        {
            "operation": "investigate",
            "candidates": [draft(c) for c in candidates],
            "existing_tests": tests,
            "max_inputs": 2,
            "proposal": checked(
                {
                    "schema_version": "stage2.v1",
                    "proposal_id": "proposal-" + uuid4().hex,
                    **{k: v for k, v in target.items() if k != "mode"},
                },
                "TestProposal",
            ),
        },
    )


def assess(problem, candidates, row, tool, cancel):
    """Offline train/validation labels; results never enter runtime evidence or prompts."""
    if row["split"] not in {"train", "validation"}:
        raise ValueError("Final assessment cannot supply learning labels")
    tests = [
        checked(
            {
                "schema_version": "stage2.v1",
                "test_id": "private-" + str(index),
                "input_codec_version": "json.v1",
                "inputs": t["args"],
                "related_inputs": None,
                "oracle_spec": {"kind": "literal", "expected": t["expected"]},
                "oracle_status": "authoritative",
                "oracle_source": "user",
                "domain_valid": True,
                "requirement_ids": [r["requirement_id"] for r in problem["requirements"]],
                "provenance": "supplied",
            },
            "TestCase",
        )
        for index, t in enumerate(row["assessment_tests"])
    ]
    req = request(
        problem,
        {
            "operation": "evaluate",
            "candidates": [draft(c) for c in candidates],
            "tests": tests,
            "stop_on_first_hard_failure": False,
        },
    )
    result = CheckedToolPort(tool).call(req, cancel)
    if result["status"] != "ok" or cancel.is_set():
        raise RuntimeError("Private assessment failed; no labels admitted")
    labels = {}
    for candidate in candidates:
        own = [e for e in result["executions"] if e["candidate_id"] == candidate["candidate_id"]]
        labels[candidate["candidate_id"]] = (
            bool(tests)
            and {e["test_id"] for e in own} == {t["test_id"] for t in tests}
            and all(
                e["outcome"] == "pass"
                and e["exception"] is None
                and all(
                    not i["mutated"] and i["before_hash"] == i["after_hash"]
                    for i in e["input_effects"]
                )
                for e in own
            )
        )
    return labels, {"request": req, "result": result}


def rejoin(ledger, run_id, source_manifest, rows):
    snapshot = ledger.snapshot(run_id)
    metadata = records(ledger, run_id, "metadata")
    if (
        snapshot["runtime_mode"] != "live"
        or snapshot["status"] not in {"supported_patch", "unresolved"}
        or len(metadata) != 1
        or metadata[0]["mode"] != "live"
    ):
        raise ValueError("Critic corpus requires terminal native/Docker runs")
    meta = metadata[0]
    source = meta["provenance"]
    if type(source) is not dict or source.get("split") not in {"train", "validation"}:
        raise ValueError("Only declared learning split provenance is accepted")
    row = rows.get(source["record_id"])
    if (
        row is None
        or row["split"] != source["split"]
        or row["base_problem_id"] != source["base_problem_id"]
        or source["source_manifest_hash"] != json_hash(source_manifest)
        or runtime_input(row)[0] != snapshot["problem"]
        or source["runtime_input_hash"] != json_hash(snapshot["problem"])
        or json_hash(meta["profile"]) != snapshot["profile_hash"]
        or meta["model_manifest_hash"] != snapshot["model_manifest_hash"]
    ):
        raise ValueError("Frozen episode/source/profile identities do not rejoin")
    with ledger.connection() as db:
        transports = list(
            db.execute("SELECT status,response FROM requests WHERE run_id=?", (run_id,))
        )
    if not transports or any(
        t["status"] != "settled" or not t["response"] or json.loads(t["response"])["status"] != "ok"
        for t in transports
    ):
        raise ValueError("Incomplete transport evidence is not training data")
    episodes = [checked(e, "EpisodeBundle") for e in records(ledger, run_id, "episode")]
    if not episodes or any(e["problem"] != snapshot["problem"] for e in episodes):
        raise ValueError("Missing or mismatched frozen runtime states")
    return snapshot, episodes, row


def collect(ledger, reports, tool, out, *, seed=17):
    out = Path(out).resolve()
    if local_path("artifacts") not in out.parents:
        raise ValueError("Private targets/receipts must stay under ignored artifacts")
    if out.exists():
        raise FileExistsError("Critic corpus is immutable")
    source_manifest, source_rows = load_stage1(local_path("data/manifests/stage1.json"))
    rows = {r["record_id"]: r for r in source_rows}
    run_ids = [r["run_id"] for p in reports for r in json.loads(Path(p).read_text())["runs"]]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("Duplicate run IDs")
    # Rejoin every input before publishing any label or admitting it to native training.
    frozen = [rejoin(ledger, rid, source_manifest, rows) for rid in run_ids]
    out.mkdir(parents=True)
    cancel = Event()
    data, receipts, rejected, skipped = [], [], [], []
    for snapshot, episodes, row in frozen:
        candidates = [c for c in snapshot["candidates"] if c["origin"] != "original"]
        if not candidates:
            skipped.append({"run_id": snapshot["run_id"], "reason": "no genuine repair candidate"})
            continue
        labels, proof = assess(snapshot["problem"], candidates, row, tool, cancel)
        receipts.append({"kind": "private_assessment", "run_id": snapshot["run_id"], **proof})
        # A genuine state after audit is preferred; no final facts are backfilled into it.
        episode = next((e for e in episodes if e["audit_gaps"]), episodes[0])
        available = [c for c in episode["candidates"] if c["origin"] != "original"][:2]
        if not available:
            continue
        modes = [
            m
            for m in MODES
            if m != "validate_revision" or any(c["origin"].endswith("_revision") for c in available)
        ]
        for mode in modes:
            targets = [
                c
                for c in available
                if mode != "validate_revision" or c["origin"].endswith("_revision")
            ]
            correct = all(labels[c["candidate_id"]] for c in targets)
            target = reviewed_proposal(
                episode["problem"],
                [c["candidate_id"] for c in targets],
                mode,
                seed,
                observation=correct,
            )
            own = [
                e
                for e in episode["executions"]
                if e["candidate_id"] in target["target_candidate_ids"]
            ]
            prompt = critic_input_prompt(
                episode["problem"],
                episode["tests"],
                targets,
                own,
                mode,
                seed,
                gaps=episode["audit_gaps"],
                trace_reader=ledger.read_object,
            )
            req = investigation(episode["problem"], episode["tests"], targets, target)
            result = CheckedToolPort(tool).call(req, cancel)
            receipts.append(
                {
                    "kind": "reviewed_experiment",
                    "run_id": snapshot["run_id"],
                    "request": req,
                    "result": result,
                }
            )
            if result["status"] != "ok" or not result["executions"]:
                rejected.append(
                    {"run_id": snapshot["run_id"], "mode": mode, "reason": result["status"]}
                )
                continue
            false_hard = correct and authorized_failure(result)
            if false_hard or any(not t["domain_valid"] for t in result["tests"]):
                rejected.append(
                    {"run_id": snapshot["run_id"], "mode": mode, "reason": "false rejection/domain"}
                )
                continue
            item = {
                "run_id": snapshot["run_id"],
                "record_id": row["record_id"],
                "base_problem_id": row["base_problem_id"],
                "family_id": row["family_id"],
                "split": row["split"],
                "provenance": row["provenance"],
                "episode_hash": json_hash(episode),
                "episode": episode,
                "mode": mode,
                "correct_case": correct,
                "invalid_context": False,
                "prompt": prompt,
                "target": target,
                "receipt_hash": json_hash(receipts[-1]),
                "authorized_failure_yield": authorized_failure(result),
                "label_source": "reviewed offline experiment on genuine student state",
            }
            data.append(item)
            if mode == modes[0]:
                # Disclosed augmentation: a genuinely rejected, deliberately unknown scope.
                # It is not counted as another student failure or another base problem.
                invalid = {**target, "requirement_ids": ["unknown-reviewed-requirement"]}
                bad_req = investigation(episode["problem"], episode["tests"], targets, invalid)
                bad = CheckedToolPort(tool).call(bad_req, cancel)
                if bad["status"] != "invalid_input":
                    raise RuntimeError("Unknown-scope proposal was not rejected")
                receipts.append(
                    {
                        "kind": "synthetic_invalid_proposal",
                        "run_id": snapshot["run_id"],
                        "request": bad_req,
                        "result": bad,
                    }
                )
                fallback = reviewed_proposal(
                    episode["problem"],
                    [c["candidate_id"] for c in targets],
                    mode,
                    seed,
                    observation=True,
                )
                fallback_req = investigation(
                    episode["problem"], episode["tests"], targets, fallback
                )
                fallback_result = CheckedToolPort(tool).call(fallback_req, cancel)
                if fallback_result["status"] != "ok" or not fallback_result["executions"]:
                    raise RuntimeError("No-objection correction failed execution filtering")
                receipts.append(
                    {
                        "kind": "invalid_context_correction",
                        "run_id": snapshot["run_id"],
                        "request": fallback_req,
                        "result": fallback_result,
                    }
                )
                data.append(
                    {
                        **item,
                        "invalid_context": True,
                        "target": fallback,
                        "authorized_failure_yield": False,
                        "receipt_hash": json_hash(receipts[-1]),
                        "prompt": prompt
                        + "\nPreviously rejected proposal (scope is unapproved):\n"
                        + canonical_json(invalid).decode()
                        + "\nUse a legal observation; do not repeat this scope.",
                        "label_source": "synthetic invalid-proposal correction "
                        "on genuine student state",
                    }
                )
        if json_hash(ledger.snapshot(snapshot["run_id"])) != json_hash(snapshot):
            raise RuntimeError("Offline label job changed a frozen runtime run")
        print(
            json.dumps(
                {"record_id": row["record_id"], "accepted": len(data), "rejected": len(rejected)}
            ),
            flush=True,
        )
    stats = {}
    for split, filename in (("train", "train.jsonl"), ("validation", "valid.jsonl")):
        selected = [r for r in data if r["split"] == split]
        if not selected:
            raise ValueError("Both genuine train and validation episodes are required")
        stats[split] = {
            "records": len(selected),
            "base_problems": len({r["base_problem_id"] for r in selected}),
            "correct_cases": sum(r["correct_case"] for r in selected),
            "invalid_contexts": sum(r["invalid_context"] for r in selected),
            "modes": dict(Counter(r["mode"] for r in selected)),
        }
        (out / filename).write_bytes(
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
                for r in selected
            )
        )
    (out / "records.jsonl").write_bytes(b"".join(canonical_json(r) + b"\n" for r in data))
    (out / "receipts.jsonl").write_bytes(b"".join(canonical_json(r) + b"\n" for r in receipts))
    manifest = {
        "version": "stage2.critic-data.v1",
        "role": "critic",
        "runtime_mode": "live",
        "contains_final_assessment": False,
        "source_manifest_hash": json_hash(source_manifest),
        "reports": {str(Path(p).resolve()): file_hash(p) for p in reports},
        "splits": stats,
        "files": {
            n: file_hash(out / n)
            for n in ("train.jsonl", "valid.jsonl", "records.jsonl", "receipts.jsonl")
        },
        "rejected": rejected,
        "skipped": skipped,
        "limitations": [
            "Small synthetic source pool; states are not independent bases.",
            "Reviewed targets are not model outputs or measured Judge action labels.",
            "Only actual revisions supply validate_revision cases; missing modes remain missing.",
            "Invalid contexts are disclosed proposal augmentations, not student failures.",
        ],
    }
    write_report(out / "manifest.json", manifest)
    return manifest


def validate(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        if (
            Path(name).name != name
            or (directory / name).is_symlink()
            or file_hash(directory / name) != digest
        ):
            raise ValueError("Unsafe path or changed corpus bytes")
    rows = [json.loads(line) for line in (directory / "records.jsonl").read_text().splitlines()]
    bases = {
        s: {r["base_problem_id"] for r in rows if r["split"] == s} for s in ("train", "validation")
    }
    if bases["train"] & bases["validation"] or any(r["split"] not in bases for r in rows):
        raise ValueError("Learning split contamination")
    for row in rows:
        checked(row["target"], "CriticDraft")
        if row["target"]["oracle_spec"]["kind"] == "literal":
            raise ValueError("Training literals cannot become runtime authority")
        if row["episode_hash"] != json_hash(checked(row["episode"], "EpisodeBundle")):
            raise ValueError("Frozen episode changed")
    stats = manifest["splits"]["train"]
    return {
        "records": len(rows),
        "files_verified": True,
        "split_disjoint": True,
        "correct_mix_target_met": stats["correct_cases"] >= 0.25 * stats["records"],
        "invalid_mix_target_met": stats["invalid_contexts"] >= 0.1 * stats["records"],
        "mode_coverage": sorted(stats["modes"]),
        "manifest_hash": file_hash(directory / "manifest.json"),
    }
