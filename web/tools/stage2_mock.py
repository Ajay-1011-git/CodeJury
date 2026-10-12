#!/usr/bin/env python3
"""stage2.v1 mock API (standard library only).

Serves the SYNTHETIC fixtures from contracts/stage2-fixtures. It never executes input, never
trains, and always reports runtime_mode "fixture" (the UI shows a persistent banner).

  python3 web/tools/stage2_mock.py --port 8001 --scenario audit-gap
"""

import argparse
import copy
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ["audit-gap", "supported", "refusal", "stale", "withdraw", "unresolved", "cancelled",
             "infrastructure_error", "invalid_input"]
RUN_KEYS = {"schema_version", "source", "function_name", "contract_text", "domain_schema",
            "helper_interfaces", "requirements", "supplied_tests", "allowed_dependencies",
            "resource_profile", "policy_mode", "seed"}
TERMINAL = {"supported_patch", "unresolved", "invalid_input", "infrastructure_error", "cancelled"}


def load(contracts: Path) -> dict:
    directory = contracts / "stage2-fixtures"
    return {p.stem: json.loads(p.read_text()) for p in directory.glob("*.json")}


class State:
    def __init__(self, fx, scenario, unavailable, benchmark):
        self.fx, self.scenario, self.unavailable, self.benchmark = fx, scenario, unavailable, benchmark
        self.lock = threading.Lock()
        self.runs: dict[str, dict] = {}
        self.counter = 0

    def error(self, code, message, fields=()):
        return {"schema_version": "stage2.v1",
                "error": {"code": code, "message": message, "field_errors": list(fields)}}

    def terminal_snapshot(self, run_id):
        name = {"unresolved": "snapshot-unresolved", "cancelled": "snapshot-cancelled",
                "infrastructure_error": "snapshot-infrastructure_error",
                "invalid_input": "snapshot-invalid_input"}.get(self.scenario, "snapshot-supported")
        snap = copy.deepcopy(self.fx[name])
        snap["run_id"] = run_id
        if self.scenario == "stale":
            for cand in snap["candidates"]:
                if cand["eligibility"] == "eligible":
                    cand["verification_suite_hash"] = "0" * 64  # qualification no longer current
        return snap

    def snapshot(self, run_id, poll):
        run = self.runs[run_id]
        if run["cancelled"]:
            snap = copy.deepcopy(self.fx["snapshot-cancelled"])
            snap["run_id"] = run_id
            return snap
        if poll == 0:
            snap = copy.deepcopy(self.fx["snapshot-running"])
            snap.update(status="queued", phase="queued", run_id=run_id)
            return snap
        if poll == 1:
            snap = copy.deepcopy(self.fx["snapshot-running"])
            snap["run_id"] = run_id
            return snap
        return self.terminal_snapshot(run_id)

    def events(self, run_id, after, poll):
        events = copy.deepcopy(self.fx["events"]["events"])
        if self.scenario == "refusal":
            events += [
                {**copy.deepcopy(events[6]), "event_id": 13, "type": "action_refused",
                 "payload": {**events[6]["payload"], "message": "Judge chose a stale option; refused."}},
                {**copy.deepcopy(events[6]), "event_id": 14, "type": "action_selected",
                 "payload": {**events[6]["payload"], "message": "Fixed fallback selected after refusal."}},
            ]
        visible = events[: 4 if poll == 0 else 8 if poll == 1 else len(events)]
        for e in visible:
            e["run_id"] = run_id
        page = [e for e in visible if e["event_id"] > after][:500]
        return {"schema_version": "stage2.v1", "run_id": run_id, "events": page,
                "next_after": max([e["event_id"] for e in page], default=after)}


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CodeJuryStage2Mock"

        def log_message(self, *_):
            pass

        def send(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send(204, {})

        def route(self, method):
            path = urlparse(self.path)
            parts = [p for p in path.path.split("/") if p]
            if state.unavailable:
                return self.send(503, state.error("unavailable", "Live dependencies are unavailable."))
            fx = state.fx
            if method == "GET" and parts == ["health"]:
                return self.send(200, fx["health"])
            if method == "GET" and parts == ["examples"]:
                return self.send(200, fx["examples"])
            if method == "GET" and parts == ["stage2", "training-report"]:
                return self.send(200, fx["training-report"] if state.benchmark != "not-run"
                                 else fx["training-not-started"])
            if method == "GET" and parts == ["stage2", "benchmark-report"]:
                return self.send(200, fx["benchmark-report" if state.benchmark == "completed"
                                         else "benchmark-not-run"])
            if method == "POST" and parts == ["runs"]:
                return self.create()
            if len(parts) >= 2 and parts[0] == "runs":
                return self.run_route(method, parts, path)
            return self.send(404, state.error("not_found", "Unknown route."))

        def create(self):
            size = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(size) or b"null")
            except json.JSONDecodeError:
                return self.send(422, state.error("invalid_json", "Body is not JSON."))
            if not isinstance(body, dict) or body.get("schema_version") != "stage2.v1":
                return self.send(422, state.fx["error-version"])
            if set(body) != RUN_KEYS:
                extra = sorted(set(body) ^ RUN_KEYS)
                return self.send(422, state.error("invalid_request", "Unknown or missing keys.", extra))
            with state.lock:
                active = [r for r in state.runs.values() if not r["cancelled"] and r["polls"] < 3]
                if active:
                    return self.send(409, state.error("busy", "Another run owns the model and runner."))
                state.counter += 1
                run_id = f"mock2-run-{state.counter}"
                state.runs[run_id] = {"polls": 0, "cancelled": False}
            return self.send(202, {"schema_version": "stage2.v1", "run_id": run_id,
                                   "status": "queued", "runtime_mode": "fixture"})

        def run_route(self, method, parts, path):
            run_id = parts[1]
            if re.fullmatch(r"run-mock-\d+", run_id):
                return self.send(409, state.error("legacy_stage1_run", "Archived Stage 1 run id."))
            run = state.runs.get(run_id)
            if run is None:
                return self.send(404, state.error("unknown_run", f"Unknown run {run_id}."))
            tail = parts[2:]
            if method == "POST" and tail == ["cancel"]:
                run["cancelled"] = True
                return self.send(200, state.snapshot(run_id, run["polls"]))
            if method != "GET":
                return self.send(404, state.error("not_found", "Unknown route."))
            if not tail:
                snap = state.snapshot(run_id, run["polls"])
                run["polls"] += 1
                return self.send(200, snap)
            if tail == ["events"]:
                query = parse_qs(path.query)
                try:
                    after = int(query.get("after", ["0"])[0])
                    if after < 0:
                        raise ValueError
                except ValueError:
                    return self.send(422, state.error("bad_cursor", "after must be an integer >= 0.", ["after"]))
                return self.send(200, state.events(run_id, after, max(0, run["polls"] - 1)))
            if tail[0] == "candidates" and len(tail) == 2:
                snap = state.terminal_snapshot(run_id)
                for cand in snap["candidates"]:
                    if cand["candidate_id"] == tail[1]:
                        return self.send(200, cand)
                return self.send(404, state.error("unknown_candidate", "Unknown candidate."))
            if tail == ["report"]:
                if run["polls"] < 3 and not run["cancelled"]:
                    return self.send(409, state.error("not_terminal", "Run is not terminal yet."))
                if state.scenario == "withdraw" and not run["cancelled"]:
                    snap = state.terminal_snapshot(run_id)
                    snap = copy.deepcopy(state.fx["snapshot-infrastructure_error"])
                    snap["run_id"] = run_id
                    return self.send(200, snap)
                return self.send(200, state.snapshot(run_id, run["polls"]))
            return self.send(404, state.error("not_found", "Unknown route."))

        def do_GET(self):
            self.route("GET")

        def do_POST(self):
            self.route("POST")

    return Handler


def serve(port, scenario, unavailable=False, benchmark="completed", contracts=ROOT / "contracts"):
    state = State(load(contracts), scenario, unavailable, benchmark)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    return server, state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--scenario", choices=SCENARIOS, default="audit-gap")
    parser.add_argument("--benchmark", choices=["completed", "not-run"], default="completed")
    parser.add_argument("--unavailable", action="store_true")
    parser.add_argument("--contracts", type=Path, default=ROOT / "contracts")
    args = parser.parse_args()
    server, _ = serve(args.port, args.scenario, args.unavailable, args.benchmark, args.contracts)
    print(f"stage2 FIXTURE mock on http://127.0.0.1:{args.port} scenario={args.scenario}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
