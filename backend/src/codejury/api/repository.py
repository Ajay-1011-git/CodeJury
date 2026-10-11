"""Atomic run slot and restart recovery, backed by runtime-only SQLite."""

import json
import uuid

from ..contracts import validate
from .types import TERMINAL, queued


class Busy(RuntimeError):
    pass


class Repository:
    def __init__(self, store):
        self.store = store

    def claim(self, request: dict, mode: str) -> dict:
        snapshot = queued(uuid.uuid4().hex, mode=mode)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            busy = db.execute(
                "SELECT 1 FROM runs WHERE "
                "json_extract(snapshot,'$.status') IN ('queued','running') LIMIT 1"
            ).fetchone()
            if busy:
                raise Busy("The repair slot is occupied")
            db.execute(
                "INSERT INTO runs VALUES (?,?,?)",
                (snapshot["run_id"], json.dumps(request), json.dumps(snapshot)),
            )
        return snapshot

    def update(self, run_id: str, transform) -> dict:
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT snapshot FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            old = json.loads(row[0])
            if old["status"] in TERMINAL:
                return old
            snapshot = transform(old)
            if snapshot["run_id"] != run_id:
                raise ValueError("Run identity cannot change")
            validate(snapshot, "RunSnapshot")
            if snapshot["status"] in TERMINAL and snapshot["decision"] is None:
                raise ValueError("Terminal snapshot needs a decision")
            if snapshot["status"] == "supported_patch":
                selected = snapshot["decision"]["selected_candidate_id"]
                candidates = [c for c in snapshot["candidates"] if c["candidate_id"] == selected]
                if (
                    not candidates
                    or candidates[0]["origin"] == "original"
                    or candidates[0]["eligibility"] != "eligible"
                ):
                    raise ValueError("Supported patch requires an eligible generated candidate")
            elif (
                snapshot["decision"] is not None
                and snapshot["decision"]["selected_candidate_id"] is not None
            ):
                raise ValueError("Only supported_patch may select a candidate")
            db.execute("UPDATE runs SET snapshot=? WHERE id=?", (json.dumps(snapshot), run_id))
        return snapshot

    def finish(self, run_id: str, status: str, reason: str) -> dict:
        changed = []

        def terminal(snapshot):
            changed.append(True)
            snapshot.update(
                status=status,
                phase="finished",
                termination_reason=reason,
                decision={
                    "selected_candidate_id": None,
                    "verification_scope": [],
                    "unresolved_requirements": [],
                    "evidence_ids": [],
                    "reason": reason,
                },
            )
            return snapshot

        snapshot = self.update(run_id, terminal)
        if changed:
            self.store.append_event(run_id, "run_finished", reason)
        return snapshot

    def recover(self) -> None:
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT id FROM runs WHERE "
                "json_extract(snapshot,'$.status') IN ('queued','running')"
            ).fetchall()
        for (run_id,) in rows:
            self.finish(
                run_id, "infrastructure_error", "Backend restarted before repair completion"
            )
