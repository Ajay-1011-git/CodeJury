"""Search self-test against the real sandbox (pending when no VM/image is available)."""

import argparse
import sys
from pathlib import Path

from .domains import analyze_source
from .runner import Evaluator
from .search import SearchEngine
from .search.operators import sha
from .selftest import run_native

MAXFN = (
    "def f(values):\n    best = values[0]\n    for v in values:\n        if v < best:\n"
    "            best = v\n    return best\n"
)
POS = (
    "def f(values):\n    total = 0\n    for i in range(1, len(values)):\n"
    "        if values[i] < 0:\n            total += values[i]\n    return total\n"
)


def _test(test_id, inputs, expected):
    return {
        "test_id": test_id,
        "inputs": inputs,
        "related_inputs": None,
        "oracle_spec": {"kind": "literal", "expected": expected},
        "oracle_status": "authoritative",
        "oracle_source": "user",
        "domain_valid": True,
        "requirement_ids": [],
        "provenance": "supplied",
    }


def _search(sandbox, source, tests, depth):
    info = analyze_source(source, "f", [], [])
    problem = {
        "problem_id": "st",
        "function_name": "f",
        "signature": info.signature,
        "helper_interfaces": [],
        "allowed_dependencies": [],
    }
    ev = Evaluator(sandbox, problem, id_prefix="st", max_executions=4000)
    parent = {
        "candidate_id": "orig",
        "source": source,
        "source_hash": sha(source),
        "requirement_ids": [],
    }
    return SearchEngine(
        ev,
        problem,
        [parent],
        tests,
        sites=[],
        families=[
            "comparison",
            "boundary_constant",
            "boolean_negation",
            "arithmetic",
            "variable_reference",
        ],
        depth=depth,
        candidate_limit=48,
        id_prefix="st",
    ).run()


def cases(sandbox, settings):
    one = _search(
        sandbox,
        MAXFN,
        [_test("a", [[3, 1, 2]], 3), _test("b", [[5]], 5), _test("c", [[1, 9, 4]], 9)],
        1,
    )
    pos_tests = [
        _test("a", [[1, 2]], 3),
        _test("b", [[-1, -2]], 0),
        _test("c", [[5, -3]], 5),
        _test("d", [[-4, 2]], 2),
        _test("e", [[0]], 0),
    ]
    single = _search(sandbox, POS, pos_tests, 1)
    two = _search(sandbox, POS, pos_tests, 2)
    chain = two.candidates and two.candidates[0]["edits"]
    return {
        "comparator_repair": any(
            c["edits"][0]["operator_family"] == "comparison" for c in one.candidates
        ),
        "single_edit_cannot_repair_two_bug_case": single.candidates == [],
        "two_edit_repair_hash_chain": bool(chain)
        and len(chain) == 2
        and chain[0]["result_source_hash"] == chain[1]["parent_source_hash"],
        "caps_respected": max(one.search_candidates, two.search_candidates) <= 48,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="search_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("self-test")
    st.add_argument("--config", required=True, type=Path)
    st.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    return run_native(args.config, args.out, "search-self-test.json", cases)


if __name__ == "__main__":
    sys.exit(main())
