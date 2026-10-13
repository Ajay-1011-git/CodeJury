"""Read existing role evidence without opening final assessment contents."""

import argparse
import json
from pathlib import Path

import yaml

from codejury.models.worker import file_hash
from codejury.stage2_core.data import final_pool_metadata, write_report
from codejury.stage2_core.registry import Registry, local_path


def audit():
    runtime = yaml.safe_load(local_path("config/stage2_core/runtime.yaml").read_text())
    registry = Registry(local_path(runtime["model_manifest"]))
    inventory = {}
    for role in ("fixer_a", "fixer_b", "critic", "judge"):
        registry.verify_adapter(role)
        inventory[role] = registry.identity(role)
    reports = {}
    for name in ("judge-learning/pilot-v2", "judge-learning/full-v2", "general-learning/full-v1"):
        directory = local_path("artifacts/stage2_core/" + name)
        result = json.loads((directory / "report.json").read_text())
        native = json.loads((directory / "native-result.json").read_text())
        reports[name] = {
            k: result.get(k)
            for k in ("completed_steps", "updates_verified", "reload_verified", "adapter_hash")
        }
        reports[name]["native_parameter_hash"] = native["parameter_hash"]
        reports[name]["report_hash"] = file_hash(directory / "report.json")
        if not result["updates_verified"] or not result["reload_verified"]:
            raise ValueError("Existing native job failed integrity gate")
    return {
        "status": "preserved_native_baselines",
        "roles": inventory,
        "jobs": reports,
        "registry_hash": registry.manifest_hash,
        "final_pool": final_pool_metadata(local_path("config/stage2_core/training/fixer_a.yaml")),
        "teacher_promoted": False,
        "pending": [
            "teacher executable comparison",
            "conditional downstream refresh",
            "General selection/parity",
            "live acceptance",
            "frozen final benchmark",
        ],
        "menu_compatibility": "ID-only remap; controller and bijection tests required; "
        "any promoted A invalidates affected downstream outcomes",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = audit()
    write_report(Path(args.out), result)
    print(json.dumps(result))
