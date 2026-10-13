"""Canonical API semantics with explicit trusted fixtures; no hardware quality claims."""

import json
import sqlite3
from threading import Event

from fastapi.testclient import TestClient

from codejury.stage2_core.api import create_app
from codejury.stage2_core.api.worker import Busy, Unavailable
from codejury.stage2_core.contracts import checked
from codejury.stage2_core.intake import prepare

from .test_candidates import fixture
from .test_controller import controller


class FixtureWorker:
    mode = "fixture"

    def __init__(self, tmp_path):
        self.control = controller(tmp_path)
        self.ledger = self.control.ledger
        self.active = None
        self.unavailable = False
        self.dispatched = []

    def health(self):
        return {
            "model_ready": True,
            "tools_ready": True,
            "trained_roles": [],
            "full_stage2_ready": False,
            "default_policy": "fixed",
        }

    def registry(self):
        raise OSError("Fixture has no trained adapter registry")

    def recover(self):
        return self.ledger.recover()

    def claim(self, create):
        if self.active:
            raise Busy()
        if self.unavailable:
            raise Unavailable()
        self.problem, self.tests = prepare(create)
        self.seed, self.cancel_event = create["seed"], Event()
        self.active = self.control.admit(
            self.problem, self.tests, cancel=self.cancel_event, seed=self.seed
        )
        with self.ledger.connection() as db:
            db.execute("UPDATE runs SET status='queued' WHERE id=?", (self.active,))
        return {
            "schema_version": "stage2.v1",
            "run_id": self.active,
            "status": "queued",
            "runtime_mode": "fixture",
        }

    def dispatch(self, run_id):
        self.dispatched.append(run_id)

    def cancel(self, run_id):
        self.cancel_event.set()
        self.control.run(
            self.problem, self.tests, cancel=self.cancel_event, seed=self.seed, admitted=True
        )
        self.active = None
        return self.ledger.snapshot(run_id)

    def close(self):
        if self.active:
            self.cancel(self.active)


def test_admission_is_durable_before_dispatch_busy_no_duplicate_and_cancel(tmp_path):
    worker = FixtureWorker(tmp_path)
    with TestClient(create_app(worker)) as client:
        health = client.get("/health").json()
        checked(health, "Health")
        assert health["runtime_mode"] == "fixture" and not health["full_stage2_ready"]
        accepted = client.post("/runs", json=fixture("run-create"))
        assert accepted.status_code == 202
        run_id = accepted.json()["run_id"]
        assert worker.dispatched == [run_id] and not worker.control.model.requests
        snapshot = client.get(f"/runs/{run_id}").json()
        checked(snapshot, "RunSnapshot")
        assert snapshot["status"] == "queued"
        assert client.post("/runs", json=fixture("run-create")).status_code == 409
        assert client.get(f"/runs/{run_id}/events?after=-1").status_code == 422
        page = client.get(f"/runs/{run_id}/events").json()
        checked(page, "EventPage")
        assert (
            page["events"]
            and client.get(f"/runs/{run_id}/events?after={page['next_after']}").json()["events"]
            == []
        )
        cancelled = client.post(f"/runs/{run_id}/cancel").json()
        assert cancelled["status"] == "cancelled"
        assert client.get(f"/runs/{run_id}/report").json() == cancelled
        assert not worker.control.model.requests


def test_unavailable_or_bad_input_does_not_create_a_run(tmp_path):
    worker = FixtureWorker(tmp_path)
    with TestClient(create_app(worker)) as client:
        worker.unavailable = True
        assert client.post("/runs", json=fixture("run-create")).status_code == 503
        assert client.post("/runs", json={"schema_version": "stage1.v1"}).status_code == 422
        assert client.post("/runs", content="x" * (256 * 1024 + 1)).status_code == 422
        with worker.ledger.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0


def test_legacy_and_unknown_ids_are_separate_without_opening_old_sources(tmp_path):
    legacy = tmp_path / "stage1.sqlite3"
    with sqlite3.connect(legacy) as db:
        db.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, request TEXT)")
        db.execute("INSERT INTO runs VALUES (?,?)", ("old", "private-source-must-not-appear"))
    before = legacy.read_bytes()
    worker = FixtureWorker(tmp_path / "stage2")
    with TestClient(create_app(worker, stage1_database=legacy)) as client:
        archived = client.get("/runs/old")
        assert archived.status_code == 409
        assert archived.json()["error"]["code"] == "legacy_stage1_run"
        assert client.get("/runs/unknown").status_code == 404
        assert "private-source" not in archived.text
    assert legacy.read_bytes() == before


def test_reports_use_actual_cards_and_benchmark_stays_not_run(tmp_path):
    worker = FixtureWorker(tmp_path)
    with TestClient(create_app(worker)) as client:
        training = client.get("/stage2/training-report").json()
        checked(training, "TrainingReport")
        assert training["cards"] == []
        benchmark = client.get("/stage2/benchmark-report").json()
        checked(benchmark, "BenchmarkReport")
        assert benchmark["status"] == "not_run" and benchmark["research_outcome"] == "not_measured"
        assert client.get("/").status_code == 200
        assert "stage2" in client.get("/").text.lower()


def test_restart_recovers_accepted_run_without_new_generation(tmp_path):
    worker = FixtureWorker(tmp_path)
    create = fixture("run-create")
    accepted = worker.claim(create)
    worker.active = None  # Simulated process loss; no continuation is dispatched.
    with TestClient(create_app(worker)) as client:
        run_id = accepted["run_id"]
        recovered = client.get(f"/runs/{run_id}").json()
        assert recovered["status"] == "infrastructure_error"
        assert not worker.control.model.requests
        assert json.dumps(create["source"]) not in client.get("/stage2/benchmark-report").text
