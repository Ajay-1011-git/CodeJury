"""Rejoin unchanged independent B execution evidence with newly executed A validation."""

import json
from pathlib import Path

from codejury.models.worker import file_hash

from ..data import write_report
from ..registry import Registry, local_path
from ..training.fixer_b.evaluate import paired


def check(cfg):
    root = local_path(cfg["artifact_root"])
    result = json.loads((root / "comparison-v1.json").read_text())
    if not result["selected"]:
        return {"status": "current_roles_retained"}
    a_path = Path(result["reports"][result["selected"]]["path"])
    b_path = local_path("artifacts/stage2_core/fixer-b-training/alpha4-validation-200/report.json")
    a, b = json.loads(a_path.read_text()), json.loads(b_path.read_text())
    original = Registry(root / "baseline-registry.json")
    selected = Registry(Path(result["candidate_registry"]))
    b_registry = Registry(Path(b["registry_path"]))
    b_rows = [r for r in b["rows"] if r["role"] == "fixer_b"]
    if (
        b["runtime_mode"] != "live"
        or b["view"] != "independent"
        or b["seed"] != a["seed"]
        or b["max_new_tokens"] != a["max_new_tokens"]
        or b["source_manifest_hash"] != a["source_manifest_hash"]
        or b_registry.identity("fixer_b") != original.identity("fixer_b")
        or b_registry.identity("fixer_b") != selected.identity("fixer_b")
        or len(b_rows) != 20
        or any(
            r["response_status"] != "ok"
            or r["adapter_hash"] != original.identity("fixer_b")["adapter_hash"]
            for r in b_rows
        )
    ):
        raise ValueError("Unchanged B evidence is not compatible with this A comparison")
    joined = paired(a["rows"] + b_rows)
    report = {
        "status": "paired_initial_execution_evidence_rejoined",
        "current_pair": b["summary"],
        "candidate_pair": joined,
        "non_regressing_union": joined["union_solved"] >= b["summary"]["union_solved"],
        "a_report_hash": file_hash(a_path),
        "b_report_hash": file_hash(b_path),
        "b_adapter_hash": original.identity("fixer_b")["adapter_hash"],
        "b_retrained": False,
        "b_training_lineage": "Original A failure-mining lineage preserved",
        "scope": "Initial independent B view/weights/seed unchanged; "
        "real prior B executions reused. "
        "This is not a new full controller evaluation or updated B failure-mining run.",
        "final_contents_opened": False,
    }
    path = root / "paired-comparison-v1.json"
    if not path.exists():
        write_report(path, report)
    return report
