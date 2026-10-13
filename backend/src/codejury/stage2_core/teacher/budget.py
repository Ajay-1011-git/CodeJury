"""Integer nano-dollar accounting; unknown charges stay reserved and stop dispatch."""

import fcntl
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

CAP = 1_000_000_000
MAX_ATTEMPTS = 60
CONTEXT = 131072
MAX_OUTPUT = 4096
# Published dollars / million tokens, represented as nano-dollars per token.
INPUT_RATE = 150
OUTPUT_RATE = 600
RESERVATION = CONTEXT * INPUT_RATE + MAX_OUTPUT * OUTPUT_RATE


class Halt(RuntimeError):
    pass


class Ledger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS attempts ("
                "id INTEGER PRIMARY KEY, request TEXT, status TEXT, charge INTEGER, "
                "result TEXT, retry_at REAL DEFAULT 0)"
            )

    def connect(self):
        return sqlite3.connect(self.path)

    @contextmanager
    def exclusive(self):
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def summary(self):
        with self.connect() as db:
            count, charge = db.execute(
                "SELECT count(*),coalesce(sum(charge),0) FROM attempts"
            ).fetchone()
            unknown = db.execute(
                "SELECT count(*) FROM attempts WHERE status='reserved'"
            ).fetchone()[0]
        return {
            "attempts": count,
            "charged_or_reserved_usd": charge / CAP,
            "unknown_usage_attempts": unknown,
            "cap_usd": 1.0,
        }

    def cached(self, request):
        with self.connect() as db:
            row = db.execute(
                "SELECT result FROM attempts WHERE request=? AND status='ok' "
                "ORDER BY id DESC LIMIT 1",
                (request,),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def reserve(self, request, *, completion=True):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count, cost, unknown, retry_at = db.execute(
                "SELECT count(*),coalesce(sum(charge),0),"
                "coalesce(sum(status='reserved'),0),coalesce(max(retry_at),0) FROM attempts"
            ).fetchone()
            repeats = db.execute(
                "SELECT count(*) FROM attempts WHERE request=?", (request,)
            ).fetchone()[0]
            reserve = RESERVATION if completion else 0
            if unknown or count >= MAX_ATTEMPTS or cost + reserve > CAP or repeats >= 3:
                raise Halt("Teacher stopped: unknown charge, spend cap, or attempt cap")
            if retry_at > time.time():
                raise Halt("Teacher rate limit backoff is still active")
            return db.execute(
                "INSERT INTO attempts(request,status,charge) VALUES(?,'reserved',?)",
                (request, reserve),
            ).lastrowid

    def settle(self, attempt, *, status, charge, result=None, retry_at=0):
        if type(charge) is not int or charge < 0:
            raise ValueError("Invalid charge")
        with self.connect() as db:
            changed = db.execute(
                "UPDATE attempts SET status=?,charge=?,result=?,retry_at=? "
                "WHERE id=? AND status='reserved'",
                (
                    status,
                    charge,
                    json.dumps(result) if result is not None else None,
                    retry_at,
                    attempt,
                ),
            ).rowcount
            if changed != 1:
                raise Halt("Attempt was already settled")
