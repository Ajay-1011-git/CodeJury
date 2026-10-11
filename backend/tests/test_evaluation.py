import json

import pytest

from codejury.evaluation.stage1 import aggregate, freeze_then_assess, single
from codejury.models.worker import Generation
from codejury.runner import Result


class FixtureRunner:
    def __init__(self, answer_path=None, hidden_output=9):
        self.calls = []
        self.answer_path = answer_path
        self.hidden_output = hidden_output

    def execute(self, source, name, args):
        self.calls.append(args)
        if args == [99]:
            assert self.answer_path.exists(), "Private tests ran before final answer freeze"
            return Result(self.hidden_output, None, False, 1, [], False)
        return Result(2 if "return 2" in source else 0, None, False, 1, [], False)


class FixtureModel:
    def __init__(self, text):
        self.text = text
        self.views = []

    def generate(self, role, view, **kwargs):
        self.views.append(view)
        return Generation(self.text, 10, 20, 1, 1)


def request():
    return {
        "schema_version": "stage1.v1",
        "source": "def solve(n):\n    return 0\n",
        "function_name": "solve",
        "contract_text": "Return two.",
        "input_domain": [
            {"kind": "integer", "min": 0, "max": 100, "min_length": None, "max_length": None}
        ],
        "supplied_tests": [{"test_id": "visible", "args": [1], "expected": 2}],
        "approved_property": None,
        "resource_profile": "stage1-demo",
    }


def test_private_failure_never_revises_frozen_answer(tmp_path):
    path = tmp_path / "answer.json"
    runner = FixtureRunner(path, hidden_output=8)
    model = FixtureModel(
        json.dumps(
            {"source": "def solve(n):\n    return 2\n", "diagnosis": "Fixture", "assumptions": []}
        )
    )
    answer = single(request(), model, runner)
    assert answer["accepted"]
    assert runner.calls == [[1], [1]]
    assessed = freeze_then_assess(
        answer, request(), [{"test_id": "hidden", "args": [99], "expected": 9}], runner, path
    )
    assert assessed["incorrect_accepted"] and not assessed["solved"]
    assert len(model.views) == 1
    assert "[99]" not in json.dumps(model.views)
    assert json.loads(path.read_text()) == answer
    with pytest.raises(FileExistsError):
        freeze_then_assess(answer, request(), [], runner, path)


def test_malformed_single_is_unresolved_without_hidden_execution(tmp_path):
    model = FixtureModel("```json invalid```")
    runner = FixtureRunner(tmp_path / "answer.json")
    answer = single(request(), model, runner)
    row = freeze_then_assess(
        answer,
        request(),
        [{"test_id": "h", "args": [99], "expected": 9}],
        runner,
        tmp_path / "answer.json",
    )
    assert row["unresolved"] and row["malformed"]
    assert len(model.views) == 1  # Single means no format retry.
    assert runner.calls == [[1]]
    assert row["usage"]["output_tokens"] == 20


def test_type_sensitive_assessment(tmp_path):
    runner = FixtureRunner(tmp_path / "a.json", hidden_output=True)
    answer = {
        "accepted": True,
        "source": "def solve(n):\n    return 2\n",
        "usage": {"elapsed_ms": 1, "output_tokens": 3},
        "malformed": False,
    }
    row = freeze_then_assess(
        answer,
        request(),
        [{"test_id": "h", "args": [99], "expected": 1}],
        runner,
        tmp_path / "a.json",
    )
    assert row["incorrect_accepted"]


def test_counts_and_missing_measurements():
    rows = [
        {
            "solved": True,
            "unresolved": False,
            "incorrect_accepted": False,
            "usage": {"elapsed_ms": 10, "output_tokens": 30},
        },
        {
            "solved": False,
            "unresolved": False,
            "incorrect_accepted": True,
            "usage": {"elapsed_ms": 20, "output_tokens": 40},
        },
        {
            "solved": False,
            "unresolved": True,
            "incorrect_accepted": False,
            "usage": {"elapsed_ms": 30, "output_tokens": 50},
        },
    ]
    result = aggregate("trained_a_single", rows)
    assert result == {
        "method": "trained_a_single",
        "total": 3,
        "solved": 1,
        "unresolved": 1,
        "incorrect_accepted": 1,
        "mean_elapsed_ms": 20,
        "mean_output_tokens": 40,
    }
    empty = aggregate("raw_single", [])
    assert empty["mean_elapsed_ms"] is None and empty["mean_output_tokens"] is None


def test_runtime_serves_only_public_aggregate_and_checks_counts(tmp_path):
    from codejury.api.training_report import load_report, not_started

    report = not_started()
    report.update(status="pilot_only", steps=10, adapter_sha256="a" * 64, train_base_problems=40)
    path = tmp_path / "public.json"
    path.write_text(json.dumps(report))
    assert load_report(path=path)["status"] == "pilot_only"
    assert load_report("fixture", path)["status"] == "not_started"
    report["status"] = "completed"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError):
        load_report(path=path)
    report.update(
        evaluation_base_problems=3,
        evaluation=[
            aggregate(
                method,
                [
                    {
                        "solved": True,
                        "unresolved": False,
                        "incorrect_accepted": False,
                        "usage": {"elapsed_ms": 1, "output_tokens": 1},
                    }
                    for _ in range(3)
                ],
            )
            for method in ["raw_single", "trained_a_single", "stage1_loop"]
        ],
    )
    path.write_text(json.dumps(report))
    assert load_report(path=path)["status"] == "completed"
    report["evaluation"][0]["total"] = 4
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError):
        load_report(path=path)
