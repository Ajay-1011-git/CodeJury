"""Stage 1 endpoints with frozen success/error envelopes and one durable slot."""

import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from jsonschema import ValidationError
from starlette.exceptions import HTTPException

from ..contracts import validate
from ..contracts.intake import IntakeError, validate_request
from ..controller.worker import LocalWorker
from ..storage import Store
from .repository import Busy, Repository
from .stage2_bridge import PREFIX as STAGE2_PREFIX
from .stage2_bridge import load_stage2_app, stage2_busy
from .stage2_bridge import transcript as stage2_transcript
from .training_report import load_report
from .types import TERMINAL, error


def response(body: dict, definition: str, status: int = 200):
    validate(body, definition)
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})


def examples() -> dict:
    request = {
        "schema_version": "stage1.v1",
        "source": "def unique(values):\n    return sorted(set(values))\n",
        "function_name": "unique",
        "contract_text": "Return exactly the first occurrence of each integer in input order.",
        "input_domain": [
            {"kind": "list_integer", "min": -1000, "max": 1000, "min_length": 0, "max_length": 30}
        ],
        "supplied_tests": [{"test_id": "order", "args": [[3, 1, 3, 2]], "expected": [3, 1, 2]}],
        "approved_property": "unique_preserve_order_ints",
        "resource_profile": "stage1-demo",
    }
    return {
        "schema_version": "stage1.v1",
        "examples": [
            {
                "example_id": "unique-order",
                "title": "Preserve first-occurrence order",
                "description": "Public input with a supplied failing order example.",
                "request": request,
            },
            {
                "example_id": "sum-ints",
                "title": "Sum signed integers",
                "description": (
                    "Public mechanics demo; sum algorithm family overlaps training. Unscored."
                ),
                "request": {
                    **request,
                    "source": "def total(values):\n    return 0\n",
                    "function_name": "total",
                    "contract_text": (
                        "Return the sum of all input integers; an empty input returns zero."
                    ),
                    "supplied_tests": [
                        {"test_id": "sum-visible", "args": [[2, -4, 7]], "expected": 5}
                    ],
                    "approved_property": "sum_ints",
                },
            },
        ],
    }


def create_app(store=None, worker=None, *, web_dir=None, stage2=None, intake_store=None) -> FastAPI:
    """stage2: an optional Stage 2 app, served under /s2 with one model run across stages."""
    store = store or Store()
    repository = Repository(store)
    worker = worker or LocalWorker(store)

    @asynccontextmanager
    async def lifespan(_app):
        repository.recover()
        if stage2 is not None:
            try:
                stage2.state.worker.recover()
            except Exception:  # e.g. a standalone Stage 2 server already owns the ledger
                app.state.stage2_error = "Stage 2 is unavailable: another server owns its ledger"
        yield
        worker.close()
        if stage2 is not None and app.state.stage2_error is None:
            stage2.state.worker.close()

    app = FastAPI(title="CodeJury Stage 1", lifespan=lifespan)
    app.state.store, app.state.worker = store, worker
    app.state.repository = repository
    app.state.stage2_error = None
    origins = os.getenv("CODEJURY_ALLOWED_ORIGINS", "http://localhost:8080").split(",")
    if any(
        not re.fullmatch(r"http://(?:localhost|127\.0\.0\.1):[0-9]{1,5}", origin)
        for origin in origins
    ):
        raise ValueError("Only explicit localhost development origins are supported")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_query(_request, exc):
        return response(
            error(
                "invalid_input", "Invalid request parameter", [str(e["loc"]) for e in exc.errors()]
            ),
            "Error",
            422,
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request, exc):
        return response(
            error("not_found" if exc.status_code == 404 else "http_error", "Request unavailable"),
            "Error",
            exc.status_code,
        )

    @app.exception_handler(KeyError)
    async def missing(_request, _exc):
        return response(error("not_found", "Unknown run or candidate"), "Error", 404)

    @app.get("/health")
    def health():
        return response(
            {
                "schema_version": "stage1.v1",
                "service": "codejury-stage1",
                "runtime_mode": worker.mode,
                **worker.health(),
                "stage2_enabled": False,
            },
            "Health",
        )

    @app.middleware("http")
    async def revalidate_static(request: Request, call_next):
        # Browsers otherwise reuse stale UI modules after an update; ETags keep this cheap.
        response = await call_next(request)
        if request.method == "GET" and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-cache"
        return response

    if stage2 is not None:

        @app.middleware("http")
        async def stage2_gate(request: Request, call_next):
            path = request.url.path
            if path == STAGE2_PREFIX or path.startswith(STAGE2_PREFIX + "/"):
                body = {"schema_version": "stage2.v1", "error": {"field_errors": []}}
                if app.state.stage2_error:
                    body["error"].update(code="unavailable", message=app.state.stage2_error)
                    return JSONResponse(body, status_code=503)
                if (
                    request.method == "POST"
                    and path == STAGE2_PREFIX + "/runs"
                    and repository.busy()
                ):
                    body["error"].update(code="busy", message="A Stage 1 repair is running")
                    return JSONResponse(body, status_code=409)
            return await call_next(request)

    @app.get("/examples")
    def get_examples():
        return response(examples(), "Examples")

    @app.post("/runs")
    async def create_run(request: Request):
        try:
            raw = bytearray()
            async for chunk in request.stream():
                if len(raw) + len(chunk) > 256 * 1024:
                    raise IntakeError("Request body exceeds 256 KiB")
                raw.extend(chunk)
            payload = json.loads(raw)
            validate_request(payload)
        except (
            json.JSONDecodeError,
            ValidationError,
            IntakeError,
            ValueError,
            TypeError,
            RecursionError,
        ):
            return response(
                error(
                    "invalid_input",
                    "Request violates Stage 1 source, domain or oracle requirements",
                ),
                "Error",
                422,
            )
        health = worker.health()
        if not health["model_ready"] or not health["sandbox_ready"]:
            return response(
                error("unavailable", "Local model or isolated sandbox is not ready"), "Error", 503
            )
        try:
            if stage2 is not None and stage2_busy(stage2):
                raise Busy("A Stage 2 debate is running")
            snapshot = repository.claim(payload, worker.mode)
        except Busy:
            return response(
                error("busy", "A queued or running repair occupies the only slot"), "Error", 409
            )
        store.append_event(snapshot["run_id"], "run_started", "Accepted for fixed Stage 1 policy")
        try:
            worker.start(snapshot["run_id"])
        except Exception:
            repository.finish(
                snapshot["run_id"],
                "infrastructure_error",
                "Worker dispatch failed after acceptance",
            )
        return response(
            {key: snapshot[key] for key in ("schema_version", "run_id", "status", "runtime_mode")},
            "RunAccepted",
            202,
        )

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        return response(store.snapshot(run_id), "RunSnapshot")

    @app.get("/runs/{run_id}/events")
    def events(run_id: str, after: str = "0"):
        if not re.fullmatch(r"[0-9]{1,18}", after):
            return response(error("invalid_input", "after must be an integer >=0"), "Error", 422)
        return response(store.events(run_id, int(after)), "EventPage")

    @app.get("/runs/{run_id}/candidates/{candidate_id}")
    def candidate(run_id: str, candidate_id: str):
        snapshot = store.snapshot(run_id)
        body = next((c for c in snapshot["candidates"] if c["candidate_id"] == candidate_id), None)
        return response(body or store.candidate(run_id, candidate_id), "Candidate")

    @app.post("/runs/{run_id}/cancel")
    def cancel(run_id: str):
        snapshot = store.snapshot(run_id)
        if snapshot["status"] not in TERMINAL:
            stopped = worker.cancel(run_id)
            if stopped:
                snapshot = repository.finish(run_id, "cancelled", "User cancelled repair")
            else:
                snapshot = store.snapshot(run_id)
        return response(snapshot, "RunSnapshot")

    @app.get("/runs/{run_id}/report")
    def report(run_id: str):
        snapshot = store.snapshot(run_id)
        if snapshot["status"] not in TERMINAL:
            return response(
                error("not_terminal", "Report is available after termination"), "Error", 409
            )
        return response(snapshot, "RunSnapshot")

    @app.get("/runs/{run_id}/transcript")
    def transcript(run_id: str):
        # Model outputs and engine reports for the Action history; written when a run finishes.
        snapshot = store.snapshot(run_id)
        body = {"schema_version": "stage1.v1", "run_id": run_id, "available": False}
        path = store.directory / f"{run_id}-episode.json"
        if (
            snapshot["status"] in TERMINAL
            and re.fullmatch(r"[0-9a-f]{32}", run_id)
            and path.is_file()
        ):
            try:
                episode = json.loads(path.read_text())
                body.update(
                    available=True,
                    generations=[
                        {"role": g["role"], "format_retry": g["format_retry"], "text": g["text"]}
                        for g in episode.get("generations", [])
                    ],
                    actions=episode.get("actions", []),
                )
            except (OSError, ValueError, KeyError, TypeError):
                pass
        return JSONResponse(body, headers={"Cache-Control": "no-store"})

    @app.get("/stage1/training-report")
    def training_report():
        try:
            return response(load_report(worker.mode), "TrainingReport")
        except (OSError, ValueError, ValidationError):
            return response(error("unavailable", "Public training report is invalid"), "Error", 503)

    if stage2 is not None:
        from ..intake.interpreter import Interpreter
        from ..intake.store import DraftStore
        from .intake import local_request
        from .intake import router as intake_router

        intake_store = intake_store or DraftStore(
            stage2.state.ledger.directory / "intake", Interpreter()
        )
        app.state.intake_store = intake_store
        app.include_router(intake_router(intake_store, stage2, app, repository))

        @app.get(STAGE2_PREFIX + "/runs/{run_id}/transcript")
        def stage2_run_transcript(run_id: str, request: Request):
            if not local_request(request, fixture=app.state.worker.mode == "fixture"):
                return JSONResponse(
                    {
                        "schema_version": "stage2.v1",
                        "error": {
                            "code": "invalid_input",
                            "message": "Transcripts are available only to the local dashboard",
                            "field_errors": [],
                        },
                    },
                    status_code=403,
                    headers={"Cache-Control": "no-store"},
                )
            # Fails with the Stage 2 not-found envelope for unknown runs.
            stage2.state.ledger.snapshot(run_id)
            body = stage2_transcript(stage2.state.ledger.directory, run_id)
            provenance = intake_store.provenance_for_run(run_id)
            if provenance:
                body.update(provenance)
            from .turns import turn_records

            snapshot = stage2.state.ledger.snapshot(run_id)
            events = (
                stage2.state.ledger.events(run_id)
                if hasattr(stage2.state.ledger, "events")
                else []
            )
            body["turns"] = turn_records(
                snapshot, events, body["calls"], (provenance or {}).get("interpreter")
            )
            return JSONResponse(body, headers={"Cache-Control": "no-store"})

        app.mount(STAGE2_PREFIX, stage2, name="stage2")

    # Register the UI last so /health, /runs and the other API routes win.
    directory = (
        Path(web_dir) if web_dir is not None else Path(__file__).resolve().parents[4] / "web"
    )
    if (directory / "index.html").is_file():
        app.mount("/", StaticFiles(directory=directory, html=True), name="web")
    else:

        @app.get("/")
        def root():
            return {"service": "codejury-stage1", "api": "/docs"}

    return app


app = create_app(stage2=load_stage2_app())
