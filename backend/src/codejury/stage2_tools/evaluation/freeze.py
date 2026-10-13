"""Bind the final experiment to a clean commit, exact code, weights and configuration."""

import json
import os
import platform
import subprocess
from pathlib import Path

from codejury.models.worker import file_hash
from codejury.stage2_core.contracts import json_hash
from codejury.stage2_core.data import write_report
from codejury.stage2_core.registry import local_path


def identity(config, port):
    backend = local_path(".")
    root = backend.parent
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, text=True
    ).strip()
    if dirty:
        raise ValueError("Commit and validate all tracked changes before freezing final assessment")
    if config["profile"] != "final" or config["split"] != "final_assessment":
        raise ValueError("E4 freezes only the declared final experiment")
    if any(
        config["methods"][m]["training_token_opportunity"] <= 0 for m in ("B1", "B2", "B3", "CJ")
    ):
        raise ValueError("Record measured training opportunities before the final freeze")
    source = backend / "src" / "codejury"
    paths = [
        *source.joinpath("stage2_core").rglob("*.py"),
        *source.joinpath("stage2_tools").rglob("*.py"),
    ]
    tracked = set(subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines())
    if any(str(p.relative_to(root)) not in tracked for p in paths):
        raise ValueError("Commit every runtime and benchmark source before the final freeze")
    registry = port.base_registry
    opportunity = json.loads(port.opportunity_report.read_text())
    if (
        opportunity["registry_hash"] != registry.manifest_hash
        or not opportunity["comparable"]
        or opportunity["runtime_mode"] != "live"
        or opportunity["contains_final_assessment"]
        or config["methods"]["CJ"]["training_token_opportunity"]
        != opportunity["council_completion_tokens"]
        or config["methods"]["B3"]["training_token_opportunity"]
        != opportunity["general"]["completion_tokens"]
    ):
        raise ValueError("Final comparison must match the genuine comparable-exposure audit")
    # Verify every real adapter file, including the experimental controls.
    for record in [registry, *port.variants.values()]:
        for role in record.record["adapters"]:
            record.verify_adapter(role)
    return {
        "version": "stage2.e4-freeze.v1",
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "config_hash": json_hash(config),
        "source_hash": json_hash(
            {str(p.relative_to(backend)): file_hash(p) for p in sorted(paths)}
        ),
        "registry_hash": registry.manifest_hash,
        "opportunity_hash": file_hash(port.opportunity_report),
        "final_asset_hash": json.loads(local_path(config["manifest"]).read_text())["splits"][
            "final_assessment"
        ]["sha256"],
        "control_registry_hashes": {k: v.manifest_hash for k, v in sorted(port.variants.items())},
        "runtime_hash": port.tool.sandbox.runtime_hash,
        "hardware": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "memory_bytes": int(
                subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            ),
        },
        "base_revision_hash": registry.base["base_revision_hash"],
        "assessment_manifest_hash": file_hash(local_path(config["manifest"])),
        "final_contents_opened": False,
    }


def write(path, config, port):
    path = Path(path).resolve()
    if local_path("artifacts") not in path.parents or path.exists():
        raise ValueError("An immutable ignored E4 freeze file is required")
    record = identity(config, port)
    if consumed_marker(record).exists():
        raise ValueError("This final asset was already consumed on this Mac; do not tune and retry")
    write_report(path, record)
    return record


def verify(path, config, port):
    path = Path(path).resolve()
    if path.is_symlink() or json.loads(path.read_text()) != identity(config, port):
        raise ValueError("Final methods/code/configuration differ from the E4 freeze")
    # Consume before opening the final asset. Interrupted/failed experiments stay consumed.
    record = json.loads(path.read_text())
    with consumed_marker(record).open("x") as stream:
        stream.write(json.dumps({"freeze_hash": file_hash(path)}) + "\n")
    with path.with_name(path.name + ".consumed").open("x") as stream:
        stream.write(json.dumps({"freeze_hash": file_hash(path)}) + "\n")
    return True


def consumed_marker(record):
    return Path("/private/tmp") / (
        "codejury-final-" + str(os.getuid()) + "-" + record["final_asset_hash"] + ".consumed"
    )
