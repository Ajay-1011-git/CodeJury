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
