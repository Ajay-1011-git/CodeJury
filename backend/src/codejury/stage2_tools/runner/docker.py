"""Docker/Colima sandbox: fixed argv, no mounts, bounded streams, whole-container watchdog.

Everything here is verified only against a live ARM64 Colima VM; with no daemon the self-test
reports those checks as pending rather than passed.
"""

import hashlib
import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

import yaml

from .base import Cancelled, InfrastructureError, WatchdogTimeout, validate_envelope

CONFIG = Path(__file__).resolve().parents[4] / "config/stage2_tools/runner.yaml"
ENTRY = Path(__file__).with_name("entry.py")


def load_config(path: Path | str | None = None) -> dict:
    return yaml.safe_load(Path(path or CONFIG).read_text())


class DockerSandbox:
    def __init__(self, config_path: Path | str | None = None, *, home: Path | None = None):
        self.config = load_config(config_path)
        limits = self.config["limits"]
        self.limits = limits
        self.image = os.environ.get(self.config["image_env"], "")
        if not self.image.startswith("sha256:"):
            raise InfrastructureError(
                f"{self.config['image_env']} must hold the built runner image id (sha256:...)"
            )
        self.home = home or Path.home()
        worker = hashlib.sha256(ENTRY.read_bytes()).hexdigest()
        self.runtime_hash = hashlib.sha256(
            json.dumps(
                {"image": self.image, "worker": worker, "limits": limits}, sort_keys=True
            ).encode()
        ).hexdigest()

    def docker(self, *args: str) -> list[str]:
        return ["docker", "--context", self.config["context"], *args]

    def ready(self) -> dict:
        profile = self.config["colima_profile"]
        try:
            vm = yaml.safe_load((self.home / f".colima/{profile}/colima.yaml").read_text())
            lima = yaml.safe_load(
                (self.home / f".colima/_lima/colima-{profile}/lima.yaml").read_text()
            )
            if (
                vm.get("mounts")
                or vm.get("forwardAgent")
                or lima.get("mounts")
                or lima.get("ssh", {}).get("forwardAgent")
            ):
                raise InfrastructureError("Runner VM must have no host directory or agent shares")
            info = subprocess.run(
                self.docker("image", "inspect", self.image),
                capture_output=True, text=True, check=True, timeout=10,
            )  # fmt: skip
            image = json.loads(info.stdout)[0]
            if image["Architecture"] != "arm64" or image["Id"] != self.image:
                raise InfrastructureError("Runner image architecture/digest mismatch")
        except InfrastructureError:
            raise
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError) as exc:
            raise InfrastructureError("Dedicated runner VM or image unavailable") from exc
        return {"image_id": self.image, "architecture": image["Architecture"], "host_mounts": []}

    def argv(self, name: str) -> list[str]:
        lim = self.limits
        return self.docker(
            "create", "--name", name,
            "--label", f"codejury.stage2-worker-pid={os.getpid()}",
            "--pull", "never", "--platform", "linux/arm64",
            "--network", "none", "--user", "65532:65532", "--read-only",
            "--tmpfs", f"/tmp:rw,noexec,nosuid,size={lim['tmpfs_mb']}m",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--memory", f"{lim['memory_mb']}m", "--memory-swap", f"{lim['memory_mb']}m",
            "--pids-limit", str(lim["pids"]), "--cpus", str(lim["cpus"]),
            "--init", "--log-driver", "none", "-i",
            self.image, *self.config["entrypoint"],
        )  # fmt: skip

    def inspect_job(self, name: str) -> dict:
        lim = self.limits
        out = subprocess.run(
            self.docker("inspect", name), capture_output=True, text=True, check=True, timeout=10
        )
        job = json.loads(out.stdout)[0]
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
            or host["Memory"] != lim["memory_mb"] * 1024 * 1024
            or host["PidsLimit"] != lim["pids"]
        ):
            raise InfrastructureError("Container isolation inspection failed")
        return {"mounts": [], "network": "none", "read_only": True, "user": "65532:65532",
                "memory_bytes": host["Memory"], "pids_limit": host["PidsLimit"]}  # fmt: skip

    def cleanup_orphans(self) -> int:
        """Remove labelled jobs from earlier workers of this user; returns how many."""
        listed = subprocess.run(
            self.docker("ps", "-aq", "--filter", "label=codejury.stage2-worker-pid"),
            capture_output=True, text=True, check=True, timeout=10,
        )  # fmt: skip
        ids = [c for c in listed.stdout.split() if len(c) == 12 and c.isalnum()]
        for container in ids:
            subprocess.run(self.docker("rm", "-f", container), capture_output=True, timeout=10)
        return len(ids)

    def run(self, job: dict, cancel: threading.Event | None = None) -> dict:
        lim = self.limits
        job = {"call_timeout_s": lim["call_timeout_s"], **job}
        payload = json.dumps(job, allow_nan=False).encode()
        if len(payload) > lim["max_job_bytes"]:
            raise ValueError("Sandbox job too large")
        self.ready()
        if cancel is not None and cancel.is_set():
            raise Cancelled("cancelled before sandbox job")
        name = "codejury-s2-" + uuid.uuid4().hex
        output, errors = bytearray(), bytearray()
        overflow = threading.Event()
        try:
            subprocess.run(self.argv(name), capture_output=True, check=True, timeout=20)
            self.inspect_job(name)
            process = subprocess.Popen(
                self.docker("start", "-ai", name),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )  # fmt: skip
        except (OSError, subprocess.SubprocessError, InfrastructureError) as exc:
            self._remove(name)
            raise InfrastructureError("Sandbox creation failed") from exc

        def drain(stream, target):
            while block := os.read(stream.fileno(), 4096):
                target.extend(block[: max(0, lim["max_stdout_bytes"] - len(target))])
                if len(target) >= lim["max_stdout_bytes"]:
                    overflow.set()

        readers = [
            threading.Thread(target=drain, args=(s, t), daemon=True)
            for s, t in ((process.stdout, output), (process.stderr, errors))
        ]
        for reader in readers:
            reader.start()
        n_calls = len(job["calls"])
        limit = lim["watchdog_slack_s"] + n_calls * (job["call_timeout_s"] + 0.5)
        start = time.monotonic()
        try:
            process.stdin.write(payload)
            process.stdin.close()
            while process.poll() is None:
                if cancel is not None and cancel.is_set():
                    raise Cancelled("cancelled during sandbox job")
                if overflow.is_set() or time.monotonic() - start > limit:
                    raise WatchdogTimeout("sandbox watchdog expired")
                time.sleep(0.02)
            for reader in readers:
                reader.join(timeout=1)
            if process.returncode != 0:
                raise InfrastructureError("Sandbox worker exited abnormally")
            envelope = json.loads(output)
            validate_envelope(envelope, n_calls)
            return envelope
        except (json.JSONDecodeError, BrokenPipeError) as exc:
            raise InfrastructureError("Malformed sandbox output") from exc
        finally:
            self._remove(name)  # removing the container kills its whole process tree
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for reader in readers:
                reader.join(timeout=1)
            for stream in (process.stdout, process.stderr):
                stream.close()

    def _remove(self, name: str) -> None:
        subprocess.run(self.docker("rm", "-f", name), capture_output=True, check=False, timeout=15)
