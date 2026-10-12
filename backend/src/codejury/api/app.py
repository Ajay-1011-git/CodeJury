"""Stage 1 endpoints with frozen success/error envelopes and one durable slot."""

import json
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jsonschema import ValidationError
from starlette.exceptions import HTTPException

from ..contracts import validate
from ..contracts.intake import IntakeError, validate_request
from ..controller.worker import LocalWorker
from ..storage import Store
from .repository import Busy, Repository
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
            }
        ],
    }


def create_app(store=None, worker=None) -> FastAPI:
    store = store or Store()
    repository = Repository(store)
    worker = worker or LocalWorker(store)

    @asynccontextmanager
    async def lifespan(_app):
        repository.recover()
        yield
        worker.close()

    app = FastAPI(title="CodeJury Stage 1", lifespan=lifespan)
    app.state.store, app.state.worker = store, worker
    app.state.repository = repository
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

    @app.get("/")
    def root():
        return {"service": "codejury-stage1", "api": "/docs"}

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

    @app.get("/stage1/training-report")
    def training_report():
        try:
            return response(load_report(worker.mode), "TrainingReport")
        except (OSError, ValueError, ValidationError):
            return response(error("unavailable", "Public training report is invalid"), "Error", 503)

    return app


app = create_app()
