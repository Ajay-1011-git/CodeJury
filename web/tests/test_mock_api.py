import json
import os
import threading
import time
import unittest
import urllib.request
import urllib.error
from http.server import HTTPServer

from web.tools.mock_api import load_fixtures, MockServerState, make_handler

class MockApiIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts_dir = "contracts"
        cls.fixtures = load_fixtures(cls.contracts_dir)
        cls.port = 8011
        cls.host = "127.0.0.1"
        cls.state = MockServerState(cls.fixtures, scenario="supported")
        handler = make_handler(cls.state)
        cls.server = HTTPServer((cls.host, cls.port), handler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://{cls.host}:{cls.port}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        # Reset state active run between tests
        self.state.active_run = None
        self.state.scenario = "supported"
        self.state.unavailable = False

    def _request(self, path, method="GET", body=None, headers=None):
        url = f"{self.base_url}{path}"
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)
        data = None
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body).encode("utf-8")
                req_headers["Content-Type"] = "application/json"
            elif isinstance(body, bytes):
                data = body
            elif isinstance(body, str):
                data = body.encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req) as res:
                content = res.read().decode("utf-8")
                json_data = json.loads(content) if content else None
                return res.status, json_data, res.headers
        except urllib.error.HTTPError as err:
            content = err.read().decode("utf-8")
            try:
                json_data = json.loads(content)
            except Exception:
                json_data = content
            return err.code, json_data, err.headers

    def test_health_and_examples(self):
        status, health, headers = self._request("/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["schema_version"], "stage1.v1")
        self.assertEqual(health["runtime_mode"], "fixture")
        self.assertIn("no-cache", headers.get("Cache-Control", ""))

        status, examples, _ = self._request("/examples")
        self.assertEqual(status, 200)
        self.assertEqual(examples["schema_version"], "stage1.v1")
        self.assertIsInstance(examples["examples"], list)
        self.assertGreater(len(examples["examples"]), 0)

    def test_cors_options(self):
        status, _, headers = self._request("/runs", method="OPTIONS", headers={"Origin": "http://127.0.0.1:8080"})
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "http://127.0.0.1:8080")

    def test_post_run_lifecycle_and_report(self):
        create_payload = self.fixtures["run_create"]
        status, accepted, _ = self._request("/runs", method="POST", body=create_payload)
        self.assertEqual(status, 202)
        self.assertEqual(accepted["status"], "queued")
        self.assertEqual(accepted["runtime_mode"], "fixture")
        run_id = accepted["run_id"]
        self.assertTrue(run_id.startswith("run-mock-"))

        # Poll 0: queued
        status, snap0, _ = self._request(f"/runs/{run_id}")
        self.assertEqual(status, 200)
        self.assertEqual(snap0["status"], "queued")
        self.assertIsNone(snap0["decision"])

        # Early report query should return 409
        status, err_rep, _ = self._request(f"/runs/{run_id}/report")
        self.assertEqual(status, 409)
        self.assertEqual(err_rep["error"]["code"], "RUN_NOT_TERMINAL")

        # Poll 1: running
        status, snap1, _ = self._request(f"/runs/{run_id}")
        self.assertEqual(status, 200)
        self.assertEqual(snap1["status"], "running")

        # Poll 2: terminal (supported_patch)
        status, snap2, _ = self._request(f"/runs/{run_id}")
        self.assertEqual(status, 200)
        self.assertEqual(snap2["status"], "supported_patch")
        self.assertIsNotNone(snap2["decision"])
        self.assertEqual(snap2["decision"]["selected_candidate_id"], "cand-001")

        # GET candidate
        status, cand, _ = self._request(f"/runs/{run_id}/candidates/cand-001")
        self.assertEqual(status, 200)
        self.assertEqual(cand["candidate_id"], "cand-001")
        self.assertEqual(cand["origin"], "fixer_a")

        # GET terminal report succeeds
        status, rep, _ = self._request(f"/runs/{run_id}/report")
        self.assertEqual(status, 200)
        self.assertEqual(rep["status"], "supported_patch")

    def test_cancel_flow(self):
        create_payload = self.fixtures["run_create"]
        status, accepted, _ = self._request("/runs", method="POST", body=create_payload)
        self.assertEqual(status, 202)
        run_id = accepted["run_id"]

        # Cancel run
        status, cancelled_snap, _ = self._request(f"/runs/{run_id}/cancel", method="POST", body={})
        self.assertEqual(status, 200)
        self.assertEqual(cancelled_snap["status"], "cancelled")
        self.assertIn("cancelled", cancelled_snap["termination_reason"].lower())

    def test_cursor_idempotence_and_events(self):
        create_payload = self.fixtures["run_create"]
        status, accepted, _ = self._request("/runs", method="POST", body=create_payload)
        run_id = accepted["run_id"]

        # GET events after=0
        status, page1, _ = self._request(f"/runs/{run_id}/events?after=0")
        self.assertEqual(status, 200)
        self.assertGreater(len(page1["events"]), 0)
        self.assertGreater(page1["next_after"], 0)

        # Idempotence: query with after=2 twice
        status, page_a, _ = self._request(f"/runs/{run_id}/events?after=2")
        status, page_b, _ = self._request(f"/runs/{run_id}/events?after=2")
        self.assertEqual(status, 200)
        self.assertEqual(page_a["events"], page_b["events"])
        self.assertEqual(page_a["next_after"], page_b["next_after"])

        # Invalid after parameter returns 422
        status, err, _ = self._request(f"/runs/{run_id}/events?after=-5")
        self.assertEqual(status, 422)
        self.assertEqual(err["error"]["code"], "INVALID_QUERY")

        status, err, _ = self._request(f"/runs/{run_id}/events?after=notanumber")
        self.assertEqual(status, 422)

    def test_unknown_ids_404(self):
        status, err, _ = self._request("/runs/unknown-run-id-123")
        self.assertEqual(status, 404)
        self.assertEqual(err["error"]["code"], "RUN_NOT_FOUND")

        # Candidate 404
        create_payload = self.fixtures["run_create"]
        status, accepted, _ = self._request("/runs", method="POST", body=create_payload)
        status, err, _ = self._request(f"/runs/{accepted['run_id']}/candidates/unknown-cand-xyz")
        self.assertEqual(status, 404)
        self.assertEqual(err["error"]["code"], "CANDIDATE_NOT_FOUND")

    def test_non_json_input_422(self):
        status, err, _ = self._request("/runs", method="POST", body="<not-valid-json/>", headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 422)
        self.assertEqual(err["error"]["code"], "INVALID_JSON")

    def test_busy_run_slot_409(self):
        create_payload = self.fixtures["run_create"]
        status, _, _ = self._request("/runs", method="POST", body=create_payload)
        self.assertEqual(status, 202)

        # While still queued (poll 0), immediately submitting second run gives 409
        status, err, _ = self._request("/runs", method="POST", body=create_payload)
        self.assertEqual(status, 409)
        self.assertEqual(err["error"]["code"], "RUN_SLOT_BUSY")

    def test_service_unavailable_503(self):
        self.state.unavailable = True
        status, err, _ = self._request("/health")
        self.assertEqual(status, 503)
        self.assertEqual(err["error"]["code"], "SERVICE_UNAVAILABLE")

        status, err, _ = self._request("/runs", method="POST", body=self.fixtures["run_create"])
        self.assertEqual(status, 503)

    def test_all_scenarios(self):
        scenarios = ["unresolved", "infrastructure_error", "invalid_input", "cancelled"]
        for scen in scenarios:
            self.state.scenario = scen
            self.state.active_run = None
            status, accepted, _ = self._request("/runs", method="POST", body=self.fixtures["run_create"])
            self.assertEqual(status, 202)
            run_id = accepted["run_id"]
            # Poll to terminal
            self._request(f"/runs/{run_id}")  # poll 0 (queued)
            self._request(f"/runs/{run_id}")  # poll 1 (running)
            status, snap, _ = self._request(f"/runs/{run_id}")  # poll 2 (terminal)
            self.assertEqual(status, 200)
            self.assertEqual(snap["status"], scen)
            self.assertEqual(snap["runtime_mode"], "fixture")

    def test_training_report_modes(self):
        self.state.scenario = "supported"
        status, rep_default, _ = self._request("/stage1/training-report")
        self.assertEqual(status, 200)
        self.assertEqual(rep_default["status"], "not_started")

        self.state.scenario = "completed_training"
        status, rep_comp, _ = self._request("/stage1/training-report")
        self.assertEqual(status, 200)
        self.assertEqual(rep_comp["status"], "completed")

if __name__ == "__main__":
    unittest.main()
