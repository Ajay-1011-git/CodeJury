import threading

from conftest import literal_test, make_problem
from hostsandbox import FixtureHostSandbox

import codejury.stage2_tools.auditor.engine as engine_module
from codejury.stage2_tools.auditor import AuditCache, Auditor, gap_is_stale
from codejury.stage2_tools.oracles import suite_hash
from codejury.stage2_tools.runner import Evaluator
from codejury.stage2_tools.search.operators import EditProposal, sha

POSITIVES = (
    "def f(values):\n    total = 0\n    for v in values:\n        if v > 0:\n"
    "            total += v\n    return total\n"
)
WEAK = [literal_test("a", [[2, 3]], 5), literal_test("b", [[-1]], 0)]
STRONG = WEAK + [literal_test("c", [[1]], 1)]


def audit(
    source,
    tests,
    *,
    max_mutants=24,
    remaining=48,
    budget=5000,
    cancel=None,
    cache=None,
    reqs=("r",),
    sandbox=None,
):
    problem = make_problem(source, "f")
    ev = Evaluator(
        sandbox or FixtureHostSandbox(),
        problem,
        id_prefix="a",
        max_executions=budget,
        cancel=cancel,
    )
    cand = {"candidate_id": "cand", "source": source}
    out = Auditor(
        ev,
        problem,
        cand,
        tests,
        max_mutants=max_mutants,
        suite=suite_hash(tests),
        id_prefix="a",
        episode_remaining=remaining,
        requirement_ids=list(reqs),
        cache=cache,
    ).run()
    return out, ev


def mutant_at(out, before, after, line=None):
    return next(
        m
        for m in out.mutants
        if (m["edit"]["before"], m["edit"]["after"]) == (before, after)
        and (line is None or m["edit"]["location"]["lineno"] == line)
    )


def test_weak_suite_leaves_survivor_and_followup_distinguishes_it():
    out, _ = audit(POSITIVES, WEAK)
    survivor = mutant_at(out, "0", "1", 4)  # `v > 0` -> `v > 1`
    assert survivor["outcome"] == "survived" and survivor["equivalence_status"] == "unknown"
    gap = next(g for g in out.gaps if survivor["mutant_id"] in g["mutant_ids"])
    assert gap["interpretation"] == "unresolved_test_gap" and gap["requirement_ids"] == ["r"]
    assert gap["candidate_source_hash"] == sha(POSITIVES) and gap["suite_hash"] == suite_hash(WEAK)
    assert survivor["suite_hash"] == suite_hash(WEAK) and survivor["parent_candidate_id"] == "cand"
    # an approved follow-up test kills the formerly surviving probe; the old gap is stale
    after, _ = audit(POSITIVES, STRONG)
    assert mutant_at(after, "0", "1", 4)["outcome"] == "killed"
    assert mutant_at(after, "0", "1", 4)["test_ids"] == ["c"]
    assert gap_is_stale(gap, sha(POSITIVES), suite_hash(STRONG)) is True
    assert gap_is_stale(gap, sha(POSITIVES), suite_hash(WEAK)) is False
    assert gap_is_stale(gap, sha(POSITIVES + "# revised\n"), suite_hash(WEAK)) is True


def test_equivalent_survivor_is_not_an_accusation_and_equivalence_is_only_observed():
    src = "def f(values):\n    total = 0\n    for v in values:\n        if v >= 0:\n            total += v\n    return total\n"  # noqa: E501
    out, _ = audit(src, WEAK)
    eq = mutant_at(out, "v >= 0", "v > 0")  # genuinely equivalent: adding zero changes nothing
    assert eq["outcome"] == "survived"
    # sampled agreement on observation tests is not a proof
    obs = [
        {
            **literal_test("o", [[0, 0]], 0, status="observation_only"),
            "oracle_source": "model",
            "oracle_spec": {"kind": "observation", "hypothesis": "h"},
        }
    ]
    out2, _ = audit(src, WEAK + obs)
    assert mutant_at(out2, "v >= 0", "v > 0")["equivalence_status"] == "observed_equivalent"
    assert mutant_at(out2, "0", "1", 4)["equivalence_status"] in {
        "unknown",
        "observed_equivalent",
        "observed_different",
    }
    assert all(
        set(g) >= {"interpretation"} and g["interpretation"] == "unresolved_test_gap"
        for g in out2.gaps
    )
    assert not any("candidate" in m and m.get("eligibility") for m in out2.mutants)


def test_observation_can_show_a_survivor_is_behaviourally_different():
    obs = [
        {
            **literal_test("o", [[1]], 1, status="observation_only"),
            "oracle_source": "model",
            "oracle_spec": {"kind": "observation", "hypothesis": "probe boundary"},
        }
    ]
    out, _ = audit(POSITIVES, WEAK + obs)
    survivor = mutant_at(out, "0", "1", 4)
    assert (
        survivor["outcome"] == "survived" and survivor["equivalence_status"] == "observed_different"
    )


def test_proposed_oracle_cannot_kill():
    proposed = [{**literal_test("p", [[1]], 999, status="proposed"), "oracle_source": "model"}]
    out, _ = audit(POSITIVES, proposed)
    assert out.mutants and all(m["outcome"] == "survived" for m in out.mutants)
    assert any("no authoritative tests" in w for w in out.warnings)


def test_invalid_duplicate_timeout_are_separate(monkeypatch):
    def fake(source, families=None, limit=None):
        ph = sha(source)

        def p(text, line=1):
            loc = {"lineno": line, "col_offset": 0, "end_lineno": line, "end_col_offset": 1}
            return EditProposal("comparison", loc, "x", "y", text, ph, sha(text))

        loop = "def f(values):\n    while True:\n        pass\n"
        broken = "def f(values:\n"
        dup = source.replace("v > 0", "v < 0")
        return [
            p(loop, 2),
            p(broken, 3),
            p(dup, 4),
            p(dup, 5),
            p(source.replace("total += v", "total += 2 * v"), 6),
        ]

    monkeypatch.setattr(engine_module, "enumerate_edits", fake)
    ev_sandbox = FixtureHostSandbox()
    problem = make_problem(POSITIVES, "f")
    ev = Evaluator(ev_sandbox, problem, id_prefix="a", max_executions=500, call_timeout_s=0.3)
    out = Auditor(
        ev,
        problem,
        {"candidate_id": "cand", "source": POSITIVES},
        STRONG,
        max_mutants=24,
        suite=suite_hash(STRONG),
        id_prefix="a",
    ).run()
    by_line = {m["edit"]["location"]["lineno"]: m["outcome"] for m in out.mutants}
    assert by_line[2] == "timeout" and by_line[3] == "invalid"
    assert by_line[4] == "killed" and by_line[5] == "duplicate" and by_line[6] == "killed"
    assert {m["outcome"] for m in out.mutants} == {"timeout", "invalid", "killed", "duplicate"}


def test_caps_24_per_version_and_48_per_episode():
    body = "".join(f"    x{i} = {i + 3}\n" for i in range(40))
    big = "def f(values):\n" + body + "    return sum(values)\n"
    tests = [literal_test("a", [[1, 2]], 3)]
    out, _ = audit(big, tests, max_mutants=40)
    assert len(out.mutants) == 24
    out, _ = audit(big, tests, max_mutants=24, remaining=5)
    assert len(out.mutants) == 5
    out, ev = audit(big, tests, remaining=0)
    assert out.mutants == [] and out.status == "budget_exhausted" and ev.used == 0
    out, _ = audit(big, tests, max_mutants=24)
    assert "96-proposal preflight cap reached" in out.warnings


def test_families_are_diversified_in_a_small_probe_budget():
    out, _ = audit(POSITIVES, WEAK, max_mutants=4)
    assert len({m["edit"]["operator_family"] for m in out.mutants}) >= 3


def test_hash_keyed_cache_reuses_without_new_executions():
    cache = AuditCache()
    first, ev1 = audit(POSITIVES, WEAK, cache=cache)
    second, ev2 = audit(POSITIVES, WEAK, cache=cache)
    assert ev1.used > 0 and ev2.used == 0
    assert [m["outcome"] for m in first.mutants] == [m["outcome"] for m in second.mutants]
    new_suite, ev3 = audit(POSITIVES, STRONG, cache=cache)  # a new suite never reuses stale rows
    assert ev3.used > 0


def test_budget_exhaustion_and_cancel_return_only_completed_probes():
    out, ev = audit(POSITIVES, WEAK, budget=3)
    assert len(out.mutants) < 24 and out.status == "budget_exhausted" and ev.used <= 3
    cancel = threading.Event()
    cancel.set()
    out, ev = audit(POSITIVES, WEAK, cancel=cancel)
    assert out.mutants == [] and out.status == "cancelled" and ev.used == 0


def test_gap_requirement_mapping_is_empty_with_warning_when_unjustified():
    out, _ = audit(POSITIVES, WEAK, reqs=())
    assert out.gaps and all(g["requirement_ids"] == [] for g in out.gaps)
    assert any("no reviewed requirement mapping" in w for w in out.warnings)


def test_gaps_group_by_location_and_family_and_validate_against_schema():
    from codejury.stage2_tools.codec import validate

    out, _ = audit(POSITIVES, WEAK)
    keys = [
        (g["location"]["lineno"], g["location"]["col_offset"], g["operator_family"])
        for g in out.gaps
    ]
    assert len(keys) == len(set(keys))
    for g in out.gaps:
        validate(g, "AuditGap")
    for m in out.mutants:
        validate(m, "ProbeMutant")
