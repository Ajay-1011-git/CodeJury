"""Hash-verified TRAIN sources only; no assessment values in remote request construction."""

import json
import time
from pathlib import Path

import yaml

from codejury.models.worker import file_hash

from ..contracts import canonical_json, json_hash
from ..data import config, load_stage1, runtime_example, write_report
from ..registry import local_path
from ..views import visible_problem, visible_tests
from .budget import Halt
from .redaction import clean


def settings(path):
    cfg = yaml.safe_load(Path(path).read_text())
    expected = {
        "version": "stage2.teacher.v1",
        "model": "openai/gpt-oss-120b",
        "max_base_problems": 20,
        "variants_per_base": 2,
        "max_http_attempts": 60,
        "max_cost_usd": 1.0,
        "max_completion_tokens": 4096,
        "max_in_flight": 1,
        "timeout_seconds": 60,
        "sdk_retries": 0,
        "additional_attempts_per_example": 2,
    }
    if any(cfg.get(k) != v for k, v in expected.items()):
        raise ValueError("Teacher pilot policy differs from authorized caps")
    return cfg


def source(cfg):
    if cfg["source_config"] != "config/stage2_core/training/fixer_a.yaml":
        raise ValueError("Only the audited A training-source configuration is authorized")
    source_cfg = config(local_path(cfg["source_config"]))
    if source_cfg["source_manifest"] != "data/manifests/stage1.json":
        raise ValueError("Teacher source manifest is outside the authorized training pool")
    manifest_path = local_path(source_cfg["source_manifest"])
    manifest, rows = load_stage1(manifest_path)
    return manifest, rows, file_hash(manifest_path)


def remote_prompt(row):
    if row["split"] != "train":
        raise ValueError("Only TRAIN can be sent to teacher")
    problem, tests = runtime_example(row)
    payload = {
        "problem": visible_problem(problem),
        "tests": visible_tests(tests),
        "buggy_source": problem["source"],
    }
    return clean(canonical_json(payload).decode())


def selected_rows(rows):
    # Prefer the second corruption (when present); all bases already belong to TRAIN.
    bases = {}
    for row in sorted(rows, key=lambda r: r["record_id"]):
        if row["split"] == "train":
            bases.setdefault(row["base_problem_id"], []).append(row)
    # Round robin across families, avoiding twenty copies of one operation family.
    families = {}
    for base in sorted(bases):
        row = bases[base][-1]
        families.setdefault(row["family_id"], []).append(row)
    chosen = []
    while families and len(chosen) < 20:
        for family in list(sorted(families)):
            chosen.append(families[family].pop(0))
            if not families[family]:
                del families[family]
            if len(chosen) == 20:
                break
    return chosen


def collect(cfg, teacher, *, smoke=False):
    manifest, rows, manifest_hash = source(cfg)
    root = local_path(cfg["artifact_root"]) / "proposals-v1"
    root.mkdir(parents=True, exist_ok=True)
    selected = selected_rows(rows)
    plan = {
        "source_manifest_hash": manifest_hash,
        "source_seal": json_hash(manifest),
        "record_ids": [r["record_id"] for r in selected],
        "variants": 2,
        "selection": "deterministic round-robin TRAIN family, last corruption/base",
    }
    plan_path = root / "plan.json"
    if plan_path.exists():
        if json.loads(plan_path.read_text()) != plan:
            raise ValueError("Collection source/selection changed")
    else:
        write_report(plan_path, plan)
    completed = 0
    for row in selected[:1] if smoke else selected:
        for variant in range(2):
            lineage = {
                "record_id": row["record_id"],
                "base_problem_id": row["base_problem_id"],
                "family_id": row["family_id"],
                "split": "train",
                "role": "fixer_a",
                "source_manifest_hash": manifest_hash,
                "record_hash": json_hash(row),
                "variant": variant,
            }
            prompt = remote_prompt(row)
            path = root / f"{json_hash(lineage)}.json"
            if path.exists():
                old = json.loads(path.read_text())
                if old["lineage"] != lineage or old["prompt_hash"] != json_hash(prompt):
                    raise ValueError("Cached proposal lineage mismatch")
                completed += 1
                continue
            try:
                result = teacher.propose(prompt, lineage, variant, max_attempts=1 if smoke else 3)
            except Halt:
                print(
                    json.dumps(
                        {
                            "status": "collection_stopped",
                            "completed": completed,
                            **teacher.ledger.summary(),
                        }
                    ),
                    flush=True,
                )
                raise
            write_report(
                path, {"lineage": lineage, "prompt_hash": json_hash(prompt), "response": result}
            )
            completed += 1
            print(
                json.dumps(
                    {"status": "proposal_saved", "completed": completed, **teacher.ledger.summary()}
                ),
                flush=True,
            )
            if not smoke:
                time.sleep(
                    6
                )  # Conservative pacing; provider 429 still halts with persisted backoff.
            if smoke:
                return {"completed": completed, **teacher.ledger.summary()}
    return {"completed": completed, **teacher.ledger.summary()}
