"""Strict JSON boundaries and deterministic identities for the frozen wire contract."""

import copy
import hashlib
import json
import math
from threading import Event

from jsonschema import Draft202012Validator, validators

from ..contract_check import load_schema

StrictValidator = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        "integer", lambda checker, value: type(value) is int
    ),
)


def _json_types(value) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_types(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_types(item)
        return
    raise ValueError("Only finite JSON values and string keys are permitted")


def canonical_json(value) -> bytes:
    _json_types(value)
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def json_hash(value) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def source_hash(source: str) -> str:
    if type(source) is not str:
        raise ValueError("Source must be an exact UTF-8 string")
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def checked(record, definition: str) -> dict:
    canonical_json(record)
    schema = load_schema()
    if definition not in schema["$defs"]:
        raise ValueError("Unknown contract definition")
    StrictValidator({**schema, "$ref": f"#/$defs/{definition}"}).validate(record)
    return copy.deepcopy(record)


def cache_key(
    source: str, test: dict, oracle_hash: str, runtime_hash: str, resource_hash: str
) -> str:
    checked(test, "TestCase")
    for value in (source, oracle_hash, runtime_hash, resource_hash):
        if (
            type(value) is not str
            or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError("Cache identities must be exact SHA-256 hashes")
    return json_hash(
        {
            "source": source,
            "test": test,
            "oracle": oracle_hash,
            "runtime": runtime_hash,
            "resource": resource_hash,
        }
    )


class Boundary:
    """Validate and copy both sides; cancellation token passes to the actual worker."""

    def __init__(self, port, method: str, request_type: str, response_type: str):
        self.port, self.method = port, method
        self.request_type, self.response_type = request_type, response_type

    def invoke(self, request: dict, cancel: Event) -> dict:
        request = checked(request, self.request_type)
        if cancel.is_set():
            raise InterruptedError("Cancelled before dispatch")
        response = checked(getattr(self.port, self.method)(request, cancel), self.response_type)
        if response["request_id"] != request["request_id"]:
            raise ValueError("Response request ID mismatch")
        for field in ("role", "method", "config_hash"):
            if field in request and response.get(field) != request[field]:
                raise ValueError(f"Response {field} mismatch")
        return response


class CheckedModelPort(Boundary):
    def __init__(self, port):
        super().__init__(port, "generate", "ModelRequest", "ModelResponse")

    generate = Boundary.invoke


class CheckedToolPort(Boundary):
    def __init__(self, port):
        super().__init__(port, "call", "ToolRequest", "ToolResult")

    call = Boundary.invoke


class CheckedRolloutPort(Boundary):
    def __init__(self, port):
        super().__init__(port, "continue_episode", "RolloutRequest", "RolloutResult")

    continue_episode = Boundary.invoke


class CheckedBaselinePort(Boundary):
    def __init__(self, port):
        super().__init__(port, "run", "MethodRequest", "MethodResult")

    run = Boundary.invoke
