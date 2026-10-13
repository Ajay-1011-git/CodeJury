"""Share the actual verified teacher A opportunities with the General comparator."""

import json
from pathlib import Path

from codejury.models.worker import file_hash

from ...contracts import json_hash
from ...data import learning_example
from ...registry import Registry, local_path


def opportunities(cfg, source_rows, registry_path):
    if set(cfg) != {"corpus", "training_report", "selected_step", "records"}:
        raise ValueError("Unknown teacher opportunity fields")
    corpus = local_path(cfg["corpus"])
    report_path = local_path(cfg["training_report"])
    if (
        local_path("artifacts") not in corpus.parents
        or local_path("artifacts") not in report_path.parents
    ):
        raise ValueError("Teacher opportunities must use private immutable artifacts")
    report = json.loads(report_path.read_text())
    manifest = json.loads((corpus / "manifest.json").read_text())
    if (
        manifest["role"] != "fixer_a"
        or manifest["runtime_mode"] != "live"
        or manifest["contains_final_assessment"] is not False
        or report["role"] != "fixer_a"
        or report["phase"] != "full"
        or not report["updates_verified"]
        or not report["reload_verified"]
        or report["data_manifest_hash"] != file_hash(corpus / "manifest.json")
    ):
        raise ValueError("Actual verified teacher A training is required")
    checkpoint = next((c for c in report["candidates"] if c["step"] == cfg["selected_step"]), None)
    if checkpoint is None or Registry(Path(checkpoint["registry_path"])).identity(
        "fixer_a"
    ) != Registry(Path(registry_path)).identity("fixer_a"):
        raise ValueError("Teacher opportunities differ from the deployed A candidate")
    for name, digest in manifest["files"].items():
        if Path(name).name != name or file_hash(corpus / name) != digest:
            raise ValueError("Teacher corpus changed")
    for name, digest in manifest["teacher_receipts"].items():
        if file_hash(local_path(name)) != digest:
            raise ValueError("Teacher verification receipt changed")
    metadata = json.loads((corpus / "records.json").read_text())
    chats = [json.loads(line) for line in (corpus / "train.jsonl").read_text().splitlines()]
    if len(metadata) != len(chats) or cfg["records"] != len(chats):
        raise ValueError("General must receive every teacher pilot training opportunity")
    rows = []
    for record, chat in zip(metadata, chats, strict=True):
        source = source_rows.get(record["record_id"])
        if (
            source is None
            or source["split"] != record["split"]
            or record["split"] != "train"
            or record["base_problem_id"] != source["base_problem_id"]
            or chat["messages"][1]["content"] != learning_example(source)["a_prompt"]
        ):
            raise ValueError("Teacher opportunity source/view/split mismatch")
        target = json.loads(chat["messages"][2]["content"])
        if record["target_hash"] != json_hash(target):
            raise ValueError("Teacher opportunity target mismatch")
        if record["origin"] == "groq_verified":
            receipt = json.loads(local_path(record["teacher_receipt"]).read_text())
            if receipt["status"] != "accepted" or receipt["draft"] != target:
                raise ValueError("Unverified teacher target")
        elif (
            record["origin"] != "existing_verified" or target != learning_example(source)["target"]
        ):
            raise ValueError("Unverified replay target")
        rows.append(
            {
                "component": "fixer_a",
                "task": "repair",
                "split": "train",
                "record_id": record["record_id"],
                "base_problem_id": record["base_problem_id"],
                "provenance": {"original": source["provenance"], "origin": record["origin"]},
                "source_record_hash": json_hash(record),
                "chat": chat,
            }
        )
    return rows, {
        "teacher_manifest_hash": file_hash(corpus / "manifest.json"),
        "native_report_hash": file_hash(report_path),
        "selected_step": cfg["selected_step"],
        "opportunities": len(rows),
        "unique_teacher_targets": manifest["mix"]["unique_teacher_targets"],
    }
