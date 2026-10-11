"""Schema-validated smoke on the running API; unavailable live model is reported honestly."""

import argparse
import json
from pathlib import Path

import httpx

from codejury.contracts import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    contracts = args.contract.parent
    with httpx.Client(base_url=args.base_url, timeout=20) as client:
        for path, definition, status in [
            ("/health", "Health", 200),
            ("/examples", "Examples", 200),
            ("/stage1/training-report", "TrainingReport", 200),
            ("/runs/unknown", "Error", 404),
        ]:
            result = client.get(path)
            assert result.status_code == status
            assert result.headers["cache-control"] == "no-store"
            validate(result.json(), definition, contracts)
            print(f"PASS GET {path}: {status} {definition}")
        health = client.get("/health").json()
        request = client.get("/examples").json()["examples"][0]["request"]
        result = client.post("/runs", json=request)
        expected = 202 if health["model_ready"] and health["sandbox_ready"] else 503
        assert result.status_code == expected
        validate(result.json(), "RunAccepted" if expected == 202 else "Error", contracts)
        if expected == 202:
            run_id = result.json()["run_id"]
            cancelled = client.post(f"/runs/{run_id}/cancel")
            validate(cancelled.json(), "RunSnapshot", contracts)
        invalid = client.post("/runs", json={})
        assert invalid.status_code == 422
        validate(invalid.json(), "Error", contracts)
        print(
            json.dumps(
                {
                    "runtime_mode": health["runtime_mode"],
                    "model_ready": health["model_ready"],
                    "sandbox_ready": health["sandbox_ready"],
                    "run_submission_status": expected,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
