"""Fixed Stage 1 policy: A, raw Critic, at most one A revision; evidence owns selection."""

import copy
import difflib
import json
import threading
import time
from dataclasses import asdict

from ..api.repository import Repository
from ..contracts.intake import source_hash, validate_request, validate_test
from ..models.views import parse_critic, parse_repair, repair_view
from ..models.worker import ModelWorker
from ..properties import outcome
from ..properties.engine import explore
from ..runner import Cancelled, DockerRunner, InfrastructureError


class BudgetExceeded(Exception):
    pass


class Episode:
    def __init__(
        self, request, store, run_id, cancellation, model, runner, *, execution_cap=400, seconds=600
    ):
        if not 1 <= execution_cap <= 400 or not 0 < seconds <= 600:
            raise ValueError("Cannot exceed Stage 1 resource limits")
        self.request, self.store, self.run_id = request, store, run_id
        self.cancel, self.model, self.runner = cancellation, model, runner
        self.repository = Repository(store)
        self.start = time.monotonic()
        self.deadline = self.start + seconds
        self.execution_cap = execution_cap
        self.cache, self.generations, self.actions = {}, [], []
        self.format_retries = 0
        self.snapshot = store.snapshot(run_id)
        self.snapshot.update(status="running", **model.identity)
        self.snapshot["tests"] = [self.supplied(t) for t in request["supplied_tests"]]

    @staticmethod
    def supplied(test):
        return {
            **copy.deepcopy(test),
            "oracle_kind": "literal",
            "property_id": None,
            "oracle_status": "authoritative",
            "oracle_source": "user",
            "requirement_id": test["test_id"],
            "provenance": "supplied",
            "reason": "Supplied user expectation",
        }

    def save(self, phase=None):
        if phase:
            self.snapshot["phase"] = phase
        self.snapshot["usage"]["elapsed_ms"] = int((time.monotonic() - self.start) * 1000)
        self.repository.update(self.run_id, lambda _: copy.deepcopy(self.snapshot))

    def guard(self):
        if self.cancel.is_set():
            raise Cancelled("User cancelled repair")
        if time.monotonic() >= self.deadline:
            raise BudgetExceeded("Episode 600-second deadline exhausted")

    def event(self, kind, message, candidate=None, test=None, evidence=None):
        self.store.append_event(
            self.run_id, kind, message, candidate_id=candidate, test_id=test, evidence_ids=evidence
        )

    def candidate(self, source, origin, diagnosis, parent=None):
        cid = (
            "original" if origin == "original" else f"candidate-{len(self.snapshot['candidates'])}"
        )
        body = {
            "candidate_id": cid,
            "parent_id": parent,
            "origin": origin,
            "source": source,
            "source_sha256": source_hash(source),
            "diagnosis": diagnosis,
            "diff": "".join(
                difflib.unified_diff(
                    self.request["source"].splitlines(True),
                    source.splitlines(True),
                    fromfile="original",
                    tofile=cid,
                )
            ),
            "eligibility": "pending",
            "rejection_reason": None,
        }
        self.store.add_candidate(self.run_id, body)
        self.snapshot["candidates"].append(body)
        self.event("candidate_created", f"Fixed Stage 1 policy created {origin}", cid)
        self.save()
        return body

    def admit_property(self, args):
        prop = self.request["approved_property"]
        for test in self.snapshot["tests"]:
            if test["provenance"] == "property_engine" and test["args"] == args:
                return test
        ids = {t["test_id"] for t in self.snapshot["tests"]}
        tid = "property-" + str(len(self.snapshot["tests"]))
        while tid in ids:
            tid += "-p"
        body = {
            "test_id": tid,
            "args": copy.deepcopy(args),
            "oracle_kind": "property" if prop else "observation",
            "expected": None,
            "property_id": prop,
            "oracle_status": "authoritative" if prop else "observation_only",
            "oracle_source": "reviewed_contract" if prop else "model",
            "requirement_id": prop,
            "provenance": "property_engine",
            "reason": "Disclosed approved oracle" if prop else "Observation without expected value",
        }
        validate_test(body, self.request)
        self.snapshot["tests"].append(body)
        self.event("test_admitted", body["reason"], test=tid)
        return body

    def execute(self, candidate, tests, *, force=False):
        self.guard()
        outputs = []
        for start in range(0, len(tests), 8):
            batch = tests[start : start + 8]
            self.guard()
            fresh = []
            for test in batch:
                key = (candidate["source_sha256"], json.dumps(test["args"], sort_keys=True))
                if force or key not in self.cache:
                    if key not in [k for k, _ in fresh]:
                        fresh.append((key, test))
            usage = self.snapshot["usage"]
            if usage["function_executions"] + len(fresh) > self.execution_cap:
                raise BudgetExceeded("400-execution budget exhausted; incomplete checks rejected")
            if fresh:
                usage["function_executions"] += len(fresh)  # Charge attempted sandbox work.
                results = self.runner.execute_many(
                    candidate["source"],
                    self.request["function_name"],
                    [t["args"] for _, t in fresh],
                    self.cancel,
                    deadline=self.deadline,
                )
                if len(results) != len(fresh):
                    raise InfrastructureError("Sandbox batch count mismatch")
                for (key, _), result in zip(fresh, results):
                    self.cache[key] = asdict(result)
            for test in batch:
                key = (candidate["source_sha256"], json.dumps(test["args"], sort_keys=True))
                actual = self.cache[key]
                label = outcome(
                    test, actual["actual_output"], input_mutated=actual["input_mutated"]
                )
                if test["oracle_status"] == "authoritative" and actual["exception_type"]:
                    label = "timeout" if actual["exception_type"] == "TimeoutError" else "error"
                row = {
                    "execution_id": f"execution-{len(self.snapshot['executions']) + 1}",
                    "candidate_id": candidate["candidate_id"],
                    "test_id": test["test_id"],
                    "outcome": label,
                    **copy.deepcopy(actual),
                }
                self.snapshot["executions"].append(row)
                outputs.append(row)
                self.event(
                    "execution_completed",
                    label,
                    candidate["candidate_id"],
                    test["test_id"],
                    [row["execution_id"]],
                )
            self.save()
        return outputs

    def failures(self, rows):
        return [row for row in rows if row["outcome"] in {"fail", "error", "timeout"}]

    def supplied_evidence(self, rows):
        tests = {t["test_id"]: t for t in self.snapshot["tests"] if t["provenance"] == "supplied"}
        return [
            {
                "test_id": r["test_id"],
                "args": tests[r["test_id"]]["args"],
                "result": {
                    k: r[k]
                    for k in (
                        "actual_output",
                        "exception_type",
                        "input_mutated",
                        "duration_ms",
                        "trace",
                        "trace_truncated",
                    )
                },
            }
            for r in self.failures(rows)
            if r["test_id"] in tests
        ]

    def generate(self, role, view, *, retry=False):
        self.guard()
        usage = self.snapshot["usage"]
        cap = min(1024 if role == "fixer_a" else 512, 4096 - usage["output_tokens"])
        if cap < 1:
            raise BudgetExceeded("4096-output-token budget exhausted")
        try:
            generated = self.model.generate(
                role,
                view,
                max_tokens=cap,
                cancel=self.cancel,
                deadline=self.deadline,
                format_retry=retry,
            )
        except (Cancelled, TimeoutError, ValueError):
            self.charge(self.model.last_usage)
            raise
        self.charge(asdict(generated))
        self.generations.append({"role": role, "format_retry": retry, **asdict(generated)})
        self.actions.append({"action": "generate", "source": "fixed_stage1_policy", "role": role})
        self.save()
        return generated.text

    def charge(self, generated):
        usage = self.snapshot["usage"]
        usage["input_tokens"] += generated["input_tokens"]
        usage["output_tokens"] += generated["output_tokens"]
        usage["peak_memory_mb"] = max(usage["peak_memory_mb"] or 0, generated["peak_memory_mb"])

    def repair(self, evidence, counterexample=None, parent=None):
        view = repair_view(self.request, evidence, counterexample)
        for _ in range(2):
            text = self.generate("fixer_a", view, retry=bool(self.format_retries))
            try:
                patch = parse_repair(text, self.request)
                return self.candidate(
                    patch["source"],
                    "fixer_a_revision" if parent else "fixer_a",
                    patch["diagnosis"],
                    parent,
                )
            except ValueError:
                if self.format_retries:
                    return None
                self.format_retries += 1
        return None

    def checks(self, candidate, proposal):
        self.save("challenge")
        report = explore(
            self.request,
            proposal,
            lambda args, force=False: self.execute(
                candidate, [self.admit_property(a) for a in args], force=force
            ),
        )
        self.actions.append(
            {"action": "property_exploration", "source": "property_engine", **report}
        )
        # Final independent replay of every authoritative test, including earlier counterexamples.
        final = self.execute(candidate, self.snapshot["tests"], force=True)
        candidate["eligibility"] = "rejected" if self.failures(final) else "eligible"
        candidate["rejection_reason"] = (
            "Authoritative executed failure" if self.failures(final) else None
        )
        self.save()
        return final, report

    def finish(self, status, reason, selected=None):
        self.snapshot.update(
            status=status,
            phase="finished",
            termination_reason=reason,
            decision={
                "selected_candidate_id": selected["candidate_id"] if selected else None,
                "verification_scope": [
                    t["test_id"]
                    for t in self.snapshot["tests"]
                    if t["oracle_status"] == "authoritative"
                ]
                if selected
                else [],
                "unresolved_requirements": [] if selected else [reason],
                "evidence_ids": [r["execution_id"] for r in self.snapshot["executions"]],
                "reason": reason,
            },
        )
        self.save()
        self.event("run_finished", reason)
        path = self.store.directory / (self.run_id + "-episode.json")
        path.write_text(
            json.dumps(
                {
                    "request": self.request,
                    "snapshot": self.snapshot,
                    "actions": self.actions,
                    "generations": self.generations,
                },
                indent=2,
            )
            + "\n"
        )
        return self.snapshot

    def perform(self):
        validate_request(self.request)
        self.event("run_started", "Fixed Stage 1 policy; no trained Judge")
        self.save("reproduce")
        original = self.candidate(self.request["source"], "original", "Submitted baseline")
        baseline = self.execute(original, self.snapshot["tests"])
        original.update(
            eligibility="rejected", rejection_reason="Original baseline cannot be selected"
        )
        reproduced = bool(self.failures(baseline))
        self.snapshot["original_failure_reproduced"] = reproduced
        self.event(
            "original_checked",
            "Supplied failure reproduced" if reproduced else "No supplied failure",
        )
        if not reproduced:
            return self.finish("unresolved", "No authoritative supplied failure reproduced")
        self.save("generate")
        candidate = self.repair(self.supplied_evidence(baseline))
        if candidate is None:
            return self.finish("unresolved", "Repair JSON invalid after single format retry")
        self.save("supplied_tests")
        supplied = self.execute(candidate, self.snapshot["tests"])
        self.save("challenge")
        proposal = {
            "property_id": self.request["approved_property"],
            "family": "general",
            "reason": "Deterministic fallback",
        }
        raw = self.generate("critic", {"request": self.request, "candidate": candidate["source"]})
        try:
            proposal = parse_critic(raw, self.request["approved_property"])
            action_source = "raw_critic"
        except ValueError:
            action_source = "deterministic_fallback"
            self.event("test_rejected", "Invalid Critic proposal; deterministic general fallback")
        self.actions.append({"action": "challenge_proposal", "source": action_source, **proposal})
        final, report = self.checks(candidate, proposal)
        if candidate["eligibility"] == "eligible":
            return self.finish(
                "supported_patch",
                "All admitted authoritative checks passed; bounded scope",
                candidate,
            )
        self.save("revise")
        self.event(
            "revision_requested", "Fixed policy permits one revision", candidate["candidate_id"]
        )
        revised = self.repair(
            self.supplied_evidence(supplied), report["counterexample"], candidate["candidate_id"]
        )
        if revised is None:
            return self.finish("unresolved", "Revision JSON invalid; no eligible candidate")
        final, _ = self.checks(revised, proposal)
        # New counterexamples invalidate any older patch by independent replay.
        old_rows = self.execute(candidate, self.snapshot["tests"], force=True)
        candidate["eligibility"] = "rejected" if self.failures(old_rows) else "eligible"
        selected = (
            revised
            if revised["eligibility"] == "eligible"
            else candidate
            if candidate["eligibility"] == "eligible"
            else None
        )
        return self.finish(
            "supported_patch" if selected else "unresolved",
            "All admitted authoritative checks passed; bounded scope"
            if selected
            else "No generated candidate passed all authoritative checks",
            selected,
        )


def run(
    request,
    store,
    run_id,
    cancellation=None,
    *,
    model=None,
    runner=None,
    config=None,
    execution_cap=400,
    seconds=600,
):
    episode = Episode(
        request,
        store,
        run_id,
        cancellation or threading.Event(),
        model or ModelWorker(config),
        runner or DockerRunner(),
        execution_cap=execution_cap,
        seconds=seconds,
    )
    try:
        return episode.perform()
    except Cancelled as exc:
        status, reason = "cancelled", str(exc)
    except (BudgetExceeded, TimeoutError, ValueError) as exc:
        status, reason = "unresolved", str(exc)
    except InfrastructureError as exc:
        status, reason = "infrastructure_error", str(exc)
    for candidate in episode.snapshot["candidates"]:
        if candidate["eligibility"] == "pending":
            candidate.update(eligibility="rejected", rejection_reason="Incomplete verification")
    return episode.finish(status, reason)
