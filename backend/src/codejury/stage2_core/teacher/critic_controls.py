"""Correct-target controls from actual current candidates, with real local receipts."""

import json
from collections import Counter
from pathlib import Path
from threading import Event

from codejury.models.worker import file_hash
from codejury.stage2_tools.critic_training.data import authorized_failure, investigation, validate
from codejury.stage2_tools.factory import make_tool_port

from ..contracts import CheckedToolPort, canonical_json, json_hash
from ..controller.bootstrap import critic_input_prompt, reviewed_proposal
from ..data import write_report
from ..ledger import Ledger
from ..registry import MODEL_SYSTEM, local_path


def controls(corpus, ledger_path, tool_config, out):
    corpus, out = Path(corpus), Path(out)
    validate(corpus)
    if out.exists():
        raise ValueError("Correct-control corpus is immutable")
    manifest = json.loads((corpus / "manifest.json").read_text())
    rows = [json.loads(line) for line in (corpus / "records.jsonl").read_text().splitlines()]
    receipts = [json.loads(line) for line in (corpus / "receipts.jsonl").read_text().splitlines()]
    assessments = {r["run_id"]: r for r in receipts if r["kind"] == "private_assessment"}
    selected, seen = [], set()
    ledger = Ledger(Path(ledger_path))
    tool = make_tool_port(local_path(tool_config))
    tool.sandbox.ready()
    new_receipts = []
    for row in rows:
        if row["split"] != "validation" or row["invalid_context"] or row["run_id"] in seen:
            continue
        seen.add(row["run_id"])
        assessment = assessments[row["run_id"]]
        expected_ids = {t["test_id"] for t in assessment["request"]["parameters"]["tests"]}
        episode = row["episode"]
        for candidate in episode["candidates"]:
            if candidate["origin"] == "original":
                continue
            cid = candidate["candidate_id"]
            own = [e for e in assessment["result"]["executions"] if e["candidate_id"] == cid]
            correct = (
                bool(expected_ids)
                and {e["test_id"] for e in own} == expected_ids
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
            if not correct:
                continue
            visible = [e for e in episode["executions"] if e["candidate_id"] == cid]
            mode = "discriminate"
            target = reviewed_proposal(episode["problem"], [cid], mode, 17, observation=True)
            prompt = critic_input_prompt(
                episode["problem"],
                episode["tests"],
                [candidate],
                visible,
                mode,
                17,
                gaps=episode["audit_gaps"],
                trace_reader=ledger.read_object,
            )
            request = investigation(episode["problem"], episode["tests"], [candidate], target)
            result = CheckedToolPort(tool).call(request, Event())
            if result["status"] != "ok" or not result["executions"] or authorized_failure(result):
                raise ValueError("Reviewed correct-target control failed actual filtering")
            receipt = {
                "kind": "current_correct_candidate_subset",
                "run_id": row["run_id"],
                "classification_receipt_hash": json_hash(assessment),
                "request": request,
                "result": result,
            }
            new_receipts.append(receipt)
            selected.append(
                {
                    **row,
                    "mode": mode,
                    "correct_case": True,
                    "invalid_context": False,
                    "prompt": prompt,
                    "target": target,
                    "receipt_hash": json_hash(receipt),
                    "authorized_failure_yield": False,
                    "label_source": "Actual current candidate subset passing trusted local "
                    "assessment; no reference source inserted in prompt",
                }
            )
    if not selected:
        raise ValueError("No actual correct candidate controls; compatibility remains unproven")
    data = [r for r in rows if r["split"] == "train"] + selected
    out.mkdir(parents=True)
    stats = {}
    for split, name in [("train", "train.jsonl"), ("validation", "valid.jsonl")]:
        subset = [r for r in data if r["split"] == split]
        stats[split] = {
            "records": len(subset),
            "base_problems": len({r["base_problem_id"] for r in subset}),
            "correct_cases": sum(r["correct_case"] for r in subset),
            "invalid_contexts": sum(r["invalid_context"] for r in subset),
            "modes": dict(Counter(r["mode"] for r in subset)),
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
    (out / "records.jsonl").write_bytes(b"".join(canonical_json(r) + b"\n" for r in data))
    (out / "receipts.jsonl").write_bytes(
        b"".join(canonical_json(r) + b"\n" for r in receipts + new_receipts)
    )
    result = {
        **manifest,
        "splits": stats,
        "files": {
            n: file_hash(out / n)
            for n in ("train.jsonl", "valid.jsonl", "records.jsonl", "receipts.jsonl")
        },
        "derived_from_manifest_hash": file_hash(corpus / "manifest.json"),
        "control_scope": "Validation-only subset of actually generated candidates; approved "
        "runtime scope, no correctness indicator or hidden test in prompt",
    }
    write_report(out / "manifest.json", result)
    validate(out)
    return result
