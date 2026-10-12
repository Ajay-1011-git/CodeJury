"""Single episode budget authority, with per-dispatch ceilings and final reserve."""

import copy
import threading
import time

from ..contracts import checked

CAPS = {
    "output_tokens": 10000,
    "input_tokens": 100000,
    "function_executions": 3000,
    "elapsed_ms": 900000,
    "learned_candidates": 8,
    "search_candidates": 48,
    "audit_mutants": 48,
    "judge_decisions": 8,
}
COUNTERS = set(CAPS) - {"elapsed_ms"}


def zero_usage() -> dict:
    return {"schema_version": "stage2.v1", **dict.fromkeys(CAPS, 0), "peak_memory_mb": None}


class BudgetExceeded(ValueError):
    pass


class BudgetAccount:
    def __init__(
        self, limits: dict | None = None, *, final_executions: int = 128, clock=time.monotonic
    ):
        self.limits = checked(limits if limits is not None else CAPS, "Budget")
        self.clock = clock
        self.started = clock()
        self.used = zero_usage()
        self.pending = {}
        self.settled = set()
        self.lock = threading.RLock()
        self.faulted = False
        self.reserve_final(final_executions)

    def reserve_final(self, executions: int) -> None:
        with self.lock:
            if (
                type(executions) is not int
                or not 0 <= executions <= self.limits["function_executions"]
            ):
                raise ValueError("Invalid final qualification reserve")
            committed = self.used["function_executions"] + sum(
                r["ceiling"]["function_executions"] for r in self.pending.values()
            )
            if committed + executions > self.limits["function_executions"]:
                raise BudgetExceeded("Final suite cannot fit remaining execution budget")
            self.final_executions = executions

    def usage(self) -> dict:
        with self.lock:
            result = copy.deepcopy(self.used)
            result["elapsed_ms"] = max(0, int((self.clock() - self.started) * 1000))
            return result

    def remaining(self, *, final: bool = False) -> dict:
        with self.lock:
            usage = self.usage()
            result = {key: max(0, self.limits[key] - usage[key]) for key in CAPS}
            for reservation in self.pending.values():
                for key in COUNTERS:
                    result[key] = max(0, result[key] - reservation["ceiling"][key])
            if not final:
                result["function_executions"] = max(
                    0, result["function_executions"] - self.final_executions
                )
            return result

    def dispatch(
        self, request_id: str, ceiling: dict, *, attempts: dict | None = None, final: bool = False
    ) -> None:
        with self.lock:
            if self.faulted:
                raise BudgetExceeded("Untrusted cost report; episode must stop")
            if not request_id or request_id in self.pending or request_id in self.settled:
                raise ValueError("Duplicate or missing request ID")
            ceiling = checked(ceiling, "Budget")
            attempts = attempts or {}
            if any(
                key not in {"learned_candidates", "judge_decisions"}
                or type(value) is not int
                or value < 0
                for key, value in attempts.items()
            ):
                raise ValueError("Invalid controller attempt costs")
            remaining = self.remaining(final=final)
            if remaining["elapsed_ms"] == 0 or ceiling["elapsed_ms"] == 0:
                raise BudgetExceeded("Episode wall deadline reached")
            for key in CAPS:
                if ceiling[key] + attempts.get(key, 0) > remaining[key]:
                    raise BudgetExceeded(f"Insufficient {key}, including final reserve")
            for key, value in attempts.items():
                self.used[key] += value
            self.pending[request_id] = {"ceiling": ceiling, "attempts": attempts}

    def preview(self, request_id: str, delta: dict) -> dict:
        with self.lock:
            if request_id not in self.pending:
                raise ValueError("Missing dispatch or duplicate cost settlement")
            try:
                delta = checked(delta, "ResourceUsage")
                for key, cost in self.pending[request_id]["attempts"].items():
                    if delta[key] not in (0, cost):
                        raise BudgetExceeded("Reported attempt cost disagrees with dispatch")
                    # Attempt was charged before generation, including malformed/invalid choices.
                    delta[key] = 0
                ceiling = self.pending[request_id]["ceiling"]
                if any(delta[key] > ceiling[key] for key in CAPS):
                    raise BudgetExceeded("Reported usage exceeds dispatched ceiling")
                if any(self.used[key] + delta[key] > self.limits[key] for key in COUNTERS):
                    raise BudgetExceeded("Episode budget overflow")
            except Exception:
                self.faulted = True
                raise
            return delta

    def settle(self, request_id: str, delta: dict) -> None:
        with self.lock:
            delta = self.preview(request_id, delta)
            for key in COUNTERS:
                self.used[key] += delta[key]
            peak = delta["peak_memory_mb"]
            if peak is not None:
                self.used["peak_memory_mb"] = max(self.used["peak_memory_mb"] or 0, peak)
            del self.pending[request_id]
            self.settled.add(request_id)
