"""A single adapter learns the same authorized repair, proposal and action tasks."""

import json
import random
from pathlib import Path

import yaml

from codejury.models.worker import file_hash

from ...contracts import canonical_json, json_hash
from ...data import learning_example, load_stage1, write_report
from ...registry import MODEL_SYSTEM, local_path


def read_lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def chat(prompt, target):
    return {
        "messages": [
            {"role": "system", "content": MODEL_SYSTEM},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": canonical_json(target).decode()},
        ]
    }


def repairs(directory, role, source_rows):
    directory = Path(directory)
    report = json.loads((directory / "report.json").read_text())
    session = json.loads((directory / "session.json").read_text())
    if report["phase"] != "full" or not report["updates_verified"] or not report["reload_verified"]:
        raise ValueError("General repair targets require genuine verified native role training")
    data = Path(session["data_directory"])
    if any(file_hash(data / name) != digest for name, digest in session["data_hashes"].items()):
        raise ValueError("Native repair exports changed")
    result = {}
    b_plan = json.loads((directory / "plan.json").read_text()) if role == "fixer_b" else None
    for split, name in (("train", "train.jsonl"), ("validation", "valid.jsonl")):
        if b_plan is None:
            records = read_lines(directory / "pools" / split / "records.jsonl")
        else:
            records = b_plan[split]
        examples = []
        expected = []
        for record in records:
            row = source_rows.get(record["record_id"])
            if (
                row is None
                or row["split"] != split
                or row["base_problem_id"] != record["base_problem_id"]
            ):
                raise ValueError("General repair target failed split/source rejoin")
            learning = learning_example(row)
            if record["target"]["source"] != learning["target"]["source"]:
                raise ValueError("General repair target changed the validated reference")
            prompt = record["a_prompt"] if role == "fixer_a" else record["prompt"]
            wanted = learning["a_prompt"] if role == "fixer_a" else learning["b_prompt"]
            if prompt != wanted:
                raise ValueError("General must inherit the actual role's runtime-visible prompt")
            messages = chat(prompt, record["target"])
            expected.append(messages)
            examples.append(
                {
                    "component": role,
                    "task": "repair",
                    "split": split,
                    "record_id": record["record_id"],
                    "base_problem_id": record["base_problem_id"],
                    "provenance": row["provenance"],
                    "chat": messages,
                }
            )
        if expected != read_lines(data / name):
            raise ValueError("General targets differ from the native training export")
        result[split] = examples
    return result, {
        "native_report_hash": file_hash(directory / "report.json"),
        "native_session_hash": file_hash(directory / "session.json"),
    }


def learned(directory, role):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        manifest["role"] != role
        or manifest["runtime_mode"] != "live"
        or manifest["contains_final_assessment"] is not False
    ):
        raise ValueError("General proposals/actions require actual final-free execution labels")
    for name, digest in manifest["files"].items():
        if Path(name).name != name or file_hash(directory / name) != digest:
            raise ValueError("Learned role corpus changed")
    records = read_lines(directory / "records.jsonl")
    if any(r["split"] not in {"train", "validation"} for r in records):
        raise ValueError("Final data cannot enter General learning")
    result = {}
    for split, name in (("train", "train.jsonl"), ("validation", "valid.jsonl")):
        subset = [r for r in records if r["split"] == split]
        expected = [chat(r["prompt"], r["target"]) for r in subset]
        if expected != read_lines(directory / name):
            raise ValueError("Learning label/chat rejoin failed")
        result[split] = [
            {
                "component": role,
                "task": "test" if role == "critic" else "action",
                "split": split,
                "record_id": r["record_id"],
                "base_problem_id": r["base_problem_id"],
                "source_record_hash": json_hash(r),
                "chat": c,
            }
            for r, c in zip(subset, expected, strict=True)
        ]
    return result, {"label_manifest_hash": file_hash(directory / "manifest.json")}


def build(config_path, out):
    cfg = yaml.safe_load(Path(config_path).read_text())
    if cfg["version"] != "stage2.general-learning.v1":
        raise ValueError("Unknown General learning configuration")
    out = Path(out).resolve()
    if local_path("artifacts") not in out.parents or out.exists():
        raise ValueError("Immutable ignored General corpus output required")
    source_manifest, source_rows = load_stage1(local_path(cfg["source_manifest"]))
    by_id = {r["record_id"]: r for r in source_rows}
    components, proofs = {}, {}
    for role, path in (("fixer_a", "a_training"), ("fixer_b", "b_training")):
        components[role], proofs[role] = repairs(local_path(cfg[path]), role, by_id)
    for role, path in (("critic", "critic_corpus"), ("judge", "judge_corpus")):
        components[role], proofs[role] = learned(local_path(cfg[path]), role)
    if set(cfg["component_records"]) != set(components):
        raise ValueError("Declare all four actual learned task opportunities")
    rng, rows = random.Random(cfg["seed"]), []
    for role, splits in components.items():
        count = cfg["component_records"][role]
        if type(count) is not int or not 1 <= count <= 2000:
            raise ValueError("Invalid bounded component sampling")
        pool = splits["train"]
        if not pool:
            raise ValueError("Empty learned component")
        # Preserve B's genuine weighting/duplicate records. Repetition is disclosed.
        chosen = []
        while len(chosen) < count:
            cycle = list(pool)
            rng.shuffle(cycle)
            chosen.extend(cycle[: count - len(chosen)])
        rows.extend(chosen)
        rows.extend(splits["validation"])
    train_bases = {r["base_problem_id"] for r in rows if r["split"] == "train"}
    valid_bases = {r["base_problem_id"] for r in rows if r["split"] == "validation"}
    if train_bases & valid_bases:
        raise ValueError("General base-problem split contamination")
    out.mkdir(parents=True)
    stats = {}
    for split, name in (("train", "train.jsonl"), ("validation", "valid.jsonl")):
        subset = [r for r in rows if r["split"] == split]
        (out / name).write_bytes(b"".join(canonical_json(r["chat"]) + b"\n" for r in subset))
        stats[split] = {
            "records": len(subset),
            "base_problems": len({r["base_problem_id"] for r in subset}),
            "component_counts": {k: sum(r["component"] == k for r in subset) for k in components},
        }
    (out / "records.jsonl").write_bytes(b"".join(canonical_json(r) + b"\n" for r in rows))
    manifest = {
        "version": "stage2.general-corpus.v1",
        "role": "general",
        "runtime_mode": "live",
        "contains_final_assessment": False,
        "source_manifest_hash": json_hash(source_manifest),
        "config_hash": json_hash(cfg),
        "component_proofs": proofs,
        "splits": stats,
        "files": {n: file_hash(out / n) for n in ("train.jsonl", "valid.jsonl", "records.jsonl")},
        "limitations": [
            "Repeated task records are not independent base problems.",
            "Configured update opportunity is not exact completion-token parity.",
            "Specialist tuning/pilot compute is reported separately.",
        ],
    }
    write_report(out / "manifest.json", manifest)
    return manifest
