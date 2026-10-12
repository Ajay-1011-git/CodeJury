"""ValueDomain validation and type-sensitive membership.

Domain limits (architecture): integers within +/-1,000,000, strings <=128 codepoints over an
explicit alphabet, lists <=64, dictionaries <=20 entries with explicit required keys, unions of
2-6 alternatives, container nesting <=4. Unions may overlap; membership accepts any option.
"""

import keyword

from ..codec import CodecError, validate_value

INT_LIMIT = 1_000_000
MAX_STRING = 128
MAX_LIST = 64
MAX_DICT = 20
MAX_NESTING = 4
MAX_ALPHABET = 256


class DomainError(ValueError):
    pass


def _nesting(domain: dict) -> int:
    kind = domain.get("kind")
    if kind == "list":
        return 1 + _nesting(domain["item_domain"])
    if kind == "dict":
        return 1 + _nesting(domain["value_domain"])
    if kind == "union":
        return max(_nesting(option) for option in domain["options"])
    return 0


def validate_domain(domain: dict, _depth: int = 0) -> None:
    if _depth > 2 * MAX_NESTING + 2:
        raise DomainError("Domain nesting exceeds the limit")
    if not isinstance(domain, dict) or "kind" not in domain:
        raise DomainError("Domain must be an object with a kind")
    kind = domain["kind"]
    keys = set(domain)
    expected = {
        "null": {"kind"},
        "boolean": {"kind"},
        "integer": {"kind", "min", "max"},
        "string": {"kind", "alphabet", "min_length", "max_length"},
        "list": {"kind", "item_domain", "min_length", "max_length"},
        "dict": {"kind", "key_domain", "value_domain", "required_keys", "min_size", "max_size"},
        "union": {"kind", "options"},
    }
    if kind not in expected:
        raise DomainError(f"Unknown domain kind {kind!r}")
    if keys != expected[kind]:
        raise DomainError(f"Domain fields for {kind} must be exactly {sorted(expected[kind])}")
    if kind == "integer":
        lo, hi = domain["min"], domain["max"]
        if type(lo) is not int or type(hi) is not int or not -INT_LIMIT <= lo <= hi <= INT_LIMIT:
            raise DomainError("Integer bounds must satisfy -1000000 <= min <= max <= 1000000")
    elif kind == "string":
        alphabet = domain["alphabet"]
        lo, hi = domain["min_length"], domain["max_length"]
        if type(alphabet) is not str or not 1 <= len(alphabet) <= MAX_ALPHABET:
            raise DomainError("String alphabet must contain 1-256 codepoints")
        if len(set(alphabet)) != len(alphabet):
            raise DomainError("String alphabet has duplicate codepoints")
        if any(0xD800 <= ord(ch) <= 0xDFFF or ord(ch) < 32 for ch in alphabet):
            raise DomainError("Alphabet may not contain surrogates or control characters")
        if type(lo) is not int or type(hi) is not int or not 0 <= lo <= hi <= MAX_STRING:
            raise DomainError("String lengths must satisfy 0 <= min_length <= max_length <= 128")
    elif kind == "list":
        lo, hi = domain["min_length"], domain["max_length"]
        if type(lo) is not int or type(hi) is not int or not 0 <= lo <= hi <= MAX_LIST:
            raise DomainError("List lengths must satisfy 0 <= min_length <= max_length <= 64")
        validate_domain(domain["item_domain"], _depth + 1)
    elif kind == "dict":
        validate_domain(domain["key_domain"], _depth + 1)
        if domain["key_domain"]["kind"] != "string":
            raise DomainError("Dictionary key domain must be a string domain")
        validate_domain(domain["value_domain"], _depth + 1)
        required = domain["required_keys"]
        lo, hi = domain["min_size"], domain["max_size"]
        if type(lo) is not int or type(hi) is not int or not 0 <= lo <= hi <= MAX_DICT:
            raise DomainError("Dictionary sizes must satisfy 0 <= min_size <= max_size <= 20")
        if (
            type(required) is not list
            or len(required) > MAX_DICT
            or len(set(required)) != len(required)
            or any(type(k) is not str for k in required)
        ):
            raise DomainError("Required keys must be unique strings, at most 20")
        if len(required) > hi:
            raise DomainError("More required keys than max_size")
        for key in required:
            problem = check_value(domain["key_domain"], key)
            if problem:
                raise DomainError(f"Required key {key!r} is outside the key domain")
    elif kind == "union":
        options = domain["options"]
        if type(options) is not list or not 2 <= len(options) <= 6:
            raise DomainError("Union needs 2-6 alternatives")
        for option in options:
            validate_domain(option, _depth + 1)
    if _depth == 0 and _nesting(domain) > MAX_NESTING:
        raise DomainError("Container nesting exceeds 4")


def check_value(domain: dict, value: object) -> str | None:
    """Return None when the value is in the domain, else a short reason. Type-sensitive."""
    kind = domain["kind"]
    if kind == "null":
        return None if value is None else "expected null"
    if kind == "boolean":
        return None if type(value) is bool else "expected boolean"
    if kind == "integer":
        if type(value) is not int:
            return "expected integer (booleans are not integers)"
        return None if domain["min"] <= value <= domain["max"] else "integer out of bounds"
    if kind == "string":
        if type(value) is not str:
            return "expected string"
        if not domain["min_length"] <= len(value) <= domain["max_length"]:
            return "string length outside domain"
        return None if set(value) <= set(domain["alphabet"]) else "character outside alphabet"
    if kind == "list":
        if type(value) is not list:
            return "expected list"
        if not domain["min_length"] <= len(value) <= domain["max_length"]:
            return "list length outside domain"
        for item in value:
            problem = check_value(domain["item_domain"], item)
            if problem:
                return problem
        return None
    if kind == "dict":
        if type(value) is not dict:
            return "expected dictionary"
        if not domain["min_size"] <= len(value) <= domain["max_size"]:
            return "dictionary size outside domain"
        for key in domain["required_keys"]:
            if key not in value:
                return f"missing required key {key!r}"
        for key, item in value.items():
            problem = check_value(domain["key_domain"], key) or check_value(
                domain["value_domain"], item
            )
            if problem:
                return problem
        return None
    if kind == "union":
        reasons = [check_value(option, value) for option in domain["options"]]
        return None if None in reasons else "value matches no union alternative"
    return "unknown domain"


def value_in_domain(domain: dict, value: object) -> bool:
    return check_value(domain, value) is None


def validate_arg_domains(domain_schema: list[dict]) -> None:
    if type(domain_schema) is not list or not 1 <= len(domain_schema) <= 6:
        raise DomainError("1-6 argument domains are required")
    names = set()
    for arg in domain_schema:
        name = arg.get("name") if isinstance(arg, dict) else None
        if set(arg) != {"name", "domain"} or type(name) is not str:
            raise DomainError("Argument domain must have name and domain")
        if not name.isidentifier() or keyword.iskeyword(name) or name in names:
            raise DomainError(f"Invalid or duplicate argument name {name!r}")
        names.add(name)
        validate_domain(arg["domain"])


def check_args(domain_schema: list[dict], inputs: object) -> str | None:
    """Reason an input vector is not a valid call for the schema, else None."""
    if type(inputs) is not list or len(inputs) != len(domain_schema):
        return "argument count differs from the domain schema"
    try:
        validate_value(inputs)
    except CodecError as exc:
        return str(exc)
    for arg, value in zip(domain_schema, inputs):
        problem = check_value(arg["domain"], value)
        if problem:
            return f"{arg['name']}: {problem}"
    return None
