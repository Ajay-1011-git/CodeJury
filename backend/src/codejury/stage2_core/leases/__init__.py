"""Kernel-backed Mac compute lease; crash recovery never relies on PID guesses."""

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

KINDS = {"runtime", "training", "teacher", "benchmark"}


class LeaseBusy(RuntimeError):
    pass


class ComputeLease:
    def __init__(
        self,
        path: Path | None = None,
        *,
        owner: str,
        job_id: str,
        kind: str,
        cancel: Event | None = None,
    ):
        if not owner or not job_id or kind not in KINDS:
            raise ValueError("Lease needs owner, job identity and supported kind")
        self.path = (
            Path(path)
            if path is not None
            else Path(f"/private/tmp/codejury-compute-{os.getuid()}.lock")
        )
        self.owner, self.job_id, self.kind = owner, job_id, kind
        self.cancel = cancel if cancel is not None else Event()
        self.fd = None

    def acquire(self):
        self.check_cancel()
        if self.fd is not None:
            raise ValueError("Lease already acquired")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(fd)
            raise LeaseBusy("Another runtime/training/teacher/benchmark owns compute") from exc
        try:
            self.check_cancel()
            metadata = {
                "pid": os.getpid(),
                "owner": self.owner,
                "job_id": self.job_id,
                "kind": self.kind,
                "started_utc": datetime.now(timezone.utc).isoformat(),
            }
            os.ftruncate(fd, 0)
            os.write(fd, json.dumps(metadata).encode())
            os.fsync(fd)
        except BaseException:
            os.close(fd)
            raise
        self.fd = fd
        return self

    def check_cancel(self) -> None:
        if self.cancel.is_set():
            raise InterruptedError("Compute job cancelled")

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        # Never unlink: replacing the inode would permit two simultaneous lock owners.

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *_):
        self.release()
