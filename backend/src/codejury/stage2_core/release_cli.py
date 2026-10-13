"""Portable local adapter bundle; hidden data, ledgers and base weights stay out."""

import argparse
import copy
import json
import shutil
import zipfile
from pathlib import Path

from codejury.models.worker import file_hash

from .contracts import checked
from .data import write_report
from .registry import ADAPTER_FILES, REQUIRED, Registry, local_path


def package(registry_path, benchmark_path, out):
    source = Registry(Path(registry_path))
    roles = REQUIRED | {"general"}
    if (
        not source.readiness()["ready"]
        or set(source.record["adapters"]) != roles
        or any(source.record["adapters"][r]["card"]["status"] != "completed" for r in roles)
    ):
        raise ValueError(
            "Portable release requires four completed native roles and the General comparator"
        )
    benchmark = checked(json.loads(Path(benchmark_path).read_text()), "BenchmarkReport")
    run_meta_path = Path(benchmark_path).parent / "run-meta.json"
    run_meta = json.loads(run_meta_path.read_text())
    if (
        benchmark["runtime_mode"] != "live"
        or benchmark["status"] != "completed"
        or benchmark["dataset_id"] != "final_assessment"
        or run_meta["mode"] != "live"
        or run_meta["dataset_id"] != benchmark["dataset_id"]
        or run_meta["manifest_hash"] != benchmark["dataset_manifest_hash"]
        or run_meta["registry_hash"] != source.manifest_hash
        or not run_meta["freeze_hash"]
    ):
        raise ValueError(
            "A completed genuine final benchmark, with any measured outcome, is required"
        )
    out = Path(out).resolve()
    archive = out.with_name(out.name + ".zip")
    root = local_path("artifacts")
    if root not in out.parents or out.exists() or archive.exists():
        raise ValueError("Use a new ignored immutable local release directory")
    directories = {r: source.verify_adapter(r) for r in roles}
    out.mkdir(parents=True)
    portable = copy.deepcopy(source.record)
    portable["base"]["path"] = "models/Phi4-mini"
    for role in sorted(roles):
        destination = out / "adapters" / role
        destination.mkdir(parents=True)
        for name in sorted(ADAPTER_FILES):
            shutil.copyfile(directories[role] / name, destination / name)
        portable["adapters"][role]["path"] = str(destination.relative_to(local_path(".")))
    write_report(out / "registry.json", portable)
    restored = Registry(out / "registry.json")
    for role in roles:
        restored.verify_adapter(role)
        if restored.identity(role) != source.identity(role):
            raise ValueError("Portable copy changed a model identity")
    write_report(out / "benchmark-report.json", benchmark)
    write_report(
        out / "training-report.json",
        checked(
            {
                "schema_version": "stage2.v1",
                "runtime_mode": "live",
                "cards": [source.record["adapters"][r]["card"] for r in sorted(roles)],
                "note": "Four completed native jury roles and the trained General comparator. "
                "Finite synthetic benchmark; outcome is reported as measured.",
            },
            "TrainingReport",
        ),
    )
    (out / "INSTALL.md").write_text(
        "# Local Stage 2 adapters\n\n"
        "Extract this archive at the CodeJury repository root. It contains the four jury "
        "adapters plus the trained General comparator, their frozen cards and public aggregate "
        "reports. It contains no training corpus, hidden tests, ledgers or base weights.\n\n"
        "Install the frozen base at backend/models/Phi4-mini using the exact model ID/revision "
        "and file hashes in registry.json. All tokenizer/quantization/topology hashes must match. "
        "Use the repository's Mac dependencies and pinned isolated runner.\n\n"
        "From backend, set CODEJURY_STAGE2_MODEL_MANIFEST to "
        + str((out / "registry.json").relative_to(local_path(".")))
        + " and run python -m codejury.stage2_core.serve. "
        "The API/UI serve at http://127.0.0.1:8002. Native model loading verifies all bytes; "
        "the General adapter remains a research comparator, not a fifth jury member.\n"
    )
    manifest = {
        "version": "stage2.portable-release.v1",
        "runtime_mode": "live",
        "source_registry_hash": source.manifest_hash,
        "benchmark_run_meta_hash": file_hash(run_meta_path),
        "registry_hash": restored.manifest_hash,
        "base_model_id": source.base["model_id"],
        "base_revision": source.base["revision"],
        "adapter_hashes": {r: source.identity(r)["adapter_hash"] for r in sorted(roles)},
        "research_outcome": benchmark["research_outcome"],
        "contains_hidden_corpus": False,
        "adapters_included": True,
        "intended_visibility": "local_private_artifact",
        "base_weights_included": False,
        "files": {
            str(p.relative_to(out)): file_hash(p) for p in sorted(out.rglob("*")) if p.is_file()
        },
    }
    write_report(out / "manifest.json", manifest)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zipped:
        for path in sorted(out.rglob("*")):
            if path.is_file():
                zipped.write(path, str(Path("backend") / path.relative_to(local_path("."))))
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise ValueError("Portable archive integrity check failed")
    return {
        "status": "packaged",
        "archive": str(archive),
        "archive_hash": file_hash(archive),
        "registry_hash": restored.manifest_hash,
        "research_outcome": benchmark["research_outcome"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.registry, args.benchmark, args.out), indent=2), flush=True)


if __name__ == "__main__":
    main()
