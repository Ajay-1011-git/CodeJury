"""TEST-ONLY sandbox double. Runs the trusted worker entrypoint in a local subprocess.

LABEL: FIXTURE_HOST_EXEC. This executes controlled test-fixture sources on the host to verify
logic above the sandbox seam. It is NOT isolation, is never imported by the live factory and
proves nothing about Docker/VM isolation (those checks stay pending until a native run).
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from codejury.stage2_tools.runner.base import (
    Cancelled,
    InfrastructureError,
    WatchdogTimeout,
    validate_envelope,
)

ENTRY = Path(__file__).resolve().parents[2] / "src/codejury/stage2_tools/runner/entry.py"
MODE = "FIXTURE_HOST_EXEC"


class FixtureHostSandbox:
    runtime_hash = "f" * 64
    mode = MODE

    def __init__(self, wall_s: float = 12.0):
        self.wall_s = wall_s
        self.jobs = 0
        self.calls = 0

    def run(self, job: dict, cancel: threading.Event | None = None) -> dict:
        if cancel is not None and cancel.is_set():
            raise Cancelled("cancelled")
        self.jobs += 1
        self.calls += len(job["calls"])
        proc = subprocess.Popen(
            [sys.executable, "-I", str(ENTRY)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            proc.stdin.write(json.dumps(job).encode())
            proc.stdin.close()
            deadline = time.monotonic() + self.wall_s
            while proc.poll() is None:
                if cancel is not None and cancel.is_set():
                    raise Cancelled("cancelled")
                if time.monotonic() > deadline:
                    raise WatchdogTimeout("watchdog")
                time.sleep(0.01)
            out = proc.stdout.read()
            if proc.returncode != 0:
                raise InfrastructureError("worker failed")
            envelope = json.loads(out)
            validate_envelope(envelope, len(job["calls"]))
            return envelope
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            proc.stdout.close()
            proc.stderr.close()
