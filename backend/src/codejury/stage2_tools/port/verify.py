"""Business invariants of a ToolResult beyond the structural schema.

Used both before a result leaves the port (so invalid evidence never escapes) and by the
contract CLI against published fixtures.
"""

from ..codec import errors, sha256_text


class ResultError(ValueError):
    pass


EMPTY_BY_OPERATION = {
    "validate": {"candidates", "tests", "executions", "mutants", "audit_gaps", "edit_sources"},
    "evaluate": {"candidates", "tests", "mutants", "audit_gaps", "edit_sources"},
    "search": {"tests", "mutants", "audit_gaps"},
    "audit": {"candidates", "tests", "executions", "edit_sources"},
    "investigate": {"candidates", "mutants", "audit_gaps", "edit_sources"},
}


def _check_chain(candidate: dict, parents: dict[str, dict], artifacts: dict[str, str]) -> None:
    parent = parents.get(candidate["parent_id"])
    if parent is None:
        raise ResultError(f"{candidate['candidate_id']}: unknown parent {candidate['parent_id']}")
    edits = candidate["edits"]
    expected_from = parent["source_hash"]
    for edit in edits:
        if edit["parent_source_hash"] != expected_from:
            raise ResultError(f"{candidate['candidate_id']}: broken edit hash chain")
        expected_from = edit["result_source_hash"]
    if (
        expected_from != candidate["source_hash"]
        or sha256_text(candidate["source"]) != (candidate["source_hash"])
    ):
        raise ResultError(f"{candidate['candidate_id']}: final hash differs from source")
    for edit in edits[:-1]:
        mid = artifacts.get(edit["result_source_hash"])
        if mid is None or sha256_text(mid) != edit["result_source_hash"]:
            raise ResultError(f"{candidate['candidate_id']}: missing intermediate source artifact")


def verify_result(request: dict, result: dict, contracts=None) -> None:
    problems = errors(result, "ToolResult", contracts)
    if problems:
        raise ResultError("; ".join(problems))
    if result["request_id"] != request["request_id"]:
        raise ResultError("request_id mismatch")
    params = request["parameters"]
    operation = params["operation"]
    prefix = request["id_prefix"]
    for name in EMPTY_BY_OPERATION[operation]:
        if result[name]:
            raise ResultError(f"{operation} result must leave {name} empty")
    if operation != "validate" and result["validation"] is not None:
        raise ResultError("only validate may return a ValidationReceipt")
    if operation == "validate" and result["status"] == "ok" and result["validation"] is None:
        raise ResultError("validate must return a ValidationReceipt")
    seen: set[str] = set()
    for kind, key, field in (
        ("c", "candidate_id", "candidates"),
        ("t", "test_id", "tests"),
        ("e", "execution_id", "executions"),
        ("m", "mutant_id", "mutants"),
        ("g", "gap_id", "audit_gaps"),
    ):
        for item in result[field]:
            ident = item[key]
            if not ident.startswith(f"{prefix}-{kind}") or ident in seen:
                raise ResultError(f"{field}: id {ident} lacks the delegated prefix or repeats")
            seen.add(ident)
    usage = result["usage"]
    budget = request["remaining_budget"]
    for field in (
        "output_tokens",
        "input_tokens",
        "function_executions",
        "elapsed_ms",
        "learned_candidates",
        "search_candidates",
        "audit_mutants",
        "judge_decisions",
    ):
        if usage[field] > budget[field]:
            raise ResultError(f"usage {field} exceeds the remaining budget")
    if (
        usage["output_tokens"]
        or usage["input_tokens"]
        or usage["learned_candidates"]
        or usage["judge_decisions"]
    ):
        raise ResultError("tools never consume model/judge budget")
    if usage["function_executions"] < len(result["executions"]):
        raise ResultError("fewer function executions than execution rows")
    known_tests = {t["test_id"] for t in _request_tests(params)} | {
        t["test_id"] for t in result["tests"]
    }
    known_candidates = {c["candidate_id"] for c in _request_candidates(params)} | {
        c["candidate_id"] for c in result["candidates"]
    }
    for row in result["executions"]:
        if row["candidate_id"] not in known_candidates or row["test_id"] not in known_tests:
            raise ResultError(f"{row['execution_id']}: refers to an unknown candidate or test")
    if operation == "search":
        parents = {c["candidate_id"]: c for c in params["parents"]}
        artifacts = {a["source_hash"]: a["source"] for a in result["edit_sources"]}
        if len(result["candidates"]) > params["candidate_limit"]:
            raise ResultError("more candidates than candidate_limit")
        for candidate in result["candidates"]:
            if candidate["origin"] != "ast_search" or not 1 <= len(candidate["edits"]) <= 2:
                raise ResultError("search candidates need origin ast_search and 1-2 edits")
            _check_chain(candidate, parents, artifacts)
        if usage["search_candidates"] > 48:
            raise ResultError("more than 48 search candidates")
    if operation == "audit":
        if len(result["mutants"]) > params["max_mutants"]:
            raise ResultError("more probes than max_mutants")
        ids = {m["mutant_id"] for m in result["mutants"]}
        for gap in result["audit_gaps"]:
            if (
                gap["candidate_source_hash"] != params["candidate"]["source_hash"]
                or gap["suite_hash"] != params["suite_hash"]
            ):
                raise ResultError(f"{gap['gap_id']}: bound to a different source or suite")
            if not set(gap["mutant_ids"]) <= ids:
                raise ResultError(f"{gap['gap_id']}: unknown mutants")
        for mutant in result["mutants"]:
            if mutant["suite_hash"] != params["suite_hash"]:
                raise ResultError(f"{mutant['mutant_id']}: wrong suite hash")


def _request_tests(params: dict) -> list[dict]:
    if "tests" in params:
        return params["tests"]
    if "existing_tests" in params:
        return params["existing_tests"]
    return []


def _request_candidates(params: dict) -> list[dict]:
    if "candidates" in params:
        return params["candidates"]
    if "parents" in params:
        return params["parents"]
    if "candidate" in params:
        return [params["candidate"]]
    return []
