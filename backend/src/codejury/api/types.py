"""Wire objects are checked against the frozen schema, including required nulls."""

from ..contracts import validate

TERMINAL = frozenset(
    {"supported_patch", "unresolved", "invalid_input", "infrastructure_error", "cancelled"}
)


def error(code: str, message: str, fields: list[str] | None = None) -> dict:
    body = {
        "schema_version": "stage1.v1",
        "error": {"code": code, "message": message, "field_errors": fields or []},
    }
    validate(body, "Error")
    return body


def queued(run_id: str, *, mode: str = "live") -> dict:
    body = {
        "schema_version": "stage1.v1",
        "run_id": run_id,
        "status": "queued",
        "runtime_mode": mode,
        "phase": "queued",
        "model_id": None,
        "model_revision": None,
        "adapter_role": "none",
        "adapter_sha256": None,
        "original_failure_reproduced": None,
        "candidates": [],
        "tests": [],
        "executions": [],
        "decision": None,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "function_executions": 0,
            "elapsed_ms": 0,
            "peak_memory_mb": None,
        },
        "termination_reason": None,
    }
    validate(body, "RunSnapshot")
    return body
