"""Transactional evidence ledger. Candidate programs are parsed only, never executed."""

import ast
import copy
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import ValidationError

from ..budgets import CAPS, BudgetAccount
from ..contract_check import REPO_ROOT
from ..contracts import canonical_json, checked, json_hash, source_hash

ACTIVE = {"queued", "running"}
KINDS = {
    "candidates": ("Candidate", "candidate_id"),
    "tests": ("TestCase", "test_id"),
    "executions": ("Execution", "execution_id"),
    "mutants": ("ProbeMutant", "mutant_id"),
    "gaps": ("AuditGap", "gap_id"),
    "edit_sources": ("SourceArtifact", "source_hash"),
}


def encode(value) -> str:
    return canonical_json(value).decode()


def verify_source(record: dict) -> None:
    if len(record["source"].encode()) > 48000:
        raise ValueError("Candidate source exceeds byte cap")
    if source_hash(record["source"]) != record["source_hash"]:
        raise ValueError("Exact source hash mismatch")
    ast.parse(record["source"])


def verify_edits(parent: dict, draft: dict, artifacts: dict) -> None:
    current = parent["source"]
    for edit in draft["edits"]:
        if edit["parent_source_hash"] != source_hash(current):
            raise ValueError("Stale parent or broken edit hash chain")
        lines = current.encode().splitlines(keepends=True)
        location = edit["location"]
        line, end = location["lineno"], location["end_lineno"]
        if not 1 <= line <= end <= len(lines):
            raise ValueError("Invalid edit location")
        column, end_column = location["col_offset"], location["end_col_offset"]
        if not 0 <= column <= len(lines[line - 1]) or not 0 <= end_column <= len(lines[end - 1]):
            raise ValueError("Invalid UTF-8 edit offsets")
        start = sum(map(len, lines[: line - 1])) + column
        stop = sum(map(len, lines[: end - 1])) + end_column
        content = current.encode()
        if start > stop or content[start:stop] != edit["before"].encode():
            raise ValueError("Edit before text disagrees with parent location")
        current = (content[:start] + edit["after"].encode() + content[stop:]).decode()
        digest = source_hash(current)
        if digest != edit["result_source_hash"] or artifacts.get(digest) != current:
            raise ValueError("Missing intermediate source or incorrect edit result")
    if current != draft["source"]:
        raise ValueError("Final edit source differs from candidate")


class Ledger:
    def __init__(self, directory: Path):
        self.directory = Path(directory).resolve()
        for forbidden in (REPO_ROOT / "backend/data", REPO_ROOT / "backend/models"):
            if self.directory == forbidden or forbidden in self.directory.parents:
                raise ValueError("Runtime ledger must be disjoint from offline data/model paths")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.artifacts = self.directory / "objects"
        if self.artifacts.is_symlink():
            raise ValueError("Artifact store cannot be a symlink")
        self.artifacts.mkdir(exist_ok=True)
        self.path = self.directory / "ledger.sqlite3"
        self.accounts = {}
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, problem TEXT NOT NULL, mode TEXT NOT NULL,
                    profile_hash TEXT NOT NULL, model_configs TEXT NOT NULL,
                    limits TEXT NOT NULL, status TEXT NOT NULL, reason TEXT);
                CREATE TABLE IF NOT EXISTS events (
                    run_id TEXT NOT NULL REFERENCES runs(id), seq INTEGER NOT NULL,
                    body TEXT NOT NULL, PRIMARY KEY(run_id,seq));
                CREATE TABLE IF NOT EXISTS records (
                    run_id TEXT NOT NULL REFERENCES runs(id), kind TEXT NOT NULL,
                    id TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(run_id,kind,id));
                CREATE TABLE IF NOT EXISTS requests (
                    run_id TEXT NOT NULL REFERENCES runs(id), id TEXT PRIMARY KEY,
                    definition TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL,
                    response TEXT, usage TEXT);
                CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS checkpoints (
                    run_id TEXT PRIMARY KEY REFERENCES runs(id), usage TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS controller_records (
                    run_id TEXT NOT NULL REFERENCES runs(id), kind TEXT NOT NULL,
                    id TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(run_id,kind,id));
            """)
            for table in ("events", "records", "cache", "controller_records"):
                for verb in ("UPDATE", "DELETE"):
                    db.execute(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_{verb} BEFORE {verb} "
                        f"ON {table} BEGIN SELECT RAISE(ABORT, 'append-only immutable'); END"
                    )
            db.executescript("""
                CREATE TRIGGER IF NOT EXISTS requests_frozen BEFORE UPDATE ON requests
                WHEN OLD.status != 'dispatched' OR NEW.id != OLD.id
                    OR NEW.run_id != OLD.run_id OR NEW.body != OLD.body
                    OR NEW.definition != OLD.definition
                BEGIN SELECT RAISE(ABORT, 'settled request immutable'); END;
                CREATE TRIGGER IF NOT EXISTS requests_no_delete BEFORE DELETE ON requests
                BEGIN SELECT RAISE(ABORT, 'request append-only'); END;
                CREATE TRIGGER IF NOT EXISTS runs_identity BEFORE UPDATE ON runs
                WHEN NEW.id != OLD.id OR NEW.problem != OLD.problem OR NEW.mode != OLD.mode
                    OR NEW.profile_hash != OLD.profile_hash
                    OR NEW.model_configs != OLD.model_configs
                    OR NEW.limits != OLD.limits OR OLD.status NOT IN ('queued','running')
                BEGIN SELECT RAISE(ABORT, 'run identity/terminal state immutable'); END;
                CREATE TRIGGER IF NOT EXISTS runs_no_delete BEFORE DELETE ON runs
                BEGIN SELECT RAISE(ABORT, 'run append-only'); END;
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def put_object(self, content: bytes) -> str:
        digest = hashlib.sha256(content).hexdigest()
        path = self.artifacts / digest
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=self.artifacts)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fchmod(stream.fileno(), 0o400)
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if self.read_object(digest) != content:
                    raise ValueError("Immutable object identity conflict")
            directory_fd = os.open(self.artifacts, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            os.unlink(temporary)
        return digest

    def read_object(self, digest: str) -> bytes:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid artifact hash")
        fd = os.open(self.artifacts / digest, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            content = stream.read()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("Stored artifact hash mismatch")
        return content

    def create_run(
        self,
        run_id: str,
        problem: dict,
        *,
        mode: str,
        profile: dict,
        model_configs: list[str] | None = None,
        limits: dict | None = None,
        final_executions: int = 128,
    ) -> None:
        problem = checked(problem, "Problem")
        verify_source(problem)
        if mode not in {"live", "fixture"} or not run_id:
            raise ValueError("Explicit live/fixture run identity required")
        requirements = [r["requirement_id"] for r in problem["requirements"]]
        if len(requirements) != len(set(requirements)):
            raise ValueError("Duplicate requirements")
        configs = model_configs or []
        if any(len(h) != 64 or any(c not in "0123456789abcdef" for c in h) for h in configs):
            raise ValueError("Invalid frozen model config hash")
        account = BudgetAccount(limits, final_executions=final_executions)
        self.put_object(problem["source"].encode())
        with self.connection() as db:
            db.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    encode(problem),
                    mode,
                    json_hash(profile),
                    encode(configs),
                    encode(account.limits),
                    "running",
                    None,
                ),
            )
            self._event(db, run_id, "run_started", "Run admitted")
            db.execute("INSERT INTO checkpoints VALUES (?,?)", (run_id, encode(account.usage())))
        self.accounts[run_id] = account

    @staticmethod
    def _run(db, run_id: str, *, active: bool = False):
        row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        if active and row["status"] not in ACTIVE:
            raise ValueError("Run is terminal; no further work can be dispatched")
        return row

    def _event(self, db, run_id, kind, message, *, event_id=None, **references):
        self._run(db, run_id)
        last = db.execute(
            "SELECT COALESCE(MAX(seq),0) FROM events WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        if event_id is not None and (type(event_id) is not int or event_id != last + 1):
            raise ValueError("Duplicate or nonmonotonic event ID")
        payload = {
            "message": message,
            "candidate_id": None,
            "test_id": None,
            "action_id": None,
            "gap_id": None,
            "evidence_ids": [],
            **references,
        }
        event = checked(
            {
                "schema_version": "stage2.v1",
                "run_id": run_id,
                "event_id": last + 1,
                "type": kind,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            },
            "Event",
        )
        db.execute("INSERT INTO events VALUES (?,?,?)", (run_id, last + 1, encode(event)))
        return last + 1

    def append_event(self, run_id, kind, message, *, event_id=None, **references):
        with self.connection() as db:
            self._run(db, run_id, active=True)
            return self._event(db, run_id, kind, message, event_id=event_id, **references)

    @staticmethod
    def _records(db, run_id, kind) -> dict:
        return {
            row["id"]: json.loads(row["body"])
            for row in db.execute(
                "SELECT id,body FROM records WHERE run_id=? AND kind=? ORDER BY rowid",
                (run_id, kind),
            )
        }

    def records(self, run_id, kind) -> list:
        with self.connection() as db:
            self._run(db, run_id)
            return list(self._records(db, run_id, kind).values())

    def events(self, run_id) -> list:
        with self.connection() as db:
            self._run(db, run_id)
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT body FROM events WHERE run_id=? ORDER BY seq", (run_id,)
                )
            ]

    @staticmethod
    def _insert(db, run_id, kind, record):
        definition, identifier = KINDS[kind]
        checked(record, definition)
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?)",
            (run_id, kind, record[identifier], encode(record)),
        )

    def _candidate(self, db, run_id, draft, edit_sources, expected_parent_hash=None):
        draft = checked(draft, "CandidateDraft")
        verify_source(draft)
        run = self._run(db, run_id, active=True)
        problem = json.loads(run["problem"])
        if draft["problem_id"] != problem["problem_id"]:
            raise ValueError("Candidate problem mismatch")
        known = self._records(db, run_id, "candidates")
        if draft["candidate_id"] in known:
            raise ValueError("Duplicate candidate ID")
        requirements = {r["requirement_id"] for r in problem["requirements"]}
        if (
            len(set(draft["requirement_ids"])) != len(draft["requirement_ids"])
            or not set(draft["requirement_ids"]) <= requirements
        ):
            raise ValueError("Unknown or duplicate candidate requirement")
        if draft["model_config_hash"] is not None and draft["model_config_hash"] not in json.loads(
            run["model_configs"]
        ):
            raise ValueError("Unregistered model configuration provenance")
        parent = known.get(draft["parent_id"])
        if draft["parent_id"] is not None and parent is None:
            raise ValueError("Unknown parent candidate")
        if expected_parent_hash is not None and (
            parent is None or parent["source_hash"] != expected_parent_hash
        ):
            raise ValueError("Stale parent source hash")
        if draft["origin"] == "original":
            if (
                any(c["origin"] == "original" for c in known.values())
                or draft["source"] != problem["source"]
            ):
                raise ValueError("Original candidate must match the immutable problem")
        elif parent is None:
            raise ValueError("Generated candidate requires a registered parent")
        if draft["origin"].endswith("_revision"):
            family = draft["origin"].removesuffix("_revision")
            if parent["origin"] not in {family, family + "_revision"}:
                raise ValueError("Revision parent belongs to a different fixer")
        # Preserve target/helper interfaces. Execution policy stays with ToolPort.
        original_functions = {
            n.name: ast.dump(n.args)
            for n in ast.parse(problem["source"]).body
            if isinstance(n, ast.FunctionDef)
        }
        functions = {
            n.name: ast.dump(n.args)
            for n in ast.parse(draft["source"]).body
            if isinstance(n, ast.FunctionDef)
        }
        if functions != original_functions:
            raise ValueError("Candidate changed target/helper signatures")
        artifacts = {draft["source_hash"]: draft["source"]}
        for source in edit_sources:
            checked(source, "SourceArtifact")
            verify_source(source)
            artifacts[source["source_hash"]] = source["source"]
        if draft["edits"]:
            verify_edits(parent, draft, artifacts)
        event = self._event(
            db,
            run_id,
            "candidate_created",
            "Candidate committed; checks pending",
            candidate_id=draft["candidate_id"],
        )
        candidate = {
            **draft,
            "created_event_id": event,
            "eligibility": "pending",
            "rejection_reason": None,
            "verification_suite_hash": None,
        }
        self._insert(db, run_id, "candidates", candidate)
        self.put_object(draft["source"].encode())
        return candidate

    def commit_candidate(self, run_id, draft, *, edit_sources=(), expected_parent_hash=None):
        with self.connection() as db:
            candidate = self._candidate(db, run_id, draft, edit_sources, expected_parent_hash)
            for source in edit_sources:
                self.put_object(source["source"].encode())
                if source["source_hash"] not in self._records(db, run_id, "edit_sources"):
                    self._insert(db, run_id, "edit_sources", source)
            return candidate

    def _test(self, db, run_id, test):
        test = checked(test, "TestCase")
        problem = json.loads(self._run(db, run_id, active=True)["problem"])
        requirements = {r["requirement_id"]: r for r in problem["requirements"]}
        if not set(test["requirement_ids"]) <= requirements.keys():
            raise ValueError("Test has unknown requirement references")
        related = test["oracle_spec"]["kind"] == "metamorphic"
        if related != (test["related_inputs"] is not None):
            raise ValueError("Relation test must have exactly two input calls")
        if test["oracle_status"] == "authoritative":
            if not test["domain_valid"] or test["oracle_source"] == "model":
                raise ValueError("Model-proposed or out-of-domain test cannot be authoritative")
            if any(
                requirements[r]["approval_status"] != "approved" for r in test["requirement_ids"]
            ):
                raise ValueError("Unapproved requirement cannot authorize a test")
            templates = {requirements[r]["property_template_id"] for r in test["requirement_ids"]}
            kind = test["oracle_spec"]["kind"]
            if kind == "property" and test["oracle_spec"]["property_id"] not in templates:
                raise ValueError("Property oracle lacks an approved matching requirement")
            if kind == "metamorphic" and not templates & {"sum_ints", "sort_ascending_ints"}:
                raise ValueError("Relation oracle lacks a compatible approved requirement")
        self._insert(db, run_id, "tests", test)
        self._event(
            db,
            run_id,
            "test_admitted",
            "Test stored with explicit oracle status",
            test_id=test["test_id"],
        )

    def add_test(self, run_id, test):
        with self.connection() as db:
            self._test(db, run_id, test)

    def dispatch_tool(self, request: dict) -> None:
        request = checked(request, "ToolRequest")
        run_id = request["run_id"]
        account = self.accounts.get(run_id)
        if account is None:
            raise ValueError("Recovered runs cannot resume generation")
        with self.connection() as db, account.lock:
            run = self._run(db, run_id, active=True)
            if json.loads(run["problem"]) != request["problem"]:
                raise ValueError("Tool request problem is stale or altered")
            candidates = self._records(db, run_id, "candidates")
            params = request["parameters"]
            incoming = params.get("candidates", params.get("parents", []))
            if "candidate" in params:
                incoming = [params["candidate"]]
            for draft in incoming:
                known = candidates.get(draft["candidate_id"])
                if known is None or any(known[key] != value for key, value in draft.items()):
                    raise ValueError("Unknown or stale dispatched candidate")
            known_tests = self._records(db, run_id, "tests")
            for test in params.get("tests", params.get("existing_tests", [])):
                if known_tests.get(test["test_id"]) != test:
                    raise ValueError("Unknown or stale dispatched test")
            if db.execute("SELECT 1 FROM requests WHERE id=?", (request["request_id"],)).fetchone():
                raise ValueError("Duplicate request ID")
            db.execute(
                "INSERT INTO requests VALUES (?,?,?,?,?,?,?)",
                (
                    run_id,
                    request["request_id"],
                    "ToolRequest",
                    encode(request),
                    "dispatched",
                    None,
                    None,
                ),
            )
            account.dispatch(request["request_id"], request["remaining_budget"])
            db.execute(
                "UPDATE checkpoints SET usage=? WHERE run_id=?", (encode(account.usage()), run_id)
            )

    def dispatch_model(
        self, request: dict, *, candidate_attempt=False, decision_attempt=False
    ) -> None:
        request = checked(request, "ModelRequest")
        run_id = request["run_id"]
        account = self.accounts.get(run_id)
        if account is None:
            raise ValueError("Recovered runs cannot resume generation")
        purpose = request["purpose"]
        role = request["role"]
        purposes = {
            "raw": {"repair", "baseline"},
            "fixer_a": {"repair", "revise"},
            "fixer_b": {"reconstruct", "revise"},
            "critic": {"test_proposal"},
            "judge": {"action_choice"},
            "general": {"baseline"},
        }
        cap = 192 if role == "judge" else 512 if role == "critic" else 1024
        if purpose not in purposes[role] or request["max_new_tokens"] > cap:
            raise ValueError("Model role/purpose or completion cap mismatch")
        attempts = (
            {"judge_decisions": 1}
            if role == "judge"
            else {"learned_candidates": 1}
            if role in {"fixer_a", "fixer_b"}
            else {}
        )
        if (
            type(candidate_attempt) is not bool
            or type(decision_attempt) is not bool
            or (candidate_attempt and decision_attempt)
        ):
            raise ValueError("One explicit model attempt kind is permitted")
        if candidate_attempt:
            attempts = {"learned_candidates": 1}
        elif decision_attempt:
            attempts = {"judge_decisions": 1}
        ceiling = {
            **dict.fromkeys(CAPS, 0),
            "input_tokens": request["remaining_budget"]["input_tokens"],
            "output_tokens": request["max_new_tokens"],
            "elapsed_ms": request["remaining_budget"]["elapsed_ms"],
        }
        if request["max_new_tokens"] > request["remaining_budget"]["output_tokens"]:
            raise ValueError("Completion exceeds remaining output budget")
        with self.connection() as db, account.lock:
            self._run(db, run_id, active=True)
            if db.execute("SELECT 1 FROM requests WHERE id=?", (request["request_id"],)).fetchone():
                raise ValueError("Duplicate request ID")
            db.execute(
                "INSERT INTO requests VALUES (?,?,?,?,?,?,?)",
                (
                    run_id,
                    request["request_id"],
                    "ModelRequest",
                    encode(request),
                    "dispatched",
                    None,
                    None,
                ),
            )
            account.dispatch(request["request_id"], ceiling, attempts=attempts)
            db.execute(
                "UPDATE checkpoints SET usage=? WHERE run_id=?", (encode(account.usage()), run_id)
            )

    def settle_model(self, response: dict) -> None:
        response = checked(response, "ModelResponse")
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM requests WHERE id=?", (response["request_id"],)
            ).fetchone()
            if row is None or row["status"] != "dispatched" or row["definition"] != "ModelRequest":
                raise ValueError("Undispatched or duplicate model result")
            request = json.loads(row["body"])
            run = self._run(db, row["run_id"], active=True)
            account = self.accounts[row["run_id"]]
            with account.lock:
                delta = account.preview(response["request_id"], response["usage"])
                if response["role"] != request["role"]:
                    raise ValueError("Model response role mismatch")
                if response["status"] == "ok":
                    if response["text"] is None or response["model_config_hash"] not in json.loads(
                        run["model_configs"]
                    ):
                        raise ValueError("Missing text or unfrozen model config provenance")
                    if (response["role"] == "raw") != (response["adapter_hash"] is None):
                        raise ValueError("Raw/trained adapter provenance mismatch")
                checkpoint = account.usage()
                for key in CAPS.keys() - {"elapsed_ms"}:
                    checkpoint[key] += delta[key]
                if delta["peak_memory_mb"] is not None:
                    checkpoint["peak_memory_mb"] = max(
                        checkpoint["peak_memory_mb"] or 0, delta["peak_memory_mb"]
                    )
                db.execute(
                    "UPDATE requests SET status='settled', response=?, usage=? WHERE id=?",
                    (encode(response), encode(delta), response["request_id"]),
                )
                db.execute(
                    "UPDATE checkpoints SET usage=? WHERE run_id=?",
                    (encode(checkpoint), row["run_id"]),
                )
                db.commit()
                account.settle(response["request_id"], delta)

    def settle_tool(self, result: dict) -> None:
        result = checked(result, "ToolResult")
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM requests WHERE id=?", (result["request_id"],)
            ).fetchone()
            if row is None or row["status"] != "dispatched" or row["definition"] != "ToolRequest":
                raise ValueError("Undispatched or duplicate tool result")
            request = json.loads(row["body"])
            run_id = row["run_id"]
            self._run(db, run_id, active=True)
            account = self.accounts[run_id]
            with account.lock:
                delta = account.preview(result["request_id"], result["usage"])
                refusal = None
                db.execute("SAVEPOINT tool_records")
                try:
                    self._tool_records(db, run_id, request, result)
                except (ValueError, ValidationError, sqlite3.IntegrityError, SyntaxError) as exc:
                    db.execute("ROLLBACK TO tool_records")
                    refusal = exc
                    # Even refused evidence consumes the tool's reported resources once.
                    # Invalid evidence stops the episode; no retry can erase attempted work.
                    account.faulted = True
                    self._event(db, run_id, "action_refused", type(exc).__name__ + ": tool refused")
                db.execute("RELEASE tool_records")
                db.execute(
                    "UPDATE requests SET status=?, response=?, usage=? WHERE id=?",
                    (
                        "refused" if refusal else "settled",
                        encode(result),
                        encode(delta),
                        result["request_id"],
                    ),
                )
                checkpoint = account.usage()
                for key in CAPS.keys() - {"elapsed_ms"}:
                    checkpoint[key] += delta[key]
                if delta["peak_memory_mb"] is not None:
                    checkpoint["peak_memory_mb"] = max(
                        checkpoint["peak_memory_mb"] or 0, delta["peak_memory_mb"]
                    )
                db.execute(
                    "UPDATE checkpoints SET usage=? WHERE run_id=?", (encode(checkpoint), run_id)
                )
                # The SQL commit precedes in-memory settlement; requests never resume on restart.
                db.commit()
                account.settle(result["request_id"], delta)
                if refusal:
                    raise refusal

    def _tool_records(self, db, run_id, request, result):
        operation = request["parameters"]["operation"]
        allowed = {
            "validate": set(),
            "evaluate": {"executions"},
            "search": {"candidates", "executions", "edit_sources"},
            "audit": {"mutants", "audit_gaps", "executions", "edit_sources"},
            "investigate": {"tests", "executions"},
        }[operation]
        for field in ("candidates", "tests", "executions", "mutants", "audit_gaps", "edit_sources"):
            if result[field] and field not in allowed:
                raise ValueError("Tool operation returned forbidden content")
        if operation == "validate" and result["status"] == "ok" and result["validation"] is None:
            raise ValueError("Validation operation needs a receipt")
        if operation != "validate" and result["validation"] is not None:
            raise ValueError("Unexpected validation receipt")
        if any(
            result["usage"][key]
            for key in ("input_tokens", "output_tokens", "learned_candidates", "judge_decisions")
        ):
            raise ValueError("Tool cannot invent model or Judge costs")
        prefix = request["id_prefix"] + "-"
        for field, identifier in (
            ("candidates", "candidate_id"),
            ("tests", "test_id"),
            ("executions", "execution_id"),
            ("mutants", "mutant_id"),
            ("audit_gaps", "gap_id"),
        ):
            if any(not row[identifier].startswith(prefix) for row in result[field]):
                raise ValueError("Tool IDs do not belong to dispatched prefix")
        sources = result["edit_sources"]
        for source in sources:
            verify_source(source)
            self.put_object(source["source"].encode())
            if source["source_hash"] not in self._records(db, run_id, "edit_sources"):
                self._insert(db, run_id, "edit_sources", source)
        for candidate in result["candidates"]:
            if candidate["origin"] != "ast_search":
                raise ValueError("Tool cannot produce a learned candidate")
            self._candidate(db, run_id, candidate, sources)
        for test in result["tests"]:
            if test["oracle_status"] == "authoritative" and (
                test["oracle_source"] != "reviewed_contract"
                or test["oracle_spec"]["kind"] == "literal"
            ):
                raise ValueError("Tool cannot invent user authority or literal oracles")
            self._test(db, run_id, test)
        candidates = self._records(db, run_id, "candidates")
        for mutant in result["mutants"]:
            verify_source(mutant)
            parent = candidates.get(mutant["parent_candidate_id"])
            if parent is None:
                raise ValueError("Unknown mutant parent")
            artifacts = {s["source_hash"]: s["source"] for s in sources}
            artifacts[mutant["source_hash"]] = mutant["source"]
            verify_edits(parent, {**mutant, "edits": [mutant["edit"]]}, artifacts)
            if mutant["suite_hash"] != request["parameters"]["suite_hash"]:
                raise ValueError("Mutant refers to a stale suite")
            self.put_object(mutant["source"].encode())
            self._insert(db, run_id, "mutants", mutant)
        mutants = self._records(db, run_id, "mutants")
        tests = self._records(db, run_id, "tests")
        params = request["parameters"]
        dispatched_candidates = params.get("candidates", params.get("parents", []))
        if "candidate" in params:
            dispatched_candidates = [params["candidate"]]
        permitted_candidates = (
            {c["candidate_id"] for c in dispatched_candidates}
            | {c["candidate_id"] for c in result["candidates"]}
            | {m["mutant_id"] for m in result["mutants"]}
        )
        permitted_tests = {
            t["test_id"] for t in params.get("tests", params.get("existing_tests", []))
        }
        permitted_tests |= {t["test_id"] for t in result["tests"]}
        minimum_calls = 0
        for execution in result["executions"]:
            if (
                execution["candidate_id"] not in permitted_candidates
                or execution["test_id"] not in permitted_tests
            ):
                raise ValueError("Execution lies outside dispatched candidate/test scope")
            if execution["candidate_id"] not in candidates.keys() | mutants.keys():
                raise ValueError("Execution has unknown candidate reference")
            test = tests.get(execution["test_id"])
            if test is None:
                raise ValueError("Execution has unknown test reference")
            if test["oracle_status"] != "authoritative" and execution["outcome"] in {
                "pass",
                "fail",
            }:
                raise ValueError("Proposed/observed test cannot certify or reject")
            effects = execution["input_effects"]
            indexes = [effect["call_index"] for effect in effects]
            if indexes != list(range(len(indexes))) or len(indexes) > (
                2 if test["related_inputs"] is not None else 1
            ):
                raise ValueError("Invalid relation/effect call accounting")
            calls = 2 if test["related_inputs"] is not None else 1
            if execution["outcome"] in {"pass", "fail", "observed"} and len(effects) != calls:
                raise ValueError("Completed result lacks actual input-effect evidence")
            minimum_calls += max(1, len(effects))
            if execution["trace_ref"] is not None:
                self.read_object(execution["trace_ref"])
            self._insert(db, run_id, "executions", execution)
            self._event(
                db,
                run_id,
                "execution_completed",
                "Sandbox evidence committed",
                candidate_id=execution["candidate_id"],
                test_id=execution["test_id"],
                evidence_ids=[execution["execution_id"]],
            )
        if result["usage"]["function_executions"] < minimum_calls:
            raise ValueError("Reported costs omit relation or execution calls")
        if result["usage"]["search_candidates"] < len(result["candidates"]) or result["usage"][
            "audit_mutants"
        ] < len(result["mutants"]):
            raise ValueError("Candidate/probe attempts underreported")
        for gap in result["audit_gaps"]:
            if (
                gap["candidate_id"] not in candidates
                or not set(gap["mutant_ids"]) <= mutants.keys()
            ):
                raise ValueError("Audit gap has unknown provenance")
            if gap["candidate_source_hash"] != candidates[gap["candidate_id"]]["source_hash"]:
                raise ValueError("Stale audit gap source")
            if gap["suite_hash"] != request["parameters"]["suite_hash"]:
                raise ValueError("Stale audit gap suite")
            self._insert(db, run_id, "gaps", gap)
            self._event(
                db,
                run_id,
                "audit_gap_found",
                "Audit gap recorded; not proof of incorrectness",
                candidate_id=gap["candidate_id"],
                gap_id=gap["gap_id"],
            )

    def recover(self) -> list[str]:
        """On server restart, never resume accepted/running generations."""
        recovered = []
        with self.connection() as db:
            for row in db.execute(
                "SELECT id FROM runs WHERE status IN ('queued','running')"
            ).fetchall():
                run_id = row["id"]
                reason = "Backend restarted before episode completion"
                self._event(db, run_id, "run_finished", reason)
                db.execute(
                    "UPDATE runs SET status='infrastructure_error', reason=? WHERE id=?",
                    (reason, run_id),
                )
                db.execute(
                    "UPDATE requests SET status='abandoned' WHERE run_id=? AND status='dispatched'",
                    (run_id,),
                )
                recovered.append(run_id)
        for run_id in recovered:
            self.accounts.pop(run_id, None)
        return recovered

    def snapshot(self, run_id) -> dict:
        with self.connection() as db:
            run = self._run(db, run_id)
            final = db.execute(
                "SELECT body FROM controller_records WHERE run_id=? AND kind='final'",
                (run_id,),
            ).fetchone()
            if final is not None:
                return checked(json.loads(final[0]), "RunSnapshot")
            usage = (
                self.accounts[run_id].usage()
                if run_id in self.accounts
                else {
                    "schema_version": "stage2.v1",
                    **dict.fromkeys(CAPS, 0),
                    "peak_memory_mb": None,
                }
            )
            if run_id not in self.accounts:
                usage = json.loads(
                    db.execute(
                        "SELECT usage FROM checkpoints WHERE run_id=?", (run_id,)
                    ).fetchone()[0]
                )
                # Last committed elapsed measurement is a lower bound after a process crash.
            terminal = run["status"] not in ACTIVE
            metadata_row = db.execute(
                "SELECT body FROM controller_records WHERE run_id=? AND kind='metadata'", (run_id,)
            ).fetchone()
            metadata = json.loads(metadata_row[0]) if metadata_row else {}
            decision = (
                None
                if not terminal
                else {
                    "schema_version": "stage2.v1",
                    "selected_candidate_id": None,
                    "verification_scope": [],
                    "unresolved_requirements": [
                        r["requirement_id"] for r in json.loads(run["problem"])["requirements"]
                    ],
                    "evidence_ids": [],
                    "reason": run["reason"],
                    "suite_hash": None,
                }
            )
            snapshot = {
                "schema_version": "stage2.v1",
                "run_id": run_id,
                "status": run["status"],
                "runtime_mode": run["mode"],
                "phase": "finished" if terminal else "validate",
                "problem": json.loads(run["problem"]),
                "candidates": list(self._records(db, run_id, "candidates").values()),
                "tests": list(self._records(db, run_id, "tests").values()),
                "executions": list(self._records(db, run_id, "executions").values()),
                "audit_gaps": list(self._records(db, run_id, "gaps").values()),
                "probe_mutants": list(self._records(db, run_id, "mutants").values()),
                "edit_sources": list(self._records(db, run_id, "edit_sources").values()),
                "actions": [],
                "decision": decision,
                "resource_usage": usage,
                "policy_mode": metadata.get("profile", {}).get("policy_mode", "fixed"),
                "model_manifest_hash": metadata.get("model_manifest_hash"),
                "profile_hash": run["profile_hash"],
                "suite_hash": None,
                "termination_reason": run["reason"],
            }
            return checked(snapshot, "RunSnapshot")

    def cache_put(self, key: str, execution: dict) -> None:
        execution = checked(execution, "Execution")
        if execution["outcome"] in {"timeout", "error"}:
            raise ValueError("Infrastructure/time-dependent outcomes cannot be cached")
        with self.connection() as db:
            old = db.execute("SELECT body FROM cache WHERE key=?", (key,)).fetchone()
            if old is not None:
                if old[0] != encode(execution):
                    raise ValueError("Immutable cache conflict")
                return
            db.execute("INSERT INTO cache VALUES (?,?)", (key, encode(execution)))

    def cache_get(self, key: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT body FROM cache WHERE key=?", (key,)).fetchone()
            return copy.deepcopy(json.loads(row[0])) if row else None
