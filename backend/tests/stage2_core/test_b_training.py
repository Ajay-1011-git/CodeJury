"""Synthetic failure-weighting controls, explicitly excluded from native training."""

import copy
import json

import pytest

from codejury.stage2_core.contract_check import REPO_ROOT
from codejury.stage2_core.training.fixer_b import SEEDS, failure_fractions, sampling_plan


def samples():
    response = json.loads((REPO_ROOT / "contracts/stage2-fixtures/model-response.json").read_text())
    response.update(role="fixer_a", adapter_hash="a" * 64, model_config_hash="b" * 64)
    return [
        {
            "runtime_mode": "fixture",
            "split": "train",
            "base_problem_id": "base",
            "seed": seed,
            "response": copy.deepcopy(response),
            "solved": index == 0,
            "infrastructure_error": False,
            "answer_hash": "c" * 64,
        }
        for index, seed in enumerate(SEEDS)
    ]


def measure(rows):
    return failure_fractions(
        rows, adapter_hash="a" * 64, model_config_hash="b" * 64, runtime_mode="fixture"
    )


def test_actual_failure_fraction_not_disagreement():
    result = measure(samples())
    assert result["fractions"]["base"] == pytest.approx(2 / 3)
    assert not result["retry_base_ids"]


def test_infrastructure_is_not_a_student_failure():
    rows = samples()
    rows[1]["infrastructure_error"] = True
    result = measure(rows)
    assert result["fractions"] == {} and result["retry_base_ids"] == ["base"]


@pytest.mark.parametrize("mutation", ["validation", "duplicate", "missing", "adapter", "seed"])
def test_bad_measurement_provenance_rejected(mutation):
    rows = samples()
    if mutation == "validation":
        rows[0]["split"] = "validation"
    elif mutation == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "missing":
        rows.pop()
    elif mutation == "adapter":
        rows[0]["response"]["adapter_hash"] = "d" * 64
    else:
        rows[0]["seed"] = True
    with pytest.raises(ValueError):
        measure(rows)


def test_fixtures_never_become_a_native_learning_plan():
    with pytest.raises(ValueError, match="fixture"):
        sampling_plan([], measure(samples()))


@pytest.mark.parametrize("alpha,broad", [(3, 0.25), (2, 0.1), (2, 0.75)])
def test_sampling_controls_cannot_silently_change(alpha, broad):
    with pytest.raises(ValueError):
        sampling_plan([], measure(samples()), alpha=alpha, broad_fraction=broad)


@pytest.mark.parametrize("alpha", [0, 1, 2, 4])
def test_sampling_is_reproducible_and_b_view_excludes_buggy_body(alpha):
    # Pure sampler unit test. This plan is never exported or used as measured evidence.
    row = {
        "record_id": "unit-row",
        "base_problem_id": "base",
        "family_id": "unit-family",
        "split": "train",
        "provenance": {"license": "CPU fixture"},
        "contract": "Sum integers",
        "domain": [
            {"kind": "list_integer", "min": -10, "max": 10, "min_length": 0, "max_length": 8}
        ],
        "buggy_source": "def solve(values):\n    return 0\n# BUG_AND_A_BODY_SENTINEL\n",
        "correct_source": "def solve(values):\n    return sum(values)\n",
        "visible_tests": [{"test_id": "v", "args": [[2]], "expected": 2}],
        "response_target": {
            "source": "def solve(values):\n    return sum(values)\n",
            "diagnosis": "Repair",
            "assumptions": [],
        },
    }
    modeled = {**measure(samples()), "runtime_mode": "live"}
    first = sampling_plan([row], modeled, alpha=alpha, size=5)
    assert first == sampling_plan([row], modeled, alpha=alpha, size=5)
    assert first["weights"]["base"] == pytest.approx(1 + alpha * 2 / 3)
    assert 0.25 <= first["actual_broad_fraction"] <= 0.5
    assert all("BUG_AND_A_BODY_SENTINEL" not in p["b_prompt"] for p in first["plan"])
    assert first["training_started"] is False


def test_pair_metrics_measure_rescue_not_disagreement():
    from codejury.stage2_core.training.fixer_b.evaluate import paired

    rows = []
    for index, (a, b) in enumerate([(True, True), (True, False), (False, True), (False, False)]):
        for role, solved in (("fixer_a", a), ("fixer_b", b)):
            rows.append(
                {
                    "record_id": str(index),
                    "role": role,
                    "solved": solved,
                    "incorrect_accepted": False,
                    "malformed": False,
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                }
            )
    summary = paired(rows)
    assert summary["a_solved"] == summary["b_solved"] == 2
    assert summary["union_solved"] == 3 and summary["joint_failures"] == 1
    assert summary["rescued_a_failures"] == summary["overlap_solved"] == 1
    assert summary["rescue_rate"] == 0.5
    with pytest.raises(ValueError, match="Complete"):
        paired(rows[:-1])
    with pytest.raises(ValueError, match="Duplicate"):
        paired(rows + [rows[0]])


def test_chat_export_uses_only_the_frozen_prompt_and_target():
    from codejury.stage2_core.training.fixer_b.train import chats

    target = json.loads((REPO_ROOT / "contracts/stage2-fixtures/repair-draft.json").read_text())
    plan = [
        {
            "prompt": "INDEPENDENT_CONTRACT",
            "target": target,
            "b_prompt": "INDEPENDENT_CONTRACT",
            "hidden_body": "BUGGY_BODY_SENTINEL",
        }
    ]
    result = chats(plan, view="independent")
    assert result[0]["messages"][1]["content"] == "INDEPENDENT_CONTRACT"
    assert "BUGGY_BODY_SENTINEL" not in json.dumps(result)


def test_b_selection_ranks_safety_union_and_standalone_success_without_loss_reward():
    from codejury.stage2_core.training.fixer_b.select import rank

    baseline = {
        "b_incorrect_accepted": 0,
        "union_solved": 5,
        "b_solved": 3,
        "b_malformed": 0,
        "b_input_tokens": 100,
        "b_output_tokens": 200,
        "train_loss": 0.01,
    }
    rescue = {**baseline, "union_solved": 6, "train_loss": 99.0}
    harmful = {**rescue, "b_incorrect_accepted": 1}
    assert rank(rescue) < rank(baseline) < rank(harmful)


def test_adapter_handoff_split_uses_the_frozen_schema_enum():
    from codejury.stage2_core.contracts import checked

    value = json.loads((REPO_ROOT / "contracts/stage2-fixtures/artifact-manifest.json").read_text())
    value.update(kind="fixer_adapters", split="none", contains_hidden_assessment=False)
    assert checked(value, "ArtifactManifest")["split"] == "none"
