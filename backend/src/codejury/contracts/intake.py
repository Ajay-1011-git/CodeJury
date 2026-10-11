"""Stage 1 structural and business validation; AST parsing never executes source."""

import ast
import hashlib
import keyword

from ..properties import equal, expected
from . import validate

MAX_SAFE_INTEGER = 2**53 - 1


class IntakeError(ValueError):
    pass


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def inspect_source(source: str, function_name: str, arity: int) -> None:
    if len(source) > 24000 or not function_name.isidentifier() or keyword.iskeyword(function_name):
        raise IntakeError("Invalid source length or function name")
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise IntakeError("Source must be valid Python syntax") from exc
    if len(tree.body) != 1 or type(tree.body[0]) is not ast.FunctionDef:
        raise IntakeError("Source must contain exactly one top-level function")
    function = tree.body[0]
    params = function.args
    if function.name != function_name or function.decorator_list or function.returns:
        raise IntakeError("Name mismatch, decorator or return annotation")
    positional = params.posonlyargs + params.args
    if (
        len(positional) != arity
        or not 1 <= arity <= 3
        or params.vararg
        or params.kwarg
        or params.kwonlyargs
        or params.defaults
        or any(param.annotation for param in positional)
    ):
        raise IntakeError("Require 1–3 unannotated positional parameters without defaults")
    nodes = list(ast.walk(tree))
    if len(nodes) > 5000:
        raise IntakeError("Source AST exceeds node limit")
    forbidden = (
        ast.Import,
        ast.ImportFrom,
        ast.ClassDef,
        ast.AsyncFunctionDef,
        ast.Global,
        ast.Nonlocal,
        ast.Lambda,
        ast.Yield,
        ast.YieldFrom,
    )
    for node in nodes:
        if (
            isinstance(node, forbidden)
            or isinstance(node, ast.FunctionDef)
            and node is not function
        ):
            raise IntakeError(
                "Imports, helpers, classes, generators and global state are unsupported"
            )


def validate_json(value: object, depth: int = 0, remaining: list[int] | None = None) -> None:
    if remaining is None:
        remaining = [4096]
    remaining[0] -= 1
    if depth > 8 or remaining[0] < 0:
        raise IntakeError("JSON nesting or size limit exceeded")
    if value is None or type(value) is bool:
        return
    if type(value) is int and abs(value) <= MAX_SAFE_INTEGER:
        return
    if type(value) is str and len(value) <= 8000:
        return
    if type(value) is list:
        for item in value:
            validate_json(item, depth + 1, remaining)
        return
    if type(value) is dict and all(type(key) is str and len(key) <= 8000 for key in value):
        for item in value.values():
            validate_json(item, depth + 1, remaining)
        return
    raise IntakeError("Unsupported JSON value or unsafe integer")


def validate_domain(domain: dict) -> None:
    lo, hi = domain["min"], domain["max"]
    if type(lo) is not int or type(hi) is not int or not -1000 <= lo <= hi <= 1000:
        raise IntakeError("Integer bounds must satisfy -1000 <= min <= max <= 1000")
    start, end = domain["min_length"], domain["max_length"]
    if domain["kind"] == "integer":
        if start is not None or end is not None:
            raise IntakeError("Integer domains require null length fields")
    elif type(start) is not int or type(end) is not int or not 0 <= start <= end <= 30:
        raise IntakeError("List lengths must satisfy 0 <= min_length <= max_length <= 30")


def validate_args(args: list, domains: list[dict]) -> None:
    if type(args) is not list or len(args) != len(domains):
        raise IntakeError("Argument count must match input domain")
    for value, domain in zip(args, domains):
        values = [value]
        if domain["kind"] == "list_integer":
            if (
                type(value) is not list
                or not domain["min_length"] <= len(value) <= domain["max_length"]
            ):
                raise IntakeError("List argument length outside domain")
            values = value
        if any(
            type(item) is not int or not domain["min"] <= item <= domain["max"] for item in values
        ):
            raise IntakeError("Argument must contain bounded integers; booleans are unsupported")


def validate_request(request: dict) -> None:
    validate(request, "RunCreate")
    domains = request["input_domain"]
    for domain in domains:
        validate_domain(domain)
    inspect_source(request["source"], request["function_name"], len(domains))
    prop = request["approved_property"]
    if prop and (len(domains) != 1 or domains[0]["kind"] != "list_integer"):
        raise IntakeError("Approved properties require exactly one list_integer argument")
    identifiers = set()
    for test in request["supplied_tests"]:
        if test["test_id"] in identifiers:
            raise IntakeError("Duplicate supplied test ID")
        identifiers.add(test["test_id"])
        validate_args(test["args"], domains)
        validate_json(test["expected"])
        if prop and not equal(test["expected"], expected(prop, test["args"][0])):
            raise IntakeError("Supplied expectation conflicts with approved property")


def validate_test(test: dict, request: dict) -> None:
    validate(test, "TestCase")
    validate_args(test["args"], request["input_domain"])
    validate_json(test["expected"])
    kind, status, source = test["oracle_kind"], test["oracle_status"], test["oracle_source"]
    prop = test["property_id"]
    if kind in {"property", "observation"} and test["expected"] is not None:
        raise IntakeError("Property/observation expected value must be null")
    if kind == "property":
        if not prop or prop != request["approved_property"] or source != "reviewed_contract":
            raise IntakeError("Property must reference explicitly approved contract")
    elif prop is not None:
        raise IntakeError("Non-property oracle must have null property_id")
    if status == "authoritative":
        if kind == "literal":
            supplied = next(
                (t for t in request["supplied_tests"] if t["test_id"] == test["test_id"]), None
            )
            if source != "user" or test["provenance"] != "supplied" or supplied is None:
                raise IntakeError("Only supplied user literals can be authoritative")
            if not equal(test["args"], supplied["args"]) or not equal(
                test["expected"], supplied["expected"]
            ):
                raise IntakeError("Supplied oracle bytes/values cannot change")
        elif kind != "property":
            raise IntakeError("Observations cannot become authoritative")
