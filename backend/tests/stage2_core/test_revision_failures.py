"""Concrete repair evidence respects registered authority and unknown expectations."""

import copy
import json

from codejury.stage2_core.contract_check import REPO_ROOT
from codejury.stage2_core.views import evidence
from codejury.stage2_core.views.failures import first_failure


def row(**changes):
    return {
        "execution_id": "e-parent",
        "test_id": "t-approved",
        "inputs": [[2, -1]],
        "actual_output": 0,
        "exception": None,
        "outcome": "fail",
        "input_effects": [{"call_index": 0, "mutated": False}],
        "oracle_status": "authoritative",
        "oracle_spec": {"kind": "literal", "expected": 1},
        "related_inputs": [],
        **changes,
    }


def test_observations_never_become_repair_oracles_and_first_hard_failure_wins():
    observation = row(oracle_status="observation_only", actual_output=777)
    failure = first_failure([observation, row(), row(execution_id="later")])
    assert failure["execution_id"] == "e-parent"
    assert failure["expected"] == 1 and failure["actual"] == 0
    assert first_failure([observation, row(outcome="pass")]) is None


def test_property_failure_preserves_relation_without_inventing_expected_value():
    oracle = {"kind": "property", "property_id": "sum_ints", "parameters": {}}
    failure = first_failure([row(oracle_spec=oracle, actual_output=-99)])
    assert "expected" not in failure
    assert failure["oracle"] == oracle


def test_passing_output_with_registered_input_mutation_is_a_concrete_failure():
    failure = first_failure(
        [row(outcome="pass", actual_output=1, input_effects=[{"call_index": 0, "mutated": True}])]
    )
    assert failure["expected"] == failure["actual"] == 1
    assert failure["outcome"] == "pass"  # preserve the recorded outcome, explain the purity fault
    assert failure["failure_reasons"] == ["input_mutation"]


def test_timeout_and_mutation_failures_remain_concrete():
    failure = first_failure(
        [
            row(
                outcome="timeout",
                actual_output=None,
                exception={"type": "TimeoutError"},
                input_effects=[{"call_index": 0, "mutated": True}],
            )
        ]
    )
    assert failure["actual"] is None
    assert failure["expected"] == 1
    assert failure["input_effects"][0]["mutated"] is True


def test_projection_accepts_the_actual_joined_wire_execution_shape():
    snapshot = json.loads(
        (REPO_ROOT / "contracts/stage2-fixtures/snapshot-running.json").read_text()
    )
    execution = copy.deepcopy(snapshot["executions"][0])
    execution["outcome"] = "fail"
    rows = evidence([execution], snapshot["tests"], snapshot["candidates"])
    failure = first_failure(rows)
    assert failure["input_effects"] == execution["input_effects"]
    assert failure["expected"] == 5
