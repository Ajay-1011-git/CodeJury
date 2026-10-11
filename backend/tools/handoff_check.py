"""CPU handoff audit; hardware checks are explicit and separately labelled."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from codejury.contracts import SCHEMA_SHA256

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
SHARED_BASE = "c0ef9625f8a7781433d4692222a18cc86a43ae02"


def command(argv, env=None, *, quiet=False):
    result = subprocess.run(argv, cwd=BACKEND, env=env, capture_output=True, text=True, check=False)
    if not quiet:
        print(result.stdout[-5000:])
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:] or "Handoff verification failed")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    args = parser.parse_args()
    command([sys.executable, "-m", "codejury.contracts.check", str(args.contracts)])
    paths = command(
        ["git", "-C", str(ROOT), "diff", "--name-only", SHARED_BASE + "...HEAD"], quiet=True
    ).splitlines()
    if any(not p.startswith("backend/") for p in paths):
        raise ValueError("Changes outside Ajay backend since saved shared base")
    tracked = command(["git", "-C", str(ROOT), "ls-files", "backend"], quiet=True).splitlines()
    forbidden = (
        "backend/.venv/",
        "backend/models/",
        "backend/artifacts/",
        "backend/checkpoints/",
        "backend/data/private/",
    )
    if any(p.startswith(forbidden) for p in tracked):
        raise ValueError("Private/large local artifacts must not be tracked")
    # CPU boundary tests deliberately exercise an unavailable live model. They must
    # not inherit machine-specific native settings from the later hardware pass.
    with tempfile.TemporaryDirectory(prefix="codejury-cpu-check-") as directory:
        cpu_env = {k: v for k, v in os.environ.items() if not k.startswith("CODEJURY_")}
        cpu_env.update(
            CODEJURY_MODEL_DIR=str(Path(directory) / "unavailable-model"),
            CODEJURY_ADAPTER_DIR=str(Path(directory) / "unavailable-adapter"),
            CODEJURY_ALLOW_RAW="0",
        )
        command([sys.executable, "-m", "pytest", "-m", "not sandbox and not mac", "-q"], cpu_env)
    if args.native:
        env = {**os.environ, "CODEJURY_SANDBOX_TESTS": "1", "CODEJURY_MODEL_TESTS": "1"}
        command(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_runner_policy.py",
                "tests/test_runner_sandbox.py",
                "-q",
            ],
            env,
        )
        command(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_model_views.py",
                "tests/test_model_adapter.py",
                "-q",
            ],
            env,
        )
        hardware = "Real sandbox and native model tests passed"
    else:
        hardware = "Not run by this CPU invocation; see separately recorded native/sandbox evidence"
    summary = {
        "commit": command(["git", "-C", str(ROOT), "rev-parse", "HEAD"], quiet=True).strip(),
        "shared_base": SHARED_BASE,
        "contract_sha256": SCHEMA_SHA256,
        "backend_only": True,
        "cpu_suite": "passed",
        "hardware": hardware,
        "ui_integration": "pending Sarvesh; no integrated Stage1 release claim",
    }
    out = BACKEND / "artifacts/handoff/check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
