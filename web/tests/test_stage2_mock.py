import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage2_mock  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def call(base, method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read() or b"null"), res.headers
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"null"), err.headers


class Mock(unittest.TestCase):
    def serve(self, scenario="audit-gap", **kw):
        server, state = stage2_mock.serve(0, scenario, **kw)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}", state

    def run_body(self):
        return json.loads((ROOT / "contracts/stage2-fixtures/run-create.json").read_text())

    def test_health_examples_and_always_fixture(self):
        base, _ = self.serve()
        status, health, headers = call(base, "GET", "/health")
        self.assertEqual((status, health["runtime_mode"]), (200, "fixture"))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(call(base, "GET", "/examples")[0], 200)

    def test_lifecycle_cursor_and_terminal_report(self):
        base, _ = self.serve()
        status, accepted, _ = call(base, "POST", "/runs", self.run_body())
        self.assertEqual((status, accepted["status"], accepted["runtime_mode"]), (202, "queued", "fixture"))
        run = accepted["run_id"]
        self.assertEqual(call(base, "GET", f"/runs/{run}/report")[0], 409)
        seen = []
        for expected in ("queued", "running", "supported_patch"):
            _, snap, _ = call(base, "GET", f"/runs/{run}")
            self.assertEqual(snap["status"], expected)
            _, page, _ = call(base, "GET", f"/runs/{run}/events?after={max(seen, default=0)}")
            self.assertTrue(all(e["event_id"] > max(seen, default=0) for e in page["events"]))
            seen += [e["event_id"] for e in page["events"]]
            self.assertEqual(page["next_after"], max(seen))
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(call(base, "GET", f"/runs/{run}/report")[0], 200)
        self.assertEqual(call(base, "GET", f"/runs/{run}/candidates/c-a")[0], 200)
        self.assertEqual(call(base, "GET", f"/runs/{run}/candidates/nope")[0], 404)

    def test_error_codes(self):
        base, _ = self.serve()
        bad = self.run_body()
        bad["schema_version"] = "stage1.v1"
        self.assertEqual(call(base, "POST", "/runs", bad)[0], 422)
        extra = self.run_body()
        extra["unknown"] = 1
        self.assertEqual(call(base, "POST", "/runs", extra)[0], 422)
        self.assertEqual(call(base, "GET", "/runs/missing")[0], 404)
        self.assertEqual(call(base, "GET", "/runs/run-mock-3")[0], 409)  # archived Stage 1 id
        self.assertEqual(call(base, "GET", "/runs/x/events?after=-1")[0], 404)
        call(base, "POST", "/runs", self.run_body())
        self.assertEqual(call(base, "POST", "/runs", self.run_body())[0], 409)  # busy
        self.assertEqual(call(base, "GET", "/runs/mock2-run-1/events?after=-1")[0], 422)

    def test_cancel_and_scenarios(self):
        base, _ = self.serve()
        _, acc, _ = call(base, "POST", "/runs", self.run_body())
        status, snap, _ = call(base, "POST", f"/runs/{acc['run_id']}/cancel", {})
        self.assertEqual((status, snap["status"]), (200, "cancelled"))
        for scenario, final in [("unresolved", "unresolved"), ("infrastructure_error", "infrastructure_error"),
                                ("invalid_input", "invalid_input"), ("cancelled", "cancelled")]:
            base, _ = self.serve(scenario)
            _, acc, _ = call(base, "POST", "/runs", self.run_body())
            for _ in range(3):
                _, snap, _ = call(base, "GET", f"/runs/{acc['run_id']}")
            self.assertEqual(snap["status"], final, scenario)

    def test_reports_and_unavailable(self):
        base, _ = self.serve(benchmark="not-run")
        self.assertEqual(call(base, "GET", "/stage2/benchmark-report")[1]["status"], "not_run")
        self.assertEqual(call(base, "GET", "/stage2/training-report")[0], 200)
        base, _ = self.serve(benchmark="completed")
        self.assertEqual(call(base, "GET", "/stage2/benchmark-report")[1]["status"], "completed")
        base, _ = self.serve(unavailable=True)
        self.assertEqual(call(base, "GET", "/health")[0], 503)
        self.assertEqual(call(base, "POST", "/runs", self.run_body())[0], 503)


if __name__ == "__main__":
    unittest.main()
