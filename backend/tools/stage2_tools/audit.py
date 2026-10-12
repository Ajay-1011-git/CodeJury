"""Inventory the real repository/environment for Stage 2 tools (S2.01). Reads, never executes
candidate code, never reads private final records (manifest metadata only).

Usage (from backend/): python tools/stage2_tools/audit.py --out artifacts/stage2_tools/audit.json
"""

import argparse
import hashlib
import importlib.metadata as metadata
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND / "src"))

PACKAGES = ["jsonschema", "PyYAML", "hypothesis", "fastapi", "pydantic", "pytest", "httpx",
            "uvicorn", "mlx", "mlx-lm"]


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def run(*argv, timeout=10) -> str | None:
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return (done.stdout if done.returncode == 0 else None) and done.stdout.strip()


def package_versions() -> dict:
    out = {}
    for name in PACKAGES:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def loc(directory: Path, pattern: str) -> dict:
    return {str(p.relative_to(ROOT)): len(p.read_text().splitlines())
            for p in sorted(directory.rglob(pattern)) if p.is_file() and "__pycache__" not in p.parts}


def collect() -> dict:
    docker_server = run("docker", "info", "--format", "{{.ServerVersion}}")
    stage1_manifest = json.loads((BACKEND / "data/manifests/stage1.json").read_text())
    runner_yaml = (BACKEND / "config/runner.yaml").read_text() if (
        BACKEND / "config/runner.yaml").exists() else ""
    private_dir = BACKEND / "data/private"
    report = {
        "schema": "stage2-tools-audit.v1",
        "git": {"head": run("git", "-C", str(ROOT), "rev-parse", "HEAD"),
                "branch": run("git", "-C", str(ROOT), "rev-parse", "--abbrev-ref", "HEAD")},
        "environment": {
            "python": platform.python_version(),
            "python_target": "3.11 (backend/pyproject.toml requires >=3.11,<3.12)",
            "platform": platform.platform(),
            "machine": platform.machine(),
            "node": run("node", "--version"),
            "docker_client": run("docker", "--version"),
            "docker_server": docker_server,
            "colima": shutil.which("colima"),
            "uv": shutil.which("uv"),
            "packages": package_versions(),
        },
        "stage1_assets": {
            "runner_modules": loc(BACKEND / "src/codejury/runner", "*.py"),
            "property_engine": loc(BACKEND / "src/codejury/properties", "*.py"),
            "intake": loc(BACKEND / "src/codejury/contracts", "*.py"),
            "web_sources": loc(ROOT / "web/src", "*.mjs"),
            "web_mock_and_tools": loc(ROOT / "web/tools", "*.py"),
            "web_tests": sorted(str(p.relative_to(ROOT)) for p in (ROOT / "web/tests").glob("*")),
            "stage1_runner_config_image_pinned": "image_id: sha256:" in runner_yaml,
            "stage1_runner_limits": {
                "imports": "forbidden (Stage 1 inspect_source)", "helpers": "forbidden",
                "arguments": "1-3, list_integer/integer only", "int_domain": "+/-1000",
                "container": "128 MB, 16 pids, 1 cpu"},
        },
        "contracts": {
            "stage2_schema_sha256": sha(ROOT / "contracts/stage2.schema.json"),
            "stage2_ports_sha256": sha(ROOT / "contracts/shared/stage2_ports.py"),
            "backend_ports_match": sha(ROOT / "contracts/shared/stage2_ports.py")
            == sha(BACKEND / "src/codejury/stage2_ports.py"),
            "stage1_schema_sha256": sha(ROOT / "contracts/stage1-api.schema.json"),
            "constraints_sha256": sha(ROOT / "integration/stage2/constraints.txt"),
        },
        "datasets": {
            "dataset_id": stage1_manifest["dataset_id"],
            "assets": stage1_manifest["assets"],
            "private_data_present": private_dir.is_dir() and any(private_dir.iterdir()),
            "public_demo_overlap": stage1_manifest.get("public_demo_overlap"),
        },
    }
    gaps = []
    env = report["environment"]
    if not env["python"].startswith("3.11"):
        gaps.append(f"Python {env['python']} in use; project requires 3.11 (3.11 not installed here)")
    if not docker_server:
        gaps.append("No reachable Docker daemon: every native sandbox check stays pending")
    if not env["colima"]:
        gaps.append("Colima not installed: dedicated runner VM (codejury-stage2) cannot be created")
    if not report["datasets"]["private_data_present"]:
        gaps.append("Private validation/assessment/final files absent: disjointness of sealed "
                    "splits is unverified locally")
    if env["packages"]["mlx"] is None:
        gaps.append("MLX not installed: no Critic/general training or native inference possible here")
    gaps.append("Stage 1 runner forbids imports/helpers and supports only 1-3 int/list args "
                "(wrapped, not edited: Stage 2 runner lives in stage2_tools/runner)")
    gaps.append("Stage 2 runner image has not been built (needs Colima VM, then "
                "tools/stage2_tools/runner/build.sh)")
    final = next(a for a in stage1_manifest["assets"] if a["split"] == "stage2_final")
    if final["base_problems"] < 200:
        gaps.append(f"Sealed Stage 2 final pool has {final['base_problems']} base problems "
                    "(target >=200); curation is needed, never padding")
    report["missing_foundation_work"] = gaps
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = collect()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps({"missing_foundation_work": report["missing_foundation_work"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
