"""Report foundation readiness without implying inference or sandbox success."""

import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys


def inspect() -> dict:
    required = ("fastapi", "pydantic", "jsonschema", "hypothesis", "uvicorn")
    packages = {}
    for name in (*required, "mlx", "mlx-lm"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    result = {
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "packages": packages,
        "docker_cli": shutil.which("docker") is not None,
        "colima_cli": shutil.which("colima") is not None,
        "model_inference": "pending A.06 native smoke and training pilot",
        "sandbox_execution": "pending A.03 isolated execution checks",
        "foundation_ready": sys.version_info[:2] == (3, 11)
        and all(packages[name] for name in required),
    }
    if platform.system() == "Darwin":
        memory = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=False
        )
        result["memory_bytes"] = int(memory.stdout) if memory.returncode == 0 else None
    return result


if __name__ == "__main__":
    report = inspect()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["foundation_ready"] else 1)
