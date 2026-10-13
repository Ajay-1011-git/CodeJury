"""Exact split assets, read only after native method readiness and experiment freeze."""

import ast
import hashlib
import json
from pathlib import Path

from codejury.stage2_core.contracts import checked
from codejury.stage2_core.data import domain
from codejury.stage2_core.registry import local_path

from .tasks import EvalTask

PATHS = {"validation": "private/validation.jsonl", "final_assessment": "private/stage2_final.jsonl"}


def visible(row):
    """The runtime projection deliberately has no reference/assessment parameter."""
    source, contract, domains, tests, base = (
        row[k] for k in ("buggy_source", "contract", "domain", "visible_tests", "base_problem_id")
    )
    parsed = ast.parse(source)
    functions = [n for n in parsed.body if isinstance(n, ast.FunctionDef)]
    if len(functions) != 1 or functions[0].name != "solve":
        raise ValueError("This sealed import supports the declared single-solve corpus only")
    arguments = functions[0].args.args
    requirement_id = "r-" + base
    return checked(
        {
            "schema_version": "stage2.v1",
            "source": source,
            "function_name": "solve",
            "contract_text": contract,
            "domain_schema": [
                {"name": a.arg, "domain": domain(d)}
                for a, d in zip(arguments, domains, strict=True)
            ],
            "helper_interfaces": [],
            "requirements": [
                {
                    "schema_version": "stage2.v1",
                    "requirement_id": requirement_id,
                    "description": contract,
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
                for t in tests
            ],
            "allowed_dependencies": [],
            "resource_profile": "mac-standard-v1",
            "policy_mode": "learned",
            "seed": 11,
        },
        "RunCreate",
    )


def load(manifest_path, split, *, methods_ready=False, frozen=False):
    if not methods_ready or (split == "final_assessment" and not frozen):
        raise ValueError("Native methods and E4 freeze must precede assessment access")
    if split not in PATHS:
        raise ValueError("Research runner permits only the declared validation/final split")
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    entry = manifest["splits"][split]
    if entry["asset"] != PATHS[split] or entry.get("inspected_in_development", False):
        raise ValueError("Assessment asset differs from the unconsumed sealed path")
    path = local_path("data") / PATHS[split]
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Assessment symlinks are forbidden")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("Assessment bytes differ from the sealed manifest")
    rows = [json.loads(line) for line in raw.decode().splitlines()]
    asset_split = "stage2_final" if split == "final_assessment" else split
    if (
        len(rows) != entry["records"]
        or len({r["base_problem_id"] for r in rows}) != entry["base_problems"]
        or any(r["split"] != asset_split for r in rows)
    ):
        raise ValueError("Assessment split/population identity differs from the seal")
    grouped = {}
    for row in sorted(rows, key=lambda r: r["record_id"]):
        grouped.setdefault(row["base_problem_id"], row)
    # Fixed before reading outcomes: one lexicographically first variant per base.
    # The existing harness clusters by task_id, so variants must not inflate its n.
    tasks = [
        EvalTask(
            base,
            row["family_id"],
            "heldout_family",
            visible(row),
            {
                "reference_source": row["correct_source"],
                "tests": [
                    {"inputs": t["args"], "expected": t["expected"]}
                    for t in row["assessment_tests"]
                ],
            },
        )
        for base, row in sorted(grouped.items())
    ]
    return tasks, {
        "split": split,
        "source_records": len(rows),
        "selected_base_problems": len(tasks),
        "record_rule": "lexicographically first record_id per base_problem_id",
        "asset_hash": entry["sha256"],
        "variants_are_not_independent": True,
    }
