"""Runtime-only SQLite evidence store. Offline training/evaluation is never loaded here."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ..contracts import REPO_ROOT, validate
from ..contracts.intake import source_hash, validate_request


def runtime_directory() -> Path:
    path = Path(os.getenv("CODEJURY_RUNS_DIR", REPO_ROOT / "backend/artifacts/runs")).resolve()
    for name in ("training", "evaluation"):
        offline = Path(
            os.getenv(f"CODEJURY_{name.upper()}_DIR", REPO_ROOT / f"backend/artifacts/{name}")
        ).resolve()
        if path == offline or path in offline.parents or offline in path.parents:
            raise ValueError("Runtime and offline records must use disjoint directories")
    return path


class Store:
    def __init__(self, directory: Path | None = None):
        self.directory = Path(directory) if directory is not None else runtime_directory()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "runtime.sqlite3"
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, request TEXT NOT NULL, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS candidates (
                    run_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(run_id,id), FOREIGN KEY(run_id) REFERENCES runs(id));
                CREATE TABLE IF NOT EXISTS events (
                    run_id TEXT NOT NULL, id INTEGER NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(run_id,id), FOREIGN KEY(run_id) REFERENCES runs(id));
                CREATE TRIGGER IF NOT EXISTS immutable_candidates_update BEFORE UPDATE ON candidates
                    BEGIN SELECT RAISE(ABORT,'immutable candidate'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_candidates_delete BEFORE DELETE ON candidates
                    BEGIN SELECT RAISE(ABORT,'immutable candidate'); END;
                CREATE TRIGGER IF NOT EXISTS append_only_events_update BEFORE UPDATE ON events
                    BEGIN SELECT RAISE(ABORT,'append-only event'); END;
                CREATE TRIGGER IF NOT EXISTS append_only_events_delete BEFORE DELETE ON events
                    BEGIN SELECT RAISE(ABORT,'append-only event'); END;
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_run(self, request: dict, snapshot: dict) -> None:
        validate_request(request)
        validate(snapshot, "RunSnapshot")
        with self.connection() as db:
            db.execute(
                "INSERT INTO runs VALUES (?,?,?)",
                (snapshot["run_id"], json.dumps(request), json.dumps(snapshot)),
            )

    def snapshot(self, run_id: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT snapshot FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return json.loads(row[0])

    def request(self, run_id: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT request FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return json.loads(row[0])

    def add_candidate(self, run_id: str, candidate: dict) -> None:
        validate(candidate, "Candidate")
        if source_hash(candidate["source"]) != candidate["source_sha256"]:
            raise ValueError("Candidate source hash mismatch")
        with self.connection() as db:
            db.execute(
                "INSERT INTO candidates VALUES (?,?,?)",
                (run_id, candidate["candidate_id"], json.dumps(candidate)),
            )

    def candidate(self, run_id: str, candidate_id: str) -> dict:
        with self.connection() as db:
            row = db.execute(
                "SELECT body FROM candidates WHERE run_id=? AND id=?", (run_id, candidate_id)
            ).fetchone()
        if row is None:
            raise KeyError(candidate_id)
        return json.loads(row[0])

    def append_event(
        self,
        run_id: str,
        event_type: str,
        message: str,
        *,
        candidate_id: str | None = None,
        test_id: str | None = None,
        evidence_ids: list[str] | None = None,
    ) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            event_id = db.execute(
                "SELECT coalesce(max(id),0)+1 FROM events WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            event = {
                "schema_version": "stage1.v1",
                "run_id": run_id,
                "event_id": event_id,
                "type": event_type,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "message": message,
                    "candidate_id": candidate_id,
                    "test_id": test_id,
                    "evidence_ids": evidence_ids or [],
                },
            }
            validate(event, "Event")
            db.execute("INSERT INTO events VALUES (?,?,?)", (run_id, event_id, json.dumps(event)))
        return event

    def events(self, run_id: str, after: int = 0) -> dict:
        if type(after) is not int or after < 0:
            raise ValueError("after must be an integer >=0")
        self.snapshot(run_id)
        with self.connection() as db:
            rows = db.execute(
                "SELECT body FROM events WHERE run_id=? AND id>? ORDER BY id", (run_id, after)
            ).fetchall()
        events = [json.loads(row[0]) for row in rows]
        page = {
            "schema_version": "stage1.v1",
            "run_id": run_id,
            "events": events,
            "next_after": events[-1]["event_id"] if events else after,
        }
        validate(page, "EventPage")
        return page
