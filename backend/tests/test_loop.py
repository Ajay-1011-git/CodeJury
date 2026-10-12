"""Deterministic fixtures exercise policy only; never live model evidence."""

import copy
import json
import threading

import pytest

from codejury.api.repository import Repository
from codejury.contracts import REPO_ROOT, validate
from codejury.controller.loop import run
from codejury.models.worker import Generation
from codejury.runner import Result
from codejury.storage import Store


class FixtureModel:
    identity = {
        "model_id": "fixture",
        "model_revision": "fixture",
        "adapter_role": "fixer_a",
        "adapter_sha256": "fixture",
    }
    last_usage = {"input_tokens": 0, "output_tokens": 0, "elapsed_ms": 0, "peak_memory_mb": 0}

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, role, view, **kwargs):
        self.calls.append((role, copy.deepcopy(view), kwargs))
        return Generation(next(self.responses), 10, 20, 1, 1)


class FixtureRunner:
    def __init__(self):
        self.calls = []

    def execute_many(self, source, name, inputs, cancel=None, *, deadline=None):
        self.calls.extend((source, copy.deepcopy(args)) for args in inputs)
        results = []
        for args in inputs:
            # Explicit test-only outcomes. Submitted source is never compiled on host.
            values = args[0]
            output = (
                list(dict.fromkeys(values)) if "dict.fromkeys" in source else sorted(set(values))
            )
            results.append(Result(output, None, False, 1, [], False))
        return results


def patch(source):
    return json.dumps({"source": source, "diagnosis": "Fixture repair", "assumptions": []})


def request():
    r = json.loads((REPO_ROOT / "contracts/fixtures/run-create.json").read_text())
    # The plausible patch passes the ordered example but fails an approved order property.
    r["source"] = "def unique(values):\n    return []\n"
    return r


def execute(tmp_path, r, model, runner=None, **limits):
    store = Store(tmp_path)
    snap = Repository(store).claim(r, "fixture")
    return run(
        r, store, snap["run_id"], model=model, runner=runner or FixtureRunner(), **limits
    ), store


def test_property_counterexample_then_correct_revision(tmp_path):
    r = request()
    r["supplied_tests"] = [{"test_id": "ordered", "args": [[1, 2, 1]], "expected": [1, 2]}]
    runner = FixtureRunner()
    # Test original-specific baseline failure, without any host execution.
    original = runner.execute_many

    def batch(source, name, args, cancel=None, *, deadline=None):
        if "return []" in source:
            runner.calls.extend((source, copy.deepcopy(a)) for a in args)
            return [Result([], None, False, 1, [], False) for _ in args]
        return original(source, name, args, cancel)

    runner.execute_many = batch
    model = FixtureModel(
        [
            patch("def unique(values):\n    return sorted(set(values))\n"),
            json.dumps(
                {"property_id": r["approved_property"], "family": "descending", "reason": "Order"}
            ),
            patch("def unique(values):\n    return list(dict.fromkeys(values))\n"),
        ]
    )
    result, store = execute(tmp_path, r, model, runner)
    validate(result, "RunSnapshot")
    assert result["status"] == "supported_patch"
    assert result["candidates"][1]["eligibility"] == "rejected"
    assert result["candidates"][2]["eligibility"] == "eligible"
    assert [role for role, _, _ in model.calls] == ["fixer_a", "critic", "fixer_a"]
    assert model.calls[-1][1]["counterexample"]["oracle_status"] == "authoritative"
    assert result["usage"]["function_executions"] <= 400
    assert (
        store.candidate(result["run_id"], "candidate-1")["source"]
        == result["candidates"][1]["source"]
    )
    assert any(e["type"] == "revision_requested" for e in store.events(result["run_id"])["events"])


def test_invalid_critic_fallback_and_observations_do_not_reject(tmp_path):
    r = request()
    r["approved_property"] = None
    model = FixtureModel(
        [
            patch("def unique(values):\n    return list(dict.fromkeys(values))\n"),
            '{"property_id":"made_up","family":"general","reason":"invented"}',
        ]
    )
    result, store = execute(tmp_path, r, model)
    assert result["status"] == "supported_patch"
    assert all(t["oracle_status"] == "observation_only" for t in result["tests"][1:])
    assert any(e["type"] == "test_rejected" for e in store.events(result["run_id"])["events"])


def test_duplicate_inputs_cache_but_independent_final_replay(tmp_path):
    r = request()
    r["supplied_tests"].append({**r["supplied_tests"][0], "test_id": "duplicate"})
    model = FixtureModel(
        [patch("def unique(values):\n    return list(dict.fromkeys(values))\n"), "invalid"]
    )
    runner = FixtureRunner()
    result, _ = execute(tmp_path, r, model, runner)
    assert result["status"] == "supported_patch"
    matching = [x for x in runner.calls if x[1] == r["supplied_tests"][0]["args"]]
    assert len(matching) == 3  # original, generated supplied, independent final (dedup IDs)


def test_exhausted_budget_cannot_select_pending_patch(tmp_path):
    model = FixtureModel(
        [patch("def unique(values):\n    return list(dict.fromkeys(values))\n"), "invalid"]
    )
    result, _ = execute(tmp_path, request(), model, execution_cap=2)
    assert result["status"] == "unresolved"
    assert result["decision"]["selected_candidate_id"] is None
    assert all(c["eligibility"] == "rejected" for c in result["candidates"])
    assert result["usage"]["function_executions"] == 2


def test_cancel_before_work(tmp_path):
    cancel = threading.Event()
    cancel.set()
    model = FixtureModel([])
    store = Store(tmp_path)
    s = Repository(store).claim(request(), "fixture")
    result = run(request(), store, s["run_id"], cancel, model=model, runner=FixtureRunner())
    assert result["status"] == "cancelled"
    assert model.calls == []


def test_single_format_retry_is_charged(tmp_path):
    model = FixtureModel(["bad", "bad"])
    result, _ = execute(tmp_path, request(), model)
    assert result["status"] == "unresolved"
    assert result["usage"]["output_tokens"] == 40
    assert len(model.calls) == 2


def test_limits_cannot_be_loosened(tmp_path):
    with pytest.raises(ValueError):
        execute(tmp_path, request(), FixtureModel([]), execution_cap=401)
