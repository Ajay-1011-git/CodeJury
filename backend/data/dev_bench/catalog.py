"""Independently authored development problems, 14 October 2026.

This is offline authoring/scoring material. Runtime methods read runtime.jsonl only.
Expectations are hand-written; references and corruptions execute only in Docker.
One corruption per base, no teacher, downloaded dataset, or inherited corpus targets.
"""

import ast
import json
from pathlib import Path

INT = {"kind": "integer", "min": -100, "max": 100}
N = {"kind": "integer", "min": 0, "max": 30}
P = {"kind": "integer", "min": 1, "max": 30}
S = {
    "kind": "string",
    "alphabet": (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ()[]{}.,:;!?+-*/_=|"
    ),
    "min_length": 0,
    "max_length": 64,
}


def seq(item=INT, lo=0, hi=12):
    return {"kind": "list", "item_domain": item, "min_length": lo, "max_length": hi}


L = seq()
W = seq(S)
M = seq(seq(INT, 0, 6), 0, 6)
D = {
    "kind": "dict",
    "key_domain": S,
    "value_domain": INT,
    "required_keys": [],
    "min_size": 0,
    "max_size": 10,
}
ROWS = []


def add(name, tier, family, contract, args, body, old, new, cases):
    source = "def solve(" + ", ".join(n for n, _ in args) + "):\n"
    source += "\n".join("    " + line for line in body.splitlines()) + "\n"
    if body.count(old) != 1:
        raise ValueError((name, "mutation must name exactly one site", old))
    buggy = (
        source.split("\n", 1)[0]
        + "\n"
        + "\n".join("    " + line for line in body.replace(old, new, 1).splitlines())
        + "\n"
    )
    if len(cases) < 5:
        raise ValueError((name, "requires two visible and at least three scoring tests"))
    ast.parse(source)
    ast.parse(buggy)
    requirement = {
        "schema_version": "stage2.v1",
        "requirement_id": "behavior",
        "description": contract,
        "source": "reviewed_contract",
        "approval_status": "approved",
        "property_template_id": None,
        "parameters": {},
    }
    tests = [
        {
            "schema_version": "stage2.v1",
            "test_id": f"example-{i}",
            "inputs": x,
            "expected": y,
            "requirement_ids": ["behavior"],
        }
        for i, (x, y) in enumerate(cases)
    ]
    runtime = {
        "schema_version": "stage2.v1",
        "source": buggy,
        "function_name": "solve",
        "contract_text": contract + " Do not mutate any input.",
        "domain_schema": [{"name": n, "domain": d} for n, d in args],
        "helper_interfaces": [],
        "requirements": [requirement],
        "supplied_tests": tests[:2],
        "allowed_dependencies": [],
        "resource_profile": "mac-standard-v1",
        "policy_mode": "learned",
        "seed": 17,
    }
    ROWS.append(
        {
            "base_problem_id": name,
            "family_id": family,
            "tier": tier,
            "split": "development_benchmark",
            "provenance": {
                "kind": "independently_authored",
                "author": "CodeJury development",
                "date": "2026-10-14",
                "external_dataset": False,
                "mutation": {"before": old, "after": new},
            },
            "run_create": runtime,
            "correct_source": source,
            "hidden_tests": tests[2:],
        }
    )


# T1: one token changed; distinct specified behaviours, not repeated corruptions.
add(
    "unordered_pairs",
    "T1",
    "combinatorial_counts",
    "Return the number of unordered pairs of distinct items among n items.",
    [("n", N)],
    "return n * (n - 1) // 2",
    "// 2",
    "// 3",
    [([0], 0), ([4], 6), ([1], 0), ([2], 1), ([8], 28)],
)
add(
    "polygon_diagonals",
    "T1",
    "combinatorial_counts",
    ("Return the number of diagonals of an n-sided polygon; return zero below three sides."),
    [("n", N)],
    "return max(0, n * (n - 3) // 2)",
    "n - 3",
    "n - 2",
    [([3], 0), ([5], 5), ([0], 0), ([4], 2), ([8], 20)],
)
add(
    "handshake_rounds",
    "T1",
    "combinatorial_counts",
    (
        "For n players, return the minimum number of round-robin roun"
        "ds, one game per player per round; zero for fewer than two."
    ),
    [("n", N)],
    "return 0 if n < 2 else n - 1 if n % 2 == 0 else n",
    "n < 2",
    "n < 3",
    [([2], 1), ([5], 5), ([0], 0), ([1], 0), ([4], 3)],
)
add(
    "square_pyramid",
    "T1",
    "combinatorial_counts",
    "Return the total blocks in layers of sizes 1 squared through n squared.",
    [("n", N)],
    "return n * (n + 1) * (2 * n + 1) // 6",
    "// 6",
    "// 3",
    [([0], 0), ([3], 14), ([1], 1), ([2], 5), ([5], 55)],
)
add(
    "binary_tree_nodes",
    "T1",
    "combinatorial_counts",
    (
        "Return the number of nodes in a perfect binary tree with lev"
        "els levels, including zero levels."
    ),
    [("levels", N)],
    "return 2 ** levels - 1",
    "- 1",
    "+ 1",
    [([0], 0), ([3], 7), ([1], 1), ([2], 3), ([5], 31)],
)
add(
    "checkerboard_black",
    "T1",
    "matrix_geometry",
    ("Return the number of black squares on an n by n checkerboard whose top-left cell is black."),
    [("n", N)],
    "return (n * n + 1) // 2",
    "+ 1",
    "- 1",
    [([1], 1), ([3], 5), ([0], 0), ([2], 2), ([5], 13)],
)
add(
    "clock_angle",
    "T1",
    "time_geometry",
    (
        "Return the smaller angle in half-degree units between hour a"
        "nd minute hands; hour ranges 0 through 11."
    ),
    [
        ("hour", {"kind": "integer", "min": 0, "max": 11}),
        ("minute", {"kind": "integer", "min": 0, "max": 58}),
    ],
    ("angle = abs((hour % 12) * 60 + minute - minute * 12)\nreturn min(angle, 720 - angle)"),
    "* 12",
    "* 10",
    [([3, 0], 180), ([0, 30], 330), ([6, 0], 360), ([0, 0], 0), ([9, 20], 320)],
)
add(
    "leap_year",
    "T1",
    "calendar_rules",
    "Return whether year is a Gregorian leap year.",
    [("year", {"kind": "integer", "min": 1, "max": 3000})],
    "return year % 400 == 0 or (year % 4 == 0 and year % 100 != 0)",
    "% 100",
    "% 10",
    [
        ([2024], True),
        ([1900], False),
        ([2000], True),
        ([2100], False),
        ([2023], False),
        ([2020], True),
    ],
)
add(
    "century",
    "T1",
    "calendar_rules",
    ("Return the century containing positive year, so years 1 through 100 belong to century 1."),
    [("year", {"kind": "integer", "min": 1, "max": 3000})],
    "return (year - 1) // 100 + 1",
    "year - 1",
    "year + 1",
    [([100], 1), ([101], 2), ([1], 1), ([2000], 20), ([2001], 21)],
)
add(
    "full_weeks",
    "T1",
    "calendar_rules",
    "Return the number of complete seven-day weeks contained in days.",
    [("days", N)],
    "return days // 7",
    "//",
    "%",
    [([0], 0), ([15], 2), ([6], 0), ([7], 1), ([28], 4)],
)
add(
    "colon_seconds",
    "T1",
    "time_geometry",
    (
        "Return total seconds represented by nonnegative minutes and "
        "seconds, even when seconds exceeds 59."
    ),
    [("minutes", N), ("seconds", INT)],
    "return minutes * 60 + seconds",
    "* 60",
    "* 6",
    [([0, 0], 0), ([2, 5], 125), ([1, 0], 60), ([0, 75], 75), ([3, 30], 210)],
)
add(
    "fahrenheit_tenths",
    "T1",
    "unit_conversion",
    "Convert integer Celsius temperature to Fahrenheit in tenths of a degree.",
    [("celsius", INT)],
    "return celsius * 18 + 320",
    "+ 320",
    "+ 32",
    [([0], 320), ([100], 2120), ([-40], -400), ([10], 500), ([-10], 140)],
)
add(
    "tax_inclusive_cents",
    "T1",
    "unit_conversion",
    ("Return price in cents including tax at rate percent, rounding down fractional cents."),
    [("price", {"kind": "integer", "min": 0, "max": 10000}), ("rate", N)],
    "return price * (100 + rate) // 100",
    "100 + rate",
    "100 - rate",
    [([100, 10], 110), ([99, 5], 103), ([0, 20], 0), ([7, 0], 7), ([200, 25], 250)],
)
add(
    "word_join",
    "T1",
    "text_formatting",
    "Join words with a single space between each adjacent pair.",
    [("words", W)],
    "return ' '.join(words)",
    "' '",
    "'-'",
    [
        ([[]], ""),
        ([["a", "b"]], "a b"),
        ([["one"]], "one"),
        ([["", "x"]], " x"),
        ([["a", "", "b"]], "a  b"),
    ],
)
add(
    "pipe_fields",
    "T1",
    "text_formatting",
    "Split text on literal pipe characters, preserving empty fields.",
    [("text", S)],
    "return text.split('|')",
    "'|'",
    "','",
    [
        (["a|b"], ["a", "b"]),
        ([""], [""]),
        (["|"], ["", ""]),
        (["x||y"], ["x", "", "y"]),
        (["a,b"], ["a,b"]),
    ],
)
add(
    "strip_outer_spaces",
    "T1",
    "text_formatting",
    "Remove spaces at both ends while retaining interior spaces.",
    [("text", S)],
    "return text.strip(' ')",
    ".strip(",
    ".lstrip(",
    [([" a "], "a"), (["a b"], "a b"), ([""], ""), (["   "], ""), (["a  "], "a")],
)
add(
    "uppercase_words",
    "T1",
    "text_formatting",
    "Return text with all letters uppercase and other characters unchanged.",
    [("text", S)],
    "return text.upper()",
    ".upper()",
    ".lower()",
    [
        (["aB"], "AB"),
        (["123"], "123"),
        ([""], ""),
        (["Hello world"], "HELLO WORLD"),
        (["!?"], "!?"),
    ],
)
add(
    "swap_letter_case",
    "T1",
    "text_formatting",
    "Swap the case of every letter; keep other characters.",
    [("text", S)],
    "return text.swapcase()",
    ".swapcase()",
    ".lower()",
    [(["Ab"], "aB"), (["123"], "123"), ([""], ""), (["a Z"], "A z"), (["HELLO"], "hello")],
)
add(
    "pad_left",
    "T1",
    "text_formatting",
    "Pad text on the left with zero characters to reach width; never truncate.",
    [("text", S), ("width", N)],
    "return text.rjust(width, '0')",
    ".rjust(",
    ".ljust(",
    [
        (["12", 4], "0012"),
        (["a", 1], "a"),
        (["", 3], "000"),
        (["abc", 2], "abc"),
        (["-1", 4], "00-1"),
    ],
)
add(
    "prefix_match",
    "T1",
    "text_matching",
    "Return whether text begins with prefix, including an empty prefix.",
    [("text", S), ("prefix", S)],
    "return text.startswith(prefix)",
    ".startswith(",
    ".endswith(",
    [
        (["abc", "a"], True),
        (["abc", "z"], False),
        (["", ""], True),
        (["abc", "bc"], False),
        (["aba", "ab"], True),
    ],
)
add(
    "substring_membership",
    "T1",
    "text_matching",
    ("Return whether needle occurs contiguously anywhere in text; empty needle always occurs."),
    [("text", S), ("needle", S)],
    "return needle in text",
    " in ",
    " not in ",
    [
        (["abc", "b"], True),
        (["abc", "z"], False),
        (["", ""], True),
        (["aba", "ab"], True),
        (["a", "aa"], False),
    ],
)
add(
    "nonoverlap_replace",
    "T1",
    "text_matching",
    (
        "Replace all nonoverlapping occurrences of a with b in text u"
        "sing Python string replacement semantics."
    ),
    [("text", S), ("a", S), ("b", S)],
    "return text.replace(a, b)",
    "a, b",
    "b, a",
    [
        (["aba", "a", "x"], "xbx"),
        (["abc", "z", "q"], "abc"),
        (["aaaa", "aa", "b"], "bb"),
        (["", "", "x"], "x"),
        (["abc", "b", ""], "ac"),
    ],
)
add(
    "head_before_colon",
    "T1",
    "text_matching",
    "Return the text before the first colon, or all text if absent.",
    [("text", S)],
    "return text.split(':', 1)[0]",
    "[0]",
    "[-1]",
    [(["a:b:c"], "a"), (["x"], "x"), ([""], ""), ([":x"], ""), (["a:"], "a")],
)
add(
    "suffix_after_dot",
    "T1",
    "text_matching",
    "Return the suffix after the last dot, or the whole text if no dot.",
    [("text", S)],
    "return text.rsplit('.', 1)[-1]",
    ".rsplit(",
    ".split(",
    [(["a.b.c"], "c"), (["file"], "file"), ([""], ""), ([".env"], "env"), (["a."], "")],
)
add(
    "repeat_text",
    "T1",
    "text_formatting",
    "Return text repeated n times, including empty text or zero repetitions.",
    [("text", S), ("n", N)],
    "return text * n",
    " * ",
    " + ",
    [(["ab", 2], "abab"), (["", 0], ""), (["x", 0], ""), (["x", 1], "x"), (["a", 3], "aaa")],
)

# T2: loops, state, parsing and boundary repairs.
add(
    "factorial",
    "T2",
    "number_theory",
    "Return n factorial; zero factorial is one.",
    [("n", {"kind": "integer", "min": 0, "max": 18})],
    "product = 1\nfor k in range(2, n + 1):\n    product *= k\nreturn product",
    "range(2, n + 1)",
    "range(2, n)",
    [([0], 1), ([4], 24), ([1], 1), ([2], 2), ([6], 720)],
)
add(
    "euclidean_gcd",
    "T2",
    "number_theory",
    ("Return the nonnegative greatest common divisor of a and b; gcd of zero and zero is zero."),
    [("a", INT), ("b", INT)],
    "a, b = abs(a), abs(b)\nwhile b:\n    a, b = b, a % b\nreturn a",
    "a, b = b, a % b",
    "a = b\n    b = a % b",
    [([12, 8], 4), ([9, 6], 3), ([0, 0], 0), ([-15, 10], 5), ([7, 0], 7)],
)
add(
    "least_common_multiple",
    "T2",
    "number_theory",
    ("Return nonnegative least common multiple of a and b; return zero if either is zero."),
    [("a", INT), ("b", INT)],
    (
        "if a == 0 or b == 0:\n    return 0\nx, y = abs(a), abs(b)\nwhil"
        "e y:\n    x, y = y, x % y\nreturn abs(a * b) // x"
    ),
    "return abs(a * b) // x",
    "return abs(a * b) * x",
    [([4, 6], 12), ([0, 3], 0), ([-3, 5], 15), ([7, 7], 7), ([8, 12], 24)],
)
add(
    "prime_check",
    "T2",
    "number_theory",
    "Return whether n is prime; negative numbers, zero and one are not prime.",
    [("n", INT)],
    (
        "if n < 2:\n    return False\nd = 2\nwhile d * d <= n:\n    if n "
        "% d == 0:\n        return False\n    d += 1\nreturn True"
    ),
    "d * d <= n",
    "d * d < n",
    [([9], False), ([7], True), ([1], False), ([4], False), ([25], False)],
)
add(
    "divisor_list",
    "T2",
    "number_theory",
    "Return all positive divisors of positive n in ascending order.",
    [("n", P)],
    (
        "result = []\nfor d in range(1, n + 1):\n    if n % d == 0:\n   "
        "     result.append(d)\nreturn result"
    ),
    "range(1, n + 1)",
    "range(1, n)",
    [([1], [1]), ([6], [1, 2, 3, 6]), ([7], [1, 7]), ([12], [1, 2, 3, 4, 6, 12]), ([9], [1, 3, 9])],
)
add(
    "fibonacci_index",
    "T2",
    "linear_recurrences",
    "Return Fibonacci number F(n), with F(0)=0 and F(1)=1.",
    [("n", N)],
    "a, b = 0, 1\nfor _ in range(n):\n    a, b = b, a + b\nreturn a",
    "a, b = b, a + b",
    "a = b\n    b = a + b",
    [([0], 0), ([4], 3), ([1], 1), ([2], 1), ([8], 21)],
)
add(
    "decimal_digit_sum",
    "T2",
    "numeral_systems",
    "Return the sum of decimal digits of the absolute value of n.",
    [("n", {"kind": "integer", "min": -10000, "max": 10000})],
    ("n = abs(n)\ntotal = 0\nwhile n:\n    total += n % 10\n    n //= 10\nreturn total"),
    "n = abs(n)",
    "n = n",
    [([123], 6), ([-45], 9), ([0], 0), ([1000], 1), ([909], 18)],
)
add(
    "decimal_digit_count",
    "T2",
    "numeral_systems",
    "Return the number of decimal digits of absolute n; zero has one digit.",
    [("n", {"kind": "integer", "min": -10000, "max": 10000})],
    ("n = abs(n)\ncount = 1\nwhile n >= 10:\n    n //= 10\n    count += 1\nreturn count"),
    "n >= 10",
    "n > 10",
    [([10], 2), ([123], 3), ([0], 1), ([-1000], 4), ([9], 1)],
)
add(
    "binary_ones",
    "T2",
    "numeral_systems",
    "Return the count of one bits in the binary representation of nonnegative n.",
    [("n", N)],
    "count = 0\nwhile n:\n    count += n % 2\n    n //= 2\nreturn count",
    "n //= 2",
    "n //= 3",
    [([0], 0), ([7], 3), ([1], 1), ([8], 1), ([21], 3)],
)
add(
    "radix_representation",
    "T2",
    "numeral_systems",
    (
        "Represent nonnegative n in base 2 through 10 as a string of "
        "decimal digit symbols; zero is 0."
    ),
    [("n", N), ("base", {"kind": "integer", "min": 2, "max": 10})],
    (
        "if n == 0:\n    return '0'\nresult = ''\nwhile n:\n    result = "
        "str(n % base) + result\n    n //= base\nreturn result"
    ),
    "str(n % base) + result",
    "result + str(n % base)",
    [([6, 2], "110"), ([0, 2], "0"), ([10, 3], "101"), ([23, 10], "23"), ([15, 4], "33")],
)
add(
    "run_lengths",
    "T2",
    "run_encoding",
    (
        "Return lengths of consecutive equal-value runs in values, in"
        " order; empty gives an empty list."
    ),
    [("values", L)],
    (
        "if not values:\n    return []\nresult = []\ncount = 1\nfor i in "
        "range(1, len(values)):\n    if values[i] == values[i - 1]:\n  "
        "      count += 1\n    else:\n        result.append(count)\n    "
        "    count = 1\nresult.append(count)\nreturn result"
    ),
    "result.append(count)\nreturn result",
    "return result",
    [
        ([[1, 1, 2]], [2, 1]),
        ([[]], []),
        ([[7]], [1]),
        ([[1, 2, 2, 3, 3, 3]], [1, 2, 3]),
        ([[0, 0, 0]], [3]),
    ],
)
add(
    "run_value_pairs",
    "T2",
    "run_encoding",
    "Encode consecutive runs as [value,count] pairs, preserving order.",
    [("values", L)],
    (
        "result = []\nfor x in values:\n    if result and result[-1][0]"
        " == x:\n        result[-1][1] += 1\n    else:\n        result.a"
        "ppend([x, 1])\nreturn result"
    ),
    "result[-1][0] == x",
    "result[-1][1] == x",
    [
        ([[2, 2, 3]], [[2, 2], [3, 1]]),
        ([[]], []),
        ([[1]], [[1, 1]]),
        ([[0, 0, 1, 0]], [[0, 2], [1, 1], [0, 1]]),
        ([[-2, -2]], [[-2, 2]]),
    ],
)
add(
    "text_run_collapse",
    "T2",
    "run_encoding",
    (
        "Collapse each consecutive run of equal characters to one cha"
        "racter, preserving nonconsecutive repetitions."
    ),
    [("text", S)],
    (
        "result = ''\nfor ch in text:\n    if not result or ch != resul"
        "t[-1]:\n        result += ch\nreturn result"
    ),
    "ch != result[-1]",
    "ch not in result",
    [(["aaabbba"], "aba"), ([""], ""), (["x"], "x"), (["abab"], "abab"), (["  a  "], " a ")],
)
add(
    "longest_same_run",
    "T2",
    "run_encoding",
    "Return the length of the longest consecutive equal-value run; zero for empty.",
    [("values", L)],
    (
        "best = count = 0\nprevious = None\nfor x in values:\n    count "
        "= count + 1 if x == previous else 1\n    previous = x\n    bes"
        "t = max(best, count)\nreturn best"
    ),
    "previous = x",
    "previous = None",
    [([[1, 1, 2]], 2), ([[]], 0), ([[4]], 1), ([[0, 0, 0]], 3), ([[1, 2, 2, 2, 3]], 3)],
)
add(
    "word_frequencies",
    "T2",
    "mapping_relations",
    "Return a dictionary of each word to its occurrence count.",
    [("words", W)],
    ("result = {}\nfor word in words:\n    result[word] = result.get(word, 0) + 1\nreturn result"),
    "result.get(word, 0) + 1",
    "1",
    [
        ([["a", "b", "a"]], {"a": 2, "b": 1}),
        ([[]], {}),
        ([[""]], {"": 1}),
        ([["x", "x", "x"]], {"x": 3}),
        ([["A", "a"]], {"A": 1, "a": 1}),
    ],
)
add(
    "group_words_by_initial",
    "T2",
    "mapping_relations",
    (
        "Group nonempty words by their first character into lists pre"
        "serving input order; skip empty words."
    ),
    [("words", W)],
    (
        "result = {}\nfor word in words:\n    if word:\n        result.s"
        "etdefault(word[0], []).append(word)\nreturn result"
    ),
    "word[0]",
    "word[-1]",
    [
        ([["ab", "ac", "ba"]], {"a": ["ab", "ac"], "b": ["ba"]}),
        ([[]], {}),
        ([[""]], {}),
        ([["apple", "ant"]], {"a": ["apple", "ant"]}),
        ([["b", "a", "b"]], {"b": ["b", "b"], "a": ["a"]}),
    ],
)
add(
    "invert_multimap",
    "T2",
    "mapping_relations",
    (
        "Invert string-to-integer mapping into a dictionary keyed by "
        "decimal value strings; values are sorted lists of original k"
        "eys."
    ),
    [("mapping", D)],
    (
        "result = {}\nfor key, value in mapping.items():\n    result.se"
        "tdefault(str(value), []).append(key)\nreturn {key: sorted(val"
        "ue) for key, value in result.items()}"
    ),
    "result.setdefault(str(value), []).append(key)",
    "result[str(value)] = [key]",
    [
        ([{"a": 1, "b": 1}], {"1": ["a", "b"]}),
        ([{}], {}),
        ([{"z": -1}], {"-1": ["z"]}),
        ([{"b": 2, "a": 2, "c": 1}], {"2": ["a", "b"], "1": ["c"]}),
        ([{"a": 0, "b": 3}], {"0": ["a"], "3": ["b"]}),
    ],
)
add(
    "dictionary_overlay",
    "T2",
    "mapping_relations",
    ("Return a new mapping containing both dictionaries; right-hand values win on shared keys."),
    [("left", D), ("right", D)],
    (
        "result = dict(left)\nfor key, value in right.items():\n    res"
        "ult[key] = value\nreturn result"
    ),
    "result[key] = value",
    "result.setdefault(key, value)",
    [
        ([{"a": 1}, {"a": 2}], {"a": 2}),
        ([{}, {}], {}),
        ([{"a": 1}, {"b": 2}], {"a": 1, "b": 2}),
        ([{}, {"x": 0}], {"x": 0}),
        ([{"x": 3}, {}], {"x": 3}),
    ],
)
add(
    "word_positions",
    "T2",
    "mapping_relations",
    ("Return a mapping from each word to its list of zero-based positions in the input."),
    [("words", W)],
    (
        "result = {}\nfor i, word in enumerate(words):\n    result.setd"
        "efault(word, []).append(i)\nreturn result"
    ),
    ".append(i)",
    ".append(i + 1)",
    [
        ([["a", "b", "a"]], {"a": [0, 2], "b": [1]}),
        ([[]], {}),
        ([[""]], {"": [0]}),
        ([["x", "x"]], {"x": [0, 1]}),
        ([["a", "b"]], {"a": [0], "b": [1]}),
    ],
)
add(
    "balanced_parentheses",
    "T2",
    "delimiter_parsing",
    "Return whether parentheses in text are balanced; ignore all other characters.",
    [("text", S)],
    (
        "depth = 0\nfor ch in text:\n    if ch == '(':\n        depth +="
        " 1\n    elif ch == ')':\n        depth -= 1\n    if depth < 0:\n"
        "        return False\nreturn depth == 0"
    ),
    "depth < 0",
    "depth > 0",
    [(["()"], True), ([")("], False), ([""], True), (["(a(b))"], True), (["(()"], False)],
)
add(
    "parenthesis_depth",
    "T2",
    "delimiter_parsing",
    (
        "Return maximum nesting depth for balanced parentheses; retur"
        "n -1 for unbalanced text; ignore other characters."
    ),
    [("text", S)],
    (
        "depth = best = 0\nfor ch in text:\n    if ch == '(':\n        d"
        "epth += 1\n        best = max(best, depth)\n    elif ch == ')'"
        ":\n        depth -= 1\n        if depth < 0:\n            retur"
        "n -1\nreturn best if depth == 0 else -1"
    ),
    "if depth == 0 else -1",
    "if depth >= 0 else -1",
    [(["(())"], 2), (["(()"], -1), ([""], 0), ([")(("], -1), (["a(b)c"], 1)],
)
add(
    "split_words",
    "T2",
    "text_tokenization",
    ("Split text into nonempty words separated by one or more spaces, discarding outer spaces."),
    [("text", S)],
    "return [word for word in text.split(' ') if word]",
    " if word",
    " if len(word) > 1",
    [
        (["a bb"], ["a", "bb"]),
        ([""], []),
        (["  x  y "], ["x", "y"]),
        (["   "], []),
        (["abc"], ["abc"]),
    ],
)
add(
    "initials",
    "T2",
    "text_tokenization",
    "Return uppercase initials of nonempty words separated by spaces.",
    [("text", S)],
    (
        "result = ''\nfor word in text.split(' '):\n    if word:\n      "
        "  result += word[0].upper()\nreturn result"
    ),
    "word[0]",
    "word[-1]",
    [
        (["alice bob"], "AB"),
        ([""], ""),
        (["  ada  lovelace "], "AL"),
        (["x"], "X"),
        (["hello world"], "HW"),
    ],
)
add(
    "longest_word",
    "T2",
    "text_tokenization",
    (
        "Return the longest space-separated word, choosing the first "
        "on ties; empty if there are no words."
    ),
    [("text", S)],
    (
        "best = ''\nfor word in text.split():\n    if len(word) > len(b"
        "est):\n        best = word\nreturn best"
    ),
    "len(word) > len(best)",
    "len(word) >= len(best)",
    [
        (["cat dog"], "cat"),
        (["a elephant"], "elephant"),
        ([""], ""),
        (["  "], ""),
        (["ab cd e"], "ab"),
    ],
)
add(
    "vowel_groups",
    "T2",
    "text_tokenization",
    "Count consecutive runs of ASCII vowels aeiou, case insensitive.",
    [("text", S)],
    (
        "count = 0\nin_vowel = False\nfor ch in text.lower():\n    vowel"
        " = ch in 'aeiou'\n    if vowel and not in_vowel:\n        coun"
        "t += 1\n    in_vowel = vowel\nreturn count"
    ),
    "in_vowel = vowel",
    "in_vowel = False",
    [(["beautiful"], 3), (["aeiou"], 1), ([""], 0), (["bc"], 0), (["AbaE"], 2)],
)
add(
    "overlap_occurrences",
    "T2",
    "text_matching",
    (
        "Count all possibly overlapping occurrences of nonempty patte"
        "rn in text; empty pattern occurs len(text)+1 times."
    ),
    [("text", S), ("pattern", S)],
    (
        "count = 0\nfor i in range(len(text) - len(pattern) + 1):\n    "
        "if text[i:i + len(pattern)] == pattern:\n        count += 1\nr"
        "eturn count"
    ),
    "len(text) - len(pattern) + 1",
    "len(text) - len(pattern)",
    [(["aaaa", "aa"], 3), (["abc", "z"], 0), (["", ""], 1), (["abc", ""], 4), (["abc", "abc"], 1)],
)
add(
    "subsequence_text",
    "T2",
    "text_matching",
    (
        "Return whether needle is a subsequence of text in order, wit"
        "hout requiring adjacent characters."
    ),
    [("text", S), ("needle", S)],
    (
        "i = 0\nfor ch in text:\n    if i < len(needle) and ch == needl"
        "e[i]:\n        i += 1\nreturn i == len(needle)"
    ),
    "i += 1",
    "i = 1",
    [
        (["abc", "ac"], True),
        (["abc", "ca"], False),
        (["", ""], True),
        (["a", "aa"], False),
        (["aabbcc", "abc"], True),
    ],
)
add(
    "caesar_lowercase",
    "T2",
    "text_ciphers",
    ("Rotate lowercase ASCII letters by shift modulo 26; leave every other character unchanged."),
    [("text", S), ("shift", INT)],
    (
        "alphabet = 'abcdefghijklmnopqrstuvwxyz'\nresult = ''\nfor ch i"
        "n text:\n    if ch in alphabet:\n        result += alphabet[(a"
        "lphabet.index(ch) + shift) % 26]\n    else:\n        result +="
        " ch\nreturn result"
    ),
    "(alphabet.index(ch) + shift) % 26",
    "min(25, max(0, alphabet.index(ch) + shift))",
    [
        (["xyz", 3], "abc"),
        (["Ab!", 1], "Ac!"),
        (["", 10], ""),
        (["abc", -1], "zab"),
        (["z", 26], "z"),
    ],
)
add(
    "transpose_ragged",
    "T2",
    "matrix_geometry",
    (
        "Transpose ragged rows, omitting missing cells from each colu"
        "mn; empty input gives empty output."
    ),
    [("rows", M)],
    (
        "width = max([len(row) for row in rows] + [0])\nreturn [[row[i"
        "] for row in rows if i < len(row)] for i in range(width)]"
    ),
    "range(width)",
    "range(max(0, width - 1))",
    [
        ([[[1, 2], [3]]], [[1, 3], [2]]),
        ([[]], []),
        ([[[], []]], []),
        ([[[4]]], [[4]]),
        ([[[1], [2, 3], [4, 5, 6]]], [[1, 2, 4], [3, 5], [6]]),
    ],
)
add(
    "diagonal_ragged",
    "T2",
    "matrix_geometry",
    ("Return the main diagonal of ragged rows, skipping rows missing their diagonal cell."),
    [("rows", M)],
    (
        "result = []\nfor i, row in enumerate(rows):\n    if i < len(ro"
        "w):\n        result.append(row[i])\nreturn result"
    ),
    "row[i]",
    "row[0]",
    [
        ([[[1, 2], [3, 4]]], [1, 4]),
        ([[]], []),
        ([[[], [2]]], []),
        ([[[7]]], [7]),
        ([[[1], [2, 3], [4, 5, 6]]], [1, 3, 6]),
    ],
)
add(
    "chunk_list",
    "T2",
    "sequence_partitioning",
    ("Split values into consecutive chunks of positive size; retain a partial final chunk."),
    [("values", L), ("size", P)],
    (
        "result = []\nfor i in range(0, len(values), size):\n    result"
        ".append(values[i:i + size])\nreturn result"
    ),
    "len(values), size",
    "len(values) - size + 1, size",
    [
        ([[1, 2, 3], 2], [[1, 2], [3]]),
        ([[], 2], []),
        ([[1], 3], [[1]]),
        ([[1, 2, 3, 4], 2], [[1, 2], [3, 4]]),
        ([[1, 2], 1], [[1], [2]]),
    ],
)
add(
    "interleave_unequal",
    "T2",
    "sequence_partitioning",
    (
        "Alternately take one item from left and right, beginning wit"
        "h left; append remaining items when one ends."
    ),
    [("left", L), ("right", L)],
    (
        "result = []\nfor i in range(max(len(left), len(right))):\n    "
        "if i < len(left):\n        result.append(left[i])\n    if i < "
        "len(right):\n        result.append(right[i])\nreturn result"
    ),
    "max(len(left), len(right))",
    "min(len(left), len(right))",
    [
        ([[1, 2], [3]], [1, 3, 2]),
        ([[], []], []),
        ([[], [1, 2]], [1, 2]),
        ([[1], [2, 3]], [1, 2, 3]),
        ([[1, 2], [3, 4]], [1, 3, 2, 4]),
    ],
)
add(
    "sliding_window_sums",
    "T2",
    "window_algorithms",
    ("Return sums of every contiguous window of positive width k; no windows if k exceeds length."),
    [("values", L), ("k", P)],
    "return [sum(values[i:i + k]) for i in range(len(values) - k + 1)]",
    "len(values) - k + 1",
    "len(values) - k",
    [
        ([[1, 2, 3], 2], [3, 5]),
        ([[], 1], []),
        ([[5], 1], [5]),
        ([[1, -2, 3], 1], [1, -2, 3]),
        ([[1, 2], 3], []),
    ],
)
add(
    "second_distinct_largest",
    "T2",
    "order_statistics",
    (
        "Return the second largest distinct integer, or null when few"
        "er than two distinct values exist."
    ),
    [("values", L)],
    ("unique = sorted(set(values))\nif len(unique) < 2:\n    return None\nreturn unique[-2]"),
    "sorted(set(values))",
    "sorted(values)",
    [([[3, 3, 2]], 2), ([[]], None), ([[4, 4]], None), ([[1, 2, 3]], 2), ([[-1, -3, -2]], -2)],
)
add(
    "median_lower",
    "T2",
    "order_statistics",
    "Return the lower median after sorting values; return null for empty input.",
    [("values", L)],
    (
        "if not values:\n    return None\nordered = sorted(values)\nretu"
        "rn ordered[(len(ordered) - 1) // 2]"
    ),
    "(len(ordered) - 1) // 2",
    "len(ordered) // 2",
    [([[4, 1, 3, 2]], 2), ([[]], None), ([[7]], 7), ([[3, 1, 2]], 2), ([[-2, 0]], -2)],
)

# T3: edge cases and several interacting steps.
add(
    "bracket_types",
    "T3",
    "delimiter_parsing",
    (
        "Return whether (), [] and {} brackets are correctly nested a"
        "nd matched; ignore other characters."
    ),
    [("text", S)],
    (
        "stack = []\npairs = {')':'(', ']':'[', '}':'{'}\nfor ch in tex"
        "t:\n    if ch in '([{':\n        stack.append(ch)\n    elif ch "
        "in pairs:\n        if not stack or stack.pop() != pairs[ch]:\n"
        "            return False\nreturn not stack"
    ),
    "stack.pop() != pairs[ch]",
    "stack[0] != pairs[ch]",
    [(["([])"], True), (["([)]"], False), ([""], True), (["a{b[c]}"], True), (["("], False)],
)
add(
    "nested_list_flatten",
    "T3",
    "nested_structures",
    "Flatten a list of lists by one level, retaining every integer in row order.",
    [("rows", M)],
    ("result = []\nfor row in rows:\n    for x in row:\n        result.append(x)\nreturn result"),
    "for x in row:",
    "for x in row[1:]:",
    [
        ([[[1, 2], [], [3]]], [1, 2, 3]),
        ([[]], []),
        ([[[]]], []),
        ([[[0]]], [0]),
        ([[[1], [2, 3], [4]]], [1, 2, 3, 4]),
    ],
)
add(
    "pascal_row",
    "T3",
    "combinatorial_counts",
    "Return row n of Pascal triangle, with row zero equal to [1].",
    [("n", N)],
    (
        "row = [1]\nfor _ in range(n):\n    row = [1] + [row[i] + row[i"
        " + 1] for i in range(len(row) - 1)] + [1]\nreturn row"
    ),
    "row = [1] + [row[i] + row[i + 1] for i in range(len(row) - 1)] + [1]",
    "row = [1] + [row[i] + row[i + 1] for i in range(len(row) - 1)]",
    [([0], [1]), ([3], [1, 3, 3, 1]), ([1], [1, 1]), ([2], [1, 2, 1]), ([5], [1, 5, 10, 10, 5, 1])],
)
add(
    "binomial_coefficient",
    "T3",
    "combinatorial_counts",
    "Return n choose k for nonnegative n,k; zero if k exceeds n.",
    [("n", N), ("k", N)],
    (
        "if k > n:\n    return 0\nvalue = 1\nfor i in range(1, k + 1):\n "
        "   value = value * (n - i + 1) // i\nreturn value"
    ),
    "value * (n - i + 1) // i",
    "value // i * (n - i + 1)",
    [([5, 2], 10), ([3, 5], 0), ([0, 0], 1), ([6, 3], 20), ([4, 4], 1)],
)
add(
    "coin_change_min",
    "T3",
    "dynamic_programming",
    (
        "Return minimum number of positive-denomination coins needed "
        "for amount, with unlimited reuse; -1 if impossible."
    ),
    [("coins", seq(P)), ("amount", N)],
    (
        "best = [amount + 1] * (amount + 1)\nbest[0] = 0\nfor total in "
        "range(1, amount + 1):\n    for coin in coins:\n        if coin"
        " <= total:\n            best[total] = min(best[total], best[t"
        "otal - coin] + 1)\nreturn best[amount] if best[amount] <= amo"
        "unt else -1"
    ),
    "best[0] = 0",
    "best[0] = 1",
    [([[1, 3, 4], 6], 2), ([[2], 3], -1), ([[], 0], 0), ([[], 4], -1), ([[2, 5], 10], 2)],
)
add(
    "nonadjacent_sum",
    "T3",
    "dynamic_programming",
    ("Return maximum sum of nonadjacent values; choosing no values is allowed and yields zero."),
    [("values", L)],
    (
        "skip = take = 0\nfor x in values:\n    skip, take = max(skip, "
        "take), skip + x\nreturn max(skip, take)"
    ),
    "skip, take = max(skip, take), skip + x",
    "skip = max(skip, take)\n    take = skip + x",
    [([[2, 7, 9, 3, 1]], 12), ([[]], 0), ([[-1, -2]], 0), ([[5, 1, 5]], 10), ([[1, 2, 3]], 4)],
)
add(
    "longest_increasing_subsequence",
    "T3",
    "dynamic_programming",
    ("Return length of the longest strictly increasing subsequence, not necessarily contiguous."),
    [("values", L)],
    (
        "lengths = [1] * len(values)\nfor i in range(len(values)):\n   "
        " for j in range(i):\n        if values[j] < values[i]:\n      "
        "      lengths[i] = max(lengths[i], lengths[j] + 1)\nreturn ma"
        "x(lengths + [0])"
    ),
    "values[j] < values[i]",
    "values[j] <= values[i]",
    [([[1, 1, 2]], 2), ([[]], 0), ([[3, 2, 1]], 1), ([[3, 1, 2, 5, 4]], 3), ([[0, 0, 0]], 1)],
)
add(
    "edit_distance",
    "T3",
    "dynamic_programming",
    (
        "Return Levenshtein distance between strings, with insertion,"
        " deletion and substitution each costing one."
    ),
    [("left", S), ("right", S)],
    (
        "previous = list(range(len(right) + 1))\nfor i, a in enumerate"
        "(left, 1):\n    current = [i]\n    for j, b in enumerate(right"
        ", 1):\n        current.append(min(current[-1] + 1, previous[j"
        "] + 1, previous[j - 1] + (a != b)))\n    previous = current\nr"
        "eturn previous[-1]"
    ),
    "previous[j - 1] + (a != b)",
    "previous[j - 1] + (a == b)",
    [
        (["cat", "cut"], 1),
        (["", "abc"], 3),
        (["", ""], 0),
        (["kitten", "sitting"], 3),
        (["abc", "abc"], 0),
    ],
)
add(
    "lcs_length",
    "T3",
    "dynamic_programming",
    "Return length of longest common subsequence of two strings.",
    [("left", S), ("right", S)],
    (
        "previous = [0] * (len(right) + 1)\nfor a in left:\n    current"
        " = [0]\n    for j, b in enumerate(right, 1):\n        current."
        "append(previous[j - 1] + 1 if a == b else max(previous[j], c"
        "urrent[-1]))\n    previous = current\nreturn previous[-1]"
    ),
    "previous[j - 1] + 1",
    "previous[j] + 1",
    [
        (["ab", "ab"], 2),
        (["", "abc"], 0),
        (["aaa", "a"], 1),
        (["abc", "ac"], 2),
        (["xyz", "abc"], 0),
    ],
)
add(
    "longest_unique_substring",
    "T3",
    "window_algorithms",
    ("Return length of longest contiguous substring containing no repeated character."),
    [("text", S)],
    (
        "last = {}\nstart = best = 0\nfor i, ch in enumerate(text):\n   "
        " if ch in last:\n        start = max(start, last[ch] + 1)\n   "
        " last[ch] = i\n    best = max(best, i - start + 1)\nreturn bes"
        "t"
    ),
    "start = max(start, last[ch] + 1)",
    "start = last[ch] + 1",
    [(["abba"], 2), (["abcabcbb"], 3), ([""], 0), (["aaaa"], 1), (["dvdf"], 3)],
)
add(
    "max_subarray",
    "T3",
    "window_algorithms",
    "Return largest sum of a nonempty contiguous subarray, or null for empty input.",
    [("values", L)],
    (
        "if not values:\n    return None\nending = best = values[0]\nfor"
        " x in values[1:]:\n    ending = max(x, ending + x)\n    best ="
        " max(best, ending)\nreturn best"
    ),
    "ending = best = values[0]",
    "ending = best = 0",
    [([[-5, -2, -8]], -2), ([[1, -2, 3, 4]], 7), ([[]], None), ([[0]], 0), ([[-1]], -1)],
)
add(
    "minimum_cover_window",
    "T3",
    "window_algorithms",
    (
        "Return the shortest substring of text containing every disti"
        "nct character in needed; first on ties; empty when needed is"
        " empty or no cover exists."
    ),
    [("text", S), ("needed", S)],
    (
        "required = set(needed)\nif not required:\n    return ''\nbest ="
        " None\nfor start in range(len(text)):\n    seen = set()\n    fo"
        "r end in range(start, len(text)):\n        seen.add(text[end]"
        ")\n        if required <= seen:\n            part = text[start"
        ":end + 1]\n            if best is None or len(part) < len(bes"
        "t):\n                best = part\n            break\nreturn bes"
        "t if best is not None else ''"
    ),
    "len(part) < len(best)",
    "len(part) > len(best)",
    [
        (["abca", "ac"], "ca"),
        (["abc", "z"], ""),
        (["abc", ""], ""),
        (["", "a"], ""),
        (["abxxba", "ab"], "ab"),
    ],
)
add(
    "interval_union",
    "T3",
    "interval_algorithms",
    (
        "Merge closed intervals [start,end] where start <= end, inclu"
        "ding intervals touching at endpoints; return sorted disjoint"
        " intervals."
    ),
    [("intervals", seq(seq(INT, 2, 2)))],
    (
        "merged = []\nfor start, end in sorted(intervals):\n    if merg"
        "ed and start <= merged[-1][1]:\n        merged[-1][1] = max(m"
        "erged[-1][1], end)\n    else:\n        merged.append([start, e"
        "nd])\nreturn merged"
    ),
    "max(merged[-1][1], end)",
    "end",
    [
        ([[[1, 5], [2, 3]]], [[1, 5]]),
        ([[]], []),
        ([[[3, 4], [1, 2], [2, 3]]], [[1, 4]]),
        ([[[0, 0]]], [[0, 0]]),
        ([[[1, 2], [4, 5]]], [[1, 2], [4, 5]]),
    ],
)
add(
    "interval_covered_length",
    "T3",
    "interval_algorithms",
    (
        "Return total length of union of half-open intervals [start,e"
        "nd); endpoints satisfy start <= end."
    ),
    [("intervals", seq(seq(INT, 2, 2)))],
    (
        "total = 0\nlast = None\nfor start, end in sorted(intervals):\n "
        "   if last is None or start >= last:\n        total += end - "
        "start\n    elif end > last:\n        total += end - last\n    l"
        "ast = end if last is None else max(last, end)\nreturn total"
    ),
    "last = end if last is None else max(last, end)",
    "last = end",
    [
        ([[[1, 5], [2, 3], [4, 6]]], 5),
        ([[]], 0),
        ([[[0, 0]]], 0),
        ([[[1, 2], [4, 7]]], 4),
        ([[[0, 2], [2, 4]]], 4),
    ],
)
add(
    "interval_concurrency",
    "T3",
    "interval_algorithms",
    (
        "Return peak number of overlapping half-open intervals; ignor"
        "e zero-length intervals; endpoints satisfy start <= end."
    ),
    [("intervals", seq(seq(INT, 2, 2)))],
    (
        "events = []\nfor start, end in intervals:\n    if start < end:"
        "\n        events.append([start, 1])\n        events.append([en"
        "d, -1])\nactive = best = 0\nfor time, delta in sorted(events):"
        "\n    active += delta\n    best = max(best, active)\nreturn bes"
        "t"
    ),
    "events.append([end, -1])",
    "events.append([end, 1])",
    [
        ([[[0, 2], [1, 3]]], 2),
        ([[]], 0),
        ([[[0, 1], [1, 2]]], 1),
        ([[[1, 1]]], 0),
        ([[[1, 4], [2, 3], [2, 5]]], 3),
    ],
)
add(
    "binary_lower_bound",
    "T3",
    "binary_search",
    "For sorted values, return first index with value >= target or length if none.",
    [("values", L), ("target", INT)],
    (
        "lo, hi = 0, len(values)\nwhile lo < hi:\n    mid = (lo + hi) /"
        "/ 2\n    if values[mid] < target:\n        lo = mid + 1\n    el"
        "se:\n        hi = mid\nreturn lo"
    ),
    "values[mid] < target",
    "values[mid] <= target",
    [([[1, 2, 2, 4], 2], 1), ([[], 5], 0), ([[1, 3], 4], 2), ([[1, 3], 0], 0), ([[2, 2], 2], 0)],
)
add(
    "binary_upper_bound",
    "T3",
    "binary_search",
    "For sorted values, return first index with value > target or length if none.",
    [("values", L), ("target", INT)],
    (
        "lo, hi = 0, len(values)\nwhile lo < hi:\n    mid = (lo + hi) /"
        "/ 2\n    if values[mid] <= target:\n        lo = mid + 1\n    e"
        "lse:\n        hi = mid\nreturn lo"
    ),
    "hi = mid",
    "hi = mid - 1",
    [
        ([[1, 2, 2, 4], 2], 3),
        ([[], 5], 0),
        ([[1, 3], 4], 2),
        ([[1, 3], 0], 0),
        ([[2, 2], 2], 2),
        ([[1, 2, 3], 1], 1),
    ],
)
add(
    "rotated_minimum",
    "T3",
    "binary_search",
    ("Return minimum of a rotated ascending list of distinct integers, or null for empty."),
    [("values", L)],
    (
        "if not values:\n    return None\nlo, hi = 0, len(values) - 1\nw"
        "hile lo < hi:\n    mid = (lo + hi) // 2\n    if values[mid] > "
        "values[hi]:\n        lo = mid + 1\n    else:\n        hi = mid\n"
        "return values[lo]"
    ),
    "values[mid] > values[hi]",
    "values[mid] > values[0]",
    [([[3, 4, 1, 2]], 1), ([[]], None), ([[5]], 5), ([[1, 2, 3]], 1), ([[2, 3, 4, 1]], 1)],
)
add(
    "integer_square_root",
    "T3",
    "number_theory",
    "Return floor of square root of nonnegative n.",
    [("n", {"kind": "integer", "min": 0, "max": 10000})],
    (
        "lo, hi = 0, n + 1\nwhile lo + 1 < hi:\n    mid = (lo + hi) // "
        "2\n    if mid * mid <= n:\n        lo = mid\n    else:\n        "
        "hi = mid\nreturn lo"
    ),
    "mid * mid <= n",
    "mid * mid < n",
    [([9], 3), ([8], 2), ([0], 0), ([1], 1), ([100], 10)],
)
add(
    "prime_factorization",
    "T3",
    "number_theory",
    (
        "Return positive prime factors of positive n in ascending ord"
        "er with multiplicity; one yields empty."
    ),
    [("n", P)],
    (
        "result = []\nd = 2\nwhile d * d <= n:\n    while n % d == 0:\n  "
        "      result.append(d)\n        n //= d\n    d += 1\nif n > 1:\n"
        "    result.append(n)\nreturn result"
    ),
    "while n % d == 0:",
    "if n % d == 0:",
    [([12], [2, 2, 3]), ([1], []), ([7], [7]), ([16], [2, 2, 2, 2]), ([18], [2, 3, 3])],
)
add(
    "anagram_groups",
    "T3",
    "text_relations",
    (
        "Group words that are anagrams, preserving first group occurr"
        "ence order and input word order within groups; case sensitiv"
        "e."
    ),
    [("words", W)],
    (
        "groups = {}\nfor word in words:\n    key = str(sorted(word))\n "
        "   groups.setdefault(key, []).append(word)\nreturn list(group"
        "s.values())"
    ),
    "key = str(sorted(word))",
    "key = str(sorted(set(word)))",
    [
        ([["ab", "ba", "aab"]], [["ab", "ba"], ["aab"]]),
        ([[]], []),
        ([["", ""]], [["", ""]]),
        ([["a", "A"]], [["a"], ["A"]]),
        ([["eat", "tea", "bat", "ate"]], [["eat", "tea", "ate"], ["bat"]]),
    ],
)
add(
    "isomorphic_strings",
    "T3",
    "text_relations",
    (
        "Return whether a one-to-one character renaming maps left to "
        "right, with positions preserved."
    ),
    [("left", S), ("right", S)],
    (
        "if len(left) != len(right):\n    return False\nforward, backwa"
        "rd = {}, {}\nfor a, b in zip(left, right):\n    if (a in forwa"
        "rd and forward[a] != b) or (b in backward and backward[b] !="
        " a):\n        return False\n    forward[a] = b\n    backward[b]"
        " = a\nreturn True"
    ),
    " or (b in backward and backward[b] != a)",
    "",
    [
        (["egg", "add"], True),
        (["ab", "cc"], False),
        (["", ""], True),
        (["a", "ab"], False),
        (["foo", "bar"], False),
    ],
)
add(
    "longest_palindromic_substring",
    "T3",
    "text_relations",
    ("Return longest contiguous palindromic substring, choosing the earliest start on ties."),
    [("text", S)],
    (
        "best = ''\nfor start in range(len(text)):\n    for end in rang"
        "e(start + 1, len(text) + 1):\n        part = text[start:end]\n"
        "        if part == part[::-1] and len(part) > len(best):\n   "
        "         best = part\nreturn best"
    ),
    "len(part) > len(best)",
    "len(part) >= len(best)",
    [(["babad"], "bab"), (["cbbd"], "bb"), ([""], ""), (["a"], "a"), (["ab"], "a")],
)
add(
    "prefix_common",
    "T3",
    "text_relations",
    "Return the longest common prefix of all words; empty list gives empty string.",
    [("words", W)],
    (
        "if not words:\n    return ''\nprefix = words[0]\nfor word in wo"
        "rds[1:]:\n    while prefix and not word.startswith(prefix):\n "
        "       prefix = prefix[:-1]\nreturn prefix"
    ),
    "while prefix and not word.startswith(prefix):",
    "if prefix and not word.startswith(prefix):",
    [
        ([["flower", "flow", "flight"]], "fl"),
        ([[]], ""),
        ([["abc", ""]], ""),
        ([["one"]], "one"),
        ([["ab", "xy"]], ""),
    ],
)
add(
    "version_compare",
    "T3",
    "structured_text",
    (
        "Compare dot-separated nonnegative integer versions, treating"
        " missing components as zero; return -1, 0, or 1."
    ),
    [("left", S), ("right", S)],
    (
        "a = [int(x) for x in left.split('.')]\nb = [int(x) for x in r"
        "ight.split('.')]\nfor i in range(max(len(a), len(b))):\n    x "
        "= a[i] if i < len(a) else 0\n    y = b[i] if i < len(b) else "
        "0\n    if x != y:\n        return -1 if x < y else 1\nreturn 0"
    ),
    "range(max(len(a), len(b)))",
    "range(min(len(a), len(b)))",
    [
        (["1", "1.1"], -1),
        (["2.0", "1.9"], 1),
        (["1.0", "1"], 0),
        (["1.10", "1.2"], 1),
        (["0", "0.0"], 0),
    ],
)
add(
    "path_normalize",
    "T3",
    "structured_text",
    (
        "Normalize an absolute slash-separated path: ignore empty and"
        " dot components, pop one component on double-dot without goi"
        "ng above root."
    ),
    [("text", S)],
    (
        "parts = []\nfor part in text.split('/'):\n    if part == '..':"
        "\n        if parts:\n            parts.pop()\n    elif part and"
        " part != '.':\n        parts.append(part)\nreturn '/' + '/'.jo"
        "in(parts)"
    ),
    "elif part and part != '.':",
    "elif part:",
    [
        (["/a/./b/../c"], "/a/c"),
        (["/"], "/"),
        (["/../../x"], "/x"),
        (["/a//b/"], "/a/b"),
        (["/a/.."], "/"),
    ],
)
add(
    "roman_numeral_value",
    "T3",
    "structured_text",
    (
        "Return integer value of a valid uppercase Roman numeral usin"
        "g subtractive pairs; empty string gives zero."
    ),
    [("text", S)],
    (
        "values = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000"
        "}\ntotal = 0\nfor i, ch in enumerate(text):\n    value = values"
        "[ch]\n    if i + 1 < len(text) and value < values[text[i + 1]"
        "]:\n        total -= value\n    else:\n        total += value\nr"
        "eturn total"
    ),
    "total -= value",
    "total += value",
    [(["IV"], 4), (["XII"], 12), ([""], 0), (["MCMXCIV"], 1994), (["XL"], 40)],
)
add(
    "grid_paths",
    "T3",
    "dynamic_programming",
    (
        "Return count of paths from top-left to bottom-right of a rec"
        "tangular 0/1 grid, moving right or down; 1 blocks a cell. Em"
        "pty grid or empty row gives zero."
    ),
    [("grid", seq(seq({"kind": "integer", "min": 0, "max": 1}, 0, 6), 0, 6))],
    (
        "if not grid or not grid[0]:\n    return 0\ncounts = [0] * len("
        "grid[0])\ncounts[0] = 1\nfor row in grid:\n    for j, blocked i"
        "n enumerate(row):\n        if blocked:\n            counts[j] "
        "= 0\n        elif j:\n            counts[j] += counts[j - 1]\nr"
        "eturn counts[-1]"
    ),
    "counts[j] = 0",
    "counts[j] = counts[j]",
    [
        ([[[0, 0], [0, 0]]], 2),
        ([[[1, 0], [0, 0]]], 0),
        ([[]], 0),
        ([[[]]], 0),
        ([[[0, 1, 0], [0, 0, 0]]], 1),
    ],
)
add(
    "flood_fill_count",
    "T3",
    "grid_connectivity",
    ("Count 4-neighbor-connected groups of 1s in a rectangular 0/1 grid; do not mutate the grid."),
    [("grid", seq(seq({"kind": "integer", "min": 0, "max": 1}, 0, 6), 0, 6))],
    (
        "seen = set()\ncount = 0\nfor r in range(len(grid)):\n    for c "
        "in range(len(grid[r])):\n        if grid[r][c] == 1 and (r,c)"
        " not in seen:\n            count += 1\n            stack = [(r"
        ",c)]\n            seen.add((r,c))\n            while stack:\n  "
        "              x,y = stack.pop()\n                for a,b in ["
        "(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:\n                    if 0 <"
        "= a < len(grid) and 0 <= b < len(grid[a]) and grid[a][b] == "
        "1 and (a,b) not in seen:\n                        seen.add((a"
        ",b))\n                        stack.append((a,b))\nreturn coun"
        "t"
    ),
    "(x,y+1)",
    "(x,y+2)",
    [
        ([[[1, 1]]], 1),
        ([[[1, 0], [0, 1]]], 2),
        ([[]], 0),
        ([[[]]], 0),
        ([[[1, 1, 0], [0, 1, 0], [0, 0, 1]]], 2),
    ],
)
add(
    "spiral_rectangular",
    "T3",
    "matrix_traversal",
    (
        "Return entries of a rectangular matrix in clockwise spiral o"
        "rder starting at top-left; empty gives empty."
    ),
    [("rows", M)],
    (
        "if not rows or not rows[0]:\n    return []\ntop,left = 0,0\nbot"
        "tom,right = len(rows)-1,len(rows[0])-1\nresult = []\nwhile top"
        " <= bottom and left <= right:\n    for c in range(left,right+"
        "1):\n        result.append(rows[top][c])\n    top += 1\n    for"
        " r in range(top,bottom+1):\n        result.append(rows[r][rig"
        "ht])\n    right -= 1\n    if top <= bottom:\n        for c in r"
        "ange(right,left-1,-1):\n            result.append(rows[bottom"
        "][c])\n        bottom -= 1\n    if left <= right:\n        for "
        "r in range(bottom,top-1,-1):\n            result.append(rows["
        "r][left])\n        left += 1\nreturn result"
    ),
    "if top <= bottom:",
    "if top < bottom:",
    [
        ([[[1, 2], [3, 4]]], [1, 2, 4, 3]),
        ([[]], []),
        ([[[1, 2, 3]]], [1, 2, 3]),
        ([[[1], [2], [3]]], [1, 2, 3]),
        ([[[1, 2, 3], [4, 5, 6], [7, 8, 9]]], [1, 2, 3, 6, 9, 8, 7, 4, 5]),
        ([[[1, 2, 3], [4, 5, 6]]], [1, 2, 3, 6, 5, 4]),
    ],
)
add(
    "rotate_matrix_clockwise",
    "T3",
    "matrix_traversal",
    (
        "Rotate rectangular matrix clockwise by 90 degrees; empty inp"
        "ut or zero-width rows gives empty."
    ),
    [("rows", M)],
    (
        "if not rows or not rows[0]:\n    return []\nreturn [[rows[r][c"
        "] for r in range(len(rows)-1,-1,-1)] for c in range(len(rows"
        "[0]))]"
    ),
    "range(len(rows)-1,-1,-1)",
    "range(len(rows))",
    [
        ([[[1, 2], [3, 4]]], [[3, 1], [4, 2]]),
        ([[]], []),
        ([[[]]], []),
        ([[[1, 2, 3]]], [[1], [2], [3]]),
        ([[[1], [2]]], [[2, 1]]),
    ],
)
add(
    "pair_sum_indices",
    "T3",
    "pair_algorithms",
    (
        "Return [i,j] with i<j and values[i]+values[j]=target, choosi"
        "ng smallest j then smallest i; null if absent."
    ),
    [("values", L), ("target", INT)],
    (
        "seen = {}\nfor j,x in enumerate(values):\n    if target - x in"
        " seen:\n        return [seen[target - x], j]\n    if x not in "
        "seen:\n        seen[x] = j\nreturn None"
    ),
    "if x not in seen:",
    "if True:",
    [
        ([[1, 1, 2], 3], [0, 2]),
        ([[2, 7, 11], 9], [0, 1]),
        ([[], 0], None),
        ([[3], 6], None),
        ([[0, 0], 0], [0, 1]),
    ],
)
add(
    "three_sum_unique",
    "T3",
    "pair_algorithms",
    (
        "Return all distinct sorted triples summing to zero, lexicogr"
        "aphically ordered; use three distinct positions."
    ),
    [("values", L)],
    (
        "triples = set()\nfor i in range(len(values)):\n    for j in ra"
        "nge(i+1,len(values)):\n        for k in range(j+1,len(values)"
        "):\n            if values[i]+values[j]+values[k] == 0:\n      "
        "          triples.add(tuple(sorted([values[i],values[j],valu"
        "es[k]])))\nreturn [list(t) for t in sorted(triples)]"
    ),
    "range(j+1,len(values))",
    "range(j,len(values))",
    [
        ([[-1, 0, 1]], [[-1, 0, 1]]),
        ([[]], []),
        ([[0, 0]], []),
        ([[0, 0, 0]], [[0, 0, 0]]),
        ([[-2, 0, 1, 1, 2]], [[-2, 0, 2], [-2, 1, 1]]),
    ],
)
add(
    "inversion_count",
    "T3",
    "pair_algorithms",
    ("Count pairs of indices i<j with values[i]>values[j]; equal values do not form inversions."),
    [("values", L)],
    (
        "count = 0\nfor i in range(len(values)):\n    for j in range(i+"
        "1,len(values)):\n        if values[i] > values[j]:\n          "
        "  count += 1\nreturn count"
    ),
    "values[i] > values[j]",
    "values[i] >= values[j]",
    [([[2, 1, 1]], 2), ([[]], 0), ([[3, 2, 1]], 3), ([[1, 2, 3]], 0), ([[5, 5]], 0)],
)
add(
    "next_greater_values",
    "T3",
    "stack_algorithms",
    ("For each value, return the first strictly greater value to its right, or null if none."),
    [("values", L)],
    (
        "result = [None] * len(values)\nstack = []\nfor i,x in enumerat"
        "e(values):\n    while stack and values[stack[-1]] < x:\n      "
        "  result[stack.pop()] = x\n    stack.append(i)\nreturn result"
    ),
    "values[stack[-1]] < x",
    "values[stack[-1]] <= x",
    [
        ([[2, 2, 3]], [3, 3, None]),
        ([[]], []),
        ([[3, 2, 1]], [None, None, None]),
        ([[1, 3, 2]], [3, None, None]),
        ([[4]], [None]),
    ],
)
add(
    "stock_span",
    "T3",
    "stack_algorithms",
    (
        "For each price return consecutive days ending today whose pr"
        "ices are at most today price, including today."
    ),
    [("prices", L)],
    (
        "result = []\nstack = []\nfor i,price in enumerate(prices):\n   "
        " while stack and prices[stack[-1]] <= price:\n        stack.p"
        "op()\n    result.append(i - stack[-1] if stack else i + 1)\n  "
        "  stack.append(i)\nreturn result"
    ),
    "prices[stack[-1]] <= price",
    "prices[stack[-1]] < price",
    [
        ([[10, 10]], [1, 2]),
        ([[]], []),
        ([[100, 80, 60, 70, 60, 75, 85]], [1, 1, 1, 2, 1, 4, 6]),
        ([[1, 2, 3]], [1, 2, 3]),
        ([[3, 2, 1]], [1, 1, 1]),
    ],
)
add(
    "rainwater_volume",
    "T3",
    "height_geometry",
    "For nonnegative bar heights, return total units of trapped rainwater.",
    [("heights", seq(N))],
    (
        "water = 0\nfor i,h in enumerate(heights):\n    left = max(heig"
        "hts[:i+1])\n    right = max(heights[i:])\n    water += max(0, "
        "min(left,right) - h)\nreturn water"
    ),
    "min(left,right)",
    "max(left,right)",
    [([[2, 0, 2]], 2), ([[]], 0), ([[1]], 0), ([[3, 0, 1, 3]], 5), ([[0, 1, 2]], 0)],
)
add(
    "largest_histogram_rectangle",
    "T3",
    "height_geometry",
    ("Return area of largest rectangle beneath consecutive nonnegative histogram bars."),
    [("heights", seq(N))],
    (
        "best = 0\nfor i in range(len(heights)):\n    lowest = heights["
        "i]\n    for j in range(i,len(heights)):\n        lowest = min("
        "lowest,heights[j])\n        best = max(best,lowest * (j-i+1))"
        "\nreturn best"
    ),
    "lowest = min(lowest,heights[j])",
    "lowest = heights[j]",
    [([[2, 1, 2]], 3), ([[]], 0), ([[5]], 5), ([[2, 2, 2]], 6), ([[2, 1, 5, 6, 2, 3]], 10)],
)

add(
    "polynomial_horner",
    "T3",
    "polynomial_algebra",
    (
        "Evaluate polynomial whose coefficients are in descending pow"
        "er order at integer x; empty coefficients gives zero."
    ),
    [("coefficients", L), ("x", {"kind": "integer", "min": -5, "max": 5})],
    (
        "value = 0\nfor coefficient in coefficients:\n    value = value"
        " * x + coefficient\nreturn value"
    ),
    "value * x + coefficient",
    "(value + coefficient) * x",
    [([[2, 3, 4], 2], 18), ([[], 3], 0), ([[5], 0], 5), ([[1, 0, -1], -2], 3), ([[0, 2], 4], 2)],
)
add(
    "postfix_arithmetic",
    "T3",
    "expression_parsing",
    (
        "Evaluate valid space-separated postfix expressions with inte"
        "ger tokens and binary operators +, - and *; a nonempty valid"
        " expression leaves one value."
    ),
    [("text", S)],
    (
        "stack = []\nfor token in text.split():\n    if token in ('+','"
        "-','*'):\n        right = stack.pop()\n        left = stack.po"
        "p()\n        stack.append(left + right if token == '+' else l"
        "eft - right if token == '-' else left * right)\n    else:\n   "
        "     stack.append(int(token))\nreturn stack[-1]"
    ),
    "left - right",
    "right - left",
    [(["3 2 -"], 1), (["2 3 + 4 *"], 20), (["5"], 5), (["-2 3 *"], -6), (["4 2 - 3 *"], 6)],
)

# Independent replacements for nine bases rejected by the initial split audit.
add(
    "ascii_letters_only",
    "T1",
    "text_character_classes",
    "Return whether text is nonempty and contains ASCII letters only.",
    [("text", S)],
    "return text.isalpha()",
    ".isalpha()",
    ".isalnum()",
    [(["abc"], True), (["a1"], False), ([""], False), (["XYZ"], True), (["a b"], False)],
)
add(
    "digit_text_only",
    "T1",
    "text_character_classes",
    "Return whether text is nonempty and consists entirely of decimal digits.",
    [("text", S)],
    "return text.isdigit()",
    ".isdigit()",
    ".isalnum()",
    [(["123"], True), (["a1"], False), ([""], False), (["00"], True), (["-2"], False)],
)
add(
    "multiplication_table",
    "T2",
    "matrix_geometry",
    ("Return n by n multiplication table whose row i and column j contain (i+1)*(j+1)."),
    [("n", {"kind": "integer", "min": 0, "max": 6})],
    "return [[(i+1)*(j+1) for j in range(n)] for i in range(n)]",
    "(i+1)*(j+1)",
    "i*(j+1)",
    [
        ([2], [[1, 2], [2, 4]]),
        ([0], []),
        ([1], [[1]]),
        ([3], [[1, 2, 3], [2, 4, 6], [3, 6, 9]]),
        ([4], [[1, 2, 3, 4], [2, 4, 6, 8], [3, 6, 9, 12], [4, 8, 12, 16]]),
    ],
)
add(
    "rectangular_border",
    "T2",
    "matrix_traversal",
    (
        "Return border entries of a rectangular matrix clockwise from"
        " top-left, each border cell once."
    ),
    [("rows", M)],
    (
        "if not rows or not rows[0]:\n    return []\nheight,width = len"
        "(rows),len(rows[0])\nresult = list(rows[0])\nfor r in range(1,"
        "height):\n    result.append(rows[r][-1])\nif height > 1:\n    r"
        "esult += list(reversed(rows[-1][:-1]))\nif width > 1:\n    for"
        " r in range(height-2,0,-1):\n        result.append(rows[r][0]"
        ")\nreturn result"
    ),
    "if width > 1:",
    "if height > 1:",
    [
        ([[[1], [2], [3]]], [1, 2, 3]),
        ([[]], []),
        ([[[1, 2, 3]]], [1, 2, 3]),
        ([[[1, 2], [3, 4]]], [1, 2, 4, 3]),
        ([[[1, 2, 3], [4, 5, 6], [7, 8, 9]]], [1, 2, 3, 6, 9, 8, 7, 4]),
    ],
)
add(
    "arithmetic_triplets",
    "T2",
    "pair_algorithms",
    (
        "Count triples of indices i<j<k for which values[i],values[j]"
        ",values[k] form an arithmetic progression, including repeate"
        "d equal values."
    ),
    [("values", L)],
    (
        "count = 0\nfor i in range(len(values)):\n    for j in range(i+"
        "1,len(values)):\n        for k in range(j+1,len(values)):\n   "
        "         if values[i]+values[k] == 2*values[j]:\n            "
        "    count += 1\nreturn count"
    ),
    "2*values[j]",
    "values[j]",
    [([[1, 2, 3]], 1), ([[]], 0), ([[0, 0, 0]], 1), ([[1, 3, 5, 7]], 2), ([[3, 2, 1]], 1)],
)
add(
    "rotate_text_left",
    "T2",
    "text_ciphers",
    (
        "Rotate text left by k positions modulo text length; negative"
        " k rotates right; empty remains empty."
    ),
    [("text", S), ("k", INT)],
    "if not text:\n    return ''\nk %= len(text)\nreturn text[k:] + text[:k]",
    "k %= len(text)",
    "k = min(max(k,0),len(text))",
    [
        (["abcd", 5], "bcda"),
        (["", 3], ""),
        (["abc", -1], "cab"),
        (["x", 100], "x"),
        (["abc", 3], "abc"),
    ],
)
add(
    "hamming_distance",
    "T3",
    "text_relations",
    ("Return count of differing positions in equal-length strings; return -1 if lengths differ."),
    [("left", S), ("right", S)],
    (
        "if len(left) != len(right):\n    return -1\ncount = 0\nfor a,b "
        "in zip(left,right):\n    if a != b:\n        count += 1\nreturn"
        " count"
    ),
    "if len(left) != len(right):",
    "if False:",
    [(["ab", "a"], -1), (["abc", "axc"], 1), (["", ""], 0), (["ab", "cd"], 2), (["aa", "aa"], 0)],
)
add(
    "top_frequent_words",
    "T3",
    "mapping_relations",
    (
        "Return up to k distinct words by descending frequency, break"
        "ing ties lexicographically; k nonnegative."
    ),
    [("words", W), ("k", N)],
    (
        "counts = {}\nfor word in words:\n    counts[word] = counts.get"
        "(word,0)+1\nranked = sorted([[-count,word] for word,count in "
        "counts.items()])\nreturn [word for count,word in ranked[:k]]"
    ),
    "[-count,word]",
    "[count,word]",
    [
        ([["b", "a", "b", "c"], 2], ["b", "a"]),
        ([[], 3], []),
        ([["x"], 0], []),
        ([["b", "a"], 3], ["a", "b"]),
        ([["z", "z", "a"], 1], ["z"]),
    ],
)
add(
    "zigzag_text_rows",
    "T3",
    "text_layout",
    (
        "Write text in zigzag over positive rows, moving down then up"
        " repeatedly; read rows top to bottom."
    ),
    [("text", S), ("rows", P)],
    (
        "if rows == 1:\n    return text\nparts = [''] * rows\nrow,direct"
        "ion = 0,1\nfor ch in text:\n    parts[row] += ch\n    if row =="
        " 0:\n        direction = 1\n    elif row == rows-1:\n        di"
        "rection = -1\n    row += direction\nreturn ''.join(parts)"
    ),
    "direction = -1",
    "direction = 1",
    [
        (["abcdef", 3], "aebdfc"),
        (["", 2], ""),
        (["abc", 1], "abc"),
        (["abcd", 2], "acbd"),
        (["ab", 5], "ab"),
    ],
)
EXCLUDED = {
    name: "training/validation base, family or normalized-source overlap"
    for name in (
        "factorial",
        "euclidean_gcd",
        "least_common_multiple",
        "prime_check",
        "divisor_list",
        "integer_square_root",
        "prime_factorization",
        "run_lengths",
        "substring_membership",
    )
}

add(
    "row_major_coordinates",
    "T1",
    "matrix_indexing",
    "Return [row,column] of zero-based flattened index in a grid of positive width.",
    [("index", N), ("width", P)],
    "return [index // width, index % width]",
    "index // width",
    "index % width",
    [([5, 3], [1, 2]), ([0, 4], [0, 0]), ([3, 3], [1, 0]), ([7, 2], [3, 1]), ([1, 10], [0, 1])],
)
add(
    "punctuation_sentences",
    "T2",
    "text_tokenization",
    (
        "Count nonempty spans of non-space characters separated by an"
        "y sequence of periods, question marks or exclamation marks; "
        "count an unterminated final span."
    ),
    [("text", S)],
    (
        "count = 0\ncontent = False\nfor ch in text:\n    if ch in '.?!'"
        ":\n        if content:\n            count += 1\n            con"
        "tent = False\n    elif ch != ' ':\n        content = True\nretu"
        "rn count + int(content)"
    ),
    "count + int(content)",
    "count",
    [(["Hi! Bye"], 2), ([""], 0), (["..."], 0), (["a?! b."], 2), ([" x "], 1)],
)
add(
    "local_peak_indices",
    "T2",
    "height_geometry",
    (
        "Return indices strictly greater than each existing immediate"
        " neighbor; singleton is a peak, empty has none."
    ),
    [("values", L)],
    (
        "result = []\nfor i,x in enumerate(values):\n    if (i == 0 or "
        "x > values[i-1]) and (i+1 == len(values) or x > values[i+1])"
        ":\n        result.append(i)\nreturn result"
    ),
    "i+1 == len(values)",
    "i == len(values)",
    [([[1, 3, 2]], [1]), ([[]], []), ([[7]], [0]), ([[2, 1, 3]], [0, 2]), ([[2, 2]], [])],
)
add(
    "polynomial_derivative",
    "T2",
    "polynomial_algebra",
    (
        "Given coefficients in ascending power order, return derivati"
        "ve coefficients in ascending order; constants and empty inpu"
        "t yield empty."
    ),
    [("coefficients", L)],
    (
        "result = []\nfor power in range(1,len(coefficients)):\n    res"
        "ult.append(power * coefficients[power])\nreturn result"
    ),
    "power * coefficients[power]",
    "(power+1) * coefficients[power]",
    [([[3, 2, 4]], [2, 8]), ([[]], []), ([[5]], []), ([[0, 0, 1]], [0, 2]), ([[1, -3]], [-3])],
)
add(
    "matrix_zero_rows_columns",
    "T3",
    "matrix_dependency",
    (
        "Return rectangular matrix with every row and column containi"
        "ng an original zero replaced entirely by zeros; keep inputs "
        "unchanged."
    ),
    [("rows", M)],
    (
        "zero_rows = set()\nzero_cols = set()\nfor i,row in enumerate(r"
        "ows):\n    for j,x in enumerate(row):\n        if x == 0:\n    "
        "        zero_rows.add(i)\n            zero_cols.add(j)\nreturn"
        " [[0 if i in zero_rows or j in zero_cols else x for j,x in e"
        "numerate(row)] for i,row in enumerate(rows)]"
    ),
    "i in zero_rows or j in zero_cols",
    "i in zero_rows and j in zero_cols",
    [
        ([[[1, 0], [3, 4]]], [[0, 0], [3, 0]]),
        ([[]], []),
        ([[[]]], [[]]),
        ([[[1, 2], [3, 4]]], [[1, 2], [3, 4]]),
        ([[[0, 2, 3], [4, 5, 6], [7, 8, 9]]], [[0, 0, 0], [0, 5, 6], [0, 8, 9]]),
    ],
)
add(
    "graph_reachable",
    "T3",
    "graph_traversal",
    (
        "Return sorted vertices reachable from start in a directed ad"
        "jacency-list graph, including start; empty graph or start ou"
        "tside graph gives empty."
    ),
    [("graph", seq(seq(N, 0, 6), 0, 6)), ("start", N)],
    (
        "if start >= len(graph):\n    return []\nseen = {start}\nstack ="
        " [start]\nwhile stack:\n    vertex = stack.pop()\n    for neigh"
        "bor in graph[vertex]:\n        if 0 <= neighbor < len(graph) "
        "and neighbor not in seen:\n            seen.add(neighbor)\n   "
        "         stack.append(neighbor)\nreturn sorted(seen)"
    ),
    "stack.append(neighbor)",
    "stack = []",
    [
        ([[[1], [2], []], 0], [0, 1, 2]),
        ([[], 0], []),
        ([[[0]], 0], [0]),
        ([[[1], [0], []], 0], [0, 1]),
        ([[[], []], 1], [1]),
    ],
)
add(
    "graph_shortest_distance",
    "T3",
    "graph_traversal",
    (
        "Return number of edges in shortest directed path from start "
        "to goal in adjacency-list graph; -1 for unreachable or out-o"
        "f-range endpoint."
    ),
    [("graph", seq(seq(N, 0, 6), 0, 6)), ("start", N), ("goal", N)],
    (
        "if start >= len(graph) or goal >= len(graph):\n    return -1\n"
        "queue = [[start,0]]\nseen = {start}\nwhile queue:\n    vertex,d"
        "istance = queue.pop(0)\n    if vertex == goal:\n        return"
        " distance\n    for neighbor in graph[vertex]:\n        if 0 <="
        " neighbor < len(graph) and neighbor not in seen:\n           "
        " seen.add(neighbor)\n            queue.append([neighbor,dista"
        "nce+1])\nreturn -1"
    ),
    "queue.pop(0)",
    "queue.pop()",
    [
        ([[[1, 2], [3], [4], [], [3]], 0, 3], 2),
        ([[], 0, 0], -1),
        ([[[0]], 0, 0], 0),
        ([[[], []], 0, 1], -1),
        ([[[1], [2], []], 0, 2], 2),
    ],
)
add(
    "graph_indegrees",
    "T3",
    "graph_incidence",
    (
        "Return indegree of every vertex of directed adjacency-list g"
        "raph; count repeated edges separately and ignore out-of-rang"
        "e neighbors."
    ),
    [("graph", seq(seq(N, 0, 6), 0, 6))],
    (
        "degrees = [0] * len(graph)\nfor neighbors in graph:\n    for v"
        "ertex in neighbors:\n        if 0 <= vertex < len(graph):\n   "
        "         degrees[vertex] += 1\nreturn degrees"
    ),
    "degrees[vertex] += 1",
    "degrees[vertex] = 1",
    [
        ([[[1, 1], [0]]], [1, 2]),
        ([[]], []),
        ([[[0]]], [1]),
        ([[[], [0], [0]]], [2, 0, 0]),
        ([[[5], []]], [0, 0]),
    ],
)
EXCLUDED.update(
    {
        name: "semantic training-family overlap or conservative AST near-duplicate gate"
        for name in (
            "checkerboard_black",
            "full_weeks",
            "colon_seconds",
            "word_join",
            "repeat_text",
            "run_value_pairs",
            "text_run_collapse",
            "longest_same_run",
        )
    }
)


def write(directory=None):
    directory = Path(directory or Path(__file__).parent)
    directory.joinpath("private").mkdir(exist_ok=True)
    selected = [row for row in ROWS if row["base_problem_id"] not in EXCLUDED]
    directory.joinpath("excluded.json").write_text(json.dumps(EXCLUDED, indent=2) + "\n")
    visible = [
        {k: v for k, v in row.items() if k not in {"correct_source", "hidden_tests"}}
        for row in selected
    ]
    scoring = [
        {
            k: row[k]
            for k in ("base_problem_id", "family_id", "split", "correct_source", "hidden_tests")
        }
        for row in selected
    ]
    for relative, rows in [("runtime.jsonl", visible), ("private/scoring.jsonl", scoring)]:
        directory.joinpath(relative).write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        )
    print(
        json.dumps(
            {
                "base_problems": len(selected),
                "tiers": {
                    tier: sum(row["tier"] == tier for row in selected)
                    for tier in ("T1", "T2", "T3")
                },
            }
        )
    )


if __name__ == "__main__":
    write()
