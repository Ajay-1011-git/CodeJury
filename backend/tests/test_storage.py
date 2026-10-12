import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from codejury.api.types import queued
from codejury.contracts import REPO_ROOT
from codejury.contracts.intake import source_hash
from codejury.storage import Store, runtime_directory


@pytest.fixture
def store(tmp_path):
    store = Store(tmp_path)
    request = json.loads((REPO_ROOT / "contracts/fixtures/run-create.json").read_text())
    store.create_run(request, queued("run-one"))
    return store


def test_exact_hash_and_immutable_candidate_after_revision(store):
    source = "def unique(values):\n    return values\n"
    candidate = {
        "candidate_id": "first",
        "parent_id": None,
        "origin": "fixer_a",
        "source": source,
        "source_sha256": source_hash(source),
        "diagnosis": "test",
        "diff": "",
        "eligibility": "pending",
        "rejection_reason": None,
    }
    store.add_candidate("run-one", candidate)
    revision = {
        **candidate,
        "candidate_id": "revision",
        "parent_id": "first",
        "origin": "fixer_a_revision",
        "source": source + "\n",
        "source_sha256": source_hash(source + "\n"),
    }
    store.add_candidate("run-one", revision)
    assert store.candidate("run-one", "first") == candidate
    with pytest.raises(sqlite3.IntegrityError):
        store.add_candidate("run-one", {**candidate, "diagnosis": "changed"})
    with store.connection() as db, pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.execute("UPDATE candidates SET body='{}'")


def test_events_survive_restart_and_concurrent_append(store):
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(
            executor.map(lambda i: store.append_event("run-one", "run_started", str(i)), range(12))
        )
    reopened = Store(store.directory)
    events = reopened.events("run-one")["events"]
    assert [event["event_id"] for event in events] == list(range(1, 13))
    assert reopened.events("run-one", 10)["next_after"] == 12
    assert reopened.events("run-one", 50)["next_after"] == 50
    with reopened.connection() as db, pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("DELETE FROM events")


def test_json_types_survive_storage(store):
    assert type(store.request("run-one")["supplied_tests"][0]["args"][0][0]) is int
    assert store.snapshot("run-one")["original_failure_reproduced"] is None


def test_offline_paths_are_separate(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEJURY_RUNS_DIR", str(tmp_path / "same"))
    monkeypatch.setenv("CODEJURY_TRAINING_DIR", str(tmp_path / "same" / "train"))
    with pytest.raises(ValueError, match="disjoint"):
        runtime_directory()
