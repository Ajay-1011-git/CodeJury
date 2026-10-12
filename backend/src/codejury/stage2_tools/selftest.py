"""Shared plumbing for the search/audit self-test CLIs: real sandbox or explicit pending."""

import json
import subprocess
from pathlib import Path

import yaml

from .runner import InfrastructureError
from .runner.docker import DockerSandbox


def write_report(out_dir: Path, name: str, report: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / name).write_text(json.dumps(report, indent=2, sort_keys=True))


def run_native(config: Path, out_dir: Path, report_name: str, cases) -> int:
    """cases(sandbox, settings) -> {check: bool}. No sandbox -> every check stays pending."""
    settings = yaml.safe_load(Path(config).read_text())
    runner_config = Path(config).with_name(settings.get("runner_config", "runner.yaml"))
    report = {"mode": "native_sandbox", "config": str(config), "settings": settings}
    try:
        sandbox = DockerSandbox(runner_config)
        report["environment"] = sandbox.ready()
        report["runtime_hash"] = sandbox.runtime_hash
        report["checks"] = cases(sandbox, settings)
        report["overall"] = "passed" if all(report["checks"].values()) else "failed"
    except (InfrastructureError, OSError, subprocess.SubprocessError) as exc:
        report["checks"] = "pending_native"
        report["overall"] = "pending_native"
        report["reason"] = f"{type(exc).__name__}: {exc}"
        report["logic_evidence"] = "CPU tests with FIXTURE_HOST_EXEC only; see docs"
    write_report(out_dir, report_name, report)
    print(json.dumps({"overall": report["overall"], "reason": report.get("reason")}, indent=2))
    return {"passed": 0, "pending_native": 3}.get(report["overall"], 1)
