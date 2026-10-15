"""Local, durable one-shot raw-model comparisons beside the frozen wire API."""

import json
import os
import re
import sqlite3
import threading
import time
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from codejury.stage2_core.api.worker import Busy, Unavailable
from codejury.stage2_core.budgets import CAPS
from codejury.stage2_core.contracts import checked, json_hash
from codejury.stage2_core.factory import make_model_port
from codejury.stage2_core.views import freeze_initial
from codejury.stage2_tools.domains import check_bundle
from codejury.stage2_tools.factory import make_tool_port
from codejury.stage2_tools.runner.executor import Evaluator

from .intake import envelope, local_request

RUN_ID = re.compile(r"run-[0-9a-f]{32}")
SCOPE = (
    "One local Phi-4-mini attempt without CodeJury adapters. It sees the original "
    "bug and approved specification, not the jury's proposals or debate. Both "
    "outputs are checked on the same original approved examples. Passing these "
    "examples is not proof of correctness. The jury may use more compute and checks."
)


def raw_source(text):
    """Preserve source bytes; tolerate one JSON fence and ignore metadata fields."""
    if not isinstance(text, str) or len(text.encode()) > 96000:
        raise ValueError("Missing or oversized reply")
    text = text.strip()
    match = re.fullmatch(r"```(?:json)?[ \t]*\n(.*)\n```", text, re.DOTALL)
    if match:
        text = match.group(1)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    value = json.loads(text, object_pairs_hook=unique)
    if not isinstance(value, dict) or not isinstance(value.get("source"), str):
        raise ValueError("Reply has no source string")
    return value["source"]


def common_tests(snapshot):
    original_ids = set(snapshot["problem"]["supplied_test_ids"])
    return [t for t in snapshot["tests"] if t["test_id"] in original_ids and t["provenance"] == "supplied"
            and t["oracle_status"] == "authoritative" and t["domain_valid"]]


def evaluate_source(sandbox, problem, tests, source, cancel):
    if source is None:
        return None
    try:
        check_bundle(source, problem)
    except ValueError:
        return {"status": "unsupported_source", "passed": 0, "total": len(tests),
                "executions": [], "function_executions": 0}
    evaluator = Evaluator(sandbox, problem, id_prefix="comparison-" + uuid4().hex,
                          max_executions=3000, cancel=cancel)
    rows = evaluator.evaluate({"candidate_id": "comparison", "source": source}, tests)
    complete = bool(tests) and len(rows) == len(tests)
    passed = sum(r["outcome"] == "pass" and all(
        not e["mutated"] and e["before_hash"] == e["after_hash"] for e in r["input_effects"]
    ) for r in rows)
    return {"status": "passed_examples" if complete and passed == len(tests) else
            "failed_examples" if complete else "incomplete", "passed": passed,
            "total": len(tests), "executions": rows, "function_executions": evaluator.used}


class ComparisonService:
    def __init__(self, stage2, *, model_factory=None, sandbox_factory=None, provenance=None):
        self.worker, self.ledger = stage2.state.worker, stage2.state.ledger
        directory = self.ledger.directory / "comparisons"
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "comparisons.sqlite3"
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS comparisons (run_id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        os.chmod(self.path, 0o600)
        self.model_factory = model_factory or (lambda: make_model_port(self.worker.runtime_config))
        self.sandbox_factory = sandbox_factory or (lambda: make_tool_port(self.worker.tool_config).sandbox)
        self.provenance = provenance or (lambda run_id: None)
        self.thread = self.cancel = None
        self.closed = False

    def connect(self):
        return sqlite3.connect(self.path)

    def recover(self):
        with self.connect() as db:
            for run_id, raw in db.execute("SELECT run_id,body FROM comparisons").fetchall():
                body = json.loads(raw)
                if body["status"] == "running":
                    body.update(status="error", message="Comparison interrupted by a server restart. No new attempt was started.")
                    db.execute("UPDATE comparisons SET body=? WHERE run_id=?", (json.dumps(body), run_id))

    def save(self, body):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO comparisons VALUES (?,?)", (body["run_id"], json.dumps(body)))

    def snapshot(self, run_id):
        if not RUN_ID.fullmatch(run_id):
            raise KeyError(run_id)
        snapshot = self.ledger.snapshot(run_id)
        if snapshot.get("status") not in {"supported_patch", "unresolved"}:
            raise Busy("Finish the jury run before comparing")
        return snapshot

    def get(self, run_id):
        snapshot = self.snapshot(run_id)
        with self.connect() as db:
            row = db.execute("SELECT body FROM comparisons WHERE run_id=?", (run_id,)).fetchone()
        if row:
            return json.loads(row[0])
        decision = snapshot.get("decision") or {}
        winner = next((c for c in snapshot["candidates"] if c["candidate_id"] == decision.get("selected_candidate_id")), None)
        tests = common_tests(snapshot)
        return {
            "comparison_version": 1, "run_id": run_id, "status": "not_started", "scope": SCOPE,
            "authority_label": (self.provenance(run_id) or {}).get("authority_label"),
            "baseline_seed": 17, "baseline_max_output_tokens": 1024,
            "function_name": snapshot["problem"]["function_name"],
            "original_source": snapshot["problem"]["source"],
            "specification": {k: snapshot["problem"][k] for k in
                              ("signature", "contract_text", "domain_schema", "requirements")},
            "tests": tests, "suite_hash": json_hash(tests),
            "jury": {"status": snapshot["status"], "reason": decision.get("reason"),
                     "source": winner["source"] if winner else None,
                     "usage": snapshot["resource_usage"], "checks": None},
            "baseline": None,
        }

    def claim(self, run_id):
        body = self.get(run_id)
        if body["status"] != "not_started":
            return body
        if self.closed or getattr(self.worker, "closed", False):
            raise Unavailable("Comparison worker is closed")
        if not self.worker.lock.acquire(blocking=False):
            latest = self.get(run_id)
            if latest["status"] != "not_started":
                return latest
            raise Busy("Another repair or comparison is using local compute")
        model = None
        try:
            # Recheck after taking the shared repair slot for simultaneous submissions.
            body = self.get(run_id)
            if body["status"] != "not_started":
                self.worker.lock.release()
                return body
            snapshot = self.snapshot(run_id)
            model = self.model_factory()
            identity = model.registry.identity("raw")
            if identity["adapter_hash"] is not None:
                raise Unavailable("The baseline must have no adapter")
            if model.registry.manifest_hash != snapshot["model_manifest_hash"]:
                raise Unavailable("The model registry changed since this jury run")
            sandbox = self.sandbox_factory()
            sandbox.ready()
            cancel = threading.Event()
            model.start(cancel)
            body.update(status="running", message="Phi-4-mini is making one independent attempt.")
            body["baseline"] = {"identity": identity, "source": None, "reply": None,
                                "usage": None, "checks": None}
            self.save(body)
            self.cancel = cancel
            self.thread = threading.Thread(target=self._run, args=(body, snapshot, model, sandbox, cancel),
                                           daemon=True, name="raw-comparison")
            self.thread.start()
            return self.get(run_id)
        except BaseException:
            if model is not None:
                model.close()
            self.worker.lock.release()
            raise

    def _run(self, body, snapshot, model, sandbox, cancel):
        started = time.monotonic()
        timer = threading.Timer(120, cancel.set)
        timer.daemon = True
        timer.start()
        try:
            tests, problem = body["tests"], snapshot["problem"]
            # Initial supplied facts only: no jury candidate, debate or generated test.
            prompt = freeze_initial(problem, tests, original_evidence=()).a
            request = checked({
                "schema_version": "stage2.v1", "request_id": "model-" + uuid4().hex,
                "run_id": body["run_id"], "role": "raw", "purpose": "baseline",
                "prompt": prompt, "seed": snapshot.get("seed", 17), "max_new_tokens": 1024,
                "remaining_budget": {**CAPS, "elapsed_ms": 120000},
            }, "ModelRequest")
            response = model.generate(request, cancel)
            if any(response[k] != body["baseline"]["identity"][k] for k in
                   ("adapter_hash", "model_revision_hash", "model_config_hash")):
                raise ValueError("Raw model identity mismatch")
            raw = body["baseline"]
            raw.update(reply=response.get("text"), usage=response["usage"],
                       model_status=response["status"], prompt_sha256=json_hash(prompt))
            if response["status"] == "ok":
                try:
                    raw["source"] = raw_source(response["text"])
                except (ValueError, TypeError, RecursionError):
                    raw["format_status"] = "No usable source in the reply"
                else:
                    raw["format_status"] = "Source read verbatim from JSON; an outer Markdown fence is allowed"
                    raw["checks"] = evaluate_source(sandbox, problem, tests, raw["source"], cancel)
            else:
                raw["format_status"] = "The model did not complete its reply"
            body["jury"]["checks"] = evaluate_source(sandbox, problem, tests, body["jury"]["source"], cancel)
            body.update(status="complete", message="Comparison saved. Results cover the shared examples only.")
        except Exception as exc:
            body.update(status="error", message="Local comparison could not finish (" + type(exc).__name__ + "). No replacement reply was generated.")
        finally:
            timer.cancel()
            body["comparison_elapsed_ms"] = int((time.monotonic() - started) * 1000)
            try:
                self.save(body)
            finally:
                try:
                    model.close()
                finally:
                    self.worker.lock.release()

    def close(self):
        self.closed = True
        if self.cancel is not None:
            self.cancel.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=15)


def router(service, main_app, repository):
    routes = APIRouter(prefix="/s2x/runs")

    def allowed(request):
        return local_request(request, fixture=main_app.state.worker.mode == "fixture")

    @routes.get("/{run_id}/baseline")
    def get_baseline(run_id: str, request: Request):
        if not allowed(request):
            return envelope("forbidden", "Comparisons are available only to the local dashboard", 403)
        try:
            return JSONResponse(service.get(run_id), headers={"Cache-Control": "no-store"})
        except KeyError:
            return envelope("not_found", "Unknown jury run", 404)
        except Busy:
            return envelope("not_finished", "Finish the jury run before comparing", 409)

    @routes.post("/{run_id}/baseline")
    async def start_baseline(run_id: str, request: Request):
        if not allowed(request):
            return envelope("forbidden", "Comparisons are available only to the local dashboard", 403)
        if main_app.state.stage2_error:
            return envelope("unavailable", "The local jury runtime is unavailable", 503)
        if repository.busy():
            return envelope("busy", "Another local repair is running; try again when it finishes", 409)
        try:
            body = await run_in_threadpool(service.claim, run_id)
            return JSONResponse(body, status_code=202 if body["status"] == "running" else 200,
                                headers={"Cache-Control": "no-store"})
        except KeyError:
            return envelope("not_found", "Unknown jury run", 404)
        except Busy:
            return envelope("busy", "Finish the active repair or comparison, then try again", 409)
        except Exception:
            return envelope("unavailable", "Local compute, the frozen model or Docker is unavailable; no comparison was started", 503)

    return routes
