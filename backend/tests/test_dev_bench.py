"Benchmark boundaries and failure classification; no models/cloud/downloads."

import copy
import json

import pytest

from codejury.dev_bench import (
    ROOT,
    execute_tests,
    load_runtime,
    load_scoring,
    passes,
    summarize,
    wilson,
)
from codejury.dev_bench.runner import categorize, score_records
from codejury.stage2_core.intake import prepare
from codejury.stage2_core.views import freeze_initial
from codejury.training.data import assert_disjoint


def test_benchmark_population_and_prompt_boundaries():
    rows, scoring = load_runtime(), load_scoring()
    assert len(rows) == len(scoring) == 100
    assert {r["base_problem_id"] for r in rows} == scoring.keys()
    assert all(r["provenance"]["kind"] == "independently_authored" for r in rows)
    for row in rows:
        problem, tests = prepare(row["run_create"])
        views = freeze_initial(problem, tests)
        private = scoring[row["base_problem_id"]]
        assert private["correct_source"] not in views.a
        assert "buggy_source" not in views.b
        assert "hidden_tests" not in views.a + views.b
        assert "correct_source" not in views.a + views.b
        assert len(tests) == 2 and len(private["hidden_tests"]) >= 3
        assert {t["test_id"] for t in private["hidden_tests"]}.isdisjoint(
            {t["test_id"] for t in row["run_create"]["supplied_tests"]}
        )


def test_runtime_reader_rejects_added_scoring_field(tmp_path):
    row = copy.deepcopy(load_runtime()[0])
    row["hidden_tests"] = []
    (tmp_path / "runtime.jsonl").write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="scoring fields"):
        load_runtime(tmp_path)


def test_split_identity_check_uses_names_families_and_normalized_sources():
    base = {
        "base_problem_id": "one",
        "family_id": "family",
        "split": "train",
        "correct_source": "def solve(x):\n    return x + 1\n",
    }
    other = {
        "base_problem_id": "two",
        "family_id": "other",
        "split": "development_benchmark",
        "correct_source": "def solve(value):\n    return value * 2\n",
    }
    assert_disjoint([base, other], identity_only=True)
    for key in ("base_problem_id", "family_id"):
        with pytest.raises(ValueError, match="leaks"):
            assert_disjoint([base, {**other, key: base[key]}], identity_only=True)
    with pytest.raises(ValueError, match="leaks"):
        assert_disjoint(
            [base, {**other, "correct_source": "def solve(z):\n    return z + 1\n"}],
            identity_only=True,
        )
    with pytest.raises(ValueError, match="missing required"):
        assert_disjoint([base])


def test_wilson_and_independent_seed_denominators():
    assert wilson(0, 0) is None
    assert wilson(0, 10)[1] == pytest.approx(0.2775328)
    assert wilson(10, 10)[0] == pytest.approx(0.7224672)
    rows = [
        {
            "method": "J-current",
            "seed": seed,
            "tier": "T2",
            "base_problem_id": str(i),
            "outcome": "solved" if i == 0 else "unresolved",
        }
        for seed in (17, 29, 43)
        for i in range(4)
    ]
    stats = summarize(rows)
    assert all(r["bases"] == 4 for r in stats)
    assert all(r["solve_rate"] == 0.25 for r in stats)
    with pytest.raises(ValueError, match="Repeated base"):
        summarize(rows + [rows[0]])


def test_scoring_type_sensitive_purity_and_status():
    result = {
        "status": "ok",
        "mutated": False,
        "before_hash": "a" * 64,
        "after_hash": "a" * 64,
        "output": 1,
    }
    assert passes(result, {"expected": 1})
    assert not passes(result, {"expected": True})
    assert not passes({**result, "mutated": True}, {"expected": 1})
    assert not passes({**result, "status": "timeout"}, {"expected": 1})
    assert not passes({**result, "after_hash": "b" * 64}, {"expected": 1})


def test_outcomes_keep_bad_predictions_distinct_from_acceptance():
    record = {
        "error_type": None,
        "status": "supported_patch",
        "selected_source": "source",
        "unverified_prediction": False,
        "output_validity": {},
    }
    assert categorize(record, True) == "solved"
    assert categorize(record, False) == "wrong_accepted"
    assert categorize({**record, "unverified_prediction": True}, False) == "unresolved"
    assert categorize({**record, "status": "infrastructure_error"}, True) == "infrastructure"
    assert categorize({**record, "status": "invalid_input"}, None) == "invalid"
    assert (
        categorize({**record, "status": "cancelled", "selected_source": None}, None) == "unresolved"
    )
    assert (
        categorize(
            {
                **record,
                "status": "unresolved",
                "selected_source": None,
                "output_validity": {"fixer_a": {"calls": 2, "malformed": 2}},
            },
            None,
        )
        == "invalid"
    )


class Sandbox:
    """Returns fixtures only; does not execute source on the host."""

    limits = {"chunk_calls": 2}

    def __init__(self):
        self.jobs = []

    def run(self, job, cancel):
        self.jobs.append(job)
        return {
            "results": [
                {
                    "status": "ok",
                    "output": 6,
                    "exception": None,
                    "before_hash": "a" * 64,
                    "after_hash": "a" * 64,
                    "mutated": False,
                    "duration_ms": 0,
                }
                for _ in job["calls"]
            ]
        }


def test_scoring_expectations_are_not_sent_to_candidate():
    row = load_runtime()[0]
    private = load_scoring()[row["base_problem_id"]]
    sandbox = Sandbox()
    result = execute_tests(
        sandbox, private["correct_source"], row["run_create"], private["hidden_tests"]
    )
    assert len(result) == len(private["hidden_tests"])
    assert len(sandbox.jobs) == 2
    for job in sandbox.jobs:
        assert set(job) == {"source", "function_name", "allowed_imports", "calls"}
        assert all(set(call) == {"inputs", "trace_lines"} for call in job["calls"])
        assert "expected" not in json.dumps(job)


def test_only_selected_source_is_scored():
    row = load_runtime()[0]
    sandbox = Sandbox()
    record = {
        "base_problem_id": row["base_problem_id"],
        "selected_source": None,
        "unverified_prediction": False,
        "error_type": None,
        "status": "unresolved",
        "output_validity": {},
        "candidate_pool": [{"source": "never execute"}],
    }
    results = list(score_records([record], [row], load_scoring(), sandbox))
    assert results[0]["outcome"] == "unresolved"
    assert results[0]["hidden_correct"] is None
    assert sandbox.jobs == []


def test_catalogue_is_absent_from_runtime_reader():
    import codejury.dev_bench as module

    assert "catalog" not in module.__dict__
    assert (ROOT / "private/scoring.jsonl").is_file()


def test_best_of_n_uses_eight_blind_attempts_without_revision_or_critic(tmp_path):
    from stage2_core.test_controller import ScriptedModel, controller, run

    from codejury.dev_bench.runner import BestOfN

    model = ScriptedModel()
    control = controller(tmp_path, model=model, cls=BestOfN)
    result = run(control)
    assert result["status"] == "supported_patch"
    assert len(model.requests) == 8
    assert {r["role"] for r in model.requests} == {"fixer_a"}
    assert {r["purpose"] for r in model.requests} == {"repair"}
    assert len({r["prompt"] for r in model.requests}) == 1
    assert [a["kind"] for a in result["actions"]] == ["select"]
    assert result["resource_usage"]["learned_candidates"] == 8


def test_best_of_n_counts_malformed_attempts_against_the_same_cap(tmp_path):
    from stage2_core.test_controller import ScriptedModel, controller, run

    from codejury.dev_bench.runner import BestOfN, output_validity

    class Malformed(ScriptedModel):
        def generate(self, request, cancel):
            response = super().generate(request, cancel)
            response["text"] = "{"
            return response

    model = Malformed()
    control = controller(tmp_path, model=model, cls=BestOfN)
    result = run(control)
    assert result["status"] == "unresolved"
    assert len(model.requests) == 8
    assert result["resource_usage"]["learned_candidates"] == 8
    assert output_validity(control.ledger, result["run_id"])["fixer_a"]["malformed"] == 8
