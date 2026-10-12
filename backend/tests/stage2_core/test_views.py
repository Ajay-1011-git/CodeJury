"""Sentinel and fact-preservation checks; no code or native model is executed."""

import copy
import json

import pytest
from jsonschema import ValidationError

from codejury.stage2_core.contract_check import REPO_ROOT
from codejury.stage2_core.intake import prepare
from codejury.stage2_core.views import critic, evidence, freeze_initial, judge, revision


def fixture(name):
    return json.loads((REPO_ROOT / f"contracts/stage2-fixtures/{name}.json").read_text())


def test_controller_ids_and_interfaces_preserve_user_values():
    create = fixture("run-create-helper")
    problem, tests = prepare(create)
    assert problem["signature"] == "gcd_values(values)"
    assert tests[0]["test_id"] != create["supplied_tests"][0]["test_id"]
    assert tests[0]["inputs"] == create["supplied_tests"][0]["inputs"]
    assert tests[0]["oracle_spec"]["expected"] == 6
    assert prepare(create)[0]["problem_id"] != problem["problem_id"]


def test_b_never_receives_buggy_or_helper_bodies_and_is_frozen():
    create = fixture("run-create-helper")
    create["source"] += "\n# BUG_BODY_SENTINEL HELPER_BODY_SENTINEL\n"
    problem, tests = prepare(create)
    views = freeze_initial(problem, tests)
    assert "BUG_BODY_SENTINEL" in views.a
    assert "HELPER_BODY_SENTINEL" not in views.b
    assert "return gcd" not in views.b and "result = 1" not in views.b
    assert "pair_gcd(a, b)" in views.b and "gcd(0,0)=0" in views.b
    problem["source"] = "changed"
    tests[0]["inputs"][0][0] = 100
    assert "changed" not in views.b and "[12,18]" in views.b


@pytest.mark.parametrize("field", ["hidden_reference", "assessment_tests", "a_diagnosis"])
def test_hidden_fields_fail_closed_at_all_problem_views(field):
    problem = fixture("problem")
    problem[field] = "HIDDEN_SENTINEL"
    with pytest.raises(ValidationError):
        freeze_initial(problem, [])
    with pytest.raises(ValidationError):
        critic(problem, [], [], [])


def test_b_excludes_a_trace_but_a_has_original_evidence():
    row = fixture("tool-evaluate-result")["executions"][0]
    row["actual_output"] = "A_TRACE_SENTINEL"
    views = freeze_initial(fixture("problem"), [], original_evidence=[row])
    assert "A_TRACE_SENTINEL" in views.a and "A_TRACE_SENTINEL" not in views.b
    row["hidden_reference"] = "HIDDEN"
    with pytest.raises(ValidationError):
        freeze_initial(fixture("problem"), [], original_evidence=[row])


@pytest.mark.parametrize("mutation", ["helper", "domain", "duplicate", "default", "class"])
def test_invalid_interfaces_rejected_without_execution(mutation):
    create = fixture("run-create-helper")
    if mutation == "helper":
        create["helper_interfaces"] = []
    elif mutation == "domain":
        create["domain_schema"][0]["name"] = "wrong"
    elif mutation == "duplicate":
        create["source"] += "\ndef gcd_values(values):\n    return 0\n"
    elif mutation == "default":
        create["source"] = create["source"].replace("values):", "values=evil()):")
    else:
        create["source"] += "\nclass Evil: pass\n"
    with pytest.raises(ValueError):
        prepare(create)


def test_revision_contains_exact_observations_and_registered_oracle():
    snapshot = fixture("snapshot-running")
    candidate = next(c for c in snapshot["candidates"] if c["candidate_id"] == "c-a")
    row = copy.deepcopy(fixture("tool-evaluate-result")["executions"][0])
    row["actual_output"] = 99
    row["outcome"] = "fail"
    row["trace_ref"] = "a" * 64
    text = revision(
        "fixer_a",
        snapshot["problem"],
        snapshot["tests"],
        candidate,
        [row],
        trace_reader=lambda _: b"OBSERVED_TRACE",
    )
    assert '"actual_output":99' in text and '"expected":5' in text
    assert "OBSERVED_TRACE" in text and '"expected":99' not in text
    with pytest.raises(ValueError, match="parent"):
        revision(
            "fixer_a",
            snapshot["problem"],
            snapshot["tests"],
            candidate,
            [{**row, "candidate_id": "stale"}],
        )


def test_judge_state_has_no_original_or_candidate_bodies():
    snapshot = fixture("snapshot-running")
    text = judge(fixture("state-snapshot"), snapshot["tests"], snapshot["candidates"], [])
    assert "def sum_values" not in text and "state-before-gap" in text
    assert '"omitted_evidence_count":0' in text
    with pytest.raises(ValueError):
        evidence(fixture("tool-evaluate-result")["executions"], [], snapshot["candidates"])
