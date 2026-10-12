"""Auditor self-test against the real sandbox (pending when no VM/image is available)."""

import argparse
import sys
from pathlib import Path

from .auditor import Auditor
from .domains import analyze_source
from .oracles import suite_hash
from .runner import Evaluator
from .selftest import run_native

CAND = ("def f(values):\n    total = 0\n    for v in values:\n        if v > 0:\n"
        "            total += v\n    return total\n")  # fmt: skip


def _test(test_id, inputs, expected):
    return {
        "test_id": test_id, "inputs": inputs, "related_inputs": None,
        "oracle_spec": {"kind": "literal", "expected": expected},
        "oracle_status": "authoritative", "oracle_source": "user", "domain_valid": True,
        "requirement_ids": [], "provenance": "supplied",
    }  # fmt: skip


def _audit(sandbox, tests, remaining=48):
    info = analyze_source(CAND, "f", [], [])
    problem = {"problem_id": "st", "function_name": "f", "signature": info.signature,
               "helper_interfaces": [], "allowed_dependencies": []}  # fmt: skip
    ev = Evaluator(sandbox, problem, id_prefix="au", max_executions=4000)
    return Auditor(ev, problem, {"candidate_id": "c", "source": CAND}, tests, max_mutants=24,
                   suite=suite_hash(tests), id_prefix="au", episode_remaining=remaining).run()


def cases(sandbox, settings):
    weak = [_test("a", [[2, 3]], 5), _test("b", [[-1]], 0)]
    strong = weak + [_test("c", [[1]], 1)]
    before, after = _audit(sandbox, weak), _audit(sandbox, strong)

    def at(out):
        return next(m for m in out.mutants
                    if m["edit"]["location"]["lineno"] == 4 and m["edit"]["after"] == "1")  # fmt: skip

    return {
        "weak_boundary_survives": at(before)["outcome"] == "survived",
        "followup_kills_probe": at(after)["outcome"] == "killed",
        "gap_unresolved_not_accusation": all(
            g["interpretation"] == "unresolved_test_gap" for g in before.gaps
        ),
        "caps_24_48": len(_audit(sandbox, weak, remaining=5).mutants) == 5
        and len(before.mutants) <= 24,
    }  # fmt: skip


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="audit_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("self-test")
    st.add_argument("--config", required=True, type=Path)
    st.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    return run_native(args.config, args.out, "audit-self-test.json", cases)


if __name__ == "__main__":
    sys.exit(main())
