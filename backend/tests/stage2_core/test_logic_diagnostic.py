"""Incomplete comparisons and concealed tier regressions cannot promote a trial."""

import copy

import pytest

from codejury.dev_bench import SEEDS
from codejury.stage2_core.training.diagnostic import DIAGNOSTIC_IDS, paired_comparison


def records():
    return [
        {
            "method": "J-current",
            "base_problem_id": base,
            "seed": seed,
            "tier": "T2" if index < 6 else "T3",
            "outcome": "unresolved",
        }
        for index, base in enumerate(DIAGNOSTIC_IDS)
        for seed in SEEDS
    ]


def test_complete_paired_comparison_preserves_seed_denominators():
    before, after = records(), records()
    after[0]["outcome"] = "solved"
    result = paired_comparison(before, after)
    assert result["eligible_for_default"]
    assert all(row["bases"] in (6, 12) for row in result["after"])
    assert result["transitions"][0]["after"] == "solved"


@pytest.mark.parametrize("fault", ["missing", "duplicate", "extra", "method", "tier"])
def test_incomplete_or_changed_population_rejected(fault):
    before, after = records(), records()
    if fault == "missing":
        after.pop()
    elif fault == "duplicate":
        after[-1] = copy.deepcopy(after[0])
    elif fault == "extra":
        after.append({**after[0], "base_problem_id": "undeclared"})
    else:
        after[0][fault] = "B-single" if fault == "method" else "T3"
    with pytest.raises(ValueError):
        paired_comparison(before, after)


def test_aggregate_gain_cannot_hide_tier_loss_or_wrong_acceptance():
    before, after = records(), records()
    before[0]["outcome"] = "solved"
    after[18]["outcome"] = after[21]["outcome"] = "solved"
    result = paired_comparison(before, after)
    assert not result["eligible_for_default"]
    assert {"seed": 17, "tier": "T2"} in result["gate_failures"]
    after = records()
    after[0]["outcome"] = "wrong_accepted"
    assert not paired_comparison(records(), after)["eligible_for_default"]


def test_matching_but_relabelled_tiers_cannot_change_the_predeclared_population():
    before, after = records(), records()
    before[0]["tier"] = after[0]["tier"] = "T3"
    with pytest.raises(ValueError, match="predeclared tiers"):
        paired_comparison(before, after)
