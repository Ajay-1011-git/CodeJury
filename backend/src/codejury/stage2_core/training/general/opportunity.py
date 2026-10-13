"""Actual deployed completion exposure, separated from pilots and checkpoint search."""

import json
from pathlib import Path

from codejury.models.worker import file_hash

from ...data import write_report
from ...registry import Registry, local_path


def exposure(directory, step):
    directory = Path(directory)
    rows = [json.loads(line) for line in (directory / "loss.jsonl").read_text().splitlines()]
    measured = next((r for r in rows if r["kind"] == "train" and r["iteration"] == step), None)
    if measured is None or measured["trained_tokens"] <= 0:
        raise ValueError("Actual selected-step completion exposure is required")
    return {
        "optimizer_updates": step,
        "completion_tokens": measured["trained_tokens"],
        "peak_memory_mb": measured["peak_memory_mb"],
        "loss_file_hash": file_hash(directory / "loss.jsonl"),
    }


def audit(
    registry_path,
    general_report,
    judge_selection,
    out,
    *,
    relative_tolerance=0.1,
    general_step=None,
):
    registry = Registry(Path(registry_path))
    general = json.loads(Path(general_report).read_text())
    judge = json.loads(Path(judge_selection).read_text())
    judge_report_path = Path(judge["training_report_path"])
    if file_hash(judge_report_path) != judge["training_report_hash"]:
        raise ValueError("Selected Judge training report changed")
    judge_report = json.loads(judge_report_path.read_text())
    if (
        judge_report["role"] != "judge"
        or judge_report["phase"] != "full"
        or not judge_report["updates_verified"]
        or not judge_report["reload_verified"]
        or not any(c["step"] == judge["selected"]["step"] for c in judge_report["candidates"])
    ):
        raise ValueError("Selected Judge must match a saved verified full training checkpoint")
    critic = json.loads(
        local_path("artifacts/stage2_tools/critic-training/selected-v1/selection.json").read_text()
    )
    general_step = general_step or general["completed_steps"]
    checkpoint = next((c for c in general["candidates"] if c["step"] == general_step), None)
    if checkpoint is None:
        raise ValueError("General selected step was not saved by the verified full job")
    measured_registry = Registry(Path(checkpoint["registry_path"]))
    if (
        general["role"] != "general"
        or general["phase"] != "full"
        or not general["updates_verified"]
        or not general["reload_verified"]
        or registry.identity("general")["adapter_hash"]
        != measured_registry.identity("general")["adapter_hash"]
        or registry.identity("judge")["adapter_hash"]
        != judge["selected"]["evaluation"]["adapter_hash"]
        or registry.identity("critic")["adapter_hash"]
        != critic["selected"]["evaluation"]["adapter_hash"]
    ):
        raise ValueError("Opportunity audit must match actual deployed adapter identities")
    roles = {
        "a_inherited": exposure(local_path("artifacts/training/fixer_a_seed17"), 100),
        "fixer_a": exposure(local_path("artifacts/stage2_core/fixer-a-refresh/full-seed17"), 100),
        "fixer_b": exposure(local_path("artifacts/stage2_core/fixer-b-training/alpha4-full"), 200),
        "critic": exposure(
            local_path("artifacts/stage2_tools/critic-training/full-v1"), critic["selected"]["step"]
        ),
        "judge": exposure(
            judge_report_path.parent, judge["selected"]["step"]
        ),
    }
    for role, directory in (
        ("fixer_a", "artifacts/stage2_core/fixer-a-refresh/full-seed17"),
        ("fixer_b", "artifacts/stage2_core/fixer-b-training/alpha4-full"),
    ):
        actual = json.loads(local_path(directory + "/report.json").read_text())
        if registry.identity(role)["adapter_hash"] != actual["adapter_hash"]:
            raise ValueError("Deployed repair role differs from its measured full job")
    comparator = exposure(Path(general_report).parent, general_step)
    tokens = sum(r["completion_tokens"] for r in roles.values())
    difference = abs(comparator["completion_tokens"] - tokens) / tokens
    record = {
        "version": "stage2.training-opportunity.v1",
        "runtime_mode": "live",
        "registry_hash": registry.manifest_hash,
        "roles": roles,
        "council_completion_tokens": tokens,
        "council_optimizer_updates": sum(r["optimizer_updates"] for r in roles.values()),
        "general": comparator,
        "completion_token_relative_difference": difference,
        "comparable": difference <= relative_tolerance,
        "declared_relative_tolerance": relative_tolerance,
        "scope": "Completion tokens learned by the deployed checkpoints, including inherited A.",
        "limitations": [
            "Matching exposure does not claim identical information or curriculum.",
            "Specialist alpha/view/pilot/validation search has extra compute; report separately.",
            "Repeated examples are not additional independent base problems.",
        ],
        "contains_final_assessment": False,
    }
    out = Path(out).resolve()
    if local_path("artifacts") not in out.parents or out.exists():
        raise ValueError("Immutable ignored opportunity audit output required")
    write_report(out, record)
    return record
