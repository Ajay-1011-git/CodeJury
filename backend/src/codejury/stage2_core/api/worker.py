"""One durable API slot; native compute is acquired before accepting a run."""

import fcntl
import os
import threading

from ..controller import FixedController
from ..controller.learned import LearnedController
from ..factory import make_model_port
from ..intake import prepare
from ..ledger import Ledger
from ..registry import local_path


class Busy(RuntimeError):
    pass


class Unavailable(RuntimeError):
    pass


class Worker:
    mode = "live"

    def __init__(
        self,
        directory=None,
        *,
        runtime_config=None,
        tool_config=None,
        model_port=None,
        tool_port=None,
    ):
        self.ledger = Ledger(directory or local_path("artifacts/stage2_core/runtime"))
        self.runtime_config = runtime_config or local_path("config/stage2_core/runtime.yaml")
        self.tool_config = tool_config or local_path("../integration/stage2/tools.yaml")
        self.provided_model, self.provided_tool = model_port, tool_port
        self.lock = threading.Lock()
        self.active = self.thread = self.cancel_event = self.model = None
        self.service_fd = None
        self.closed = False

    def recover(self):
        # Hold a distinct server-instance lock; the native compute lease remains global.
        self.service_fd = os.open(
            self.ledger.directory / "api-instance.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        )
        try:
            fcntl.flock(self.service_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.service_fd)
            self.service_fd = None
            raise Busy("Another server owns this runtime ledger") from None
        return self.ledger.recover()

    def registry(self):
        if self.provided_model is not None:
            return self.provided_model.registry
        with make_model_port(self.runtime_config) as model:
            return model.registry

    def health(self):
        trained, model_ready, full = [], False, False
        try:
            registry = self.registry()
            trained = sorted(
                r
                for r, a in registry.record["adapters"].items()
                if a["card"]["status"] == "completed"
            )
            model_ready = {"fixer_a", "fixer_b"} <= set(trained)
            full = registry.readiness()["ready"]
        except (ValueError, OSError, KeyError):
            pass
        tools_ready = False
        try:
            from codejury.stage2_tools.factory import make_tool_port

            (self.provided_tool or make_tool_port(self.tool_config)).sandbox.ready()
            tools_ready = True
        except Exception:
            pass
        return {
            "model_ready": model_ready,
            "tools_ready": tools_ready,
            "trained_roles": trained,
            "full_stage2_ready": full and tools_ready,
            "default_policy": "learned" if full else "fixed",
        }

    def claim(self, create):
        if self.closed or not self.lock.acquire(blocking=False):
            raise Busy("A repair owns the runtime slot")
        model = None
        try:
            from codejury.stage2_tools.factory import make_tool_port
            from codejury.stage2_tools.oracles.gate import check_intake

            check_intake(create)
            problem, tests = prepare(create)
            try:
                model = self.provided_model or make_model_port(self.runtime_config)
                if model.closed:
                    model = make_model_port(self.runtime_config)
            except (ValueError, OSError, KeyError) as exc:
                raise Unavailable("Model registry is unavailable") from exc
            registry = model.registry
            ready = registry.readiness()
            if not {"fixer_a", "fixer_b"} <= set(registry.record["adapters"]):
                raise Unavailable("A/B adapters are unavailable")
            if create["policy_mode"] == "learned" and not ready["ready"]:
                raise Unavailable("The learned policy needs four completed trained roles")
            try:
                if self.provided_tool is not None:
                    from codejury.stage2_tools.port import ToolPortImpl

                    tool = ToolPortImpl(
                        self.provided_tool.sandbox, contracts=self.provided_tool.contracts
                    )
                else:
                    tool = make_tool_port(self.tool_config)
                tool.sandbox.ready()
            except Exception as exc:
                raise Unavailable("Isolated tools are unavailable") from exc
            cancel = threading.Event()
            try:
                model.start(cancel)
            except Exception as exc:
                raise Unavailable("Native compute is busy or unavailable") from exc
            identities = {r: registry.identity(r) for r in ["raw", *registry.record["adapters"]]}
            cls = LearnedController if create["policy_mode"] == "learned" else FixedController
            control = cls(
                self.ledger,
                model,
                tool,
                identities,
                manifest_hash=registry.manifest_hash,
                runtime_hash=tool.sandbox.runtime_hash,
                mode="live",
            )
            run_id = control.admit(problem, tests, cancel=cancel, seed=create["seed"])
            with self.ledger.connection() as db:
                db.execute("UPDATE runs SET status='queued' WHERE id=?", (run_id,))
            self.active, self.cancel_event, self.model = run_id, cancel, model
            self.thread = threading.Thread(
                target=self._run,
                args=(control, problem, tests, create["seed"]),
                name="stage2-runtime",
                daemon=True,
            )
            return {
                "schema_version": "stage2.v1",
                "run_id": run_id,
                "status": "queued",
                "runtime_mode": "live",
            }
        except BaseException:
            if model is not None:
                model.close()
            self.lock.release()
            raise

    def dispatch(self, run_id):
        if run_id != self.active or self.thread is None:
            raise ValueError("Unclaimed run dispatch")
        self.thread.start()

    def _run(self, control, problem, tests, seed):
        try:
            control.run(problem, tests, cancel=self.cancel_event, seed=seed, admitted=True)
        finally:
            self.model.close()
            self.active = self.cancel_event = self.model = None
            self.lock.release()

    def cancel(self, run_id):
        snapshot = self.ledger.snapshot(run_id)
        if snapshot["status"] in {"queued", "running"} and run_id == self.active:
            self.cancel_event.set()
        return self.ledger.snapshot(run_id)

    def close(self):
        self.closed = True
        if self.cancel_event is not None:
            self.cancel_event.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=10)
        if self.model is not None:
            self.model.close()
        if self.service_fd is not None:
            os.close(self.service_fd)
            self.service_fd = None
