"""Fixed argv, no mounts, bounded streams, and whole-container watchdog."""

import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..contracts import REPO_ROOT
from ..contracts.intake import inspect_source, validate_json


class InfrastructureError(RuntimeError):
    pass


class Cancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class Result:
    actual_output: object
    exception_type: str | None
    input_mutated: bool
    duration_ms: int
    trace: list[str]
    trace_truncated: bool


class DockerRunner:
    context = "colima-codejury-stage1"

    def __init__(self, config: Path | None = None):
        path = config or REPO_ROOT / "backend/config/runner.yaml"
        settings = yaml.safe_load(path.read_text())
        self.image = settings["image_id"]
        if not isinstance(self.image, str) or not self.image.startswith("sha256:"):
            raise InfrastructureError("Runner image digest has not been built and pinned")

    def docker(self, *args: str) -> list[str]:
        return ["docker", "--context", self.context, *args]

    def ready(self) -> dict:
        config = Path.home() / ".colima/codejury-stage1/colima.yaml"
        try:
            vm = yaml.safe_load(config.read_text())
            effective = yaml.safe_load(
                (Path.home() / ".colima/_lima/colima-codejury-stage1/lima.yaml").read_text()
            )
            if (
                vm.get("mounts")
                or vm.get("forwardAgent")
                or effective.get("mounts")
                or effective.get("ssh", {}).get("forwardAgent")
            ):
                raise InfrastructureError(
                    "Dedicated VM must have no host directory or SSH agent shares"
                )
            info = subprocess.run(
                self.docker("image", "inspect", self.image),
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            image = json.loads(info.stdout)[0]
            if image["Architecture"] != "arm64" or image["Id"] != self.image:
                raise InfrastructureError("Runner image architecture/digest mismatch")
        except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
            raise InfrastructureError("Dedicated runner VM/image unavailable") from exc
        return {"image_id": self.image, "architecture": image["Architecture"], "host_mounts": []}

    def argv(self, name: str) -> list[str]:
        return self.docker(
            "create",
            "--name",
            name,
            "--label",
            f"codejury.worker-pid={os.getpid()}",
            "--pull",
            "never",
            "--platform",
            "linux/arm64",
            "--network",
            "none",
            "--user",
            "65532:65532",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "128m",
            "--memory-swap",
            "128m",
            "--pids-limit",
            "16",
            "--cpus",
            "1",
            "--init",
            "--log-driver",
            "none",
            "-i",
            self.image,
        )

    def cleanup_worker(self, pid):
        """Only our labelled jobs belonging to a terminated native worker."""
        listed = subprocess.run(
            self.docker("ps", "-aq", "--filter", f"label=codejury.worker-pid={int(pid)}"),
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        for container in listed.stdout.splitlines():
            if len(container) == 12 and all(c in "0123456789abcdef" for c in container):
                subprocess.run(
                    self.docker("rm", "-f", container), capture_output=True, timeout=10, check=True
                )

    def inspect_job(self, name: str) -> dict:
        inspected = subprocess.run(
            self.docker("inspect", name), capture_output=True, text=True, check=True, timeout=10
        )
        job = json.loads(inspected.stdout)[0]
        host = job["HostConfig"]
        if (
            job["Mounts"]
            or host["Binds"]
            or host["Privileged"]
            or host["NetworkMode"] != "none"
            or not host["ReadonlyRootfs"]
            or job["Config"]["User"] != "65532:65532"
            or host["CapDrop"] != ["ALL"]
            or "no-new-privileges" not in host["SecurityOpt"]
            or host["Memory"] != 128 * 1024 * 1024
            or host["PidsLimit"] != 16
        ):
            raise InfrastructureError("Container isolation inspection failed")
        return {
            "mounts": [],
            "network": "none",
            "read_only": True,
            "user": "65532:65532",
            "memory_bytes": host["Memory"],
            "pids_limit": host["PidsLimit"],
        }

    def execute(
        self, source: str, function_name: str, args: list, cancel: threading.Event | None = None
    ) -> Result:
        return self._execute(source, function_name, [args], cancel, batch=False)[0]

    def execute_many(self, source, function_name, batch_args, cancel=None, *, deadline=None):
        if not 1 <= len(batch_args) <= 8:
            raise ValueError("Batch must contain 1–8 invocations")
        return self._execute(
            source, function_name, batch_args, cancel, batch=True, deadline=deadline
        )

    def _execute(self, source, function_name, batch_args, cancel, *, batch, deadline=None):
        for args in batch_args:
            inspect_source(source, function_name, len(args))
            validate_json(args)
        self.ready()
        if cancel is not None and cancel.is_set():
            raise Cancelled("Run cancelled before execution")
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("Episode deadline reached before sandbox job")
        name = "codejury-job-" + uuid.uuid4().hex
        payload = json.dumps(
            {
                "source": source,
                "function_name": function_name,
                ("batch_args" if batch else "args"): batch_args if batch else batch_args[0],
            }
        ).encode()
        if len(payload) > 65536:
            raise ValueError("Job input too large")
        output, errors = bytearray(), bytearray()
        overflow = threading.Event()
        try:
            subprocess.run(self.argv(name), capture_output=True, check=True, timeout=15)
            self.inspect_job(name)
            if cancel is not None and cancel.is_set():
                raise Cancelled("Run cancelled during sandbox creation")
            process = subprocess.Popen(
                self.docker("start", "-ai", name),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except (OSError, subprocess.SubprocessError, InfrastructureError, Cancelled) as exc:
            subprocess.run(
                self.docker("rm", "-f", name), capture_output=True, check=False, timeout=10
            )
            if isinstance(exc, Cancelled):
                raise
            raise InfrastructureError("Sandbox creation failed") from exc

        def drain(stream, target):
            while block := os.read(stream.fileno(), 4096):
                target.extend(block[: max(0, 65536 - len(target))])
                if len(target) >= 65536:
                    overflow.set()

        readers = [
            threading.Thread(target=drain, args=(stream, target), daemon=True)
            for stream, target in ((process.stdout, output), (process.stderr, errors))
        ]
        for reader in readers:
            reader.start()
        start = time.monotonic()
        try:
            process.stdin.write(payload)
            process.stdin.close()
            while process.poll() is None:
                if cancel is not None and cancel.is_set():
                    raise Cancelled("Run cancelled during execution")
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError("Episode deadline reached during sandbox job")
                if overflow.is_set() or time.monotonic() - start > (
                    4 + 3 * len(batch_args) if batch else 4
                ):
                    return [
                        Result(
                            None,
                            "OutputLimitExceeded" if overflow.is_set() else "TimeoutError",
                            False,
                            int((time.monotonic() - start) * 1000),
                            [],
                            overflow.is_set(),
                        )
                        for _ in batch_args
                    ]
                time.sleep(0.02)
            for reader in readers:
                reader.join(timeout=1)
            if process.returncode != 0:
                raise InfrastructureError("Sandbox worker failed; no candidate outcome available")
            envelope = json.loads(output)
            bodies = envelope["results"] if batch else [envelope]
            if len(bodies) != len(batch_args):
                raise ValueError("Batch result count mismatch")
            results = []
            for body in bodies:
                if set(body) != set(Result.__dataclass_fields__):
                    raise ValueError("Invalid worker result envelope")
                validate_json(body["actual_output"])
                if type(body["input_mutated"]) is not bool or type(body["duration_ms"]) is not int:
                    raise ValueError("Invalid worker result types")
                if body["exception_type"] is not None and type(body["exception_type"]) is not str:
                    raise ValueError("Invalid exception type")
                if type(body["trace"]) is not list or any(
                    type(x) is not str for x in body["trace"]
                ):
                    raise ValueError("Invalid trace")
                if type(body["trace_truncated"]) is not bool:
                    raise ValueError("Invalid truncation flag")
                results.append(Result(**body))
            return results
        except (json.JSONDecodeError, ValueError, BrokenPipeError) as exc:
            raise InfrastructureError("Malformed sandbox output") from exc
        finally:
            subprocess.run(
                self.docker("rm", "-f", name), capture_output=True, timeout=10, check=False
            )
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for reader in readers:
                reader.join(timeout=1)
            for stream in (process.stdout, process.stderr):
                stream.close()
