"""ToolPort: validate/evaluate/search/audit/investigate behind one contract-checked facade.

Nothing here executes candidate code; execution goes through the injected SandboxPort. Tests of
this class need no running partner implementation.
"""

import threading

from ..auditor import AuditCache, Auditor
from ..codec import errors, sha256_text
from ..domains import (
    DomainError,
    SourceError,
    analyze_source,
    check_args,
    check_bundle,
    validate_arg_domains,
)
from ..investigation import InvestigationError, Investigator
from ..oracles import OracleError, admit_test
from ..oracles.gate import check_requirements
from ..runner import Evaluator, InfrastructureError
from ..search import SearchEngine
from .verify import ResultError, verify_result

ZERO_USAGE = {
    "schema_version": "stage2.v1",
    "output_tokens": 0,
    "input_tokens": 0,
    "function_executions": 0,
    "elapsed_ms": 0,
    "learned_candidates": 0,
    "search_candidates": 0,
    "audit_mutants": 0,
    "judge_decisions": 0,
    "peak_memory_mb": None,
}


class RequestRejected(ValueError):
    def __init__(self, message: str, fields: list[str] | None = None):
        super().__init__(message)
        self.fields = fields or []


def _error(code: str, message: str, fields=()) -> dict:
    return {"code": code, "message": message[:500], "field_errors": list(fields)[:8]}


def _result(request_id: str, status: str, **kw) -> dict:
    base = {
        "schema_version": "stage2.v1",
        "request_id": request_id,
        "status": status,
        "validation": None,
        "candidates": [],
        "tests": [],
        "executions": [],
        "mutants": [],
        "audit_gaps": [],
        "edit_sources": [],
        "usage": dict(ZERO_USAGE),
        "warnings": [],
        "error": None,
    }
    base.update(kw)
    return base


class ToolPortImpl:
    mode = "live"

    def __init__(self, sandbox, *, contracts=None):
        self.sandbox = sandbox
        self.contracts = contracts
        self.audit_cache = AuditCache()
        self.last_evaluator: Evaluator | None = None

    # -- public ---------------------------------------------------------------------------
    def call(self, request: dict, cancel: threading.Event) -> dict:
        request_id = request.get("request_id") if isinstance(request, dict) else None
        if not (isinstance(request_id, str) and 1 <= len(request_id) <= 120):
            request_id = "invalid-request"
        try:
            problems = errors(request, "ToolRequest", self.contracts)
            if problems:
                raise RequestRejected("ToolRequest failed structural validation", problems)
            self._check_request(request)
            if cancel.is_set():
                return _result(request_id, "cancelled")
            result = self._dispatch(request, cancel)
            verify_result(request, result, self.contracts)
            return result
        except RequestRejected as exc:
            return _result(
                request_id, "invalid_input", error=_error("invalid_input", str(exc), exc.fields)
            )
        except InfrastructureError as exc:
            return _result(
                request_id,
                "infrastructure_error",
                error=_error("infrastructure_error", str(exc)),
                usage=self._usage_so_far(),
            )
        except ResultError as exc:
            return _result(
                request_id,
                "infrastructure_error",
                error=_error("internal_contract_violation", str(exc)),
                usage=self._usage_so_far(),
            )

    def _usage_so_far(self) -> dict:
        ev = self.last_evaluator
        usage = dict(ZERO_USAGE)
        if ev is not None:
            usage.update(function_executions=ev.used, elapsed_ms=ev.elapsed_ms)
        return usage

    # -- request checks -------------------------------------------------------------------
    def _check_request(self, request: dict) -> None:
        problem = request["problem"]
        if len(request["id_prefix"]) > 100:
            raise RequestRejected("id_prefix must leave room for delegated suffixes")
        try:
            if sha256_text(problem["source"]) != problem["source_hash"]:
                raise RequestRejected("Problem.source_hash does not match its source")
            info = analyze_source(
                problem["source"],
                problem["function_name"],
                problem["helper_interfaces"],
                problem["allowed_dependencies"],
            )
            if info.signature != problem["signature"]:
                raise RequestRejected("Problem.signature does not match the source")
            validate_arg_domains(problem["domain_schema"])
            check_requirements(problem["requirements"], problem["domain_schema"])
        except (SourceError, DomainError, OracleError) as exc:
            raise RequestRejected(f"Problem rejected: {exc}") from exc
        params = request["parameters"]
        operation = params["operation"]
        if operation in {"evaluate", "search", "audit", "investigate"}:
            tests = params.get("tests", params.get("existing_tests", []))
            self._check_tests(problem, tests)
        drafts = []
        if operation == "evaluate":
            drafts = params["candidates"]
        elif operation == "search":
            drafts = params["parents"]
        elif operation == "audit":
            drafts = [params["candidate"]]
        elif operation == "investigate":
            drafts = params["candidates"]
        ids = set()
        for draft in drafts:
            if draft["candidate_id"] in ids:
                raise RequestRejected(f"Duplicate candidate id {draft['candidate_id']}")
            ids.add(draft["candidate_id"])
            if draft["problem_id"] != problem["problem_id"]:
                raise RequestRejected(
                    f"Candidate {draft['candidate_id']} belongs to another problem"
                )
            if sha256_text(draft["source"]) != draft["source_hash"]:
                raise RequestRejected(
                    f"Candidate {draft['candidate_id']} hash does not match source"
                )
        if operation == "search" and len({c["candidate_id"] for c in drafts}) != len(drafts):
            raise RequestRejected("Duplicate parents")

    def _check_tests(self, problem: dict, tests: list[dict]) -> None:
        seen = set()
        for test in tests:
            if test["test_id"] in seen:
                raise RequestRejected(f"Duplicate test id {test['test_id']}")
            seen.add(test["test_id"])
            try:
                settled = admit_test(test, problem)
            except OracleError as exc:
                raise RequestRejected(f"Test {test['test_id']}: {exc}") from exc
            if test["domain_valid"] != settled["domain_valid"]:
                raise RequestRejected(f"Test {test['test_id']}: wrong domain_valid flag")
            if test["oracle_status"] == "authoritative" and settled["oracle_status"] != (
                "authoritative"
            ):
                raise RequestRejected(
                    f"Test {test['test_id']} claims authority the oracle gate does not grant"
                )

    # -- dispatch -------------------------------------------------------------------------
    def _evaluator(self, request, cancel) -> Evaluator:
        budget = request["remaining_budget"]
        self.last_evaluator = Evaluator(
            self.sandbox,
            request["problem"],
            id_prefix=request["id_prefix"],
            max_executions=budget["function_executions"],
            cancel=cancel,
        )
        return self.last_evaluator

    def _usage(self, ev: Evaluator, **extra) -> dict:
        usage = dict(ZERO_USAGE)
        usage.update(function_executions=ev.used, elapsed_ms=ev.elapsed_ms, **extra)
        return usage

    @staticmethod
    def _status(ev: Evaluator, outcome_status: str = "ok") -> str:
        if ev.cancelled or outcome_status == "cancelled":
            return "cancelled"
        if outcome_status == "budget_exhausted" or ev.exhausted:
            return "budget_exhausted"
        return "ok"

    def _dispatch(self, request: dict, cancel: threading.Event) -> dict:
        params = request["parameters"]
        operation = params["operation"]
        rid = request["request_id"]
        problem = request["problem"]
        if operation == "validate":
            return self._validate(rid, problem, params)
        budget = request["remaining_budget"]
        if budget["function_executions"] < 1:
            return _result(rid, "budget_exhausted", warnings=["no function executions remain"])
        ev = self._evaluator(request, cancel)
        if operation == "evaluate":
            rows, warnings = [], []
            for candidate in params["candidates"]:
                done = ev.evaluate(
                    candidate,
                    params["tests"],
                    stop_on_first_hard_failure=params["stop_on_first_hard_failure"],
                )
                rows.extend(done)
                if candidate["candidate_id"] in ev.static_rejections:
                    warnings.append(
                        f"{candidate['candidate_id']} rejected statically: "
                        f"{ev.static_rejections[candidate['candidate_id']]}"
                    )
                if ev.cancelled or ev.exhausted:
                    break
            return _result(
                rid, self._status(ev), executions=rows, usage=self._usage(ev), warnings=warnings
            )
        if operation == "search":
            limit = min(params["candidate_limit"], budget["search_candidates"])
            if limit < 1:
                return _result(rid, "budget_exhausted", warnings=["no search candidates remain"])
            engine = SearchEngine(
                ev,
                problem,
                params["parents"],
                params["tests"],
                sites=params["sites"],
                families=params["families"],
                depth=params["depth"],
                candidate_limit=limit,
                id_prefix=request["id_prefix"],
            )
            out = engine.run()
            return _result(
                rid,
                self._status(ev, out.status),
                candidates=out.candidates,
                executions=out.executions,
                edit_sources=out.edit_sources,
                usage=self._usage(ev, search_candidates=out.search_candidates),
                warnings=out.warnings,
            )
        if operation == "audit":
            return self._audit(rid, request, ev)
        return self._investigate(rid, request, ev)

    def _validate(self, rid: str, problem: dict, params: dict) -> dict:
        try:
            info = analyze_source(
                params["source"],
                problem["function_name"],
                problem["helper_interfaces"],
                problem["allowed_dependencies"],
            )
            if info.signature != problem["signature"]:
                raise SourceError("Target signature changed")
            warnings = []
            for test in params["tests"]:
                reason = check_args(problem["domain_schema"], test["inputs"])
                if reason:
                    warnings.append(f"test {test['test_id']} outside the domain: {reason}")
            receipt = {
                "valid": True,
                "signature": info.signature,
                "error": None,
                "warnings": warnings,
            }
        except SourceError as exc:
            receipt = {
                "valid": False,
                "signature": None,
                "error": _error("invalid_source", str(exc)),
                "warnings": [],
            }
        return _result(rid, "ok", validation=receipt)

    def _audit(self, rid: str, request: dict, ev: Evaluator) -> dict:
        params, problem = request["parameters"], request["problem"]
        remaining = request["remaining_budget"]["audit_mutants"]
        candidate = params["candidate"]
        try:
            check_bundle(candidate["source"], problem)
        except SourceError as exc:
            raise RequestRejected(f"Audit candidate rejected: {exc}") from exc
        approved = [
            r["requirement_id"]
            for r in problem["requirements"]
            if r["approval_status"] == "approved"
        ]
        mapped = [r for r in candidate["requirement_ids"] if r in approved]
        justified = mapped if len(approved) == 1 and mapped == approved else []
        out = Auditor(
            ev,
            problem,
            candidate,
            params["tests"],
            max_mutants=params["max_mutants"],
            suite=params["suite_hash"],
            id_prefix=request["id_prefix"],
            episode_remaining=remaining,
            requirement_ids=justified,
            cache=self.audit_cache,
        ).run()
        return _result(
            rid,
            self._status(ev, out.status),
            mutants=out.mutants,
            audit_gaps=out.gaps,
            usage=self._usage(ev, audit_mutants=len(out.mutants)),
            warnings=out.warnings,
        )

    def _investigate(self, rid: str, request: dict, ev: Evaluator) -> dict:
        params, problem = request["parameters"], request["problem"]
        try:
            out = Investigator(
                ev,
                problem,
                params["proposal"],
                params["candidates"],
                params["existing_tests"],
                max_inputs=params["max_inputs"],
                id_prefix=request["id_prefix"],
            ).run()
        except InvestigationError as exc:
            raise RequestRejected(f"Proposal rejected: {exc}") from exc
        return _result(
            rid,
            self._status(ev, out.status),
            tests=out.tests,
            executions=out.executions,
            usage=self._usage(ev),
            warnings=out.warnings,
        )
