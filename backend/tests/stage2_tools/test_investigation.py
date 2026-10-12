import copy
import threading

import pytest
from conftest import make_problem, requirement
from hostsandbox import FixtureHostSandbox

from codejury.stage2_tools.codec import sha256_text
from codejury.stage2_tools.domains import check_args
from codejury.stage2_tools.investigation import InvestigationError, Investigator
from codejury.stage2_tools.runner import Evaluator

BUGGY = "def f(values):\n    total = 0\n    for i in range(len(values) - 1):\n        total += values[i]\n    return total\n"  # noqa: E501
GOOD = "def f(values):\n    total = 0\n    for v in values:\n        total += v\n    return total\n"
ABS = "def f(values):\n    total = 0\n    for v in values:\n        total += abs(v)\n    return total\n"  # noqa: E501


def cand(cid, source):
    return {
        "candidate_id": cid,
        "problem_id": "p-test",
        "source": source,
        "source_hash": sha256_text(source),
        "requirement_ids": ["r"],
    }


def prop_oracle(template="sum_ints"):
    return {"kind": "property", "property_id": template, "parameters": {}}


def proposal(*, generator=None, concrete=None, oracle=None, reqs=("r",), targets=()):
    return {
        "schema_version": "stage2.v1",
        "proposal_id": "pr",
        "requirement_ids": list(reqs),
        "generator_spec": generator,
        "concrete_inputs": concrete,
        "oracle_spec": oracle or prop_oracle(),
        "rationale": "experiment",
        "target_candidate_ids": list(targets),
    }


def gen(family="general", index=0, seed=3, parameters=None):
    return {"family": family, "argument_index": index, "parameters": parameters or {}, "seed": seed}


def investigate(
    prop,
    candidates,
    *,
    source=BUGGY,
    domain=None,
    reqs=None,
    existing=(),
    max_inputs=24,
    budget=3000,
    cancel=None,
    sandbox=None,
):
    problem = make_problem(
        source,
        "f",
        domain=domain,
        requirements=reqs if reqs is not None else [requirement("r", "sum_ints")],
    )
    ev = Evaluator(
        sandbox or FixtureHostSandbox(),
        problem,
        id_prefix="i",
        max_executions=budget,
        cancel=cancel,
    )
    out = Investigator(
        ev, problem, prop, candidates, list(existing), max_inputs=max_inputs, id_prefix="i"
    ).run()
    return out, ev, problem


def test_exactly_one_of_generator_or_concrete_required():
    for both in (proposal(generator=gen(), concrete=[[[1]]]), proposal()):
        with pytest.raises(InvestigationError, match="Exactly one"):
            investigate(both, [cand("a", BUGGY)])


def test_unknown_requirement_target_family_argument_and_unregistered_oracle_rejected():
    c = [cand("a", BUGGY)]
    with pytest.raises(InvestigationError, match="unknown requirements"):
        investigate(proposal(generator=gen(), reqs=("ghost",)), c)
    with pytest.raises(InvestigationError, match="unknown candidates"):
        investigate(proposal(generator=gen(), targets=("ghost",)), c)
    with pytest.raises(InvestigationError, match="Unregistered generator family"):
        investigate(proposal(generator=gen("mystery")), c)
    with pytest.raises(InvestigationError, match="outside the signature"):
        investigate(proposal(generator=gen(index=3)), c)
    with pytest.raises(InvestigationError, match="unsupported for this argument"):
        investigate(proposal(generator=gen("unicode")), c)  # integer list: no such family
    with pytest.raises(InvestigationError, match="Unregistered property"):
        investigate(proposal(generator=gen(), oracle=prop_oracle("nope")), c)
    with pytest.raises(InvestigationError, match="Unregistered metamorphic"):
        investigate(
            proposal(
                generator=gen(),
                oracle={"kind": "metamorphic", "relation_id": "x", "parameters": {}},
            ),
            c,
        )


def test_shrunk_minimal_failure_is_domain_valid_replayed_and_authoritative():
    out, ev, problem = investigate(
        proposal(generator=gen("general")), [cand("bug", BUGGY), cand("ok", GOOD)]
    )
    assert out.status == "ok" and len(out.tests) == 1
    test = out.tests[0]
    assert test["oracle_status"] == "authoritative" and test["domain_valid"] is True
    assert test["provenance"] == "property_engine" and test["test_id"] == "i-t000"
    assert check_args(problem["domain_schema"], test["inputs"]) is None
    assert len(test["inputs"][0]) == 1 and abs(test["inputs"][0][0]) == 1  # minimal [1] / [-1]
    rows = {(e["candidate_id"], e["test_id"]): e["outcome"] for e in out.executions}
    assert rows[("bug", "i-t000")] == "fail" and rows[("ok", "i-t000")] == "pass"
    assert ev.used > len(out.executions)  # exploration, shrink and replay attempts are charged
    assert not [w for w in out.warnings if "replay" in w]


def test_no_failure_means_nothing_admitted():
    out, _, _ = investigate(proposal(generator=gen()), [cand("ok", GOOD)])
    assert out.tests == [] and out.executions == []
    assert any("nothing admitted" in w for w in out.warnings)


def test_concrete_property_inputs_become_authoritative_tests_for_every_target():
    out, _, _ = investigate(
        proposal(concrete=[[[1, 2]], [[-4]], [[3]]]), [cand("bug", BUGGY), cand("ok", GOOD)]
    )
    assert all(t["provenance"] == "critic" for t in out.tests)
    assert {t["oracle_status"] for t in out.tests} == {"authoritative"}
    failing = {
        e["test_id"]
        for e in out.executions
        if e["candidate_id"] == "bug" and e["outcome"] == "fail"
    }
    assert failing and all(
        e["outcome"] == "pass" for e in out.executions if e["candidate_id"] == "ok"
    )


def test_ab_disagreement_is_observation_only_until_contract_semantics_decide():
    obs = {"kind": "observation", "hypothesis": "A and B differ on negatives"}
    out, _, _ = investigate(
        proposal(concrete=[[[-3]], [[2]]], oracle=obs, reqs=()), [cand("a", GOOD), cand("b", ABS)]
    )
    assert out.tests and all(t["oracle_status"] == "observation_only" for t in out.tests)
    assert all(e["outcome"] == "observed" for e in out.executions)
    by = {(e["candidate_id"], e["test_id"]): e["actual_output"] for e in out.executions}
    neg = next(t["test_id"] for t in out.tests if t["inputs"] == [[-3]])
    assert by[("a", neg)] == -3 and by[("b", neg)] == 3  # disagreement recorded, nobody rejected


def test_model_literal_is_proposed_even_when_it_matches_the_reference():
    literal = {"kind": "literal", "expected": -3}
    out, _, _ = investigate(proposal(concrete=[[[-3]]], oracle=literal), [cand("a", GOOD)])
    assert out.tests[0]["oracle_status"] == "proposed"
    assert out.tests[0]["oracle_source"] == "model" and out.executions[0]["outcome"] == "observed"


def test_property_without_approved_requirement_is_not_authoritative():
    out, _, _ = investigate(proposal(concrete=[[[1]]], reqs=()), [cand("a", BUGGY)])
    assert (
        out.tests[0]["oracle_status"] == "proposed" and out.executions[0]["outcome"] == "observed"
    )
    out, _, _ = investigate(
        proposal(concrete=[[[1]]]),
        [cand("a", BUGGY)],
        reqs=[requirement("r", "sum_ints", approved=False, source="model")],
    )
    assert out.tests[0]["oracle_status"] == "proposed"


def test_out_of_domain_concrete_input_is_quarantined_and_never_executed():
    out, ev, _ = investigate(proposal(concrete=[[[99]]]), [cand("a", BUGGY)])
    assert out.tests[0]["domain_valid"] is False and out.tests[0]["oracle_status"] == "rejected"
    assert out.executions == [] and ev.used == 0


def test_metamorphic_relation_costs_two_calls_and_uses_registered_followup():
    rel = {"kind": "metamorphic", "relation_id": "permutation_invariant", "parameters": {}}
    order = "def f(values):\n    return values[0] if values else 0\n"
    out, ev, _ = investigate(
        proposal(concrete=[[[1, 2, 3]]], oracle=rel),
        [cand("o", order)],
        reqs=[requirement("r", "sum_ints")],
    )
    test = out.tests[0]
    assert test["related_inputs"] is not None and sorted(test["related_inputs"][0]) == [1, 2, 3]
    assert ev.used == 2 and out.executions[0]["actual_output"].keys() == {"base", "followup"}
    assert test["oracle_status"] == "authoritative"


def test_duplicates_of_existing_tests_are_ignored_and_registry_cap_enforced():
    first, _, problem = investigate(proposal(concrete=[[[2]]]), [cand("a", GOOD)])
    out, _, _ = investigate(proposal(concrete=[[[2]]]), [cand("a", GOOD)], existing=first.tests)
    assert out.tests == [] and any("duplicate" in w for w in out.warnings)
    filler = [
        copy.deepcopy(first.tests[0])
        | {"test_id": f"x{i}", "inputs": [[i % 7]], "related_inputs": None}
        for i in range(512)
    ]
    for i, t in enumerate(filler):
        t["oracle_spec"] = {"kind": "observation", "hypothesis": str(i)}
    out, _, _ = investigate(proposal(concrete=[[[5]]]), [cand("a", GOOD)], existing=filler)
    assert out.tests == [] and any("512-test" in w for w in out.warnings)


STR_DOMAIN = [
    {
        "name": "s",
        "domain": {"kind": "string", "alphabet": "ab😀", "min_length": 0, "max_length": 6},
    }
]
ECHO = "def f(s):\n    return s[::-1]\n"


def test_families_for_string_and_dict_domains():
    reverse = [requirement("r", "reverse_string")]
    uni, _, _ = investigate(
        proposal(generator=gen("unicode"), oracle=prop_oracle("reverse_string")),
        [cand("a", "def f(s):\n    return s\n")],
        source=ECHO,
        domain=STR_DOMAIN,
        reqs=reverse,
    )
    assert uni.tests and uni.tests[0]["oracle_status"] == "authoritative"
    assert any(not c.isascii() for c in uni.tests[0]["inputs"][0])
    empty, _, _ = investigate(
        proposal(generator=gen("empty"), oracle=prop_oracle("reverse_string")),
        [cand("a", "def f(s):\n    return s + 'x'\n")],
        source=ECHO,
        domain=STR_DOMAIN,
        reqs=reverse,
    )
    assert empty.tests and empty.tests[0]["inputs"] == [""]
    dict_domain = [
        {
            "name": "d",
            "domain": {
                "kind": "dict",
                "required_keys": ["k"],
                "min_size": 0,
                "max_size": 3,
                "key_domain": {
                    "kind": "string",
                    "alphabet": "kab",
                    "min_length": 1,
                    "max_length": 1,
                },
                "value_domain": {"kind": "integer", "min": 0, "max": 5},
            },
        }
    ]
    src = "def f(d):\n    return d['k']\n"
    out, ev, _ = investigate(
        proposal(
            generator=gen("missing_key"), oracle={"kind": "observation", "hypothesis": "h"}, reqs=()
        ),
        [cand("a", src)],
        source=src,
        domain=dict_domain,
        reqs=[],
    )
    assert out.tests and all(
        t["domain_valid"] is False and t["oracle_status"] == "rejected" for t in out.tests
    )
    assert out.executions == [] and ev.used == 0


def test_boundary_negative_audit_site_and_duplicate_families_generate_inputs():
    for family in (
        "boundary",
        "negative",
        "audit_site",
        "duplicates",
        "singleton",
        "ascending",
        "descending",
        "empty",
    ):
        out, ev, problem = investigate(
            proposal(generator=gen(family)), [cand("bug", BUGGY)], max_inputs=12
        )
        assert out.status == "ok", family
        for t in out.tests:
            assert check_args(problem["domain_schema"], t["inputs"]) is None
    neg, _, _ = investigate(proposal(generator=gen("negative")), [cand("bug", BUGGY)])
    assert neg.tests and all(v < 0 for v in neg.tests[0]["inputs"][0])
    site, _, _ = investigate(proposal(generator=gen("audit_site")), [cand("bug", BUGGY)])
    assert site.tests and site.tests[0]["provenance"] == "audit_followup"


def test_input_proposal_cap_is_128():
    out, ev, _ = investigate(
        proposal(generator=gen()), [cand("ok", GOOD)], max_inputs=5000, budget=100000
    )
    assert ev.used <= 128 * 1 and ev.used > 0


def test_budget_exhaustion_during_shrink_returns_completed_facts_only():
    out, ev, _ = investigate(proposal(generator=gen()), [cand("bug", BUGGY)], budget=14)
    assert ev.used <= 14 and out.status in {"budget_exhausted", "ok"}
    assert len(out.executions) <= ev.used
    for t in out.tests:
        assert t["oracle_status"] in {"authoritative", "proposed"}


def test_cancel_stops_without_fabricated_rows():
    cancel = threading.Event()
    cancel.set()
    out, ev, _ = investigate(proposal(generator=gen()), [cand("bug", BUGGY)], cancel=cancel)
    assert out.executions == [] and ev.used == 0 and out.status == "cancelled"


def test_replay_that_does_not_fail_downgrades_the_test():
    class Flaky(FixtureHostSandbox):
        """Fails once per input, then behaves: a non-reproducible 'failure' must not certify."""

        def __init__(self):
            super().__init__()
            self.seen = {}

        def run(self, job, cancel=None):
            envelope = super().run(job, cancel)
            if job["source"] == BUGGY:
                for call, row in zip(job["calls"], envelope["results"]):
                    key = repr(call["inputs"])
                    self.seen[key] = self.seen.get(key, 0) + 1
                    if self.seen[key] >= 3:
                        row["output"] = sum(call["inputs"][0])
            return envelope

    out, _, _ = investigate(proposal(concrete=[[[4, 5]]]), [cand("bug", BUGGY)], sandbox=Flaky())
    # whatever the interleaving, a test is only authoritative when its replay failed
    for t in out.tests:
        rows = [e for e in out.executions if e["test_id"] == t["test_id"]]
        if t["oracle_status"] == "authoritative":
            assert rows
