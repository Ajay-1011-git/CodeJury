"""Long-lived native process, JSON IPC and cooperative/forced cancellation."""

import json
import multiprocessing
import os
import threading
import time

from ..contracts import canonical_json, checked
from ..leases import ComputeLease
from ..registry import Registry
from .engine import ModelEngine, Refused, preflight, response


def _child(connection, cancel, stop, manifest_path):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    backend = None
    lease = None
    try:
        registry = Registry(manifest_path)
        lease = ComputeLease(
            owner="stage2-core", job_id="model-worker", kind="runtime", cancel=stop
        ).acquire()
        from .native import MLXBackend

        backend = MLXBackend(registry)
        engine = ModelEngine(registry, backend)
        parent = multiprocessing.parent_process()
        connection.send_bytes(
            canonical_json(
                {"kind": "ready", "pid": os.getpid(), "manifest_hash": registry.manifest_hash}
            )
        )
        while not stop.is_set() and parent.is_alive():
            if not connection.poll(0.1):
                continue
            envelope = json.loads(connection.recv_bytes(1024 * 1024))
            if envelope["operation"] == "inspect":
                connection.send_bytes(canonical_json({"kind": "inspection", **backend.inspect()}))
                continue
            if envelope["operation"] != "generate":
                raise ValueError("Unknown worker operation")
            request = checked(envelope["request"], "ModelRequest")
            result = engine.generate(
                request,
                cancel,
                deadline=envelope["deadline"],
                on_usage=lambda usage: connection.send_bytes(
                    canonical_json(
                        {"kind": "usage", "request_id": request["request_id"], "usage": usage}
                    )
                ),
            )
            connection.send_bytes(canonical_json({"kind": "response", "response": result}))
        backend.close()
        backend = None
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        try:
            connection.send_bytes(
                canonical_json({"kind": "fatal", "exception": type(exc).__name__})
            )
        except (OSError, BrokenPipeError):
            pass
    finally:
        if backend is not None:
            backend.close()
        connection.close()
        if lease is not None:
            lease.release()


class NativeModelPort:
    def __init__(self, registry, settings):
        self.registry, self.settings = registry, settings
        self.process = self.connection = self.cancel_event = self.stop_event = None
        self.lock = threading.Lock()
        self.seen = set()
        self.closed = False

    def readiness(self):
        result = self.registry.readiness()
        result["worker_state"] = (
            "closed"
            if self.closed
            else (
                "lazy"
                if self.process is None
                else "resident"
                if self.process.is_alive()
                else "failed"
            )
        )
        result["ready"] = result["ready"] and result["worker_state"] not in {"closed", "failed"}
        return result

    def _start(self, cancel, deadline):
        if self.process is not None:
            if not self.process.is_alive():
                raise RuntimeError("Native worker exited; explicitly close and recreate the port")
            return
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe(duplex=True)
        self.cancel_event, self.stop_event = context.Event(), context.Event()
        self.process = context.Process(
            target=_child,
            args=(child, self.cancel_event, self.stop_event, self.registry.path),
            daemon=True,
        )
        self.process.start()
        child.close()
        timeout = min(deadline, time.monotonic() + self.settings["startup_timeout_s"])
        while time.monotonic() < timeout:
            if cancel.is_set():
                self.close()
                raise Refused("cancelled", "cancelled", "Cancelled while loading native model")
            if self.connection.poll(self.settings["poll_interval_s"]):
                packet = json.loads(self.connection.recv_bytes(1024 * 1024))
                if packet["kind"] != "ready":
                    self.close()
                    if packet.get("exception") == "LeaseBusy":
                        raise Refused(
                            "error", "compute_busy", "Another job holds the Mac compute lease"
                        )
                    raise RuntimeError(
                        "Native worker could not acquire compute or load model: "
                        + packet.get("exception", "unknown")
                    )
                if packet.get("manifest_hash") != self.registry.manifest_hash:
                    self.close()
                    raise Refused(
                        "error", "registry_changed", "Registry changed before worker startup"
                    )
                return
        self.close()
        raise Refused(
            "budget_exhausted" if time.monotonic() >= deadline else "error",
            "startup_deadline",
            "Native model loading exceeded deadline",
        )

    def generate(self, request, cancel):
        request = checked(request, "ModelRequest")
        if not self.lock.acquire(blocking=False):
            return response(
                self.registry,
                request,
                status="error",
                code="worker_busy",
                message="A model request is already running",
            )
        latest = None
        try:
            if self.closed:
                raise Refused("error", "worker_closed", "Native model port is closed")
            if request["request_id"] in self.seen:
                raise Refused("error", "duplicate_request", "Request ID was already dispatched")
            self.seen.add(request["request_id"])
            if cancel.is_set():
                raise Refused("cancelled", "cancelled", "Cancelled before model dispatch")
            preflight(request, self.registry)
            deadline = time.monotonic() + request["remaining_budget"]["elapsed_ms"] / 1000
            self._start(cancel, deadline)
            self.cancel_event.clear()
            self.connection.send_bytes(
                canonical_json({"operation": "generate", "request": request, "deadline": deadline})
            )
            cancellation_started = None
            while True:
                if cancel.is_set() or time.monotonic() >= deadline:
                    self.cancel_event.set()
                    cancellation_started = cancellation_started or time.monotonic()
                if (
                    cancellation_started is not None
                    and time.monotonic() - cancellation_started
                    > (self.settings["shutdown_grace_s"])
                ):
                    self.close()
                    return response(
                        self.registry,
                        request,
                        status="cancelled" if cancel.is_set() else "budget_exhausted",
                        usage=latest,
                        code="worker_stopped_partial_cost",
                        message="Worker was stopped; token costs are the last reported lower bound",
                    )
                if self.connection.poll(self.settings["poll_interval_s"]):
                    packet = json.loads(self.connection.recv_bytes(1024 * 1024))
                    if packet["kind"] == "usage":
                        if packet["request_id"] != request["request_id"]:
                            raise ValueError("Worker usage request ID mismatch")
                        latest = checked(packet["usage"], "ResourceUsage")
                    elif packet["kind"] == "response":
                        result = checked(packet["response"], "ModelResponse")
                        if (
                            result["request_id"] != request["request_id"]
                            or result["role"] != request["role"]
                        ):
                            raise ValueError("Worker response identity mismatch")
                        if any(
                            result[key] != value
                            for key, value in self.registry.identity(request["role"]).items()
                        ):
                            raise ValueError(
                                "Worker response model/adapter/config provenance mismatch"
                            )
                        return result
                    else:
                        raise RuntimeError("Native worker failed")
                if not self.process.is_alive():
                    raise RuntimeError("Native worker exited during request")
        except Refused as exc:
            return response(
                self.registry,
                request,
                status=exc.status,
                code=exc.code,
                message=exc.message,
                usage=latest,
            )
        except Exception as exc:
            self.close()
            return response(
                self.registry,
                request,
                status="error",
                code="worker_failure_partial_cost",
                message=type(exc).__name__ + "; costs are the last reported lower bound",
                usage=latest,
            )
        finally:
            self.lock.release()

    def start(self, cancel):
        """Acquire the actual cross-process lease before accepting an API run."""
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("Native worker is busy")
        try:
            if self.closed:
                raise RuntimeError("Native worker is closed")
            self._start(cancel, time.monotonic() + self.settings["startup_timeout_s"])
        finally:
            self.lock.release()

    def inspect(self):
        with self.lock:
            if self.process is None or not self.process.is_alive():
                raise RuntimeError("No resident native worker")
            self.connection.send_bytes(canonical_json({"operation": "inspect"}))
            if not self.connection.poll(self.settings["startup_timeout_s"]):
                self.close()
                raise TimeoutError("Native diagnostic timed out")
            packet = json.loads(self.connection.recv_bytes(1024 * 1024))
            if packet["kind"] != "inspection":
                raise RuntimeError("Invalid native diagnostic response")
            return {**packet, "pid": self.process.pid}

    def close(self):
        self.closed = True
        process = self.process
        if process is None:
            return
        self.stop_event.set()
        self.cancel_event.set()
        process.join(self.settings["shutdown_grace_s"])
        if process.is_alive():
            process.terminate()
            process.join(2)
        if process.is_alive():
            process.kill()
            process.join(2)
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
