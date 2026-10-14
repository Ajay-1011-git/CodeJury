import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from codejury.api.app import create_app
from codejury.api.types import queued
from codejury.contracts import REPO_ROOT, validate
from codejury.contracts.intake import source_hash
from codejury.storage import Store


class FixtureWorker:
    """Test-only injected worker. All responses are explicitly fixture mode."""

    mode = "fixture"

    def __init__(self, ready=True):
        self.ready = ready
        self.starts = []
        self.cancels = []

    def health(self):
        return {"model_ready": self.ready, "sandbox_ready": self.ready, "fixer_a_trained": False}

    def start(self, run_id):
        self.starts.append(run_id)

    def cancel(self, run_id):
        self.cancels.append(run_id)
        return True

    def close(self):
        pass


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path)
    worker = FixtureWorker()
    app = create_app(store, worker)
    with TestClient(app) as client:
        yield client, store, worker, app


@pytest.fixture
def request_body():
    return json.loads((REPO_ROOT / "contracts/fixtures/run-create.json").read_text())


def checked(response, definition, status=200):
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    validate(response.json(), definition)
    return response.json()


def test_all_endpoints_and_cancel_idempotence(setup, request_body):
    client, store, worker, _ = setup
    assert checked(client.get("/health"), "Health")["runtime_mode"] == "fixture"
    checked(client.get("/examples"), "Examples")
    checked(client.get("/stage1/training-report"), "TrainingReport")
    accepted = checked(client.post("/runs", json=request_body), "RunAccepted", 202)
    run_id = accepted["run_id"]
    checked(client.get(f"/runs/{run_id}"), "RunSnapshot")
    checked(client.get(f"/runs/{run_id}/report"), "Error", 409)
    page = checked(client.get(f"/runs/{run_id}/events"), "EventPage")
    assert page["next_after"] == 1
    assert checked(client.get(f"/runs/{run_id}/events?after=99"), "EventPage")["next_after"] == 99
    source = request_body["source"]
    candidate = {
        "candidate_id": "candidate",
        "parent_id": None,
        "origin": "original",
        "source": source,
        "source_sha256": source_hash(source),
        "diagnosis": "fixture",
        "diff": "",
        "eligibility": "pending",
        "rejection_reason": None,
    }
    store.add_candidate(run_id, candidate)
    checked(client.get(f"/runs/{run_id}/candidates/candidate"), "Candidate")
    result = checked(client.post(f"/runs/{run_id}/cancel"), "RunSnapshot")
    assert result["status"] == "cancelled" and result["decision"]["selected_candidate_id"] is None
    assert checked(client.post(f"/runs/{run_id}/cancel"), "RunSnapshot") == result
    assert worker.cancels == [run_id]
    checked(client.get(f"/runs/{run_id}/report"), "RunSnapshot")


def test_concurrent_posts_accept_at_most_one(setup, request_body):
    client, _, worker, _ = setup
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post("/runs", json=request_body), range(2)))
    assert sorted(result.status_code for result in results) == [202, 409]
    assert len(worker.starts) == 1
    for result in results:
        checked(result, "RunAccepted" if result.status_code == 202 else "Error", result.status_code)


@pytest.mark.parametrize(
    "path",
    [
        "/runs/missing",
        "/runs/missing/report",
        "/runs/missing/events",
        "/runs/missing/candidates/no",
        "/not-a-route",
    ],
)
def test_unknown_objects_use_error_envelope(setup, path):
    checked(setup[0].get(path), "Error", 404)


@pytest.mark.parametrize("after", ["-1", "true", "1.5", "abc", "99999999999999999999999999"])
def test_invalid_event_cursor(setup, request_body, after):
    client = setup[0]
    run_id = client.post("/runs", json=request_body).json()["run_id"]
    checked(client.get(f"/runs/{run_id}/events?after={after}"), "Error", 422)


def test_invalid_body_and_known_unavailability(setup, request_body):
    client, _, worker, _ = setup
    checked(client.post("/runs", json={**request_body, "unexpected": 1}), "Error", 422)
    checked(client.post("/runs", content="{"), "Error", 422)
    checked(client.post("/runs", content='"' + "x" * (256 * 1024) + '"'), "Error", 422)
    worker.ready = False
    checked(client.post("/runs", json=request_body), "Error", 503)


def test_restart_marks_accepted_work_infrastructure_error(tmp_path, request_body):
    store = Store(tmp_path)
    store.create_run(request_body, queued("abandoned", mode="fixture"))
    app = create_app(Store(tmp_path), FixtureWorker())
    with TestClient(app) as client:
        body = checked(client.get("/runs/abandoned"), "RunSnapshot")
        assert body["status"] == "infrastructure_error"
        assert body["decision"]["selected_candidate_id"] is None
        assert "restarted" in body["termination_reason"]


def test_live_default_never_exposes_fake_health(tmp_path):
    with TestClient(create_app(Store(tmp_path))) as client:
        body = checked(client.get("/health"), "Health")
        assert body["runtime_mode"] == "live"
        assert not body["model_ready"] and not body["fixer_a_trained"]


def test_transcript_only_after_termination(setup, request_body):
    client, store, _, _ = setup
    run_id = checked(client.post("/runs", json=request_body), "RunAccepted", 202)["run_id"]
    episode = {
        "generations": [
            {"role": "fixer_a", "format_retry": False, "text": "{}", "input_tokens": 9},
            {"role": "critic", "format_retry": False, "text": "not json", "input_tokens": 9},
        ],
        "actions": [{"action": "challenge_proposal", "source": "deterministic_fallback"}],
    }
    (store.directory / f"{run_id}-episode.json").write_text(json.dumps(episode))
    assert client.get(f"/runs/{run_id}/transcript").json()["available"] is False
    client.post(f"/runs/{run_id}/cancel")
    body = client.get(f"/runs/{run_id}/transcript").json()
    assert body["available"] is True
    assert body["generations"][1] == {"role": "critic", "format_retry": False, "text": "not json"}
    assert body["actions"] == episode["actions"]
    assert client.get("/runs/missing/transcript").status_code == 404
