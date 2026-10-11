"""Trusted disclosed contract oracles, evaluated independently of candidate code."""

PROPERTY_IDS = frozenset({"sort_ascending_ints", "unique_preserve_order_ints", "sum_ints"})


def equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal(left[key], right[key]) for key in left)
    return left == right


def expected(property_id: str, values: list[int]) -> int | list[int]:
    if property_id not in PROPERTY_IDS:
        raise ValueError("Unapproved property")
    if type(values) is not list or any(type(value) is not int for value in values):
        raise ValueError("Property requires a list of integers")
    if property_id == "sort_ascending_ints":
        return sorted(values)
    if property_id == "unique_preserve_order_ints":
        return list(dict.fromkeys(values))
    return sum(values)


def check(property_id: str, args: list, actual: object) -> bool:
    if len(args) != 1:
        raise ValueError("Property requires exactly one argument")
    return equal(expected(property_id, args[0]), actual)


def outcome(test: dict, actual: object, *, input_mutated: bool = False) -> str:
    """Proposals/observations never gain authority through a candidate result."""
    if test["oracle_status"] != "authoritative":
        return "observed"
    if input_mutated:
        return "fail"
    if test["oracle_kind"] == "property":
        return "pass" if check(test["property_id"], test["args"], actual) else "fail"
    if test["oracle_kind"] == "literal" and test["oracle_source"] == "user":
        return "pass" if equal(test["expected"], actual) else "fail"
    raise ValueError("Invalid authoritative oracle")
