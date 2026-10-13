"""Immutable 60/40 replay export; sampling counts are distinct from unique proposals."""

import json
import random
from pathlib import Path

from codejury.models.worker import file_hash

from ..contracts import canonical_json, json_hash
from ..data import learning_example, write_report
from ..registry import local_path
from .collect import source
from .validate import chat


def mix(existing, teacher, *, count=100, seed=17):
    if count != 100 or len(existing) < 60 or len(teacher) < 10:
        raise ValueError(
            "Pilot needs 60 original records and at least ten verified teacher records"
        )
    if any(row["split"] != "train" for row in existing + teacher):
        raise ValueError("Training mix contains non-TRAIN provenance")
    rng = random.Random(seed)
    # Include every original base before additional corruptions, reducing forgetting.
    bases = {}
    for row in sorted(existing, key=lambda r: r["record_id"]):
        bases.setdefault(row["base_problem_id"], []).append(row)
    old = [rows.pop(0) for rows in bases.values()]
    remaining = [r for rows in bases.values() for r in rows]
    rng.shuffle(remaining)
    old = (old + remaining)[:60]
    new = []
    while len(new) < 40:
        round_rows = list(teacher)
        rng.shuffle(round_rows)
        new.extend(round_rows[: 40 - len(new)])
    result = [dict(row, origin="existing_verified") for row in old]
    result += [dict(row, origin="groq_verified") for row in new]
    rng.shuffle(result)
    return result


def export(cfg, out):
    manifest, rows, source_hash = source(cfg)
    root = local_path(cfg["artifact_root"])
    proof_path = local_path("artifacts/stage2_core/fixer-a-validation/data-sandbox.json")
    proof = json.loads(proof_path.read_text())
    if (
        proof["status"] != "passed"
        or proof["reference_validation"] != "sandbox"
        or proof["reference_failures"]
        or proof["source_manifest_hash"] != json_hash(manifest)
        or proof["example_hash"] != json_hash([learning_example(row) for row in rows])
    ):
        raise ValueError("Original replay corpus lacks matching sandbox reference proof")
    source_rows = {r["record_id"]: r for r in rows}
    teacher = []
    receipt_hashes = {}
    for path in sorted((root / "validated-v1").glob("*.json")):
        if path.name.startswith("summary-"):
            continue
        receipt = json.loads(path.read_text())
        if receipt["status"] != "accepted":
            continue
        lineage = receipt["lineage"]
        row = source_rows[lineage["record_id"]]
        if (
            row["split"] != "train"
            or lineage["record_hash"] != json_hash(row)
            or lineage["source_manifest_hash"] != source_hash
            or file_hash(Path(receipt["proposal_path"])) != receipt["proposal_hash"]
            or receipt["tokens"]["runtime_prefix_matches"] is not True
        ):
            raise ValueError("Teacher receipt lineage changed")
        receipt_hashes[str(path)] = file_hash(path)
        teacher.append(
            {
                **row,
                "response_target": receipt["draft"],
                "teacher_receipt": str(path),
                "teacher_request": receipt["proposal_hash"],
            }
        )
    if len({r["base_problem_id"] for r in teacher}) < 10:
        raise ValueError("Too few verified teacher bases for the declared pilot")
    mixed = mix([r for r in rows if r["split"] == "train"], teacher)
    validation = [r for r in rows if r["split"] == "validation"]
    directory = Path(out).resolve()
    if local_path("artifacts") not in directory.parents:
        raise ValueError("Teacher targets must remain in ignored artifacts")
    directory.mkdir(parents=True, exist_ok=False)

    def target(row):
        return (
            row["response_target"]
            if row.get("origin") == "groq_verified"
            else learning_example(row)["target"]
        )

    for name, pool in [("train.jsonl", mixed), ("valid.jsonl", validation)]:
        content = b"".join(canonical_json(chat(r, target(r))) + b"\n" for r in pool)
        (directory / name).write_bytes(content)
    records = [
        {
            "record_id": r["record_id"],
            "base_problem_id": r["base_problem_id"],
            "split": r["split"],
            "origin": r["origin"],
            "target_hash": json_hash(target(r)),
            "teacher_receipt": r.get("teacher_receipt"),
        }
        for r in mixed
    ]
    write_report(directory / "records.json", records)
    result = {
        "version": "stage2.teacher-corpus.v1",
        "role": "fixer_a",
        "runtime_mode": "live",
        "contains_final_assessment": False,
        "source_manifest_hash": source_hash,
        "reference_proof_hash": file_hash(proof_path),
        "teacher_receipts": receipt_hashes,
        "mix": {
            "existing_samples": 60,
            "teacher_samples": 40,
            "unique_teacher_targets": len(teacher),
            "oversampling_disclosed": True,
        },
        "splits": {
            "train": {"records": 100, "base_problems": len({r["base_problem_id"] for r in mixed})},
            "validation": {
                "records": len(validation),
                "base_problems": len({r["base_problem_id"] for r in validation}),
            },
        },
        "files": {
            n: file_hash(directory / n) for n in ["train.jsonl", "valid.jsonl", "records.json"]
        },
    }
    write_report(directory / "manifest.json", result)
    return result
