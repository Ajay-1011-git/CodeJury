"""Sandbox seam shared by the Docker implementation and the CPU test double."""

import threading
from typing import Protocol


class InfrastructureError(RuntimeError):
    """The sandbox could not produce a trustworthy outcome; never a semantic failure."""


class Cancelled(RuntimeError):
    """Cancellation observed while a sandbox job was in flight."""


class WatchdogTimeout(RuntimeError):
    """The external watchdog killed the job; the callee never returned control."""


class SandboxPort(Protocol):
    runtime_hash: str

    def run(self, job: dict, cancel: threading.Event | None) -> dict:
        """Run one job {source, function_name, allowed_imports, calls[, call_timeout_s]}."""
        ...


def validate_envelope(envelope: dict, n_calls: int) -> list[dict]:
    """Check a worker envelope before any of it is trusted."""
    if not isinstance(envelope, dict) or not isinstance(envelope.get("results"), list):
        raise InfrastructureError("Malformed sandbox envelope")
    rows = envelope["results"]
    if len(rows) != n_calls:
        raise InfrastructureError("Sandbox result count mismatch")
    statuses = {"ok", "exception", "timeout", "unsupported", "output_invalid"}
    for row in rows:
        if not isinstance(row, dict) or row.get("status") not in statuses:
            raise InfrastructureError("Malformed sandbox result row")
        for key in ("before_hash", "after_hash"):
            value = row.get(key)
            if not (isinstance(value, str) and len(value) == 64):
                raise InfrastructureError("Malformed sandbox hash")
        if type(row.get("mutated")) is not bool or type(row.get("duration_ms")) is not int:
            raise InfrastructureError("Malformed sandbox result types")
    return rows
