#!/usr/bin/env python3
"""
CodeJury Stage 1 — Fixture-Only Mock API (stage1.v1)
Standard Library HTTP server emulating all Stage 1 endpoints for independent UI development.
"""

import argparse
import copy
import json
import os
import re
import sys
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

def load_fixtures(contracts_dir="contracts"):
    fixtures_dir = os.path.join(contracts_dir, "fixtures")
    fixture_files = {
        "health": "health.json",
        "examples": "examples.json",
        "run_create": "run-create.json",
        "run_accepted": "run-accepted.json",
        "candidate": "candidate.json",
        "error": "error.json",
        "event_page": "event-page.json",
        "snap_queued": "run-snapshot-queued.json",
        "snap_running": "run-snapshot-running.json",
        "snap_supported": "run-snapshot-supported.json",
        "snap_unresolved": "run-snapshot-unresolved.json",
        "snap_invalid": "run-snapshot-invalid-input.json",
        "snap_infra": "run-snapshot-infrastructure-error.json",
        "snap_cancelled": "run-snapshot-cancelled.json",
        "training_not_started": "training-report-not-started.json",
        "training_completed": "training-report-completed.json",
    }
    loaded = {}
    for key, filename in fixture_files.items():
        path = os.path.join(fixtures_dir, filename)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                loaded[key] = json.load(f)
        else:
            raise FileNotFoundError(f"Fixture file missing: {path}")
    return loaded

class MockServerState:
    def __init__(self, fixtures, scenario="supported", unavailable=False):
        self.fixtures = fixtures
        self.scenario = scenario
        self.unavailable = unavailable
        self.active_run = None

    def make_error(self, code, message, field_errors=None):
        return {
            "schema_version": "stage1.v1",
            "error": {
                "code": code,
                "message": message,
                "field_errors": field_errors or []
            }
        }

def make_handler(state):
    class MockHandler(BaseHTTPRequestHandler):
        def _set_cors_headers(self):
            origin = self.headers.get("Origin")
            allowed = ["http://127.0.0.1:8080", "http://localhost:8080"]
            if origin in allowed:
                self.send_header("Access-Control-Allow-Origin", origin)
            elif not origin:
                self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
            self.send_header("Access-Control-Max-Age", "600")

        def _send_json(self, status_code, body):
            data = json.dumps(body).encode("utf-8")
            self.send_response(status_code)
            self._set_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            self._set_cors_headers()
            self.end_headers()

        def do_GET(self):
            if state.unavailable:
                return self._send_json(503, state.make_error("SERVICE_UNAVAILABLE", "Model and runner sandbox unavailable."))

            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            if path == "":
                path = "/"

            if path == "/health":
                health = copy.deepcopy(state.fixtures["health"])
                health["runtime_mode"] = "fixture"
                return self._send_json(200, health)

            if path == "/examples":
                examples = copy.deepcopy(state.fixtures["examples"])
                return self._send_json(200, examples)

            if path == "/stage1/training-report":
                if state.scenario == "completed_training":
                    rep = copy.deepcopy(state.fixtures["training_completed"])
                else:
                    rep = copy.deepcopy(state.fixtures["training_not_started"])
                rep["runtime_mode"] = "fixture"
                return self._send_json(200, rep)

            # GET /runs/{run_id}
            match_run = re.match(r"^/runs/([^/]+)$", path)
            if match_run:
                run_id = match_run.group(1)
                if not state.active_run or state.active_run["run_id"] != run_id:
                    return self._send_json(404, state.make_error("RUN_NOT_FOUND", f"Run ID '{run_id}' not found."))
                
                snap = self._get_current_snapshot()
                return self._send_json(200, snap)

            # GET /runs/{run_id}/events
            match_events = re.match(r"^/runs/([^/]+)/events$", path)
            if match_events:
                run_id = match_events.group(1)
                if not state.active_run or state.active_run["run_id"] != run_id:
                    return self._send_json(404, state.make_error("RUN_NOT_FOUND", f"Run ID '{run_id}' not found."))

                query = parse_qs(parsed.query)
                after_val = query.get("after", ["0"])[0]
                try:
                    after_int = int(after_val)
                    if after_int < 0:
                        raise ValueError()
                except ValueError:
                    return self._send_json(422, state.make_error("INVALID_QUERY", "Parameter 'after' must be an integer >= 0."))

                all_events = state.active_run["events"]
                filtered = [ev for ev in all_events if ev["event_id"] > after_int]
                next_after = max([ev["event_id"] for ev in filtered]) if filtered else after_int

                return self._send_json(200, {
                    "schema_version": "stage1.v1",
                    "run_id": run_id,
                    "events": filtered,
                    "next_after": next_after
                })

            # GET /runs/{run_id}/candidates/{candidate_id}
            match_cand = re.match(r"^/runs/([^/]+)/candidates/([^/]+)$", path)
            if match_cand:
                run_id, cand_id = match_cand.groups()
                if not state.active_run or state.active_run["run_id"] != run_id:
                    return self._send_json(404, state.make_error("RUN_NOT_FOUND", f"Run ID '{run_id}' not found."))

                for cand in state.active_run["candidates"]:
                    if cand["candidate_id"] == cand_id:
                        return self._send_json(200, cand)
                return self._send_json(404, state.make_error("CANDIDATE_NOT_FOUND", f"Candidate '{cand_id}' not found."))

            # GET /runs/{run_id}/report
            match_report = re.match(r"^/runs/([^/]+)/report$", path)
            if match_report:
                run_id = match_report.group(1)
                if not state.active_run or state.active_run["run_id"] != run_id:
                    return self._send_json(404, state.make_error("RUN_NOT_FOUND", f"Run ID '{run_id}' not found."))

                snap = self._get_current_snapshot(advance=False)
                if snap["status"] in ("queued", "running"):
                    return self._send_json(409, state.make_error("RUN_NOT_TERMINAL", "Report is only available once run reaches a terminal state."))
                return self._send_json(200, snap)

            return self._send_json(404, state.make_error("NOT_FOUND", f"Endpoint {self.path} not found."))

        def do_POST(self):
            if state.unavailable:
                return self._send_json(503, state.make_error("SERVICE_UNAVAILABLE", "Model and runner sandbox unavailable."))

            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")

            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)

            if path == "/runs":
                # Check slot
                if state.active_run is not None:
                    # If existing run is still non-terminal, return 409
                    if state.active_run["poll_count"] < 2 and state.active_run["status"] not in ("cancelled", "supported_patch", "unresolved", "infrastructure_error", "invalid_input"):
                        return self._send_json(409, state.make_error("RUN_SLOT_BUSY", "Another run is currently active."))

                # Parse JSON
                try:
                    req_data = json.loads(raw_body.decode("utf-8"))
                except Exception:
                    return self._send_json(422, state.make_error("INVALID_JSON", "Request body must be valid JSON."))

                # Basic validation
                field_errors = []
                if not isinstance(req_data, dict):
                    field_errors.append("Request body must be an object")
                else:
                    if req_data.get("schema_version") != "stage1.v1":
                        field_errors.append("schema_version must be 'stage1.v1'")
                    if not req_data.get("source"):
                        field_errors.append("source must be non-empty string")
                    if not req_data.get("function_name"):
                        field_errors.append("function_name must be non-empty string")
                    if not req_data.get("contract_text"):
                        field_errors.append("contract_text must be non-empty string")
                    if not isinstance(req_data.get("input_domain"), list) or len(req_data.get("input_domain")) == 0:
                        field_errors.append("input_domain must be a non-empty array (1-3 domains)")
                    if not isinstance(req_data.get("supplied_tests"), list) or len(req_data.get("supplied_tests")) == 0:
                        field_errors.append("supplied_tests must be a non-empty array (1-30 tests)")
                    if req_data.get("resource_profile") != "stage1-demo":
                        field_errors.append("resource_profile must be 'stage1-demo'")

                if field_errors:
                    return self._send_json(422, state.make_error("VALIDATION_FAILED", "RunCreate validation failed.", field_errors))

                # Initialize new active run
                new_run_id = f"run-mock-{uuid.uuid4().hex[:8]}"
                scenario = state.scenario

                # Select base snapshot
                if scenario == "unresolved":
                    base_snap = state.fixtures["snap_unresolved"]
                elif scenario == "infrastructure_error":
                    base_snap = state.fixtures["snap_infra"]
                elif scenario == "invalid_input":
                    base_snap = state.fixtures["snap_invalid"]
                elif scenario == "cancelled":
                    base_snap = state.fixtures["snap_cancelled"]
                else:
                    base_snap = state.fixtures["snap_supported"]

                candidates = copy.deepcopy(base_snap["candidates"])
                events = copy.deepcopy(state.fixtures["event_page"]["events"])
                for ev in events:
                    ev["run_id"] = new_run_id

                state.active_run = {
                    "run_id": new_run_id,
                    "poll_count": 0,
                    "status": "queued",
                    "scenario": scenario,
                    "base_snap": base_snap,
                    "candidates": candidates,
                    "events": events
                }

                return self._send_json(202, {
                    "schema_version": "stage1.v1",
                    "run_id": new_run_id,
                    "status": "queued",
                    "runtime_mode": "fixture"
                })

            # POST /runs/{run_id}/cancel
            match_cancel = re.match(r"^/runs/([^/]+)/cancel$", path)
            if match_cancel:
                run_id = match_cancel.group(1)
                if not state.active_run or state.active_run["run_id"] != run_id:
                    return self._send_json(404, state.make_error("RUN_NOT_FOUND", f"Run ID '{run_id}' not found."))

                # Update status to cancelled
                state.active_run["status"] = "cancelled"
                state.active_run["poll_count"] = 99
                cancel_snap = copy.deepcopy(state.fixtures["snap_cancelled"])
                cancel_snap["run_id"] = run_id
                state.active_run["base_snap"] = cancel_snap
                return self._send_json(200, cancel_snap)

            return self._send_json(404, state.make_error("NOT_FOUND", f"Endpoint {self.path} not found."))

        def _get_current_snapshot(self, advance=True):
            run = state.active_run
            poll = run["poll_count"]
            run_id = run["run_id"]

            if run["status"] == "cancelled":
                snap = copy.deepcopy(state.fixtures["snap_cancelled"])
                snap["run_id"] = run_id
                return snap

            if poll == 0:
                snap = copy.deepcopy(state.fixtures["snap_queued"])
                snap["status"] = "queued"
            elif poll == 1:
                snap = copy.deepcopy(state.fixtures["snap_running"])
                snap["status"] = "running"
            else:
                snap = copy.deepcopy(run["base_snap"])

            snap["run_id"] = run_id
            snap["runtime_mode"] = "fixture"
            if advance:
                run["poll_count"] += 1
                run["status"] = snap["status"]
            return snap

        def log_message(self, format, *args):
            # Suppress default noisy access logs unless error
            pass

    return MockHandler

def run_mock_server(port=8001, host="127.0.0.1", scenario="supported", contracts="contracts", unavailable=False):
    fixtures = load_fixtures(contracts)
    state = MockServerState(fixtures, scenario=scenario, unavailable=unavailable)
    handler_class = make_handler(state)
    server = HTTPServer((host, port), handler_class)
    print(f"CodeJury Stage 1 Mock API running on http://{host}:{port} (scenario: {scenario})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Mock API.")
    finally:
        server.server_close()

def main():
    parser = argparse.ArgumentParser(description="CodeJury Stage 1 Mock API Server")
    parser.add_argument("--port", type=int, default=8001, help="Port to listen on (default 8001)")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default 127.0.0.1)")
    parser.add_argument("--contracts", default="contracts", help="Contracts directory path")
    parser.add_argument("--scenario", choices=["supported", "unresolved", "infrastructure_error", "invalid_input", "cancelled", "completed_training"],
                        default="supported", help="Simulated run outcome scenario")
    parser.add_argument("--unavailable", action="store_true", help="Simulate 503 Service Unavailable")
    args = parser.parse_args()

    run_mock_server(port=args.port, host=args.host, scenario=args.scenario, contracts=args.contracts, unavailable=args.unavailable)

if __name__ == "__main__":
    main()
