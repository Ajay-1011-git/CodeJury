"""Offline train/validation access only. Final asset contents are never opened."""

import ast
import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

from codejury.properties import equal
from codejury.training.data import assert_disjoint, normalized

from ..contracts import canonical_json, checked, json_hash
from ..intake import prepare
from ..registry import MODEL_SYSTEM, local_path
from ..views import freeze_initial

FIELDS = {
    "record_id",
    "base_problem_id",
    "family_id",
    "split",
    "provenance",
    "contract",
    "domain",
    "buggy_source",
    "correct_source",
    "visible_tests",
    "assessment_tests",
    "failure_evidence",
    "response_target",
}


def config(path):
    value = yaml.safe_load(Path(path).read_text())
    required = {
        "version",
        "source_manifest",
        "runtime_config",
        "report_directory",
        "stage2_final_seal",
        "max_new_tokens",
        "seed",
        "training_enabled",
    }
    if (
        type(value) is not dict
        or set(value) not in (required, required | {"refresh"})
        or value["version"] != "stage2.fixer-a-validation.v1"
        or type(value["max_new_tokens"]) is not int
        or value["max_new_tokens"] != 1024
        or type(value["seed"]) is not int
        or value["seed"] < 0
        or type(value["training_enabled"]) is not bool
    ):
        raise ValueError("Invalid frozen A validation configuration")
    return value


def load_stage1(manifest_path):
    path = Path(manifest_path).resolve()
    data_root = path.parent.parent.resolve()
    manifest = json.loads(path.read_text())
    if manifest["seal_sha256"] != json_hash(manifest["assets"]):
        raise ValueError("Stage 1 split seal mismatch")
    allowed = {"train": "train_source/train.jsonl", "validation": "private/validation.jsonl"}
    selected = [a for a in manifest["assets"] if a["split"] in allowed]
    if Counter(a["split"] for a in selected) != {"train": 1, "validation": 1}:
        raise ValueError("Exactly one train and validation asset required")
    rows = []
    for asset in selected:
        if asset["path"] != allowed[asset["split"]]:
            raise ValueError("Asset path differs from allowlisted train/validation path")
        unresolved = data_root / asset["path"]
        if any(p.is_symlink() for p in (unresolved, *unresolved.parents)):
            raise ValueError("Dataset symlinks forbidden")
        content = unresolved.read_bytes()
        if hashlib.sha256(content).hexdigest() != asset["sha256"]:
            raise ValueError("Source corpus hash mismatch")
        records = [json.loads(line) for line in content.decode().splitlines()]
        if (
            len(records) != asset["records"]
            or len({r["base_problem_id"] for r in records}) != asset["base_problems"]
            or any(r["split"] != asset["split"] for r in records)
        ):
            raise ValueError("Asset count/split provenance mismatch")
        rows.extend(records)
    validate_records(rows)
    # Non-learning final manifest metadata is retained; no final bytes are read.
    return manifest, rows


def validate_records(rows):
    if len({r["record_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate record identity")
    for row in rows:
        if set(row) != FIELDS or row["split"] not in {"train", "validation"}:
            raise ValueError("Only strictly shaped train/validation records accepted")
        if row["response_target"].get("source") != row["correct_source"]:
            raise ValueError("SFT target differs from the sandbox-validated reference")
        provenance = row["provenance"]
        if (
            not provenance.get("license")
            or not provenance.get("author")
            or provenance.get("external_benchmark") is not False
            or provenance.get("kind") != "synthetic"
        ):
            raise ValueError("Original synthetic provenance/license required")
    assert_disjoint(rows)
    # A shared corruption such as `return 0` is not a shared base problem when
    # the contract/domain differ. Compare the complete runtime problem identity.
    sources = {}
    for row in rows:
        key = json_hash(
            {
                "source": normalized(row["buggy_source"]),
                "contract": " ".join(row["contract"].casefold().split()),
                "domain": row["domain"],
            }
        )
        if key in sources and sources[key] != row["split"]:
            raise ValueError("Normalized runtime problem leaks across splits")
        sources[key] = row["split"]


def domain(value):
    if value["kind"] == "integer":
        return {"kind": "integer", "min": value["min"], "max": value["max"]}
    if value["kind"] == "list_integer":
        return {
            "kind": "list",
            "item_domain": {"kind": "integer", "min": value["min"], "max": value["max"]},
            "min_length": value["min_length"],
            "max_length": value["max_length"],
        }
    raise ValueError("Unsupported Stage 1 domain conversion")


def runtime_example(row):
    """Convert allowed runtime facts. Reference targets/offline tests are absent."""
    if row["split"] not in {"train", "validation"}:
        raise ValueError("Only authorized learning pools can construct these views")
    target = ast.parse(row["buggy_source"]).body[0]
    args = target.args.args
    requirement_id = "r-" + row["base_problem_id"]
    create = {
        "schema_version": "stage2.v1",
        "source": row["buggy_source"],
        "function_name": target.name,
        "contract_text": row["contract"],
        "domain_schema": [
            {"name": arg.arg, "domain": domain(d)}
            for arg, d in zip(args, row["domain"], strict=True)
        ],
        "helper_interfaces": [],
        "requirements": [
            {
                "schema_version": "stage2.v1",
                "requirement_id": requirement_id,
                "description": row["contract"],
                "source": "reviewed_contract",
                "approval_status": "approved",
                "property_template_id": None,
                "parameters": {},
            }
        ],
        "supplied_tests": [
            {
                "schema_version": "stage2.v1",
                "test_id": t["test_id"],
                "inputs": t["args"],
                "expected": t["expected"],
                "requirement_ids": [requirement_id],
            }
            for t in row["visible_tests"]
        ],
        "allowed_dependencies": [],
        "resource_profile": "mac-standard-v1",
        "policy_mode": "fixed",
        "seed": 17,
    }
    problem, tests = prepare(create, problem_id="p-" + row["record_id"])
    for index, test in enumerate(tests):
        test["test_id"] = f"t-{row['record_id']}-{index}"
    problem["supplied_test_ids"] = [t["test_id"] for t in tests]
    return checked(problem, "Problem"), tests


def learning_example(row):
    problem, tests = runtime_example(row)
    views = freeze_initial(problem, tests)
    target = checked(
        {
            **row["response_target"],
            "requirement_ids": [r["requirement_id"] for r in problem["requirements"]],
            "suspected_sites": [],
            "suggested_families": [],
        },
        "RepairDraft",
    )
    return {
        "record_id": row["record_id"],
        "base_problem_id": row["base_problem_id"],
        "family_id": row["family_id"],
        "split": row["split"],
        "provenance": row["provenance"],
        "a_prompt": views.a,
        "b_prompt": views.b,
        "view_config_hash": views.view_config_hash,
        "target": target,
    }


def audit(config_path, *, runner=None):
    settings = config(config_path)
    manifest, rows = load_stage1(local_path(settings["source_manifest"]))
    examples = [learning_example(row) for row in rows]
    failures, calls, cache = [], 0, {}
    if runner is not None:
        runner.ready()
        for row in rows:
            tests = row["visible_tests"] + row["assessment_tests"]
            key = json_hash({"source": row["correct_source"], "tests": tests})
            if key not in cache:
                cache[key] = runner.execute_many(
                    row["correct_source"], "solve", [t["args"] for t in tests]
                )
                calls += len(tests)
            if not all(
                not result.exception_type
                and not result.input_mutated
                and equal(result.actual_output, t["expected"])
                for result, t in zip(cache[key], tests, strict=True)
            ):
                failures.append(row["record_id"])
    summary = {
        split: {
            "records": sum(r["split"] == split for r in rows),
            "base_problems": len({r["base_problem_id"] for r in rows if r["split"] == split}),
            "families": len({r["family_id"] for r in rows if r["split"] == split}),
        }
        for split in ("train", "validation")
    }
    return {
        "status": "passed" if not failures else "failed",
        "pools": summary,
        "source_manifest_hash": json_hash(manifest),
        "example_hash": json_hash(examples),
        "final_contents_opened": False,
        "runtime_target_leak": False,
        "reference_validation": "sandbox" if runner is not None else "not_run",
        "reference_failures": failures,
        "function_executions": calls,
        "final_stage2_seal_present": local_path(settings["stage2_final_seal"]).is_file(),
        "training_started": False,
        "notes": [
            "Stage 1 assessment/final assets excluded before opening content.",
            "Preserved original project license text; no new redistribution grant implied.",
            "Only integer/list domains exist; expanded Stage 2 pools remain uncollected.",
            "Views omit reference source and offline assessment tests.",
        ],
    }


def write_report(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_json(value) + b"\n")


def final_pool_metadata(config_path):
    """Adopt the benchmark owner's public seal; never open hidden final assets."""
    settings = config(config_path)
    path = local_path(settings["stage2_final_seal"])
    if not path.is_file() or path.is_symlink():
        raise ValueError("Benchmark owner's public final-pool manifest is absent")
    value = json.loads(path.read_text())
    source_path = local_path(settings["source_manifest"])
    source = json.loads(source_path.read_text())
    derived = value.get("derived_from", {})
    final = value.get("splits", {}).get("final_assessment", {})
    original = [a for a in source["assets"] if a["split"] == "stage2_final"]
    if (
        value.get("schema") != "stage2-split-manifest.v1"
        or len(original) != 1
        or json_hash(source["assets"]) != source["seal_sha256"]
        or derived.get("manifest") != settings["source_manifest"]
        or derived.get("sha256") != hashlib.sha256(source_path.read_bytes()).hexdigest()
        or derived.get("stage1_seal_sha256") != source["seal_sha256"]
        or final.get("inspected_in_development") is not False
        or final.get("role") != "final"
        or final.get("asset") != original[0]["path"]
        or final.get("sha256") != original[0]["sha256"]
        or type(final.get("base_problems")) is not int
        or type(final.get("records")) is not int
        or final["base_problems"] != original[0]["base_problems"]
        or final["records"] != original[0]["records"]
        or final["base_problems"] < 1
    ):
        raise ValueError("Public final seal does not match the frozen source split metadata")
    return {
        "status": "sealed_metadata_verified",
        "manifest_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
        "final_base_problems": final["base_problems"],
        "final_records": final["records"],
        "final_contents_opened": False,
        "limited_evidence": final["base_problems"] < 200,
        "scope": "Public metadata and inherited Stage 1 seal; private final assessment remains "
        "benchmark-owner-only. This is not a final benchmark result.",
    }


def export_pools(config_path, directory, verified_report, *, base_revision_hash):
    """Export existing authorized pools, retaining references only in offline artifacts."""
    settings = config(config_path)
    manifest, rows = load_stage1(local_path(settings["source_manifest"]))
    examples = [learning_example(row) for row in rows]
    proof = json.loads(Path(verified_report).read_text())
    if (
        proof["status"] != "passed"
        or proof["reference_validation"] != "sandbox"
        or proof["reference_failures"]
        or proof["function_executions"] < 1
        or proof["source_manifest_hash"] != json_hash(manifest)
        or proof["example_hash"] != json_hash(examples)
    ):
        raise ValueError("Matching real reference validation is required before export")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    manifests = []
    for split in ("train", "validation"):
        pool = [e for e in examples if e["split"] == split]
        root = directory / split
        root.mkdir()
        files = []
        chats = [
            {
                "messages": [
                    {"role": "system", "content": MODEL_SYSTEM},
                    {"role": "user", "content": e["a_prompt"]},
                    {"role": "assistant", "content": canonical_json(e["target"]).decode()},
                ]
            }
            for e in pool
        ]
        for name, values in (("records.jsonl", pool), ("a-sft.jsonl", chats)):
            content = b"".join(canonical_json(value) + b"\n" for value in values)
            (root / name).write_bytes(content)
            files.append(
                {
                    "relative_path": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
            )
        exported = checked(
            {
                "schema_version": "stage2.v1",
                "exchange_id": "stage1-to-stage2-" + split,
                "owner": "ajay",
                "kind": "training_corpus",
                "base_revision_hash": base_revision_hash,
                "split": split,
                "files": files,
                "record_count": len(pool),
                "base_problem_count": len({e["base_problem_id"] for e in pool}),
                "contains_hidden_assessment": False,
                "note": "Authorized offline reference targets; preserve license/provenance. "
                "No final contents. Separate authorized offline training/validation pools.",
            },
            "ArtifactManifest",
        )
        write_report(root / "manifest.json", exported)
        manifests.append(exported)
    return manifests
