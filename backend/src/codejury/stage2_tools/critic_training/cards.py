"""Freeze Adapter Cards and exchange manifests from real files; refuse anything unproven."""

import hashlib
import json
from pathlib import Path

from ..codec import errors

ROLE_KIND = {
    "critic": "critic_adapter",
    "general": "general_adapter",
    "judge": "judge_adapter",
    "fixer_a": "fixer_adapters",
    "fixer_b": "fixer_adapters",
}


class CardError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_card(
    role: str,
    status: str,
    *,
    adapter_path: Path | None,
    base: dict,
    data_manifest_hash: str | None,
    config_hash: str,
    train_base_problems: int,
    train_records: int,
    log: list[dict],
    reload_verified: bool,
    evaluation_summary: str,
) -> dict:
    """`log` rows are the real optimizer log: {step, train_loss, validation_loss}."""
    if status == "completed":
        if adapter_path is None or not Path(adapter_path).is_file():
            raise CardError("A completed card needs the real adapter weights file")
        if not reload_verified:
            raise CardError("A completed card needs a verified save/reload")
        if not log:
            raise CardError("A completed card needs the real training log")
        if data_manifest_hash is None:
            raise CardError("A completed card needs the data manifest hash")
    steps = max((r["step"] for r in log), default=0)
    if status == "not_started" and (log or adapter_path):
        raise CardError("A not_started card cannot carry training evidence")
    card = {
        "schema_version": "stage2.v1",
        "role": role,
        "status": status,
        "adapter_hash": sha256_file(adapter_path) if adapter_path else None,
        "base_revision_hash": base["base_revision_hash"],
        "tokenizer_hash": base["tokenizer_hash"],
        "quantization_hash": base["quantization_hash"],
        "topology_hash": base["topology_hash"],
        "data_manifest_hash": data_manifest_hash,
        "config_hash": config_hash,
        "train_base_problems": train_base_problems,
        "train_records": train_records,
        "steps": steps,
        "evaluation_summary": evaluation_summary,
        "loss_points": [
            {
                "step": r["step"],
                "train_loss": r.get("train_loss"),
                "validation_loss": r.get("validation_loss"),
            }
            for r in log
        ],
    }
    problems = errors(card, "AdapterCard")
    if problems:
        raise CardError(f"Card violates the frozen schema: {problems[0]}")
    return card


def _inside_git(path: Path) -> bool:
    return any((p / ".git").exists() for p in [path.resolve(), *path.resolve().parents])


def export_manifest(
    role: str,
    directory: Path,
    *,
    exchange_id: str,
    base_revision_hash: str,
    records: int,
    bases: int,
) -> dict:
    """Manifest for weight bytes that live outside Git; refuses a directory inside a repository."""
    directory = Path(directory)
    if _inside_git(directory):
        raise CardError("Weights must be exported outside Git")
    files = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        if path.is_symlink():
            raise CardError("Symlinked export file")
        files.append(
            {
                "relative_path": path.relative_to(directory).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    if not files:
        raise CardError("Nothing to export")
    manifest = {
        "schema_version": "stage2.v1",
        "exchange_id": exchange_id,
        "owner": "sarvesh",
        "kind": ROLE_KIND[role],
        "base_revision_hash": base_revision_hash,
        "split": "train",
        "files": files,
        "record_count": records,
        "base_problem_count": bases,
        "contains_hidden_assessment": False,
        "note": "Exported adapter bytes; weights are not stored in Git.",
    }
    problems = errors(manifest, "ArtifactManifest")
    if problems:
        raise CardError(f"Manifest violates the frozen schema: {problems[0]}")
    return manifest


def write_json(path: Path, value: dict) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
