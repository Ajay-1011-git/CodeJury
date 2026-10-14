import json
import sqlite3
import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from codejury.api.app import create_app
from codejury.api.stage2_bridge import transcript
from codejury.contracts import REPO_ROOT
from codejury.storage import Store

RUN = "run-" + "a" * 32


class FixtureWorker:
    mode = "fixture"

    def health(self):
        return {"model_ready": True, "sandbox_ready": True, "fixer_a_trained": False}

    def start(self, run_id):
        pass

    def cancel(self, run_id):
        return True

    def close(self):
        pass


class Stage2Worker:
    def __init__(self, recover_error=None):
        self.lock = threading.Lock()
        self.recover_error = recover_error
        self.closed = False

    def recover(self):
        if self.recover_error:
            raise self.recover_error

    def close(self):
        self.closed = True


def ledger(tmp_path):
    db = sqlite3.connect(tmp_path / "ledger.sqlite3")
    db.execute(
        "CREATE TABLE requests (run_id TEXT, id TEXT, definition TEXT, body TEXT, "
        "status TEXT, response TEXT, usage TEXT)"
    )
    facts = {
        "state": {
            "available_actions": [
                {
                    "option_id": "option-01",
                    "action": {"kind": "criticize", "target_ids": ["c-1"]},
                    "prerequisite_summary": "Challenge shared agreement",
                }
            ],
            "candidate_summaries": [{"candidate_id": "c-1", "origin": "fixer_b"}],
        }
    }
    rows = [
        ({"role": "fixer_b", "purpose": "reconstruct", "prompt": "secret"}, {"status": "ok", "text": "{}"}),
        (
            {"role": "judge", "purpose": "action_choice", "prompt": "Choose.\nRuntime-visible facts:\n" + json.dumps(facts) + "\ntrailing"},
            {"status": "ok", "text": '{"action_option_id":"option-01"}'},
        ),
    ]
    for i, (body, response) in enumerate(rows):
        db.execute(
            "INSERT INTO requests VALUES (?,?,?,?,?,?,?)",
            (RUN, f"r{i}", "ModelRequest", json.dumps(body), "settled", json.dumps(response), None),
        )
    db.execute(
        "INSERT INTO requests VALUES (?,?,?,?,?,?,?)",
        (RUN, "tool", "ToolRequest", "{}", "settled", "{}", None),
    )
    db.commit()
    db.close()


def stage2_app(tmp_path, worker):
    app = FastAPI()
    app.state.worker = worker
    app.state.ledger = SimpleNamespace(directory=tmp_path, snapshot=lambda run_id: {})

    @app.get("/health")
    def health():
        return {"schema_version": "stage2.v1", "service": "codejury-stage2"}

    @app.post("/runs")
    def runs():
        return {"schema_version": "stage2.v1", "status": "queued"}

    return app


@pytest.fixture
def request_body():
    return json.loads((REPO_ROOT / "contracts/fixtures/run-create.json").read_text())


def test_transcript_orders_model_calls_and_extracts_judge_menu(tmp_path):
    ledger(tmp_path)
    body = transcript(tmp_path, RUN)
    assert [c["role"] for c in body["calls"]] == ["fixer_b", "judge"]
    assert "prompt" not in body["calls"][0]
    judge = body["calls"][1]
    assert judge["options"] == [
        {"option_id": "option-01", "kind": "criticize", "target_ids": ["c-1"], "summary": "Challenge shared agreement"}
    ]
    assert judge["scoreboard"][0]["origin"] == "fixer_b"
    assert transcript(tmp_path, "../../etc")["calls"] == []


def test_stage2_is_served_under_prefix(tmp_path):
    ledger(tmp_path)
    worker = Stage2Worker()
    app = create_app(Store(tmp_path / "s1"), FixtureWorker(), stage2=stage2_app(tmp_path, worker))
    with TestClient(app) as client:
        assert client.get("/s2/health").json()["service"] == "codejury-stage2"
        assert client.get("/health").json()["service"] == "codejury-stage1"
        assert len(client.get(f"/s2/runs/{RUN}/transcript").json()["calls"]) == 2
    assert worker.closed


def test_stage2_unavailable_when_ledger_is_owned(tmp_path):
    app = create_app(
        Store(tmp_path / "s1"),
        FixtureWorker(),
        stage2=stage2_app(tmp_path, Stage2Worker(RuntimeError("owned"))),
    )
    with TestClient(app) as client:
        response = client.get("/s2/health")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "unavailable"
        assert client.get("/health").status_code == 200


def test_one_model_run_across_stages(tmp_path, request_body):
    worker = Stage2Worker()
    app = create_app(Store(tmp_path / "s1"), FixtureWorker(), stage2=stage2_app(tmp_path, worker))
    with TestClient(app) as client:
        with worker.lock:
            busy = client.post("/runs", json=request_body)
            assert busy.status_code == 409 and busy.json()["error"]["code"] == "busy"
        assert client.post("/runs", json=request_body).status_code == 202
        blocked = client.post("/s2/runs", json={})
        assert blocked.status_code == 409
        assert blocked.json()["schema_version"] == "stage2.v1"
