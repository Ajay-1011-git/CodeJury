"""Comparison boundaries, durable one-shot admission and honest common checks."""

import copy
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from codejury.api.comparison import (
    ComparisonService, common_tests, evaluate_source, raw_source, router,
)
from codejury.stage2_core.api.worker import Busy, Unavailable
from codejury.stage2_core.budgets import zero_usage
from codejury.stage2_tools.codec import value_hash

RUN = "run-" + "a" * 32
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def snapshot():
    body = json.loads((ROOT / "contracts/stage2-fixtures/snapshot-supported.json").read_text())
    body["run_id"] = RUN
    return body


class Sandbox:
    """Canned arithmetic fixture, never executes/imports supplied candidate code."""
    runtime_hash = "f" * 64

    def __init__(self, mutated=False):
        self.mutated = mutated
        self.jobs = []

    def ready(self):
        return {}

    def run(self, job, cancel):
        self.jobs.append(job)
        return {"results": [
            {"status": "ok", "output": 0 if job["source"].endswith("return 0\n") else sum(c["inputs"][0]),
             "before_hash": value_hash(c["inputs"]), "after_hash": value_hash(c["inputs"]),
             "mutated": self.mutated, "duration_ms": 1, "trace": None}
            for c in job["calls"]
        ]}


class Model:
    def __init__(self, snapshot, *, wait=None):
        self.requests = []
        self.started = self.closed = False
        self.wait = wait
        self.registry = SimpleNamespace(
            manifest_hash=snapshot["model_manifest_hash"],
            identity=lambda role: {"adapter_hash": None, "model_revision_hash": "b" * 64,
                                   "model_config_hash": "c" * 64},
        )

    def start(self, cancel):
        self.started = True

    def generate(self, request, cancel):
        self.requests.append(request)
        if self.wait:
            self.wait.wait(3)
        return {"status": "ok", "text": '```json\n' + json.dumps({"source": "def sum_values(values):\n    return 0\n"}) + '\n```',
                "usage": {**zero_usage(), "input_tokens": 10, "output_tokens": 20},
                **self.registry.identity("raw")}

    def close(self):
        self.closed = True


def service(tmp_path, snapshot, *, model=None, sandbox=None):
    worker = SimpleNamespace(lock=threading.Lock(), closed=False)
    ledger = SimpleNamespace(directory=tmp_path, snapshot=lambda run: copy.deepcopy(snapshot) if run == RUN else (_ for _ in ()).throw(KeyError(run)))
    stage2 = SimpleNamespace(state=SimpleNamespace(worker=worker, ledger=ledger))
    model = model or Model(snapshot)
    sandbox = sandbox or Sandbox()
    result = ComparisonService(stage2, model_factory=lambda: model, sandbox_factory=lambda: sandbox)
    return result, model, worker


@pytest.mark.parametrize("fenced", [False, True])
def test_reply_recovery_preserves_code_bytes(fenced):
    source = "def f(x):\n    return x\n\n"
    text = json.dumps({"source": source, "other": "ignored metadata"})
    assert raw_source('```json\n' + text + '\n```' if fenced else text) == source


@pytest.mark.parametrize("text", ['{"source":"one","source":"two"}',
                                  'Prose {"source":"one"}', '[{"source":"one"}]'])
def test_no_prose_or_ambiguous_reply_salvage(text):
    with pytest.raises(ValueError):
        raw_source(text)


def test_common_suite_excludes_jury_generated_and_non_authoritative_tests(snapshot):
    expected = common_tests(snapshot)
    snapshot["tests"].extend([{**expected[0], "test_id": "late", "provenance": "supplied"},
                              {**expected[0], "test_id": "critic", "provenance": "critic"}])
    assert common_tests(snapshot) == expected


def test_common_evaluation_rejects_mutation_and_incomplete_checks(snapshot):
    problem, tests = snapshot["problem"], common_tests(snapshot)
    source = "def sum_values(values):\n    return sum(values)\n"
    assert evaluate_source(Sandbox(), problem, tests, source, threading.Event())["status"] == "passed_examples"
    assert evaluate_source(Sandbox(mutated=True), problem, tests, source, threading.Event())["status"] == "failed_examples"
    cancelled = threading.Event(); cancelled.set()
    assert evaluate_source(Sandbox(), problem, tests, source, cancelled)["status"] == "incomplete"
    assert evaluate_source(Sandbox(), problem, tests, "not valid source", threading.Event())["status"] == "unsupported_source"


def test_actual_reply_is_saved_once_and_prompt_never_contains_jury_solution(tmp_path, snapshot):
    original = copy.deepcopy(snapshot)
    svc, model, worker = service(tmp_path, snapshot)
    assert svc.get(RUN)["status"] == "not_started" and not model.requests
    svc.claim(RUN)
    svc.thread.join(3)
    body = svc.get(RUN)
    assert body["status"] == "complete"
    assert body["baseline"]["checks"]["status"] == "failed_examples"
    assert body["baseline"]["reply"].startswith('```json')
    assert body["baseline"]["source"].endswith('return 0\n')
    request = model.requests[0]
    assert request["role"] == "raw" and request["purpose"] == "baseline"
    assert request["max_new_tokens"] == 1024
    prompt_facts = json.loads(request["prompt"].split('Runtime-visible facts:\n')[1])
    assert prompt_facts["buggy_source"] == snapshot["problem"]["source"]
    assert [t["test_id"] for t in prompt_facts["tests"]] == [t["test_id"] for t in common_tests(snapshot)]
    assert "candidates" not in prompt_facts and not prompt_facts["evidence"]
    assert "return sum(values)" not in request["prompt"]
    assert svc.claim(RUN) == body and len(model.requests) == 1
    assert snapshot == original and not worker.lock.locked() and model.closed
    reopened, _, _ = service(tmp_path, snapshot)
    assert reopened.get(RUN) == body


def test_concurrent_duplicate_does_not_dispatch_twice(tmp_path, snapshot):
    unblock = threading.Event()
    svc, model, worker = service(tmp_path, snapshot, model=Model(snapshot, wait=unblock))
    try:
        assert svc.claim(RUN)["status"] == "running"
        assert svc.claim(RUN)["status"] == "running"
        assert worker.lock.locked()
    finally:
        unblock.set(); svc.thread.join(3)
    assert len(model.requests) == 1 and not worker.lock.locked()


def test_busy_parent_and_untrained_identity_guards(tmp_path, snapshot):
    svc, model, worker = service(tmp_path, snapshot)
    worker.lock.acquire()
    with pytest.raises(Busy):
        svc.claim(RUN)
    worker.lock.release()
    assert not model.started
    model.registry.identity = lambda role: {"adapter_hash": "d" * 64}
    with pytest.raises(Unavailable):
        svc.claim(RUN)
    assert not worker.lock.locked() and not model.started
    snapshot["status"] = "running"
    with pytest.raises(Busy):
        svc.get(RUN)


def test_registry_change_refuses_comparison_before_inference(tmp_path, snapshot):
    svc, model, worker = service(tmp_path, snapshot)
    model.registry.manifest_hash = "0" * 64
    with pytest.raises(Unavailable):
        svc.claim(RUN)
    assert not model.started and not worker.lock.locked()


def test_restart_marks_interruption_without_another_attempt(tmp_path, snapshot):
    svc, model, _ = service(tmp_path, snapshot)
    body = svc.get(RUN); body["status"] = "running"; svc.save(body)
    svc.recover()
    assert svc.get(RUN)["status"] == "error" and not model.requests


def test_interpreter_trust_label_is_preserved(tmp_path, snapshot):
    svc, _, _ = service(tmp_path, snapshot)
    svc.provenance = lambda run: {"authority_label": "Verified against an interpreted specification, not user tests"}
    assert svc.get(RUN)["authority_label"] == "Verified against an interpreted specification, not user tests"


def test_routes_guard_origins_and_reuse_saved_result(tmp_path, snapshot):
    svc, model, _ = service(tmp_path, snapshot)
    app = FastAPI()
    app.state.worker = SimpleNamespace(mode="fixture")
    app.state.stage2_error = None
    app.include_router(router(svc, app, SimpleNamespace(busy=lambda: False)))
    path = f"/s2x/runs/{RUN}/baseline"
    with TestClient(app) as client:
        for method in [client.get, client.post]:
            assert method(path, headers={"origin": "https://example.com"}).status_code == 403
            assert method(path, headers={"host": "example.com"}).status_code == 403
        assert not model.requests
        assert client.get('/s2x/runs/run-invalid/baseline').status_code == 404
        assert client.get(path).json()["status"] == "not_started"
        assert client.post(path).status_code in {200, 202}
        svc.thread.join(3)
        assert client.get(path).json()["status"] == "complete"
        assert client.post(path).status_code == 200
        assert len(model.requests) == 1
