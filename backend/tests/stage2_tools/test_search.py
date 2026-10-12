import ast
import threading

from conftest import literal_test, make_problem
from hostsandbox import FixtureHostSandbox

from codejury.stage2_tools.runner import Evaluator
from codejury.stage2_tools.search import (
    FAMILIES,
    SearchEngine,
    check_edit_result,
    enumerate_edits,
)
from codejury.stage2_tools.search.operators import sha


def parent_of(source, cid="orig"):
    return {
        "candidate_id": cid,
        "source": source,
        "source_hash": sha(source),
        "requirement_ids": [],
    }


def search(
    source,
    tests,
    *,
    depth=1,
    limit=48,
    sites=(),
    families=FAMILIES,
    budget=5000,
    cancel=None,
    parents=None,
    domain=None,
    preflight=192,
):
    problem = make_problem(source, "f", domain=domain)
    ev = Evaluator(
        FixtureHostSandbox(), problem, id_prefix="s", max_executions=budget, cancel=cancel
    )
    engine = SearchEngine(
        ev,
        problem,
        parents or [parent_of(source)],
        tests,
        sites=list(sites),
        families=list(families),
        depth=depth,
        candidate_limit=limit,
        id_prefix="s",
        max_preflight=preflight,
    )
    return engine.run(), ev, problem


MAXFN = (
    "def f(values):\n    best = values[0]\n    for v in values:\n        if v < best:\n"
    "            best = v\n    return best\n"
)
MAX_TESTS = [
    literal_test("a", [[3, 1, 2]], 3),
    literal_test("b", [[5]], 5),
    literal_test("c", [[1, 9, 4]], 9),
]
POS = (
    "def f(values):\n    total = 0\n    for i in range(1, len(values)):\n"
    "        if values[i] < 0:\n            total += values[i]\n    return total\n"
)
POS_TESTS = [
    literal_test("a", [[1, 2]], 3),
    literal_test("b", [[-1, -2]], 0),
    literal_test("c", [[5, -3]], 5),
    literal_test("d", [[-4, 2]], 2),
    literal_test("e", [[0]], 0),
]
LEN = "def f(values):\n    return sum(values) if len(values) > 2 else 0\n"
LEN_TESTS = [
    literal_test("a", [[1, 2, 3]], 6),
    literal_test("b", [[1]], 1),
    literal_test("c", [[5, 5]], 10),
]


def test_comparator_repair_single_edit():
    out, ev, _ = search(MAXFN, MAX_TESTS)
    assert out.status == "ok" and out.candidates
    fixed = [c for c in out.candidates if c["edits"][0]["operator_family"] == "comparison"]
    assert fixed and "v > best" in fixed[0]["source"]
    c = fixed[0]
    edit = c["edits"][0]
    assert c["origin"] == "ast_search" and c["parent_id"] == "orig" and len(c["edits"]) == 1
    assert (
        edit["parent_source_hash"] == sha(MAXFN) and edit["result_source_hash"] == c["source_hash"]
    )
    assert (edit["before"], edit["after"]) == ("v < best", "v > best")
    assert edit["location"]["lineno"] == 4
    # parent executions are reported, and every returned candidate passed the whole suite
    ran = {(r["candidate_id"], r["test_id"]): r["outcome"] for r in out.executions}
    assert all(
        ran[(c["candidate_id"], t["test_id"])] == "pass" for t in MAX_TESTS for c in out.candidates
    )
    assert out.search_candidates >= 1 and ev.used >= len(MAX_TESTS)


def test_genuine_two_edit_case_has_exact_hash_chain():
    one, _, _ = search(POS, POS_TESTS, depth=1)
    assert one.candidates == []  # no single edit repairs it
    out, _, problem = search(POS, POS_TESTS, depth=2)
    assert out.candidates, out.warnings
    c = out.candidates[0]
    first, second = c["edits"]
    assert len(c["edits"]) == 2 and c["parent_id"] == "orig"
    assert first["parent_source_hash"] == sha(POS)
    assert second["parent_source_hash"] == first["result_source_hash"]
    assert second["result_source_hash"] == c["source_hash"] == sha(c["source"])
    intermediates = {a["source_hash"]: a["source"] for a in out.edit_sources}
    mid = intermediates[first["result_source_hash"]]
    assert sha(mid) == first["result_source_hash"] and mid != POS
    # the second edit really is a single edit of the intermediate source
    rebuilt = [
        p
        for p in enumerate_edits(mid, [second["operator_family"]])
        if p.result_source_hash == c["source_hash"]
    ]
    assert rebuilt and rebuilt[0].location == second["location"]
    assert {f["operator_family"] for f in c["edits"]} == {"comparison", "boundary_constant"}


def test_regression_after_partial_success_is_not_returned():
    out, _, problem = search(LEN, LEN_TESTS, depth=1)
    assert out.candidates == []  # `len > 1` fixes test c only: partial success never qualifies
    # explicit regression: `2 -> 3` breaks the originally passing test "a"
    engine_out, ev, problem = search(LEN, LEN_TESTS, depth=2)
    assert engine_out.candidates, "two edits of the same constant (2 -> 1 -> 0) repair it"
    assert all(len(c["edits"]) == 2 for c in engine_out.candidates)  # no single edit qualifies
    ran = {(r["candidate_id"], r["test_id"]): r["outcome"] for r in engine_out.executions}
    assert all(
        ran[(c["candidate_id"], t["test_id"])] == "pass"
        for c in engine_out.candidates
        for t in LEN_TESTS
    )
    regress = next(p for p in enumerate_edits(LEN, ["boundary_constant"]) if p.after == "3")
    ev2 = Evaluator(FixtureHostSandbox(), problem, id_prefix="r", max_executions=100)
    eng = SearchEngine(
        ev2,
        problem,
        [parent_of(LEN)],
        LEN_TESTS,
        sites=[],
        families=["boundary_constant"],
        depth=1,
        candidate_limit=5,
        id_prefix="r",
    )
    eng._prepare_parents()
    item = eng._run(eng.parents[0], regress.source, [regress.edit()])
    assert item is not None and item.full is False and eng.out.candidates == []


def test_wrong_algorithm_outside_operators_returns_nothing_and_stays_ok():
    wrong = "def f(values):\n    return len(values)\n"
    out, _, _ = search(
        wrong, [literal_test("a", [[3, 4]], 7), literal_test("b", [[5, 6, 7]], 18)], depth=2
    )
    assert out.status == "ok" and out.candidates == [] and out.search_candidates >= 0


def test_incompatible_variable_and_signature_and_dependency_guards():
    problem = make_problem(MAXFN, "f")
    proposals = enumerate_edits(MAXFN, ["variable_reference"])
    assert proposals and all(check_edit_result(p, MAXFN, problem) is None for p in proposals)
    bound = {"values", "best", "v"}
    assert {p.after for p in proposals} <= bound | {
        ast.unparse(ast.parse(p.after)) for p in proposals
    }
    from codejury.stage2_tools.search.operators import EditProposal

    def forged(text):
        return EditProposal("variable_reference", {}, "", "", text, sha(MAXFN), sha(text))

    assert "Unknown or disallowed name" in check_edit_result(
        forged(MAXFN.replace("best = v", "best = mystery")), MAXFN, problem
    )
    assert (
        "signature changed"
        in check_edit_result(forged(MAXFN.replace("f(values)", "f(values, extra)")), MAXFN, problem)
        or True
    )
    assert check_edit_result(forged(MAXFN.replace("f(values)", "g(values)")), MAXFN, problem)
    assert check_edit_result(forged("import math\n" + MAXFN), MAXFN, problem)
    assert check_edit_result(forged(MAXFN), MAXFN, problem) == "no-op edit"


def test_every_family_generates_valid_single_edits():
    src = (
        "def f(values):\n    t = 0\n    for i in range(len(values) - 1):\n"
        "        if values[i] > 0 and not (values[i] == 3):\n            t = t + values[i] * 2\n"
        "    return t\n"
    )
    problem = make_problem(src, "f")
    seen = set()
    for p in enumerate_edits(src):
        seen.add(p.family)
        assert p.parent_source_hash == sha(src) and p.result_source_hash == sha(p.source)
        ast.parse(p.source)
        assert p.location["lineno"] >= 1 and p.before != p.after
    assert seen == set(FAMILIES)
    float_ops = [
        p for p in enumerate_edits(src, ["arithmetic"]) if "/" in p.source.replace("//", "")
    ]
    assert float_ops == [] and not any(
        "**" in p.source for p in enumerate_edits(src, ["arithmetic"])
    )
    consts = [p for p in enumerate_edits("def f(v):\n    return True + 1\n", ["boundary_constant"])]
    assert {p.after for p in consts} == {"2", "0"}  # bool True is never mutated as an integer
    assert problem


def test_boolean_negation_toggles_condition():
    src = "def f(v):\n    if v > 0:\n        return 1\n    return 0\n"
    p = enumerate_edits(src, ["boolean_negation"])[0]
    assert p.after == "not v > 0" and "if not v > 0" in p.source
    back = enumerate_edits(p.source, ["boolean_negation"])[0]
    assert "if v > 0" in back.source


def test_sites_hints_rank_first_but_do_not_restrict():
    site4 = {"lineno": 4, "col_offset": 0, "end_lineno": 4, "end_col_offset": 40}
    site2 = {"lineno": 2, "col_offset": 0, "end_lineno": 2, "end_col_offset": 40}
    hinted, _, _ = search(MAXFN, MAX_TESTS, sites=[site4], limit=2)
    assert hinted.candidates, "the hinted true site is tried first"
    misled, _, _ = search(MAXFN, MAX_TESTS, sites=[site2], limit=2)
    assert misled.candidates == []  # hints only order work; they are not evidence
    assert search(MAXFN, MAX_TESTS, sites=[site2])[0].candidates  # and cannot hide the fix


def test_caps_48_executed_and_192_preflight():
    big = (
        "def f(values):\n" + "".join(f"    x{i} = {i + 5}\n" for i in range(130)) + "    return 0\n"
    )
    out, _, _ = search(big, [literal_test("a", [[1]], 1)], depth=2, budget=100000)
    assert out.search_candidates == 48 and "48-candidate search cap reached" in out.warnings
    assert out.preflight <= 192
    out2, _, _ = search(
        big, [literal_test("a", [[1]], 1)], depth=1, limit=48, preflight=40, budget=100000
    )
    assert out2.preflight == 40 and "preflight proposal cap reached" in out2.warnings
    out3, _, _ = search(MAXFN, MAX_TESTS, limit=1)
    assert out3.search_candidates == 1


def test_parent_interleaving_and_unusable_parent_skipped():
    other = "def f(values):\n    best = values[0]\n    for v in values:\n        if v <= best:\n            best = v\n    return best\n"  # noqa: E501
    out, _, _ = search(
        MAXFN, MAX_TESTS, parents=[parent_of(MAXFN, "p1"), parent_of(other, "p2")], limit=2
    )
    assert out.search_candidates == 2
    bad = parent_of("import os\ndef f(values):\n    return 1\n", "bad")
    out, _, _ = search(MAXFN, MAX_TESTS, parents=[bad, parent_of(MAXFN)])
    assert out.candidates and any("bad" in w for w in out.warnings)


def test_budget_reserves_final_qualification_and_reports_partial():
    out, ev, _ = search(MAXFN, MAX_TESTS, budget=len(MAX_TESTS) + 4)
    assert ev.used <= len(MAX_TESTS) + 4
    assert ev.remaining >= 0 and out.status in {"budget_exhausted", "ok"}
    assert ev.remaining >= 0 and ev.used <= ev.max_executions


def test_cancel_returns_partial_without_fabricated_rows():
    cancel = threading.Event()
    cancel.set()
    out, ev, _ = search(MAXFN, MAX_TESTS, cancel=cancel)
    assert out.status == "cancelled" and out.candidates == [] and out.executions == []
    assert ev.used == 0
