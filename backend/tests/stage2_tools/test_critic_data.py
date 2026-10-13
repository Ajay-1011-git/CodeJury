"""Trusted CPU fixtures verify guards; never native training evidence."""

import copy
import json
from threading import Event

import pytest
from stage2_core.test_candidates import fixture
from stage2_core.test_controller import controller, run

from codejury.stage2_core.contracts import checked
from codejury.stage2_core.controller import records
from codejury.stage2_core.controller.bootstrap import critic_input_prompt, reviewed_proposal
from codejury.stage2_core.controller.inputs import runtime_input, training_input
from codejury.stage2_tools.critic_training.data import assess, authorized_failure, rejoin
from codejury.stage2_tools.critic_training.evaluate import scope


def test_reviewed_bootstrap_is_not_a_fabricated_model_response(tmp_path):
    control = controller(tmp_path)
    control.critic_bootstrap = "reviewed"
    result = run(control)
    assert result["status"] == "supported_patch"
    assert all(r["role"] != "raw" for r in control.model.requests)
    modes = records(control.ledger, result["run_id"], "critic_mode")
    assert modes and all(r["mode"] == "reviewed_bootstrap" for r in modes)


def test_no_objection_is_a_legal_observation_not_authority():
    problem = fixture("problem")
    target = reviewed_proposal(problem, ["a"], "challenge_agreement", 17, observation=True)
    checked(target, "CriticDraft")
    assert target["oracle_spec"]["kind"] == "observation"
    assert target["generator_spec"] is not None and target["concrete_inputs"] is None
    assert "No authorized failure" in target["rationale"]


def test_proposed_tests_do_not_count_as_authorized_failure():
    test = fixture("snapshot-running")["tests"][0]
    result = {"tests": [test], "executions": [{"test_id": test["test_id"], "outcome": "fail"}]}
    test.update(domain_valid=True, oracle_status="proposed")
    assert not authorized_failure(result)
    test["oracle_status"] = "authoritative"
    assert authorized_failure(result)
    test["domain_valid"] = False
    assert not authorized_failure(result)


def test_fixture_episodes_cannot_become_real_critic_data(tmp_path):
    control = controller(tmp_path)
    result = run(control)
    with pytest.raises(ValueError, match="native/Docker"):
        rejoin(control.ledger, result["run_id"], {}, {})


def test_scope_rejects_unknown_ids_wrong_mode_and_null_sources():
    target = reviewed_proposal(fixture("problem"), ["a"], "audit_gap", 17)
    row = {"mode": "audit_gap", "target": target}
    assert scope(target, row) == target
    for change in (
        {"target_candidate_ids": ["b"]},
        {"requirement_ids": ["unknown"]},
        {"mode": "discriminate"},
        {"generator_spec": None},
    ):
        with pytest.raises(ValueError):
            scope({**target, **change}, row)


def test_prompt_uses_only_runtime_facts_and_discloses_bounds():
    episode = fixture("episode-bundle")
    prompt = critic_input_prompt(
        episode["problem"],
        episode["tests"],
        episode["candidates"],
        episode["executions"],
        "audit_gap",
        17,
        gaps=episode["audit_gaps"],
    )
    assert "assessment_tests" not in prompt and "correct_source" not in prompt
    assert "Omitted execution summaries:" in prompt


def test_learning_inputs_and_private_assessment_refuse_final():
    row = {"split": "final_assessment"}
    with pytest.raises(ValueError):
        runtime_input(row)
    with pytest.raises(ValueError):
        training_input({"split": "validation"})
    with pytest.raises(ValueError, match="Final assessment"):
        assess({}, [], row, None, Event())


def test_observation_uses_frozen_approved_ids_without_mutating_problem():
    problem = fixture("problem")
    before = copy.deepcopy(problem)
    target = reviewed_proposal(problem, ["a"], "discriminate", 23)
    assert set(target["requirement_ids"]) <= {r["requirement_id"] for r in problem["requirements"]}
    assert json.dumps(before, sort_keys=True) == json.dumps(problem, sort_keys=True)
