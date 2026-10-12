"""Read baseline metadata without opening private final-assessment records."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import sqlite3
import subprocess
from pathlib import Path

import yaml

from codejury.stage2_core.contract_check import REPO_ROOT, check

BACKEND = REPO_ROOT / "backend"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def command(args: list[str]) -> dict:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=25, check=False)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": None, "stdout": "", "stderr": str(exc)}


def read_json(path: Path):
    return json.loads(path.read_text()) if path.is_file() else None


def audit() -> dict:
    packages = {}
    for name in (
        "fastapi",
        "pydantic",
        "jsonschema",
        "hypothesis",
        "PyYAML",
        "uvicorn",
        "mlx",
        "mlx-lm",
        "pytest",
        "httpx",
        "ruff",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    model = yaml.safe_load((BACKEND / "config/model.yaml").read_text())
    runner = yaml.safe_load((BACKEND / "config/runner.yaml").read_text())
    memory = command(["sysctl", "-n", "hw.memsize"])
    model_dir = BACKEND / "models/Phi4-mini"
    hashes = {
        p.name: digest(p)
        for p in model_dir.iterdir()
        if p.is_file() and p.suffix in {".json", ".safetensors", ".jinja"}
    }
    adapter = BACKEND / "artifacts/training/fixer_a_selected"
    freeze = read_json(adapter / "freeze.json")
    adapter_hashes = {p.name: digest(p) for p in adapter.iterdir() if p.is_file()}
    results = read_json(BACKEND / "artifacts/evaluation/stage1-results.json")
    # Published aggregate counts only: no row-level private assessment outcomes exported.
    summary = results["evaluation"] if results else []
    malformed = (
        {
            method: sum(
                bool(row.get("malformed")) for row in results["rows"] if row["method"] == method
            )
            for method in ("raw_single", "trained_a_single", "stage1_loop")
        }
        if results
        else {}
    )
    image = command(
        [
            "docker",
            "--context",
            runner["context"],
            "image",
            "inspect",
            runner["image_id"],
            "--format",
            "{{.Id}} {{.Architecture}}",
        ]
    )
    vm_mounts = command(
        ["colima", "ssh", "--profile", "codejury-stage1", "--", "cat", "/proc/mounts"]
    )
    unsafe_mounts = [
        line
        for line in vm_mounts["stdout"].splitlines()
        if any(marker in line for marker in ("/Users/", "virtiofs", "sshfs"))
    ]
    smoke = read_json(BACKEND / "artifacts/training/model-smoke.json")
    baseline_matches = bool(smoke) and hashes == smoke["local_file_sha256"]
    return {
        "scope": "Metadata audit; no new inference, training or benchmark execution",
        "git": {
            "head": command(["git", "rev-parse", "HEAD"])["stdout"],
            "status": command(["git", "status", "--short"])["stdout"],
        },
        "environment": {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "sqlite": sqlite3.sqlite_version,
            "memory_bytes": int(memory["stdout"]) if memory["returncode"] == 0 else None,
            "packages": packages,
        },
        "stage2_contract": check(REPO_ROOT / "contracts"),
        "lock_sha256": digest(BACKEND / "uv.lock"),
        "constraints_sha256": digest(REPO_ROOT / "integration/stage2/constraints.txt"),
        "package_discovery": "hatch src/codejury includes both stage2 namespaces recursively",
        "model": {
            "config": model,
            "files_sha256": hashes,
            "matches_recorded_smoke": baseline_matches,
            "adapter_files": adapter_hashes,
            "freeze": freeze,
            "recorded_switch_verified": bool(smoke and smoke["switch_verified"]),
            "fresh_inference": "pending A2.03",
        },
        "runner": {
            "config": runner,
            "image_probe": image,
            "mount_probe_returncode": vm_mounts["returncode"],
            "mount_probe_error": vm_mounts["stderr"],
            "unsafe_mounts": unsafe_mounts,
            "fresh_candidate_execution": "not run by metadata audit",
        },
        "data": {
            "manifest": read_json(BACKEND / "data/manifests/stage1.json"),
            "private_final_records_opened": False,
            "stage1_assessment_status": "development evidence only",
            "stage2_final_gate": "Sarvesh must review/seal a fresh final pool at S2.01",
        },
        "baseline": {
            "published_results": summary,
            "malformed_counts": malformed,
            "failure_buckets": {
                "format_truncation": "raw malformed 9/10; trained A 0/10 recorded",
                "wrong_algorithm": "live unique-preservation remains unresolved",
                "local_expression": "requires further training-only diagnosis",
                "weak_test_acceptance": "recorded incorrect accepted 0/10; no general claim",
                "mutation_effects": "Stage 1 rejection tests; Stage 2 expansion pending",
                "timeout_infrastructure": "Stage 1 timeout/cancel tests; recheck before jobs",
                "adapter_regression": "file hashes plus recorded A/raw/A; fresh smoke pending",
            },
        },
        "pending": [
            "A2.03 real native smoke",
            "S2.01 fresh holdout and tool audit",
            "B, Critic and Judge adapters",
            "E1–E4 merged live acceptance",
        ],
        "executables": {name: bool(shutil.which(name)) for name in ("uv", "docker", "colima")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "environment": report["environment"],
                "model_hashes_match": report["model"]["matches_recorded_smoke"],
                "runner": report["runner"],
                "pending": report["pending"],
            },
            indent=2,
        )
    )
