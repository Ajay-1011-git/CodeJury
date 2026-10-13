"""Live canonical Stage 2 API; archived Stage 1 evidence stays separate and read-only."""

import json
import os
import re
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jsonschema import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ..contract_check import REPO_ROOT, SCHEMA_HASH
from ..contracts import checked
from ..registry import local_path
from .worker import Busy, Unavailable, Worker


def response(body, definition, status=200):
    return JSONResponse(
        checked(body, definition), status_code=status, headers={"Cache-Control": "no-store"}
    )


def error(code, message, status):
    return response(
        {
            "schema_version": "stage2.v1",
            "error": {"code": code, "message": message, "field_errors": []},
        },
        "Error",
        status,
    )


def archived(run_id, path):
    if not Path(path).is_file():
        return False
    with sqlite3.connect("file:" + str(Path(path).resolve()) + "?mode=ro", uri=True) as db:
        return db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone() is not None


def create_app(
    config_path=None,
    model_port=None,
    tool_port=None,
    *,
    worker=None,
    web_dir=None,
    stage1_database=None,
    benchmark_path=None,
):
    if worker is None and config_path is not None and hasattr(config_path, "ledger"):
        worker, config_path = config_path, None
    worker = worker or Worker(
        runtime_config=config_path, model_port=model_port, tool_port=tool_port
    )
    ledger = worker.ledger
    legacy = stage1_database or local_path("artifacts/runs/runtime.sqlite3")
    benchmark = benchmark_path or local_path("docs/stage2_tools/results/benchmark-report.json")

    @asynccontextmanager
    async def lifespan(_app):
        worker.recover()
        yield
        worker.close()

    app = FastAPI(title="CodeJury Stage 2", lifespan=lifespan)
    app.state.worker, app.state.ledger = worker, ledger
    origins = os.getenv(
        "CODEJURY_STAGE2_ORIGINS", "http://127.0.0.1:8080,http://localhost:8080"
    ).split(",")
    if any(not re.fullmatch(r"http://(?:127\.0\.0\.1|localhost):[0-9]{1,5}", o) for o in origins):
        raise ValueError("Only explicit local development origins are supported")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Accept"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost"]
        + (["testserver"] if worker.mode == "fixture" else []),
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_query(_request, _exc):
        return error("invalid_input", "Invalid request parameter", 422)

    @app.exception_handler(HTTPException)
    async def http_error(_request, exc):
        if exc.status_code == 409 and exc.detail == "legacy_stage1_run":
            return error(
                "legacy_stage1_run", "Archived Stage 1 run; use the retained Stage 1 service", 409
            )
        return error("not_found", "Unknown route", exc.status_code)

    @app.exception_handler(KeyError)
    async def missing(_request, _exc):
        return error("not_found", "Unknown run or candidate", 404)

    def snapshot(run_id):
        try:
            return ledger.snapshot(run_id)
        except KeyError:
            if archived(run_id, legacy):
                raise HTTPException(409, "legacy_stage1_run") from None
            raise

    @app.get("/health")
    def health():
        return response(
            {
                "schema_version": "stage2.v1",
                "service": "codejury-stage2",
                "runtime_mode": worker.mode,
                "contract_hash": SCHEMA_HASH,
                **worker.health(),
            },
            "Health",
        )

    @app.get("/examples")
    def examples():
        public = json.loads((REPO_ROOT / "contracts/stage2-fixtures/examples.json").read_text())
        for item in public["examples"]:
            item["description"] = "Public mechanics demo; overlaps training families. Unscored."
        return response(public, "Examples")

    @app.post("/runs")
    async def create_run(request: Request, background: BackgroundTasks):
        try:
            raw = bytearray()
            async for chunk in request.stream():
                if len(raw) + len(chunk) > 256 * 1024:
                    raise ValueError("Oversized request")
                raw.extend(chunk)
            payload = checked(json.loads(raw), "RunCreate")
        except (ValueError, TypeError, ValidationError, RecursionError):
            return error("invalid_input", "Request violates the Stage 2 contract", 422)
        try:
            accepted = await run_in_threadpool(worker.claim, payload)
        except Busy:
            return error("busy", "Another repair owns the runtime slot", 409)
        except Unavailable:
            return error(
                "unavailable", "Required models, isolated tools or compute are unavailable", 503
            )
        except (ValueError, SyntaxError, ValidationError, KeyError):
            return error("invalid_input", "Unsupported source, domain or oracle requirements", 422)
        background.add_task(worker.dispatch, accepted["run_id"])
        return response(accepted, "RunAccepted", 202)

    @app.get("/runs/{run_id}")
    def get_run(run_id):
        return response(snapshot(run_id), "RunSnapshot")

    @app.get("/runs/{run_id}/events")
    def events(run_id, after: int = 0):
        snapshot(run_id)
        if after < 0:
            return error("invalid_input", "Event cursor must be nonnegative", 422)
        page = [e for e in ledger.events(run_id) if e["event_id"] > after][:500]
        return response(
            {
                "schema_version": "stage2.v1",
                "run_id": run_id,
                "events": page,
                "next_after": page[-1]["event_id"] if page else after,
            },
            "EventPage",
        )

    @app.get("/runs/{run_id}/candidates/{candidate_id}")
    def candidate(run_id, candidate_id):
        current = snapshot(run_id)
        own = next((c for c in current["candidates"] if c["candidate_id"] == candidate_id), None)
        if own is None:
            raise KeyError(candidate_id)
        return response(own, "Candidate")

    @app.post("/runs/{run_id}/cancel")
    def cancel(run_id):
        snapshot(run_id)
        return response(worker.cancel(run_id), "RunSnapshot")

    @app.get("/runs/{run_id}/report")
    def report(run_id):
        return response(snapshot(run_id), "RunSnapshot")

    @app.get("/stage2/training-report")
    def training_report():
        try:
            registry = worker.registry()
            cards = [a["card"] for _, a in sorted(registry.record["adapters"].items())]
        except (ValueError, OSError, KeyError):
            cards = []
        return response(
            {
                "schema_version": "stage2.v1",
                "runtime_mode": worker.mode,
                "cards": cards,
                "note": "Actual registered cards only. Pending roles are not completed; "
                "training/component checks do not establish final benchmark quality.",
            },
            "TrainingReport",
        )

    @app.get("/stage2/benchmark-report")
    def benchmark_report():
        if Path(benchmark).is_file():
            return response(json.loads(Path(benchmark).read_text()), "BenchmarkReport")
        return response(
            {
                "schema_version": "stage2.v1",
                "runtime_mode": worker.mode,
                "status": "not_run",
                "dataset_id": None,
                "dataset_manifest_hash": None,
                "rows": [],
                "paired_analysis_note": "Final benchmark has not run.",
                "limitations": ["All adapters/methods must freeze before final assessment."],
                "research_outcome": "not_measured",
            },
            "BenchmarkReport",
        )

    directory = Path(web_dir) if web_dir else REPO_ROOT / "web"
    if directory.is_dir():

        @app.get("/")
        def index():
            return FileResponse(directory / "stage2.html", headers={"Cache-Control": "no-store"})

        app.mount("/", StaticFiles(directory=directory), name="stage2-web")
    return app
