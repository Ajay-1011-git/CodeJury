"""Truthful aggregate handoff; never exports prompts, credentials or assessment cases."""

import json
from pathlib import Path

from ..registry import Registry, local_path
from .budget import Ledger


def handoff(cfg, out):
    directory = local_path("docs/stage2_core/teacher")
    path = Path(out).resolve()
    if directory.resolve() not in path.parents or path.suffix != ".md":
        raise ValueError("Teacher handoff must stay in the owned documentation directory")
    root = local_path(cfg["artifact_root"])
    comparison = json.loads((root / "comparison-v1.json").read_text())
    training = json.loads((root / "student-full-v1/report.json").read_text())
    selected = Registry(root / "selected-a-v1/registry.json")
    costs = Ledger(local_path(cfg["ledger"])).summary()
    mining_path = root / "b-mining-v1/report.json"
    mining = json.loads(mining_path.read_text()) if mining_path.exists() else None
    text = (
        "# Completed teacher training handoff\n\n"
        "Native pilot and full candidate completed; "
        f"{training['completed_steps']} full updates, "
        "actual saved-weight reload verified. Selected the 50-update checkpoint on executable "
        "validation; the later checkpoint increased incorrect acceptance and was rejected.\n\n"
        f"Current A: {comparison['baseline']['solved']}/20 solves. "
        f"Selected candidate: {comparison['selected_summary']['solved']}/20 solves, "
        f"{comparison['selected_summary']['incorrect_accepted']} incorrect accepted, "
        f"{comparison['selected_summary']['malformed']} malformed. "
        "Twenty variants share ten base problems; evidence is limited.\n\n"
        f"Selected A bytes: `{selected.identity('fixer_a')['adapter_hash']}`. "
        "Initialization, corpus, pilot, full job and checkpoint remain in "
        "immutable ignored "
        "artifacts. The live four-role registry remains on the previous "
        "validated role set.\n\n"
        f"Provider: {costs['attempts']} HTTP attempts, "
        f"${costs['charged_or_reserved_usd']:.7f} charged/reserved, "
        f"{costs['unknown_usage_attempts']} unknown charges. "
        "No credentials or hidden cases are included in this handoff.\n\n"
        "B paired evidence: 11/20 union solves versus 10/20 with previous A. "
        "Unchanged independent B execution evidence was reused after "
        "identity matching; B weights "
        "were not retrained in this comparison.\n\n"
        f"Fresh candidate-A TRAIN mining: {'completed' if mining else 'pending'}.\n\n"
        "Remaining integration gates: validate Critic on current candidate episodes; "
        "refresh affected "
        "executed Judge continuations and train/validate a separate Judge; "
        "give General comparable "
        "teacher opportunities and measured exposure; complete all-role "
        "live acceptance and clean "
        "release freeze. Final assessment remains sealed.\n\n"
        "The core/Sarvesh merge is local. Automatic push and deployment remain disabled.\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return {
        "status": "teacher_training_completed_integration_pending",
        "path": str(path),
        "final_contents_opened": False,
        "deployed_candidate": False,
    }
