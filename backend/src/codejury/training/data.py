"Offline manifest integrity, executable validation, and prompt/target separation."

import ast
import hashlib
import json
import runpy
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from ..contracts import REPO_ROOT
from ..contracts.intake import (
    inspect_source,
    source_hash,
    validate_args,
    validate_domain,
    validate_json,
)
from ..properties import equal
from ..runner import DockerRunner

DATA = REPO_ROOT / "backend/data"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def request_view(record):
    return {
        "schema_version": "stage1.v1",
        "source": record["buggy_source"],
        "function_name": "solve",
        "contract_text": record["contract"],
        "input_domain": record["domain"],
        "supplied_tests": record["visible_tests"],
        "approved_property": None,
        "resource_profile": "stage1-demo",
    }


def prompt_view(record):
    """Only runtime-visible request and independently executed visible failures."""
    return {"request": request_view(record), "failure_evidence": record["failure_evidence"]}


def chat_record(record):
    if record["split"] not in {"train", "validation"}:
        raise ValueError("Assessment/Stage 2 targets cannot be exported to SFT")
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Repair one pure Python function. Return only JSON with source, di"
                    "agnosis, assumptions. Preserve the contract and positional signat"
                    "ure."
                ),
            },
            {"role": "user", "content": json.dumps(prompt_view(record), separators=(",", ":"))},
            {
                "role": "assistant",
                "content": json.dumps(record["response_target"], separators=(",", ":")),
            },
        ]
    }


def normalized(source):
    tree = ast.parse(source)
    names = {}
    protected = {
        "sum",
        "abs",
        "max",
        "min",
        "range",
        "enumerate",
        "len",
        "sorted",
        "set",
        "all",
        "int",
        "str",
    }

    class Normalize(ast.NodeTransformer):
        def visit_arg(self, node):
            node.arg = names.setdefault(node.arg, f"v{len(names)}")
            return node

        def visit_Name(self, node):
            if node.id not in protected:
                node.id = names.setdefault(node.id, f"v{len(names)}")
            return node

    return ast.dump(Normalize().visit(tree), include_attributes=False)


def load_records(manifest):
    manifest = Path(manifest).resolve()
    data = json.loads(manifest.read_text())
    if data["seal_sha256"] != digest(data["assets"]):
        raise ValueError("Split manifest seal mismatch")
    records = []
    for asset in data["assets"]:
        unresolved = DATA / asset["path"]
        path = unresolved.resolve()
        if DATA.resolve() not in path.parents or unresolved.is_symlink():
            raise ValueError("Manifest asset must remain inside backend data")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != asset["sha256"]:
            raise ValueError("Dataset asset hash changed")
        rows = [json.loads(line) for line in content.decode().splitlines()]
        if any(row["split"] != asset["split"] for row in rows):
            raise ValueError("Asset split does not match row provenance")
        records.extend(rows)
    assert_disjoint(records)
    return data, records


def assert_disjoint(records):
    bases, families, solutions = {}, {}, {}
    required = {
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
    for row in records:
        if not required <= row.keys():
            raise ValueError("Dataset record missing required fields")
        split = row["split"]
        if split not in {"train", "validation", "assessment", "stage2_final"}:
            raise ValueError("Unknown split")
        for table, key in (
            (bases, row["base_problem_id"]),
            (families, row["family_id"]),
            (solutions, normalized(row["correct_source"])),
        ):
            if key in table and table[key] != split:
                raise ValueError("Base/family/normalized solution leaks across splits")
            table[key] = split
        inspect_source(row["correct_source"], "solve", len(row["domain"]))
        inspect_source(row["buggy_source"], "solve", len(row["domain"]))
        if row["response_target"]["source"] != row["correct_source"]:
            raise ValueError("Completion target is not the validated reference")
        if set(row["response_target"]) != {"source", "diagnosis", "assumptions"}:
            raise ValueError("Unexpected completion target fields")
        for domain in row["domain"]:
            validate_domain(domain)
        for test in row["visible_tests"] + row["assessment_tests"]:
            validate_args(test["args"], row["domain"])
            validate_json(test["expected"])
        prompt = prompt_view(row)
        if set(prompt) != {"request", "failure_evidence"} or set(prompt["request"]) != {
            "schema_version",
            "source",
            "function_name",
            "contract_text",
            "input_domain",
            "supplied_tests",
            "approved_property",
            "resource_profile",
        }:
            raise ValueError("Unexpected runtime prompt fields")
        visible_args = {digest(test["args"]) for test in row["visible_tests"]}
        visible_ids = {test["test_id"] for test in row["visible_tests"]}
        for failure in row["failure_evidence"]:
            if (
                set(failure) != {"test_id", "args", "result"}
                or failure["test_id"] not in visible_ids
            ):
                raise ValueError("Unexpected or hidden failure evidence fields")
            if set(failure["result"]) != {
                "actual_output",
                "exception_type",
                "input_mutated",
                "duration_ms",
                "trace",
                "trace_truncated",
            }:
                raise ValueError("Unexpected failure result fields")
        if any(digest(failure["args"]) not in visible_args for failure in row["failure_evidence"]):
            raise ValueError("Hidden failure leaked into runtime prompt")

        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for item in value.values():
                    yield from strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)

        if any(row["correct_source"] in text for text in strings(prompt)):
            raise ValueError("Reference source leaked into runtime prompt")


def validate_data(manifest, runner=None):
    data, records = load_records(manifest)
    live = runner is None or isinstance(runner, DockerRunner)
    runner = runner or DockerRunner()
    cache = {}
    rejected = []
    executions = 0

    def execute(source, args):
        nonlocal executions
        key = (source_hash(source), digest(args))
        if key not in cache:
            cache[key] = runner.execute(source, "solve", args)
            executions += 1
        return cache[key]

    for index, row in enumerate(records):
        if row["split"] == "stage2_final":
            continue
        for test in row["visible_tests"] + row["assessment_tests"]:
            result = execute(row["correct_source"], test["args"])
            if (
                result.exception_type
                or result.input_mutated
                or not equal(result.actual_output, test["expected"])
            ):
                rejected.append(
                    {"id": row["record_id"], "reason": "reference failed", "test": test["test_id"]}
                )
        failed = []
        for test in row["visible_tests"]:
            result = execute(row["buggy_source"], test["args"])
            if (
                result.exception_type
                or result.input_mutated
                or not equal(result.actual_output, test["expected"])
            ):
                failed.append(
                    {"test_id": test["test_id"], "args": test["args"], "result": asdict(result)}
                )
        if not failed:
            rejected.append({"id": row["record_id"], "reason": "bug does not fail a visible test"})
        if row["failure_evidence"] != failed:
            # Timings are measurements and legitimately differ; compare observed semantics.
            def stable(items):
                return [
                    {
                        **item,
                        "result": {k: v for k, v in item["result"].items() if k != "duration_ms"},
                    }
                    for item in items
                ]

            if stable(row["failure_evidence"]) != stable(failed):
                rejected.append({"id": row["record_id"], "reason": "failure evidence mismatch"})
        if index % 10 == 0:
            print(
                f"Validated {index + 1}/{len(records)} records; {executions} actual sandbox jobs",
                flush=True,
            )
    counts = Counter(row["split"] for row in records)
    bases = {
        split: len({row["base_problem_id"] for row in records if row["split"] == split})
        for split in counts
    }
    report = {
        "manifest_sha256": hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        "records": dict(counts),
        "base_problems": bases,
        "rejected": rejected,
        "sandbox_executions": executions,
        "image_id": runner.image,
        "execution_mode": "live" if live else "test",
    }
    print(json.dumps(report, indent=2))
    if rejected:
        raise ValueError(f"{len(rejected)} records rejected; dataset remains invalid")
    if live:
        proof = REPO_ROOT / "backend/artifacts/training/data-validation.json"
        proof.parent.mkdir(parents=True, exist_ok=True)
        proof.write_text(json.dumps(report, indent=2) + "\n")
    return report


def export_sft(manifest, out):
    _, records = load_records(manifest)
    proof = json.loads((REPO_ROOT / "backend/artifacts/training/data-validation.json").read_text())
    if (
        proof["execution_mode"] != "live"
        or proof["rejected"]
        or proof["manifest_sha256"] != hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    ):
        raise ValueError("SFT requires current successful executable validation")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if out.joinpath("test.jsonl").exists():
        raise ValueError("Remove stale assessment export before training")
    counts = {}
    for split, filename in (("train", "train.jsonl"), ("validation", "valid.jsonl")):
        selected = [chat_record(row) for row in records if row["split"] == split]
        out.joinpath(filename).write_text("".join(json.dumps(row) + "\n" for row in selected))
        counts[split] = len(selected)
    # No test.jsonl: sealed targets never reach the training loader.
    if out.joinpath("test.jsonl").exists():
        raise ValueError("Remove stale assessment export before training")
    print(json.dumps({"exported": counts, "assessment_exported": 0}))
    return counts


def collect(manifest):
    manifest = Path(manifest)
    if manifest.exists():
        raise ValueError("Refusing to overwrite an existing sealed split manifest")
    rows = runpy.run_path(str(DATA / "train_source/catalog.py"))["catalog"]()
    runner = DockerRunner()
    grouped = {split: [] for split in ("train", "validation", "assessment", "stage2_final")}

    class CorruptReturns(ast.NodeTransformer):
        def __init__(self, value):
            self.value = value

        def visit_Return(self, node):
            return ast.copy_location(ast.Return(value=ast.Constant(self.value)), node)

    rejected = 0
    for index, base in enumerate(rows):
        cases = [
            {"test_id": f"case-{i}", "args": args, "expected": value}
            for i, (args, value) in enumerate(base["cases"])
        ]
        visible, assessment = cases[:2], cases[2:]
        for test in cases:
            result = runner.execute(base["correct_source"], "solve", test["args"])
            if (
                result.exception_type
                or result.input_mutated
                or not equal(result.actual_output, test["expected"])
            ):
                raise ValueError(f"Reference failed: {base['base_problem_id']} {test['test_id']}")
        for variant, value in enumerate((0, None)):
            tree = CorruptReturns(value).visit(ast.parse(base["correct_source"]))
            buggy = ast.unparse(ast.fix_missing_locations(tree)) + "\n"
            failures = []
            for test in visible:
                result = runner.execute(buggy, "solve", test["args"])
                if (
                    result.exception_type
                    or result.input_mutated
                    or not equal(result.actual_output, test["expected"])
                ):
                    failures.append(
                        {"test_id": test["test_id"], "args": test["args"], "result": asdict(result)}
                    )
            if not failures:
                rejected += 1
                continue
            record = {
                k: base[k]
                for k in (
                    "base_problem_id",
                    "family_id",
                    "split",
                    "contract",
                    "domain",
                    "correct_source",
                )
            }
            record.update(
                record_id=f"{base['base_problem_id']}-return-{variant}",
                provenance={
                    "kind": "synthetic",
                    "author": "CodeJury project",
                    "mutation": f"replace_returns_with_{value}",
                    "license": "Project-authored; repository redistribution license not declared",
                    "external_benchmark": False,
                },
                buggy_source=buggy,
                visible_tests=visible,
                assessment_tests=assessment,
                failure_evidence=failures,
                response_target={
                    "source": base["correct_source"],
                    "diagnosis": "Synthetic return corruption violates the supplied contract.",
                    "assumptions": [],
                },
            )
            grouped[base["split"]].append(record)
        print(f"Collected {index + 1}/{len(rows)} bases: {base['base_problem_id']}", flush=True)
    assets = []
    for split, records in grouped.items():
        relative = f"train_source/{split}.jsonl" if split == "train" else f"private/{split}.jsonl"
        content = "".join(json.dumps(row, sort_keys=True) + "\n" for row in records).encode()
        path = DATA / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        assets.append(
            {
                "path": relative,
                "split": split,
                "sha256": hashlib.sha256(content).hexdigest(),
                "base_problems": len({row["base_problem_id"] for row in records}),
                "records": len(records),
            }
        )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "dataset_id": "stage1-original-synthetic-v1",
                "assets": assets,
                "seal_sha256": digest(assets),
                "rejected_variants": rejected,
                "public_demo_overlap": False,
                "note": (
                    "Assessment and Stage 2 assets are local ignored offline data. All"
                    " families split before corruption."
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"assets": assets, "rejected_variants": rejected}, indent=2))
