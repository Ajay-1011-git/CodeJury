"""Truthful aggregate report. No private source/assessment access from runtime."""


def not_started(mode: str = "live") -> dict:
    return {
        "schema_version": "stage1.v1",
        "runtime_mode": mode,
        "status": "not_started",
        "model_id": None,
        "model_revision": None,
        "adapter_sha256": None,
        "train_base_problems": 0,
        "validation_base_problems": 0,
        "evaluation_base_problems": 0,
        "train_records": 0,
        "steps": 0,
        "loss_points": [],
        "evaluation": [],
        "provenance_note": "No saved adapter with measured evaluation has been supplied.",
    }


def load_report(mode="live", path=None):
    """Read only a public aggregate export, never raw training/assessment records."""
    import json
    import os
    from pathlib import Path

    from ..contracts import REPO_ROOT, validate

    if mode != "live":
        return not_started(mode)
    path = Path(
        path
        or os.getenv(
            "CODEJURY_PUBLIC_TRAINING_REPORT",
            REPO_ROOT / "backend/artifacts/evaluation/training-report.json",
        )
    )
    if not path.exists():
        return not_started(mode)
    report = json.loads(path.read_text())
    validate(report, "TrainingReport")
    if report["runtime_mode"] != "live":
        raise ValueError("Fixture report cannot be served as live")
    if report["status"] != "not_started" and (report["steps"] < 1 or not report["adapter_sha256"]):
        raise ValueError("Training status needs actual adapter metadata")
    if report["status"] == "completed":
        methods = {r["method"] for r in report["evaluation"]}
        if (
            methods != {"raw_single", "trained_a_single", "stage1_loop"}
            or len(report["evaluation"]) != 3
        ):
            raise ValueError("Completed report needs all measured methods")
        if report["evaluation_base_problems"] < 1:
            raise ValueError("Completed report needs actual assessment bases")
        for row in report["evaluation"]:
            if row["total"] != report["evaluation_base_problems"] or (
                row["solved"] + row["unresolved"] + row["incorrect_accepted"] != row["total"]
            ):
                raise ValueError("Measured report counts inconsistent")
    return report
