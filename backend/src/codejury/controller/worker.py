"""One native worker process per accepted job; no model work in HTTP handlers."""

import multiprocessing
import threading
from pathlib import Path

from ..api.repository import Repository
from ..storage import Store


def run_job(directory: str, run_id: str, cancellation):
    store = Store(Path(directory))
    repository = Repository(store)
    try:
        from .loop import run

        run(store.request(run_id), store, run_id, cancellation)
    except Exception:
        repository.finish(run_id, "infrastructure_error", "Native repair worker failed")


class LocalWorker:
    mode = "live"

    def __init__(self, store):
        self.store = store
        self.context = multiprocessing.get_context("spawn")
        self.process = None
        self.cancellation = None
        self.lock = threading.Lock()

    def health(self) -> dict:
        try:
            from ..models.worker import readiness

            return readiness()
        except ImportError:
            return {"model_ready": False, "sandbox_ready": False, "fixer_a_trained": False}

    def start(self, run_id: str) -> None:
        with self.lock:
            if self.process is not None:
                self.process.join(timeout=1)
                if self.process.is_alive():
                    raise RuntimeError("Previous worker still occupies the process slot")
            self.cancellation = self.context.Event()
            self.process = self.context.Process(
                target=run_job,
                args=(str(self.store.directory), run_id, self.cancellation),
                daemon=True,
            )
            self.process.start()
            process, cancellation = self.process, self.cancellation

            def watch():
                process.join()
                snapshot = self.store.snapshot(run_id)
                if snapshot["status"] in {"queued", "running"}:
                    Repository(self.store).finish(
                        run_id,
                        "cancelled" if cancellation.is_set() else "infrastructure_error",
                        "User cancelled repair"
                        if cancellation.is_set()
                        else "Native worker exited before completion",
                    )

            threading.Thread(target=watch, daemon=True).start()

    def cancel(self, run_id: str) -> bool:
        with self.lock:
            if self.cancellation is not None:
                self.cancellation.set()
            if self.process is not None:
                self.process.join(timeout=5)
                return not self.process.is_alive()
            return True

    def close(self) -> None:
        with self.lock:
            if self.cancellation is not None:
                self.cancellation.set()
            if self.process is not None:
                self.process.join(timeout=5)
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join(timeout=2)
