"""The json.v1 codec: null/bool/int/string/list/string-keyed dict, nothing implicit.

No tuple/list, set/list, float or arbitrary-object conversion happens here; such values are
rejected. Booleans never equal integers and equality is type-sensitive and recursive.
"""

import hashlib
import json

MAX_SAFE_INTEGER = 2**53 - 1
MAX_DEPTH = 8
MAX_NODES = 4096
MAX_STRING = 8000


class CodecError(ValueError):
    """A value is outside json.v1."""


def validate_value(
    value: object,
    *,
    max_depth: int = MAX_DEPTH,
    max_nodes: int = MAX_NODES,
    _depth: int = 0,
    _budget: list[int] | None = None,
) -> None:
    budget = [max_nodes] if _budget is None else _budget
    budget[0] -= 1
    if _depth > max_depth or budget[0] < 0:
        raise CodecError("JSON nesting or node limit exceeded")
    kind = type(value)
    if value is None or kind is bool:
        return
    if kind is int:
        if abs(value) > MAX_SAFE_INTEGER:
            raise CodecError("Unsafe integer outside +/-(2^53-1)")
        return
    if kind is str:
        if len(value) > MAX_STRING:
            raise CodecError("String too long")
        return
    if kind is list:
        for item in value:
            validate_value(item, max_depth=max_depth, _depth=_depth + 1, _budget=budget)
        return
    if kind is dict:
        for key, item in value.items():
            if type(key) is not str or len(key) > MAX_STRING:
                raise CodecError("Dictionary keys must be strings")
            validate_value(item, max_depth=max_depth, _depth=_depth + 1, _budget=budget)
        return
    raise CodecError(f"Unsupported type {kind.__name__}; no implicit conversion is performed")


def canonical(value: object) -> str:
    """Deterministic compact text; the same bytes every run and on every platform."""
    validate_value(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


encode = canonical


def _reject_constant(name: str):
    raise CodecError(f"Non-finite constant {name} is not json.v1")


def _reject_float(text: str):
    raise CodecError(f"Float {text} is not json.v1")


def _no_duplicates(pairs):
    out = {}
    for key, item in pairs:
        if key in out:
            raise CodecError("Duplicate dictionary key")
        out[key] = item
    return out


def decode(text: str) -> object:
    try:
        value = json.loads(
            text,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_no_duplicates,
        )
    except json.JSONDecodeError as exc:
        raise CodecError("Malformed JSON") from exc
    validate_value(value)
    return value


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def value_hash(value: object) -> str:
    return sha256_text(canonical(value))


def typed_equal(a: object, b: object, _depth: int = 0) -> bool:
    if _depth > MAX_DEPTH + 1 or type(a) is not type(b):
        return False
    if type(a) is list:
        return len(a) == len(b) and all(typed_equal(x, y, _depth + 1) for x, y in zip(a, b))
    if type(a) is dict:
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k], _depth + 1) for k in a)
    return a == b
