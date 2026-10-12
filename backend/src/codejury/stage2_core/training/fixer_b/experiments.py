"""Sequential genuine B alpha trials and matched same-view control; no concurrent MLX."""

import json
from pathlib import Path

from codejury.models.worker import file_hash

from ...contracts import checked
from ...data import write_report
from ...registry import Registry
from . import ALPHAS
from .evaluate import evaluate
from .select import export_fixers, inspect_reports, rank, select
from .train import train


def run(config_path, mining_report, out, a_baseline):
    root = Path(out).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if (root / "experiment.json").exists():
        raise FileExistsError("Completed experiment refuses overwrite")
    paths = []

    def job(alpha, view):
        tag = f"alpha{alpha}" if view == "independent" else f"same-view-alpha{alpha}"
        pilot, full = root / (tag + "-pilot"), root / (tag + "-full")
        if not pilot.exists():
            train(config_path, mining_report, pilot, alpha=alpha, view=view, phase="pilot")
        if not full.exists():
            train(
                config_path,
                mining_report,
                full,
                alpha=alpha,
                view=view,
                phase="full",
                pilot_proof=pilot / "report.json",
            )
        # Existing incomplete jobs fail closed; never replay or overwrite native evidence.
        proof = json.loads((full / "report.json").read_text())
        session = json.loads((full / "session.json").read_text())
        if (
            proof["status"] != "trained_selection_pending"
            or proof["reload_verified"] is not True
            or proof["updates_verified"] is not True
            or proof["view"] != view
            or proof["alpha"] != alpha
            or session["config_file_hash"] != file_hash(config_path)
            or session["mining_report_hash"] != file_hash(mining_report)
        ):
            raise ValueError("Existing native job is not a completed verified matching trial")
        result = []
        for candidate in proof["candidates"]:
            registry = Registry(Path(candidate["registry_path"]))
            destination = root / f"{tag}-validation-{candidate['step']}"
            if not destination.exists():
                evaluate(
                    config_path, registry.path, destination, view=view, baseline_path=a_baseline
                )
            # Verify all reused reports against actual job/adapter bytes below.
            result.append(destination / "report.json")
        inspect_reports(config_path, result)
        return result

    # Start with the planned alpha2, then run all declared controls/trials.
    for alpha in (2, 0, 1, 4):
        print(json.dumps({"phase": "independent_trial", "alpha": alpha}), flush=True)
        paths.extend(job(alpha, "independent"))
    entries = inspect_reports(config_path, paths)
    if {r["report"]["alpha"] for r in entries} != set(ALPHAS):
        raise ValueError("Missing alpha trial")
    chosen = min(entries, key=lambda r: rank(r["summary"]))
    alpha = chosen["report"]["alpha"]
    print(json.dumps({"phase": "same_view_control", "alpha": alpha}), flush=True)
    controls = job(alpha, "same_as_a")
    result = select(config_path, paths, root / "selected", control_paths=controls)
    write_report(root / "experiment.json", result)
    print(json.dumps(result), flush=True)
    return result


def finalize(config_path, out):
    """Re-audit selected evidence and finish only an interrupted metadata export."""
    root = Path(out).resolve()
    selected_dir = root / "selected"
    result = json.loads((selected_dir / "selection.json").read_text())
    entries = inspect_reports(config_path, [r["path"] for r in result["comparisons"]])
    for comparison, entry in zip(result["comparisons"], entries, strict=True):
        if comparison["sha256"] != entry["sha256"] or comparison["summary"] != entry["summary"]:
            raise ValueError("Selected comparison evidence changed")
    registry = Registry(selected_dir / "registry.json")
    if (
        registry.identity("fixer_a")["adapter_hash"] != result["a_adapter_hash"]
        or registry.identity("fixer_b")["adapter_hash"] != result["adapter_hash"]
    ):
        raise ValueError("Selected adapter bytes changed")
    manifest_path = selected_dir / "exchange/manifest.json"
    if manifest_path.exists():
        manifest = checked(json.loads(manifest_path.read_text()), "ArtifactManifest")
        for file in manifest["files"]:
            path = manifest_path.parent / file["relative_path"]
            if path.stat().st_size != file["size_bytes"] or file_hash(path) != file["sha256"]:
                raise ValueError("Completed handoff bytes changed")
    else:
        export_fixers(selected_dir)
    report_path = root / "experiment.json"
    if report_path.exists():
        if json.loads(report_path.read_text()) != result:
            raise ValueError("Completed experiment evidence changed")
    else:
        write_report(report_path, result)
    return {
        "status": "verified_complete",
        "native_jobs_replayed": False,
        "registry_path": str(registry.path),
        "summary": result["selected_summary"],
    }
