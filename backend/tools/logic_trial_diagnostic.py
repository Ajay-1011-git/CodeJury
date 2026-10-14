"""Run the predeclared diagnostic after a completed baseline and local selection."""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codejury.dev_bench import ROOT, SEEDS, file_hash, read_jsonl
from codejury.dev_bench.runner import run_benchmark
from codejury.stage2_core.data import write_report
from codejury.stage2_core.registry import Registry, local_path
from codejury.stage2_core.training.diagnostic import DIAGNOSTIC_IDS, paired_comparison
from codejury.stage2_core.views import VIEW_VERSION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = json.loads((args.baseline / "summary.json").read_text())
    accepted = json.loads((args.baseline / "phase0-accepted.json").read_text())
    before = read_jsonl(args.baseline / "results.jsonl")
    if (
        not summary["protocol"]["full_population"]
        or len(before) != 900
        or accepted.get("status") != "accepted"
        or accepted.get("summary_sha256") != file_hash(args.baseline / "summary.json")
        or summary["results_sha256"] != file_hash(args.baseline / "results.jsonl")
    ):
        raise ValueError("Complete accepted baseline required")
    if VIEW_VERSION != "stage2.views.v2-concrete-failure":
        raise ValueError("The declared concrete-failure revision view must be active")
    selection = json.loads(args.selection.read_text())
    if selection["status"] != "selected_limited_validation":
        raise ValueError("Executed checkpoint selection required")
    chosen = Registry(Path(selection["registry_path"]))
    old = Registry(local_path("artifacts/stage2_core/judge-learning/selected-v2/registry.json"))
    if (
        chosen.base != old.base
        or chosen.record["topology_hash"] != old.record["topology_hash"]
        or any(
            chosen.identity(role) != old.identity(role) for role in ("fixer_b", "critic", "judge")
        )
    ):
        raise ValueError("Diagnostic must preserve base, topology and all other roles")
    paths = [
        local_path("src/codejury/stage2_core/" + name)
        for name in (
            "views/__init__.py",
            "views/failures.py",
            "candidates/__init__.py",
            "controller/learned.py",
            "model_worker/native.py",
        )
    ]
    frozen = {str(path): file_hash(path) for path in paths}
    weights_changed = (
        chosen.identity("fixer_a")["adapter_hash"] != old.identity("fixer_a")["adapter_hash"]
    )
    args.out.mkdir(parents=True, exist_ok=False)
    write_report(
        args.out / "change-protocol.json",
        {
            "version": "stage2.logic-diagnostic.v1",
            "base_problem_ids": list(DIAGNOSTIC_IDS),
            "seeds": list(SEEDS),
            "baseline_results_sha256": file_hash(args.baseline / "results.jsonl"),
            "selection_sha256": file_hash(args.selection),
            "source_hashes": frozen,
            "view_version": VIEW_VERSION,
            "selected_registry_hash": chosen.manifest_hash,
            "fixer_a_weights_changed": weights_changed,
            "automatic_default_switch": False,
        },
    )
    previous = os.environ.get("CODEJURY_STAGE2_MODEL_MANIFEST")
    os.environ["CODEJURY_STAGE2_MODEL_MANIFEST"] = str(chosen.path)
    try:
        measured = run_benchmark(
            ROOT, args.out, methods=("J-current",), seeds=SEEDS, ids=DIAGNOSTIC_IDS
        )
    finally:
        if previous is None:
            os.environ.pop("CODEJURY_STAGE2_MODEL_MANIFEST", None)
        else:
            os.environ["CODEJURY_STAGE2_MODEL_MANIFEST"] = previous
    if any(file_hash(path) != frozen[str(path)] for path in paths):
        raise ValueError("Diagnostic implementation changed during execution")
    if any(
        measured["protocol"][field] != summary["protocol"][field]
        for field in ("runtime_sha256", "scoring_sha256", "runtime_hash", "caps", "sampler")
    ):
        raise ValueError("Paired diagnostic changed the benchmark, sandbox, caps or sampler")
    result = paired_comparison(before, read_jsonl(args.out / "results.jsonl"))
    result["fixer_a_weights_changed"] = weights_changed
    if not weights_changed:
        result["scope"] = (
            "Concrete-failure revision changes with retained Fixer A weights; "
            "the local trial selected the original adapter. No full-population claim."
        )
    write_report(args.out / "comparison.json", result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
