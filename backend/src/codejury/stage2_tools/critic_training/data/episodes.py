"""Episode-set intake: path/hash/split validation of E2 bundles and label sidecars.

Fixture sets are accepted only in fixture mode; a real build refuses them, and a fixture build
refuses real sets, so synthetic episodes can never be mistaken for student failures.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from ...codec import ContractError, errors

SET_SCHEMA = "stage2-episode-set.v1"
LABEL_SCHEMA = "stage2-critic-labels.v1"
LABEL_SOURCES = {"reviewed", "reference_backed", "teacher_filtered"}


class IntakeError(ValueError):
    pass


@dataclass
class Episode:
    bundle: dict
    base_problem_id: str
    family_id: str
    provenance: str  # natural | synthetic
    label: dict | None = None


@dataclass
class EpisodeSet:
    runtime_mode: str
    split: str
    episodes: list[Episode] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    set_hash: str = ""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_child(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise IntakeError(f"Unsafe path {relative!r}")
    path = root / rel
    if path.is_symlink():
        raise IntakeError(f"Symlinked asset {relative!r}")
    if not path.is_file():
        raise IntakeError(f"Missing asset {relative!r}")
    return path


def split_ids(manifest: dict) -> dict[str, set[str]]:
    return {
        name: set(block.get("base_problem_ids", [])) for name, block in manifest["splits"].items()
    }


def load_labels(root: Path, name: str) -> dict[str, dict]:
    doc = json.loads(safe_child(root, name).read_text())
    if doc.get("schema") != LABEL_SCHEMA:
        raise IntakeError("Unknown label schema")
    if doc["source_kind"] not in LABEL_SOURCES:
        raise IntakeError("Unknown label source")
    out = {}
    for row in doc["labels"]:
        row = {**row, "source_kind": doc["source_kind"]}
        if row["run_id"] in out:
            raise IntakeError(f"Duplicate label for {row['run_id']}")
        out[row["run_id"]] = row
    return out


def load_set(
    root: Path | str, split_manifest: dict, *, split: str, runtime_mode: str
) -> EpisodeSet:
    """Validated episodes; every refused episode is retained with its reason."""
    root = Path(root)
    index = json.loads(safe_child(root, "manifest.json").read_text())
    if index.get("schema") != SET_SCHEMA:
        raise IntakeError("Unknown episode-set schema")
    if index["runtime_mode"] != runtime_mode:
        raise IntakeError(
            f"Episode set is {index['runtime_mode']!r} but this build is {runtime_mode!r}; "
            "fixture and real data are never mixed"
        )
    if index["split"] != split:
        raise IntakeError(f"Episode set split {index['split']!r} is not the requested {split!r}")
    ids = split_ids(split_manifest)
    labels = load_labels(root, index["labels"])
    result = EpisodeSet(
        runtime_mode=runtime_mode, split=split, set_hash=sha256_file(root / "manifest.json")
    )
    seen_runs: set[str] = set()
    for row in index["episodes"]:
        try:
            path = safe_child(root, row["path"])
            if sha256_file(path) != row["sha256"]:
                raise IntakeError("hash mismatch")
            base = row["base_problem_id"]
            if runtime_mode == "real":
                if base not in ids[split]:
                    raise IntakeError("base problem is not in the declared split")
                for other, members in ids.items():
                    if other != split and base in members:
                        raise IntakeError(f"base problem also appears in {other}")
            bundle = json.loads(path.read_text())
            problems = errors(bundle, "EpisodeBundle")
            if problems:
                raise IntakeError("schema: " + problems[0])
            run_id = bundle["run_id"]
            if run_id in seen_runs:
                raise IntakeError("duplicate run_id")
            seen_runs.add(run_id)
            if row["provenance"] not in ("natural", "synthetic"):
                raise IntakeError("unknown provenance")
            result.episodes.append(
                Episode(bundle, base, row["family_id"], row["provenance"], labels.get(run_id))
            )
        except (IntakeError, ContractError, KeyError, ValueError) as exc:
            result.rejected.append({"path": row.get("path"), "reason": str(exc)})
    return result
