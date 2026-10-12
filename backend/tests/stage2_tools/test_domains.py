import copy
import importlib

import pytest

from codejury.stage2_tools.codec import (
    CodecError,
    canonical,
    decode,
    typed_equal,
    validate,
    validate_value,
)
from codejury.stage2_tools.domains import (
    ALLOWLIST,
    DomainError,
    SourceError,
    analyze_source,
    check_args,
    check_bundle,
    check_value,
    normalized_hash,
    validate_arg_domains,
    validate_domain,
)

INT = {"kind": "integer", "min": -5, "max": 5}


def lst(item, lo=0, hi=4):
    return {"kind": "list", "item_domain": item, "min_length": lo, "max_length": hi}


def test_bool_never_equals_int_and_null_preserved():
    assert not typed_equal(True, 1)
    assert not typed_equal([1, [True]], [1, [1]])
    assert not typed_equal({"a": None}, {"a": 0})
    assert typed_equal({"a": [1, None, "x"]}, {"a": [1, None, "x"]})
    assert check_value(INT, True) is not None
    assert check_value({"kind": "boolean"}, 1) is not None
    assert check_value({"kind": "null"}, None) is None


def test_codec_rejects_unsafe_and_implicit_conversions():
    for bad in (1.5, (1, 2), {1, 2}, float("nan"), object(), 2**53, {1: "x"}, b"x"):
        with pytest.raises(CodecError):
            validate_value(bad)
    validate_value(2**53 - 1)
    with pytest.raises(CodecError):
        decode("[1.0]")
    with pytest.raises(CodecError):
        decode("[NaN]")
    with pytest.raises(CodecError):
        decode('{"a":1,"a":2}')
    assert decode(canonical({"b": [1, None], "a": True})) == {"a": True, "b": [1, None]}


def test_codec_depth_and_node_limits():
    deep = []
    for _ in range(12):
        deep = [deep]
    with pytest.raises(CodecError):
        validate_value(deep)
    with pytest.raises(CodecError):
        validate_value(list(range(5000)))


def test_unicode_length_counts_codepoints():
    s = {"kind": "string", "alphabet": "a😀é", "min_length": 0, "max_length": 3}
    assert check_value(s, "😀😀😀") is None  # three codepoints, more UTF-8 bytes
    assert check_value(s, "😀😀😀a") is not None
    assert check_value(s, "b") is not None


def test_nested_domain_membership_with_duplicates_negatives():
    d = lst(lst(INT, 0, 3), 0, 3)
    assert check_value(d, [[1, -5, 1], []]) is None
    assert check_value(d, [[1, 6]]) is not None
    assert check_value(d, [[True]]) is not None
    assert check_value(d, [[1], [2], [3], [4]]) is not None


def test_dict_required_keys_and_union():
    key = {"kind": "string", "alphabet": "abc", "min_length": 1, "max_length": 2}
    d = {"kind": "dict", "key_domain": key, "value_domain": INT, "required_keys": ["a"],
         "min_size": 0, "max_size": 3}  # fmt: skip
    validate_domain(d)
    assert check_value(d, {"a": 1, "b": 2}) is None
    assert "missing required key" in check_value(d, {"b": 2})
    assert check_value(d, {"a": 1, "zz9": 2}) is not None
    union = {"kind": "union", "options": [INT, {"kind": "null"}]}
    validate_domain(union)
    assert check_value(union, None) is None and check_value(union, 3) is None
    assert check_value(union, "x") is not None
    overlapping = {"kind": "union", "options": [INT, {"kind": "integer", "min": 0, "max": 100}]}
    validate_domain(overlapping)
    assert check_value(overlapping, 50) is None


@pytest.mark.parametrize(
    "domain",
    [
        {"kind": "integer", "min": 3, "max": 1},
        {"kind": "integer", "min": 0, "max": 10**7},
        {"kind": "string", "alphabet": "", "min_length": 0, "max_length": 1},
        {"kind": "string", "alphabet": "aa", "min_length": 0, "max_length": 1},
        {"kind": "string", "alphabet": "a", "min_length": 0, "max_length": 129},
        {"kind": "list", "item_domain": INT, "min_length": 0, "max_length": 65},
        {"kind": "union", "options": [INT]},
        {"kind": "union", "options": [INT] * 7},
        {"kind": "mystery"},
        {"kind": "integer", "min": 0},
    ],
)
def test_invalid_domains(domain):
    with pytest.raises(DomainError):
        validate_domain(domain)


def test_invalid_depth_and_required_keys():
    deep = INT
    for _ in range(5):
        deep = lst(deep, 0, 1)
    with pytest.raises(DomainError):
        validate_domain(deep)
    key = {"kind": "string", "alphabet": "ab", "min_length": 1, "max_length": 1}
    base = {"kind": "dict", "key_domain": key, "value_domain": INT, "min_size": 0, "max_size": 2}
    for required in (["a", "a"], ["z"], ["a", "b", "c"]):
        with pytest.raises(DomainError):
            validate_domain({**base, "required_keys": required})


def test_arg_schema_names_and_counts():
    schema = [{"name": "xs", "domain": lst(INT)}, {"name": "k", "domain": INT}]
    validate_arg_domains(schema)
    assert check_args(schema, [[1], 2]) is None
    assert check_args(schema, [[1]]) is not None
    assert check_args(schema, [[1], 9]) is not None
    with pytest.raises(DomainError):
        validate_arg_domains([{"name": "x", "domain": INT}, {"name": "x", "domain": INT}])
    with pytest.raises(DomainError):
        validate_arg_domains([{"name": "class", "domain": INT}])


# ---- source analysis -------------------------------------------------------------------

GOOD = "def f(values):\n    total = 0\n    for v in values:\n        total += v\n    return total\n"


def test_good_source_and_signature():
    info = analyze_source(GOOD, "f", [], [])
    assert info.signature == "f(values)"


def test_helper_bundle_and_alias_resolution():
    src = (
        "from math import gcd as g\n\n"
        "def pair(a, b):\n    return g(a, b)\n\n"
        "def f(values):\n    r = 0\n    for v in values:\n        r = pair(r, v)\n    return r\n"
    )
    helpers = [{"name": "pair", "signature": "pair(a, b)", "contract_text": "gcd"}]
    info = analyze_source(src, "f", helpers, ["math.gcd"])
    assert info.imports == {"g": "math.gcd"} and info.helpers == {"pair": "pair(a, b)"}
    with pytest.raises(SourceError, match="not an allowed dependency"):
        analyze_source(src, "f", helpers, [])  # dependency not approved for this problem
    with pytest.raises(SourceError, match="no reviewed interface"):
        analyze_source(src, "f", [], ["math.gcd"])
    with pytest.raises(SourceError, match="changed its reviewed signature"):
        analyze_source(src, "f", [{**helpers[0], "signature": "pair(x, y)"}], ["math.gcd"])


@pytest.mark.parametrize(
    "src,message",
    [
        ("import os\ndef f(v):\n    return 1\n", "not an allowed dependency"),
        ("import math\ndef f(v):\n    return math.sqrt(v)\n", "not an allowed dependency"),
        ("from math import sqrt\ndef f(v):\n    return 1\n", "not an allowed dependency"),
        ("def f(v):\n    return eval('1')\n", "Unknown or disallowed name"),
        ("def f(v):\n    return open('x')\n", "Unknown or disallowed name"),
        ("def f(v):\n    return v.__class__\n", "attribute"),
        ("class C:\n    pass\ndef f(v):\n    return 1\n", "Only imports"),
        ("x = 1\ndef f(v):\n    return x\n", "Only imports"),
        ("def f(v):\n    global g\n    return 1\n", "Unsupported construct"),
        ("def f(v, w=1):\n    return v\n", "positional"),
        ("def f(*v):\n    return v\n", "positional"),
        ("@d\ndef f(v):\n    return v\n", "decorators"),
        ("def f(v):\n    yield v\n", "Unsupported construct"),
        ("async def f(v):\n    return v\n", "Only imports"),
        ("def f(v):\n    def g():\n        return 1\n    return g()\n", "Nested"),
        ("def f(v):\n    return (lambda: 1)()\n", "Unsupported construct"),
        ("def f(a,b,c,d,e,g,h):\n    return a\n", "positional"),
        ("def g(v):\n    return v\n", "not defined"),
        ("def f(v:\n", "valid Python"),
    ],
)
def test_static_rejections(src, message):
    with pytest.raises(SourceError, match=message):
        analyze_source(src, "f", [], ["math.gcd"] if "math" in src else [])


def test_too_many_helpers_and_size():
    helpers = [{"name": f"h{i}", "signature": f"h{i}(x)", "contract_text": ""} for i in range(4)]
    body = "".join(f"def h{i}(x):\n    return x\n" for i in range(4))
    with pytest.raises(SourceError, match="At most 3"):
        analyze_source(body + GOOD, "f", helpers, [])
    with pytest.raises(SourceError, match="48,000"):
        analyze_source(GOOD + "#" * 49000, "f", [], [])


def test_unapproved_allowlist_member_and_non_allowlisted_dependency():
    with pytest.raises(SourceError, match="allowlist"):
        analyze_source(GOOD, "f", [], ["os.path"])


def test_changed_signature_rejected_by_bundle(fixture):
    problem = fixture("problem")
    assert check_bundle(problem["source"], problem).signature == problem["signature"]
    renamed = problem["source"].replace("(values)", "(items)").replace("len(values)", "len(items)")
    renamed = renamed.replace("values[i]", "items[i]")
    with pytest.raises(SourceError, match="signature changed"):
        check_bundle(renamed, problem)


def test_normalized_hash_ignores_formatting():
    assert normalized_hash("def f(v):\n    return v+1\n") == normalized_hash(
        "def f(v):\n        return  v + 1\n"
    )
    assert normalized_hash("def f(v):\n    return v+1\n") != normalized_hash(
        "def f(v):\n    return v+2\n"
    )


MODULES = {"math": ["gcd", "isqrt"], "bisect": ["bisect_left", "bisect_right"],
           "collections": ["Counter", "deque"]}  # fmt: skip


def test_allowlist_symbols_exist_and_are_deterministic():
    assert {f"{m}.{a}" for m, attrs in MODULES.items() for a in attrs} == ALLOWLIST
    for module, attrs in MODULES.items():
        mod = importlib.import_module(module)
        assert all(callable(getattr(mod, a)) for a in attrs)
    from bisect import bisect_left, bisect_right
    from collections import Counter, deque
    from math import gcd, isqrt

    assert gcd(12, 18) == gcd(12, 18) == 6 and isqrt(17) == isqrt(17) == 4
    assert bisect_left([1, 2, 2, 3], 2) == 1 and bisect_right([1, 2, 2, 3], 2) == 3
    assert Counter([1, 1, 2])[1] == 2 and list(deque([1, 2])) == [1, 2]


def test_wire_validation_uses_frozen_schema(fixture):
    validate(fixture("problem"), "Problem")
    validate(fixture("run-create"), "RunCreate")
    bad = copy.deepcopy(fixture("problem"))
    bad["unexpected"] = 1
    with pytest.raises(Exception):
        validate(bad, "Problem")
