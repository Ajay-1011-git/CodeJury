import copy

import pytest
from conftest import int_list, literal_test, make_problem, requirement

from codejury.stage2_tools.oracles import (
    METAMORPHIC,
    TEMPLATES,
    OracleError,
    admit_test,
    build_supplied_tests,
    check_intake,
    expected_output,
    judge,
    oracle_version,
    registry_hash,
    relation_followup,
    suite_hash,
    template_compatible,
)

SCHEMA = [{"name": "values", "domain": int_list()}]
SRC = "def f(values):\n    return sorted(values)\n"


def run_create(tests, reqs, schema=None):
    return {"domain_schema": schema or SCHEMA, "requirements": reqs,
            "supplied_tests": [
                {"schema_version": "stage2.v1", "test_id": i, "inputs": a, "expected": e,
                 "requirement_ids": r} for i, a, e, r in tests]}  # fmt: skip


def test_five_templates_semantics():
    assert expected_output("sort_ascending_ints", [[3, 1, 3, -2]]) == [-2, 1, 3, 3]  # multiplicity
    assert expected_output("unique_preserve_order_ints", [[3, 1, 3, 2, 1]]) == [3, 1, 2]
    assert expected_output("sum_ints", [[-4, 1, 2]]) == -1
    assert expected_output("reverse_string", ["ab😀"]) == "😀ba"
    assert expected_output("count_occurrences_ints", [[1, 2, 1, 1], 1]) == 3
    assert expected_output("count_occurrences_ints", [[0, 5], 1]) == 0
    original = [3, 1]
    expected_output("sort_ascending_ints", [original])
    assert original == [3, 1]  # the reference never mutates its input


def test_judge_property_checks_order_and_multiplicity_and_type():
    t = {"oracle_status": "authoritative", "inputs": [[2, 1, 2]],
         "oracle_spec": {"kind": "property", "property_id": "sort_ascending_ints", "parameters": {}}}  # fmt: skip
    assert judge(t, [[1, 2, 2]]) == "pass"
    assert judge(t, [[1, 2]]) == "fail"  # lost a duplicate
    assert judge(t, [[2, 1, 2]]) == "fail"  # wrong order
    assert judge(t, [[1, 2, True]]) == "fail"  # bool is not int
    s = {**t, "inputs": [[1]], "oracle_spec": {**t["oracle_spec"], "property_id": "sum_ints"}}
    assert judge(s, [True]) == "fail"


def test_compatibility_gates_templates():
    assert template_compatible("sum_ints", SCHEMA)
    assert not template_compatible("reverse_string", SCHEMA)
    assert not template_compatible("count_occurrences_ints", SCHEMA)
    assert not template_compatible("nope", SCHEMA)


def test_relations_registered_and_followups():
    assert set(METAMORPHIC) == {"permutation_invariant", "idempotent"}
    follow = relation_followup("permutation_invariant", [[1, 2, 3, 4]], seed=3)
    assert sorted(follow[0]) == [1, 2, 3, 4]
    assert relation_followup("idempotent", [[3, 1, 2]]) == [[1, 2, 3]]


def test_intake_rejects_conflict_with_approved_property():
    reqs = [requirement("r", "sum_ints")]
    check_intake(run_create([("a", [[1, 2]], 3, ["r"])], reqs))
    with pytest.raises(OracleError, match="contradicts approved"):
        check_intake(run_create([("a", [[1, 2]], 4, ["r"])], reqs))
    with pytest.raises(OracleError, match="contradicts approved"):
        check_intake(run_create([("a", [[1, 2]], 4, [])], reqs))  # uncited tests too


def test_intake_rejects_contradictory_literals_dupes_and_domain():
    with pytest.raises(OracleError, match="contradictory"):
        check_intake(run_create([("a", [[1]], 1, []), ("b", [[1]], 2, [])], []))
    with pytest.raises(OracleError, match="Duplicate supplied"):
        check_intake(run_create([("a", [[1]], 1, []), ("a", [[2]], 2, [])], []))
    with pytest.raises(OracleError, match="outside the domain"):
        check_intake(run_create([("a", [[99]], 1, [])], []))
    with pytest.raises(OracleError, match="unknown requirements"):
        check_intake(run_create([("a", [[1]], 1, ["ghost"])], []))


def test_intake_requirement_authority_and_template_rules():
    with pytest.raises(OracleError, match="Only user/reviewed_contract"):
        check_intake(run_create([], [requirement("r", "sum_ints", source="model")]))
    with pytest.raises(OracleError, match="incompatible"):
        check_intake(run_create([], [requirement("r", "reverse_string")]))
    with pytest.raises(OracleError, match="unregistered"):
        check_intake(run_create([], [requirement("r", "mystery")]))
    check_intake(run_create([], [requirement("r", "mystery", approved=False, source="model")]))
    bad = requirement("r", "sum_ints")
    bad["parameters"] = {"x": 1}
    with pytest.raises(OracleError, match="no parameters"):
        check_intake(run_create([], [bad]))


def test_supplied_tests_become_authoritative_literals():
    tests = build_supplied_tests(run_create([("a", [[1, 2]], 3, [])], []))
    assert tests[0]["oracle_status"] == "authoritative" and tests[0]["provenance"] == "supplied"


def prop_test(template="sum_ints", reqs=("r",), source="reviewed_contract", inputs=None):
    return {
        **literal_test("p", inputs or [[1, 2]], 0, reqs),
        "oracle_spec": {"kind": "property", "property_id": template, "parameters": {}},
        "oracle_source": source,
        "provenance": "property_engine",
    }


def test_admission_property_literal_and_observation_authority():
    problem = make_problem(SRC, "f", requirements=[requirement("r", "sum_ints")])
    assert admit_test(prop_test(), problem)["oracle_status"] == "authoritative"
    assert admit_test(prop_test(source="model"), problem)["oracle_status"] == "proposed"
    assert admit_test(prop_test(reqs=()), problem)["oracle_status"] == "proposed"  # no basis
    assert admit_test(prop_test("sort_ascending_ints"), problem)["oracle_status"] == "proposed"
    # A model literal stays proposed even if it matches the reference.
    lit = {**literal_test("m", [[1, 2]], 3, ["r"]), "oracle_source": "model",
           "provenance": "critic"}  # fmt: skip
    assert admit_test(lit, problem)["oracle_status"] == "proposed"
    obs = {**lit, "oracle_spec": {"kind": "observation", "hypothesis": "h"}}
    assert admit_test(obs, problem)["oracle_status"] == "observation_only"
    out = admit_test({**prop_test(), "inputs": [[99]]}, problem)
    assert out["domain_valid"] is False and out["oracle_status"] == "rejected"


def test_admission_metamorphic_rules():
    problem = make_problem(SRC, "f", requirements=[requirement("r", "sort_ascending_ints")])

    def meta(relation, inputs, related, reqs=("r",)):
        return {**literal_test("m", inputs, 0, reqs),
                "oracle_spec": {"kind": "metamorphic", "relation_id": relation, "parameters": {}},
                "related_inputs": related, "oracle_source": "reviewed_contract",
                "provenance": "property_engine"}  # fmt: skip

    ok = admit_test(meta("permutation_invariant", [[1, 2, 3]], [[3, 1, 2]]), problem)
    assert ok["oracle_status"] == "authoritative"
    assert admit_test(meta("idempotent", [[3, 1]], [[1, 3]]), problem)["oracle_status"] == (
        "authoritative"
    )
    with pytest.raises(OracleError, match="require related_inputs"):
        admit_test(meta("idempotent", [[3, 1]], None), problem)
    with pytest.raises(OracleError, match="do not instantiate"):
        admit_test(meta("permutation_invariant", [[1, 2]], [[1, 5]]), problem)
    with pytest.raises(OracleError, match="registered relation"):
        admit_test(meta("made_up", [[1, 2]], [[2, 1]]), problem)
    with pytest.raises(OracleError, match="Only metamorphic"):
        admit_test({**prop_test(), "related_inputs": [[1]]}, problem)
    # No approved sort/sum basis -> relation cannot reject
    weak = make_problem(SRC, "f", requirements=[requirement("r", None)])
    assert admit_test(meta("permutation_invariant", [[1, 2]], [[2, 1]]), weak)[
        "oracle_status"
    ] == "proposed"
    # idempotent is only for sorting contracts
    summing = make_problem(SRC, "f", requirements=[requirement("r", "sum_ints")])
    assert admit_test(meta("idempotent", [[3, 1]], [[1, 3]]), summing)["oracle_status"] == (
        "proposed"
    )


def test_relation_verdicts_use_two_outputs():
    t = {"oracle_status": "authoritative", "inputs": [[1, 2]],
         "oracle_spec": {"kind": "metamorphic", "relation_id": "permutation_invariant",
                         "parameters": {}}}  # fmt: skip
    assert judge(t, [3, 3]) == "pass"
    assert judge(t, [3, 2]) == "fail"
    assert judge({**t, "oracle_status": "proposed"}, [3, 2]) == "observed"


def test_oracle_versions_and_suite_hash_are_stable_and_sensitive():
    assert len(registry_hash()) == 64 and registry_hash() == registry_hash()
    spec = {"kind": "property", "property_id": "sum_ints", "parameters": {}}
    assert oracle_version(spec) == TEMPLATES["sum_ints"].version
    assert oracle_version({"kind": "property", "property_id": "zzz", "parameters": {}}) == (
        "unregistered"
    )
    a = literal_test("a", [[1]], 1)
    b = literal_test("b", [[2]], 2)
    assert suite_hash([a, b]) == suite_hash([b, a])
    changed = copy.deepcopy(a)
    changed["inputs"] = [[3]]
    assert suite_hash([a, b]) != suite_hash([changed, b])
    flipped = {**a, "oracle_status": "proposed"}
    assert suite_hash([a]) != suite_hash([flipped])


def test_registry_yaml_mirrors_executable_registry():
    from pathlib import Path

    import yaml

    from codejury.stage2_tools.domains import ALLOWLIST, BUILTIN_CALLS

    doc = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "config/stage2_tools/registry.yaml").read_text()
    )
    assert {t["id"] for t in doc["property_templates"]} == set(TEMPLATES)
    assert {r["id"]: set(r["templates"]) for r in doc["metamorphic_relations"]} == {
        k: set(v.templates) for k, v in METAMORPHIC.items()
    }
    assert set(doc["dependency_allowlist"]) == ALLOWLIST
    assert set(doc["builtin_calls"]) == BUILTIN_CALLS
