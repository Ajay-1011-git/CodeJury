"""Executable validation selects A; training loss never ranks a checkpoint."""

import copy
import json
import shutil
from pathlib import Path

from codejury.models.worker import file_hash

from ...contracts import checked, json_hash
from ...data import config, load_stage1, write_report
from ...registry import ADAPTER_FILES, Registry, hashes, local_path


def rank(summary):
    return (
        -summary["solved"],
        summary["incorrect_accepted"],
        summary["malformed"],
        summary["input_tokens"] + summary["output_tokens"],
    )


def non_regressing(candidate, baseline):
    return (
        candidate["solved"] >= baseline["solved"]
        and candidate["incorrect_accepted"] <= baseline["incorrect_accepted"]
        and candidate["malformed"] <= baseline["malformed"]
    )


def select(config_path, baseline_path, candidate_paths, out):
    settings = config(config_path)
    source, records = load_stage1(local_path(settings["source_manifest"]))
    expected = {r["record_id"] for r in records if r["split"] == "validation"}
    reports = []
    for path in (baseline_path, *candidate_paths):
        path = Path(path).resolve()
        report = json.loads(path.read_text())
        registry = Registry(Path(report["registry_path"]))
        rows = [r for r in report["rows"] if r["role"] == "fixer_a"]
        if (
            report["status"] != "completed_diagnostic"
            or report["all_variants"] is not True
            or report["source_manifest_hash"] != json_hash(source)
            or report["seed"] != settings["seed"]
            or report["max_new_tokens"] != settings["max_new_tokens"]
            or report["base_revision_hash"] != registry.base["base_revision_hash"]
            or report["model_manifest_hash"] != registry.manifest_hash
            or len(rows) != len(expected)
            or {r["record_id"] for r in rows} != expected
            or any(
                r["response_status"] != "ok"
                or r["adapter_hash"] != registry.identity("fixer_a")["adapter_hash"]
                or r["model_config_hash"] != registry.identity("fixer_a")["model_config_hash"]
                for r in rows
            )
        ):
            raise ValueError("Incomplete/incompatible executable validation report")
        summary = {
            "total": len(rows),
            **{
                key: sum(r[key] for r in rows)
                for key in ("solved", "accepted", "incorrect_accepted", "malformed")
            },
            "input_tokens": sum(r["usage"]["input_tokens"] for r in rows),
            "output_tokens": sum(r["usage"]["output_tokens"] for r in rows),
        }
        if any(report["aggregates"]["fixer_a"][k] != v for k, v in summary.items()):
            raise ValueError("Validation aggregate disagrees with its actual rows")
        reports.append(
            {
                "path": str(path),
                "sha256": file_hash(path),
                "registry": registry,
                "summary": summary,
                "rows": rows,
            }
        )
    if any(
        r["registry"].base != reports[0]["registry"].base
        or r["registry"].record["topology_hash"] != reports[0]["registry"].record["topology_hash"]
        for r in reports
    ):
        raise ValueError("Checkpoint comparison mixes incompatible base/topology")
    baseline = reports[0]
    eligible = [r for r in reports if non_regressing(r["summary"], baseline["summary"])]
    chosen = min(eligible, key=lambda r: rank(r["summary"]))
    directory = Path(out).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    registry = chosen["registry"]
    adapter = registry.verify_adapter("fixer_a")
    for name in ADAPTER_FILES:
        shutil.copyfile(adapter / name, directory / name)
    record = copy.deepcopy(registry.record)
    entry = record["adapters"]["fixer_a"]
    entry["path"] = str(directory)
    entry["files"] = hashes(directory, ADAPTER_FILES)
    entry["card"]["status"] = "completed"
    entry["card"]["evaluation_summary"] = (
        f"Limited 20-variant/10-base validation: {chosen['summary']['solved']}/20 solved, "
        f"{chosen['summary']['incorrect_accepted']} incorrect accepted, "
        f"{chosen['summary']['malformed']} malformed. Selected by execution then format/cost; "
        "aggregate non-regression vs retained A. Synthetic integer/list scope only."
    )
    checked(entry["card"], "AdapterCard")
    write_report(directory / "registry.json", record)
    selected = Registry(directory / "registry.json")
    baseline_rows = {r["record_id"]: r for r in baseline["rows"]}
    regressions = [
        r["record_id"]
        for r in chosen["rows"]
        if baseline_rows[r["record_id"]]["solved"] and not r["solved"]
    ]
    result = {
        "status": "selected_limited_validation",
        "registry_path": str(selected.path),
        "adapter_hash": selected.identity("fixer_a")["adapter_hash"],
        "selected_report": chosen["path"],
        "selected_summary": chosen["summary"],
        "baseline_summary": baseline["summary"],
        "paired_lost_successes": regressions,
        "comparisons": [
            {
                "report_path": r["path"],
                "sha256": r["sha256"],
                "summary": r["summary"],
                "eligible": non_regressing(r["summary"], baseline["summary"]),
            }
            for r in reports
        ],
        "policy": "Non-regressing solved/incorrect-accepted/malformed counts vs retained A; "
        "rank solved descending, incorrect-accepted, malformed, token cost ascending. "
        "Ties retain the earlier supplied candidate. No training-loss ranking.",
        "limitations": [
            "20 variants share 10 bases; not 20 independent problems.",
            "Expanded Stage 2 domains/student errors remain uncollected.",
            "Final benchmark not run; earlier Stage 1 checkpoints not all compared.",
        ],
    }
    write_report(directory / "selection.json", result)
    return result
