"""Turn (candidate, test) pairs into Execution records with trusted host-side verdicts.

Candidate code runs only through the SandboxPort. The oracle verdict is computed here from the
returned data; candidate code can never assign a pass label. Only calls that completed produce
rows and usage; budget exhaustion or cancellation returns the completed prefix.
"""

import threading
import time

from ..codec import value_hash
from ..domains import SourceError, check_bundle
from ..oracles import judge
from .base import Cancelled, WatchdogTimeout

REJECTING = {"fail", "error", "timeout"}


def hard_rejection(execution: dict, test: dict) -> bool:
    return test["oracle_status"] == "authoritative" and execution["outcome"] in REJECTING


class Evaluator:
    def __init__(
        self,
        sandbox,
        problem: dict,
        *,
        id_prefix: str,
        max_executions: int,
        cancel: threading.Event | None = None,
        chunk_calls: int = 8,
        call_timeout_s: float = 2,
    ):
        self.sandbox = sandbox
        self.problem = problem
        self.id_prefix = id_prefix
        self.max_executions = max_executions
        self.cancel = cancel or threading.Event()
        self.chunk_calls = chunk_calls
        self.call_timeout_s = call_timeout_s
        self.used = 0
        self.elapsed_ms = 0
        self.exhausted = False
        self.cancelled = False
        self.traces: dict[str, list] = {}
        self.static_rejections: dict[str, str] = {}
        self._n = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_executions - self.used)

    def usage(self) -> dict:
        return {"function_executions": self.used, "elapsed_ms": self.elapsed_ms}

    # -- job plumbing -------------------------------------------------------------------
    def _job(self, source: str, calls: list[dict]) -> dict:
        return {
            "source": source,
            "function_name": self.problem["function_name"],
            "allowed_imports": self.problem["allowed_dependencies"],
            "calls": calls,
            "call_timeout_s": self.call_timeout_s,
        }

    def _run(self, source: str, calls: list[dict]) -> list[dict] | None:
        """Rows for the calls, or None when cancelled. Hung candidates become timeout rows."""
        try:
            envelope = self.sandbox.run(self._job(source, calls), self.cancel)
            return envelope["results"]
        except Cancelled:
            self.cancelled = True
            return None
        except WatchdogTimeout:
            if len(calls) == 1:
                return [_timeout_row(calls[0])]
            rows = []
            for call in calls:  # isolate the call that never returned
                part = self._run(source, [call])
                if part is None:
                    return None
                rows.extend(part)
            return rows

    # -- public ---------------------------------------------------------------------------
    def evaluate(
        self,
        candidate: dict,
        tests: list[dict],
        *,
        stop_on_first_hard_failure: bool = False,
        trace_lines: list[int] | None = None,
        check: bool = True,
    ) -> list[dict]:
        """Executions actually performed for this candidate, in test order."""
        cid, source = candidate["candidate_id"], candidate["source"]
        if check:
            try:
                check_bundle(source, self.problem)
            except SourceError as exc:
                self.static_rejections[cid] = str(exc)
                return []
        pending = [t for t in tests if t["domain_valid"] and t["oracle_status"] != "rejected"]
        done: list[dict] = []
        i = 0
        while i < len(pending):
            if self.cancel.is_set():
                self.cancelled = True
                break
            chunk, cost = [], 0
            while i < len(pending):
                need = 2 if pending[i]["related_inputs"] is not None else 1
                if chunk and cost + need > self.chunk_calls:
                    break
                if cost + need > self.remaining:
                    break
                chunk.append(pending[i])
                cost += need
                i += 1
            if not chunk:
                self.exhausted = True
                break
            calls = []
            for test in chunk:
                calls.append({"inputs": test["inputs"], "trace_lines": trace_lines})
                if test["related_inputs"] is not None:
                    calls.append({"inputs": test["related_inputs"], "trace_lines": None})
            started = time.monotonic()
            rows = self._run(source, calls)
            if rows is None:
                break
            self.elapsed_ms += int((time.monotonic() - started) * 1000)
            self.used += len(calls)
            cursor, rejected = 0, False
            for test in chunk:
                n = 2 if test["related_inputs"] is not None else 1
                execution = self._execution(cid, test, rows[cursor : cursor + n])
                cursor += n
                done.append(execution)
                rejected = rejected or hard_rejection(execution, test)
            if rejected and stop_on_first_hard_failure:
                break
        return done

    def _execution(self, candidate_id: str, test: dict, rows: list[dict]) -> dict:
        outcomes = {r["status"] for r in rows}
        failure = next((r for r in rows if r["status"] != "ok"), None)
        effects = [
            {"call_index": k, "mutated": r["mutated"], "before_hash": r["before_hash"],
             "after_hash": r["after_hash"]}
            for k, r in enumerate(rows)
        ]  # fmt: skip
        exception = None
        output = None
        if "timeout" in outcomes:
            outcome = "timeout"
        elif failure is not None:
            outcome = "error"
            info = failure.get("exception") or {"type": failure["status"], "message": "", "lineno": None}
            line = info.get("lineno")
            exception = {
                "type": str(info["type"])[:120],
                "message": str(info.get("message", ""))[:200],
                "location": None if line is None else {
                    "lineno": line, "col_offset": 0, "end_lineno": line, "end_col_offset": 0
                },
            }  # fmt: skip
        else:
            outputs = [r["output"] for r in rows]
            output = outputs[0] if len(outputs) == 1 else {"base": outputs[0], "followup": outputs[1]}
            verdict = judge(test, outputs)
            if verdict == "pass" and any(r["mutated"] for r in rows):
                verdict = "fail"  # in-place effects are outside the supported scope
            outcome = verdict
        trace = rows[0].get("trace")
        ref = None
        if trace is not None:
            ref = value_hash(trace)
            self.traces[ref] = trace
        execution = {
            "schema_version": "stage2.v1",
            "execution_id": f"{self.id_prefix}-e{self._n:03d}",
            "candidate_id": candidate_id,
            "test_id": test["test_id"],
            "runtime_hash": self.sandbox.runtime_hash,
            "actual_output": output,
            "input_effects": effects,
            "exception": exception,
            "outcome": outcome,
            "duration_ms": sum(r["duration_ms"] for r in rows),
            "trace_ref": ref,
            "trace_truncated": bool(rows[0].get("trace_truncated")),
        }
        self._n += 1
        return execution


def _timeout_row(call: dict) -> dict:
    zero = value_hash(call["inputs"])
    return {
        "status": "timeout", "output": None, "exception": None, "before_hash": zero,
        "after_hash": zero, "mutated": False, "duration_ms": 0, "trace": None,
        "trace_truncated": False,
    }  # fmt: skip

