"""Runtime-visible prompts and bounded structured model outputs."""

import copy
import json

from ..contracts.intake import inspect_source, validate_args, validate_json, validate_request
from ..properties import equal

REPAIR_SYSTEM = (
    "Repair one pure Python function. Return only JSON with source, diagnosis, assumptions. "
    "Preserve the contract and positional signature. "
    "Emit one undecorated function with unannotated positional parameters; "
    "no imports, helper functions, classes or defaults. "
    'The output object has exactly these three keys: {"source":"replacement Python source",'
    '"diagnosis":"brief explanation","assumptions":[]}. '
    "Do not copy the request envelope, change supplied tests, or use Markdown fences."
)
CRITIC_SYSTEM = (
    "Propose a bounded input family challenging the supplied candidate. Return only JSON "
    "with property_id, family, reason. Reference only the explicitly approved property. "
    "Use null property_id for observation-only input proposals. "
    "Allowed family: general, empty, singleton, duplicates, descending, boundary. "
    "Never invent an authoritative expected output."
)
FAMILIES = frozenset({"general", "empty", "singleton", "duplicates", "descending", "boundary"})


def repair_view(request, failures, counterexample=None):
    validate_request(request)
    if any(set(failure) != {"test_id", "args", "result"} for failure in failures):
        raise ValueError("Only visible failure evidence is allowed")
    result_keys = {
        "actual_output",
        "exception_type",
        "input_mutated",
        "duration_ms",
        "trace",
        "trace_truncated",
    }
    if any(
        type(failure["result"]) is not dict or set(failure["result"]) != result_keys
        for failure in failures
    ):
        raise ValueError("Unexpected failure result fields")
    for failure in failures:
        supplied = next(
            (test for test in request["supplied_tests"] if test["test_id"] == failure["test_id"]),
            None,
        )
        if supplied is None or not equal(failure["args"], supplied["args"]):
            raise ValueError("Hidden failure evidence must refer to supplied visible tests")
    body = {"request": copy.deepcopy(request), "failure_evidence": copy.deepcopy(failures)}
    if counterexample is not None:
        allowed = {"args", "actual_output", "expected", "property_id", "oracle_status"}
        if set(counterexample) != allowed:
            raise ValueError("Unexpected counterexample fields")
        validate_args(counterexample["args"], request["input_domain"])
        if counterexample["property_id"] not in {None, request["approved_property"]}:
            raise ValueError("Counterexample cannot add an unapproved property")
        body["counterexample"] = copy.deepcopy(counterexample)
    validate_json(body)
    return body


def parse_repair(text, request):
    if len(text) > 24000:
        raise ValueError("Generated response too large")
    body = json.loads(text)
    if type(body) is not dict or set(body) != {"source", "diagnosis", "assumptions"}:
        raise ValueError("Expected strict repair JSON")
    if type(body["source"]) is not str or type(body["diagnosis"]) is not str:
        raise ValueError("Repair fields must be strings")
    if len(body["diagnosis"]) > 4000 or type(body["assumptions"]) is not list:
        raise ValueError("Invalid diagnosis/assumptions")
    if len(body["assumptions"]) > 10 or any(
        type(x) is not str or len(x) > 500 for x in body["assumptions"]
    ):
        raise ValueError("Assumptions exceed bounds")
    inspect_source(body["source"], request["function_name"], len(request["input_domain"]))
    return body


def parse_critic(text, approved_property):
    body = json.loads(text)
    if type(body) is not dict or set(body) != {"property_id", "family", "reason"}:
        raise ValueError("Invalid Critic proposal shape")
    if body["property_id"] is not None and body["property_id"] != approved_property:
        raise ValueError("Critic cannot add an unapproved oracle")
    if (
        type(body["family"]) is not str
        or body["family"] not in FAMILIES
        or type(body["reason"]) is not str
        or len(body["reason"]) > 2000
    ):
        raise ValueError("Invalid Critic family/reason")
    return body
