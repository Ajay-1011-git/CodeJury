"""Run a real native repair episode outside the HTTP server."""

import argparse
import json
from pathlib import Path

from ..api.repository import Repository
from ..contracts import validate
from ..contracts.intake import validate_request
from ..storage import Store
from .loop import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    validate_request(request)
    store = Store()
    snapshot = Repository(store).claim(request, "live")
    snapshot = run(request, store, snapshot["run_id"], config=args.config)
    validate(snapshot, "RunSnapshot")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, indent=2) + "\n")
    print(
        json.dumps(
            {
                "run_id": snapshot["run_id"],
                "status": snapshot["status"],
                "usage": snapshot["usage"],
                "reason": snapshot["termination_reason"],
            }
        )
    )
    return 0 if snapshot["status"] in {"supported_patch", "unresolved"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
