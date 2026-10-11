#!/usr/bin/env python3
"""
CodeJury Stage 1 — Automated Frontend & Seam Smoke Test Harness
Exercises static file loading, API seam routes, lifecycle polling, and terminal state transitions.
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

def check_url(url, expected_status=200):
    req = urllib.request.Request(url, headers={"Accept": "text/html,application/javascript,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, res.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)

def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))

def main():
    parser = argparse.ArgumentParser(description="CodeJury Stage 1 Frontend Smoke Harness")
    parser.add_argument("--web-port", type=int, default=8080, help="Web dev server port")
    parser.add_argument("--api-port", type=int, default=8001, help="Mock API port")
    args = parser.parse_args()

    print("=== Step 1: Launching Servers ===")
    p_api = subprocess.Popen(["python3", "web/tools/mock_api.py", "--port", str(args.api_port), "--scenario", "supported"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p_web = subprocess.Popen(["python3", "-m", "http.server", str(args.web_port), "--directory", "web"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)

    try:
        print("=== Step 2: Verifying Static Web Assets & JavaScript Modules ===")
        web_base = f"http://127.0.0.1:{args.web_port}"
        api_base = f"http://127.0.0.1:{args.api_port}"

        # index.html
        status, html = check_url(f"{web_base}/index.html")
        assert status == 200, f"Failed to load index.html (status {status})"
        assert "CodeJury" in html
        assert "Fixture demonstration — no live inference" in html
        assert "Stage 1 Prototype" in html
        assert "role-fixer-a" in html
        print("  ✓ index.html loaded with Stage 1 header, role topology, and fixture banner")

        # styles.css
        status, css = check_url(f"{web_base}/styles.css")
        assert status == 200
        assert "--bg-primary" in css
        print("  ✓ styles.css loaded")

        # JS modules
        modules = ["app.mjs", "api.mjs", "state.mjs", "input.mjs", "evidence.mjs", "result.mjs", "training.mjs"]
        for m in modules:
            status, code = check_url(f"{web_base}/src/{m}")
            assert status == 200, f"Module {m} returned status {status}"
            print(f"  ✓ web/src/{m} module loaded successfully")

        print("=== Step 3: Exercising API Seam & Polling Lifecycle ===")
        # Health check
        status, health_text = check_url(f"{api_base}/health")
        assert status == 200
        health = json.loads(health_text)
        assert health["schema_version"] == "stage1.v1"
        assert health["runtime_mode"] == "fixture"
        assert health["stage2_enabled"] is False
        print("  ✓ GET /health: 200 OK (runtime_mode: fixture, stage2_enabled: false)")

        # Examples
        status, ex_text = check_url(f"{api_base}/examples")
        assert status == 200
        examples = json.loads(ex_text)
        assert len(examples["examples"]) > 0
        print(f"  ✓ GET /examples: 200 OK ({len(examples['examples'])} examples loaded)")

        # Submit run
        sample_run = examples["examples"][0]["request"]
        status, accepted = post_json(f"{api_base}/runs", sample_run)
        assert status == 202
        run_id = accepted["run_id"]
        assert accepted["status"] == "queued"
        print(f"  ✓ POST /runs: 202 Accepted (run_id: {run_id})")

        # Poll lifecycle: queued -> running -> supported_patch
        status, snap0_text = check_url(f"{api_base}/runs/{run_id}")
        snap0 = json.loads(snap0_text)
        assert snap0["status"] == "queued"
        print(f"  ✓ GET /runs/{run_id} poll 0: status=queued")

        status, snap1_text = check_url(f"{api_base}/runs/{run_id}")
        snap1 = json.loads(snap1_text)
        assert snap1["status"] == "running"
        print(f"  ✓ GET /runs/{run_id} poll 1: status=running")

        status, snap2_text = check_url(f"{api_base}/runs/{run_id}")
        snap2 = json.loads(snap2_text)
        assert snap2["status"] == "supported_patch"
        assert snap2["decision"]["selected_candidate_id"] == "cand-001"
        print(f"  ✓ GET /runs/{run_id} poll 2: status=supported_patch (selected: cand-001)")

        # Events
        status, ev_text = check_url(f"{api_base}/runs/{run_id}/events?after=0")
        ev_page = json.loads(ev_text)
        assert len(ev_page["events"]) > 0
        print(f"  ✓ GET /runs/{run_id}/events: 200 OK ({len(ev_page['events'])} events returned)")

        # Candidate
        status, cand_text = check_url(f"{api_base}/runs/{run_id}/candidates/cand-001")
        cand = json.loads(cand_text)
        assert cand["candidate_id"] == "cand-001"
        assert cand["eligibility"] == "eligible"
        print("  ✓ GET /runs/{run_id}/candidates/cand-001: 200 OK (eligible repair candidate)")

        # Terminal report
        status, rep_text = check_url(f"{api_base}/runs/{run_id}/report")
        rep = json.loads(rep_text)
        assert rep["status"] == "supported_patch"
        print("  ✓ GET /runs/{run_id}/report: 200 OK (terminal snapshot report)")

        # Training report
        status, tr_text = check_url(f"{api_base}/stage1/training-report")
        tr = json.loads(tr_text)
        assert tr["schema_version"] == "stage1.v1"
        print(f"  ✓ GET /stage1/training-report: 200 OK (status: {tr['status']})")

        print("\n=======================================================")
        print("✅ FRONTEND SMOKE TEST HARNESS COMPLETED SUCCESSFULLY!")
        print("=======================================================")
        return 0

    finally:
        p_api.terminate()
        p_web.terminate()
        p_api.wait()
        p_web.wait()

if __name__ == "__main__":
    sys.exit(main())
