"""Additional /s2x endpoints; the canonical Stage 2 schema stays frozen."""

import json
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from jsonschema import ValidationError
from starlette.concurrency import run_in_threadpool

from codejury.intake.store import DraftConflict
from codejury.stage2_core.api.worker import Busy, Unavailable
from codejury.stage2_core.teacher.budget import Halt


def envelope(code, message, status):
    return JSONResponse(
        {"spec_version": 1, "error": {"code": code, "message": message}},
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


async def payload(request):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > 128 * 1024:
            raise ValueError("Intake payload too large")
        data.extend(chunk)
    return json.loads(data)


def local_request(request, *, fixture=False):
    hosts = {"localhost", "127.0.0.1"}
    if fixture:
        hosts.add("testserver")
    if request.url.hostname not in hosts:
        return False
    origin = request.headers.get("origin")
    if origin:
        try:
            value = urlparse(origin)
            if value.scheme not in {"http", "https"} or value.hostname not in hosts:
                return False
        except ValueError:
            return False
    return True


def router(store, stage2, main_app, repository):
    routes = APIRouter(prefix="/s2x")

    def allowed(request):
        return local_request(request, fixture=main_app.state.worker.mode == "fixture")

    @routes.post("/intake")
    async def infer_spec(request: Request):
        if not allowed(request):
            return envelope("forbidden", "Intake is available only to the local dashboard", 403)
        try:
            body = await payload(request)
            draft = await run_in_threadpool(store.create, body)
            return JSONResponse(draft, headers={"Cache-Control": "no-store"})
        except (ValueError, TypeError, RecursionError, ValidationError):
            return envelope("invalid_spec", "Code or interpretation failed intake validation", 422)
        except Halt:
            return envelope(
                "interpreter_unavailable",
                "Interpreter is unavailable or its configured budget/attempt cap is reached",
                503,
            )

    @routes.get("/intake/{identifier}")
    def get_spec(identifier: str, request: Request):
        if not allowed(request):
            return envelope("forbidden", "Drafts are available only to the local dashboard", 403)
        try:
            return JSONResponse(store.get(identifier), headers={"Cache-Control": "no-store"})
        except KeyError:
            return envelope("not_found", "Unknown intake draft", 404)

    @routes.post("/intake/{identifier}/approve")
    async def approve_spec(identifier: str, request: Request, background: BackgroundTasks):
        if not allowed(request):
            return envelope("forbidden", "Approval is available only to the local dashboard", 403)

        def submit(create):
            if stage2 is None or main_app.state.stage2_error:
                raise Unavailable("Stage 2 is unavailable")
            if repository.busy():
                raise Busy("Another local repair is running")
            accepted = stage2.state.worker.claim(create)
            background.add_task(stage2.state.worker.dispatch, accepted["run_id"])
            return accepted

        try:
            decisions = await payload(request)
            accepted = await run_in_threadpool(store.approve, identifier, decisions, submit)
            return JSONResponse(accepted, status_code=202, headers={"Cache-Control": "no-store"})
        except KeyError:
            return envelope("not_found", "Unknown intake draft", 404)
        except (Busy, DraftConflict):
            return envelope("busy", "A repair or a different approval already owns this case", 409)
        except Unavailable:
            return envelope(
                "unavailable",
                "Local jury or native compute is unavailable; retry the same draft later",
                503,
            )
        except (ValueError, TypeError, RecursionError, ValidationError):
            return envelope(
                "invalid_approval",
                "Approve valid domains, requirements and at least one example",
                422,
            )

    return routes
