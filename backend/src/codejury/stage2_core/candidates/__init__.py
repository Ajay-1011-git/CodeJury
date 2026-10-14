"""Strict draft parsing, durable attempt provenance, and current-suite qualification."""

import ast
import copy
import json
from difflib import SequenceMatcher
from uuid import uuid4

from jsonschema import ValidationError

from codejury.stage2_core.budgets import BudgetExceeded
from codejury.stage2_core.contracts import (
    CheckedModelPort,
    canonical_json,
    checked,
    json_hash,
    source_hash,
)
from codejury.stage2_core.intake import interfaces
from codejury.stage2_core.views import VIEW_VERSION, freeze_initial, revision


def parse_draft(text, definition="RepairDraft"):
    if not isinstance(text, str) or len(text.encode()) > 48000:
        raise ValueError("Draft exceeds UTF-8 bound")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    value = json.loads(
        text,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
    )
    return checked(value, definition)


def normalized(source):
    return source_hash(ast.dump(ast.parse(source), include_attributes=False))


def hard_suite(problem, tests):
    problem = checked(problem, "Problem")
    requirements = {r["requirement_id"]: r for r in problem["requirements"]}
    hard = []
    for test in tests:
        test = checked(test, "TestCase")
        if test["oracle_status"] != "authoritative":
            continue
        if (
            not test["domain_valid"]
            or test["oracle_source"] == "model"
            or test["oracle_spec"]["kind"] == "observation"
            or not test["requirement_ids"]
            or any(
                r not in requirements or requirements[r]["approval_status"] != "approved"
                for r in test["requirement_ids"]
            )
        ):
            raise ValueError("Hard test lacks approved authority")
        hard.append(test)
    if len({t["test_id"] for t in hard}) != len(hard):
        raise ValueError("Duplicate hard test")
    hard.sort(key=lambda t: t["test_id"])
    return hard, json_hash(
        {"version": "hard-suite.v1", "problem_hash": json_hash(problem), "tests": hard}
    )


def validated_tests(ledger, run_id, source, signature, tests):
    supported = set()
    with ledger.connection() as db:
        receipts = db.execute(
            "SELECT body,response FROM requests WHERE run_id=? AND definition='ToolRequest' "
            "AND status='settled'",
            (run_id,),
        ).fetchall()
    for row in receipts:
        request, response = json.loads(row["body"]), json.loads(row["response"])
        params, receipt = request["parameters"], response["validation"]
        if (
            params["operation"] == "validate"
            and params["source"] == source
            and response["status"] == "ok"
            and receipt
            and receipt["valid"]
            and receipt["error"] is None
            and receipt["signature"] == signature
        ):
            supported.update(t["test_id"] for t in params["tests"] if t in tests)
    return supported


def static_error(ledger, run_id, source, signature):
    """The registered static-validation error for a source, or None if none was recorded."""
    with ledger.connection() as db:
        receipts = db.execute(
            "SELECT body,response FROM requests WHERE run_id=? AND definition='ToolRequest' "
            "AND status='settled'",
            (run_id,),
        ).fetchall()
    error = None
    for row in receipts:
        request, response = json.loads(row["body"]), json.loads(row["response"])
        params, receipt = request["parameters"], response["validation"]
        if params["operation"] != "validate" or params["source"] != source or not receipt:
            continue
        if receipt["valid"] and receipt["error"] is None and receipt["signature"] == signature:
            return None
        error = receipt["error"] or "Signature differs from the required interface"
    return error


def qualification(ledger, run_id, *, runtime_hash):
    """Projection over immutable, registered evidence; no candidate rows are overwritten."""
    snapshot = ledger.snapshot(run_id)
    problem = snapshot["problem"]
    hard, suite_hash = hard_suite(problem, snapshot["tests"])
    ids = {t["test_id"] for t in hard}
    complete = bool(ids) and set(problem["supplied_test_ids"]) <= ids
    executions = snapshot["executions"]
    with ledger.connection() as db:
        transport = db.execute(
            "SELECT status,response FROM requests WHERE run_id=?", (run_id,)
        ).fetchall()
    transport_ok = all(
        row["status"] == "settled" and json.loads(row["response"])["status"] == "ok"
        for row in transport
    )
    candidates = []
    for candidate in snapshot["candidates"]:
        supported = validated_tests(ledger, run_id, candidate["source"], problem["signature"], hard)
        current = [
            e
            for e in executions
            if e["candidate_id"] == candidate["candidate_id"]
            and e["test_id"] in ids
            and e["runtime_hash"] == runtime_hash
        ]
        passed, failed = set(), set()
        for row in current:
            test = next(t for t in hard if t["test_id"] == row["test_id"])
            calls = 2 if test["related_inputs"] is not None else 1
            effects = row["input_effects"]
            clean = (
                len(effects) == calls
                and [e["call_index"] for e in effects] == list(range(calls))
                and all(not e["mutated"] and e["before_hash"] == e["after_hash"] for e in effects)
            )
            if row["outcome"] == "pass" and row["exception"] is None and clean:
                passed.add(row["test_id"])
            elif row["outcome"] != "pass" or row["exception"] is not None or not clean:
                failed.add(row["test_id"])
        eligible = (
            snapshot["status"] == "running"
            and transport_ok
            and candidate["origin"] != "original"
            and complete
            and supported >= ids
            and passed >= ids
            and not failed
        )
        rejection = (
            "Original is evidence, never a repair"
            if candidate["origin"] == "original"
            else "Hard evidence rejects this source"
            if failed
            else None
        )
        candidates.append(
            checked(
                {
                    **candidate,
                    "eligibility": "eligible"
                    if eligible
                    else "rejected"
                    if rejection
                    else "pending",
                    "rejection_reason": rejection,
                    "verification_suite_hash": suite_hash if eligible else None,
                },
                "Candidate",
            )
        )
    return {"candidates": candidates, "suite_hash": suite_hash}


def incumbent(projected, original_source):
    eligible = [
        c
        for c in projected["candidates"]
        if c["eligibility"] == "eligible" and c["origin"] != "original"
    ]
    a = [c for c in eligible if c["origin"] == "fixer_a"]
    if a:
        return min(a, key=lambda c: c["created_event_id"])["candidate_id"]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda c: (
            1 - SequenceMatcher(None, original_source, c["source"], autojunk=False).ratio(),
            c["created_event_id"],
        ),
    )["candidate_id"]


class CandidatePool:
    def __init__(self, ledger, run_id, model_port, identities, *, model_roles=None):
        self.ledger, self.run_id = ledger, run_id
        self.port = CheckedModelPort(model_port)
        self.identities = copy.deepcopy(identities)
        self.model_roles = (
            dict(model_roles)
            if model_roles is not None
            else {"fixer_a": "fixer_a", "fixer_b": "fixer_b"}
        )
        if set(self.model_roles) != {"fixer_a", "fixer_b"} or any(
            actual not in {channel, "raw", "general"}
            for channel, actual in self.model_roles.items()
        ):
            raise ValueError("Unknown repair-channel model binding")
        a, b = [identities[self.model_roles[r]] for r in ("fixer_a", "fixer_b")]
        if (
            model_roles is None
            and (
                not a["adapter_hash"]
                or not b["adapter_hash"]
                or a["adapter_hash"] == b["adapter_hash"]
            )
        ) or a["model_revision_hash"] != b["model_revision_hash"]:
            raise ValueError("Independent fixers require distinct real adapters on the same base")
        snapshot = ledger.snapshot(run_id)
        self.initial_input_hash = json_hash(
            {"problem": snapshot["problem"], "tests": snapshot["tests"]}
        )
        self.views = freeze_initial(snapshot["problem"], snapshot["tests"], original_evidence=())
        self._initial_started = False

    def archive(self, record):
        digest = self.ledger.put_object(canonical_json({"run_id": self.run_id, **record}))
        return digest

    def original(self):
        problem = self.ledger.snapshot(self.run_id)["problem"]
        return self.ledger.commit_candidate(
            self.run_id,
            {
                "schema_version": "stage2.v1",
                "candidate_id": "c-" + uuid4().hex,
                "problem_id": problem["problem_id"],
                "parent_id": None,
                "origin": "original",
                "generation_view": "original",
                "source": problem["source"],
                "source_hash": problem["source_hash"],
                "diagnosis": "Submitted original",
                "assumptions": [],
                "requirement_ids": [r["requirement_id"] for r in problem["requirements"]],
                "model_config_hash": None,
                "edits": [],
            },
        )

    def initial_pair(self, *, seed, cancel, original=None):
        if self._initial_started:
            raise ValueError("Initial pair already dispatched")
        snapshot = self.ledger.snapshot(self.run_id)
        problem, tests = snapshot["problem"], snapshot["tests"]
        if json_hash({"problem": problem, "tests": tests}) != self.initial_input_hash:
            raise ValueError("Frozen initial view is stale")
        if (
            snapshot["status"] != "running"
            or not tests
            or validated_tests(
                self.ledger, self.run_id, problem["source"], problem["signature"], tests
            )
            != {t["test_id"] for t in tests}
        ):
            raise ValueError("Initial generation requires successful semantic intake")
        # Freeze both full prompts before either generation, durably retain audit identity.
        self.archive(
            {
                "kind": "initial_pair",
                "version": VIEW_VERSION,
                "a": self.views.a,
                "b": self.views.b,
                "view_config_hash": self.views.view_config_hash,
            }
        )
        self._initial_started = True
        original = self.original() if original is None else original
        if original not in snapshot["candidates"] and original not in self.ledger.records(
            self.run_id, "candidates"
        ):
            raise ValueError("Original must be registered before reproduction")
        if original["origin"] != "original":
            raise ValueError("Initial generation needs an original parent")
        a = self.generate("fixer_a", self.views.a, parent=original, seed=seed, cancel=cancel)
        b = self.generate("fixer_b", self.views.b, parent=original, seed=seed, cancel=cancel)
        return {"original": original, "fixer_a": a, "fixer_b": b}

    def generate(self, role, prompt, *, parent, seed, cancel, revise=False, max_attempts=2):
        if role not in {"fixer_a", "fixer_b"}:
            raise ValueError("Repair generation requires a fixer")
        actual_role = self.model_roles[role]
        identity = self.identities[actual_role]
        if revise and parent["origin"] not in {role, role + "_revision"}:
            raise ValueError("Revision parent role mismatch")
        snapshot = self.ledger.snapshot(self.run_id)
        if parent not in snapshot["candidates"]:
            raise ValueError("Generation parent is stale or unregistered")
        if revise:
            expected_prompt = revision(
                role,
                snapshot["problem"],
                snapshot["tests"],
                parent,
                [e for e in snapshot["executions"] if e["candidate_id"] == parent["candidate_id"]],
                trace_reader=self.ledger.read_object,
                static_check=static_error(
                    self.ledger, self.run_id, parent["source"], snapshot["problem"]["signature"]
                ),
            )
        else:
            if parent["origin"] != "original":
                raise ValueError("Initial reconstruction requires the original parent")
            expected_prompt = self.views.a if role == "fixer_a" else self.views.b
        if prompt != expected_prompt:
            raise ValueError("Generation prompt differs from the controller role view")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 2:
            raise ValueError("Only one generation and at most one schema retry allowed")
        for attempt in range(max_attempts):
            remaining = self.ledger.accounts[self.run_id].remaining()
            if cancel.is_set():
                return None
            if remaining["learned_candidates"] < 1 or remaining["output_tokens"] < 1:
                raise BudgetExceeded("No budget for another fixer attempt")
            request_id = "model-" + uuid4().hex
            request = checked(
                {
                    "schema_version": "stage2.v1",
                    "request_id": request_id,
                    "run_id": self.run_id,
                    "role": actual_role,
                    "purpose": "baseline"
                    if actual_role in {"raw", "general"}
                    else "revise"
                    if revise
                    else "repair"
                    if role == "fixer_a"
                    else "reconstruct",
                    "prompt": prompt,
                    "seed": seed,
                    "max_new_tokens": min(1024, remaining["output_tokens"]),
                    "remaining_budget": remaining,
                },
                "ModelRequest",
            )
            self.archive(
                {
                    "kind": "dispatch",
                    "request": request,
                    "prompt_hash": source_hash(prompt),
                    "identity": identity,
                    "view_version": VIEW_VERSION,
                    "format_retry": attempt,
                }
            )
            self.ledger.dispatch_model(request, candidate_attempt=True)
            response = self.port.generate(request, cancel)
            self.ledger.settle_model(response)
            response_ref = self.archive({"kind": "response", "response": response})
            if response["status"] != "ok" or cancel.is_set():
                return None
            if any(
                response[k] != identity[k]
                for k in ("model_revision_hash", "adapter_hash", "model_config_hash")
            ):
                raise ValueError("Model response differs from frozen role identity")
            try:
                repair = parse_draft(response["text"])
            except (ValueError, RecursionError, ValidationError) as error:
                self.ledger.append_event(
                    self.run_id,
                    "action_refused",
                    f"Malformed {role} draft; response {response_ref}; {type(error).__name__}",
                )
                # Repeat only the same allowed view, never feed prose/other-role content back.
                prompt += "\nFormat retry: return one JSON object with the exact requested fields."
                continue
            problem = self.ledger.snapshot(self.run_id)["problem"]
            try:
                interfaces(repair["source"], problem["function_name"])
            except (ValueError, SyntaxError) as error:
                self.ledger.append_event(
                    self.run_id,
                    "action_refused",
                    f"Invalid {role} source; response {response_ref}; {type(error).__name__}",
                )
                return None
            digest, ast_hash = source_hash(repair["source"]), normalized(repair["source"])
            known = self.ledger.records(self.run_id, "candidates")
            duplicate = next(
                (
                    c["candidate_id"]
                    for c in known
                    if c["source_hash"] == digest or normalized(c["source"]) == ast_hash
                ),
                None,
            )
            draft = {
                "schema_version": "stage2.v1",
                "candidate_id": "c-" + uuid4().hex,
                "problem_id": problem["problem_id"],
                "parent_id": parent["candidate_id"],
                "origin": role + "_revision" if revise else role,
                "generation_view": "feedback_revision"
                if revise
                else "targeted_repair"
                if role == "fixer_a"
                else "independent_reconstruction",
                "source": repair["source"],
                "source_hash": digest,
                "diagnosis": repair["diagnosis"],
                "assumptions": repair["assumptions"],
                "requirement_ids": repair["requirement_ids"],
                "model_config_hash": response["model_config_hash"],
                "edits": [],
            }
            try:
                candidate = self.ledger.commit_candidate(
                    self.run_id, draft, expected_parent_hash=parent["source_hash"]
                )
            except (ValueError, ValidationError) as error:
                self.ledger.append_event(
                    self.run_id,
                    "action_refused",
                    f"Refused {role} candidate; response {response_ref}; {type(error).__name__}",
                )
                return None
            # Preserve every proposal. Canonical alternatives deduplicate separately.
            self.archive(
                {
                    "kind": "proposal",
                    "request_id": request_id,
                    "seed": seed,
                    "identity": identity,
                    "candidate_id": candidate["candidate_id"],
                    "duplicate_of": duplicate,
                    "normalized_ast_hash": ast_hash,
                    "hints": {k: repair[k] for k in ("suspected_sites", "suggested_families")},
                }
            )
            return candidate
        return None

    def alternatives(self):
        seen, result = set(), []
        for candidate in self.ledger.records(self.run_id, "candidates"):
            digest = normalized(candidate["source"])
            if digest not in seen:
                seen.add(digest)
                result.append(candidate)
        return result
