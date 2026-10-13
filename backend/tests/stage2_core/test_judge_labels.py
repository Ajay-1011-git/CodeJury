"""Reward/augmentation safeguards with trusted records; no real-learning claims."""

import pytest

from codejury.stage2_core.budgets import CAPS, zero_usage
from codejury.stage2_core.contracts import json_hash
from codejury.stage2_core.training.judge_labels import augment_ids, utility
from codejury.stage2_core.training.judge_labels.evaluate import menu, valid_choice
from codejury.stage2_core.views import judge

from .test_candidates import fixture


def test_identifier_augmentation_is_consistent_and_preserves_source_and_templates():
    episode = fixture("episode-bundle")
    state = episode["state"]
    option = state["available_actions"][0]
    target = {
        "state_id": state["state_id"],
        "action_option_id": option["option_id"],
        "evidence_ids": [],
        "rationale": "fixture",
    }
    before = json_hash(episode)
    augmented, draft = augment_ids(episode, target)
    assert augmented["state"]["state_id"] == draft["state_id"] != target["state_id"]
    assert draft["action_option_id"] == augmented["state"]["available_actions"][0]["option_id"]
    assert {o["option_id"] for o in augmented["state"]["available_actions"]} == {
        f"option-{i:02d}" for i in range(1, len(state["available_actions"]) + 1)
    }
    assert augmented["problem"]["source"] == episode["problem"]["source"]
    assert augmented["problem"]["requirements"][0]["property_template_id"] == "sum_ints"
    assert all(
        c["problem_id"] == augmented["problem"]["problem_id"] for c in augmented["candidates"]
    )
    assert json_hash(episode) == before


def test_utility_scores_the_selected_patch_and_future_cost_not_pool_existence():
    starting = {
        **CAPS,
        "function_executions": CAPS["function_executions"] - 128,
        "output_tokens": 9000,
        "input_tokens": 90000,
    }
    usage = {
        **zero_usage(),
        "output_tokens": 1100,
        "input_tokens": 11000,
        "function_executions": 10,
        "elapsed_ms": 1000,
    }
    correct, delta = utility(True, "supported_patch", usage, starting, CAPS)
    wrong, _ = utility(False, "supported_patch", usage, starting, CAPS)
    unresolved, _ = utility(True, "unresolved", usage, starting, CAPS)
    assert 0.9 < correct < 1 and wrong < -1 and -0.1 < unresolved < 0
    assert delta["output_tokens"] == 100 and delta["input_tokens"] == 1000
    assert delta["function_executions"] == 10


def test_judge_view_does_not_expose_stable_dataset_ids_or_opaque_source_hashes():
    episode = fixture("episode-bundle")
    prompt = judge(episode["state"], episode["tests"], episode["candidates"], [])
    assert '"problem_id"' not in prompt and '"source_hash"' not in prompt
    assert '"suite_hash"' not in prompt
    assert '"state_id"' in prompt and '"available_actions"' in prompt


def test_native_menu_validation_rejects_stale_options_and_unshown_evidence():
    episode = fixture("episode-bundle")
    state = episode["state"]
    payload = menu(judge(state, episode["tests"], episode["candidates"], []))
    target = {
        "state_id": state["state_id"],
        "action_option_id": state["available_actions"][0]["option_id"],
        "evidence_ids": [],
        "rationale": "fixture mechanics",
    }
    valid_choice(target, payload)
    for field, value in (
        ("state_id", "stale"),
        ("action_option_id", "unoffered"),
        ("evidence_ids", ["private-result"]),
    ):
        with pytest.raises(ValueError, match="unoffered action|hidden evidence"):
            valid_choice({**target, field: value}, payload)


@pytest.mark.parametrize("status", ["cancelled", "infrastructure_error", "invalid_input"])
def test_non_success_status_never_earns_correct_selection_reward(status):
    remaining = {**CAPS, "function_executions": CAPS["function_executions"] - 128}
    reward, _ = utility(True, status, zero_usage(), remaining, CAPS)
    assert reward == 0
