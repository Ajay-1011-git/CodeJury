"""Split-manifest validation: base-problem, family and near-duplicate disjointness.

Private final/validation files stay local and are never copied into Git or runtime exchange.
When a private asset is absent the manifest's sealed hash/count is the only evidence; that is
reported as `unverified_private`, never as verified disjointness.
"""

import hashlib
import json
import os
from pathlib import Path

ROLES = {"train": "training", "validation": "validation", "development_assessment": "development",
         "final_assessment": "final"}
KEYS = ("base_problem_ids", "family_ids", "cluster_ids")
TARGET_FINAL = 200


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve(asset: str, roots: list[Path]) -> Path | None:
    relative = Path(asset)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe asset path {asset!r}")
    for root in roots:
        candidate = root / relative
        if candidate.is_symlink():
            raise ValueError(f"Symlinked asset {asset!r}")
        if candidate.is_file():
            return candidate
    return None


def load_ids(path: Path, normalized_hash) -> dict:
    """Base problem / family / near-duplicate cluster ids actually present in a jsonl asset."""
    bases, families, clusters, records = set(), set(), set(), 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        records += 1
        bases.add(row["base_problem_id"])
        families.add(row["family_id"])
        try:
            clusters.add(normalized_hash(row["correct_source"]))
        except (SyntaxError, KeyError):
            clusters.add("unparsed:" + row["base_problem_id"])
    return {"base_problem_ids": sorted(bases), "family_ids": sorted(families),
            "cluster_ids": sorted(clusters), "records": records}


def default_roots(manifest_path: Path) -> list[Path]:
    backend = manifest_path.resolve().parents[3]
    roots = [backend / "data"]
    for env in ("CODEJURY_STAGE2_EVAL_DIR",):
        if os.environ.get(env):
            roots.append(Path(os.environ[env]))
    return roots


def validate_manifest(manifest: dict, roots: list[Path], normalized_hash=None) -> dict:
    from ..domains import normalized_hash as default_hash

    normalized_hash = normalized_hash or default_hash
    violations, warnings = [], []
    splits = manifest.get("splits")
    if not isinstance(splits, dict) or set(splits) != set(ROLES):
        raise ValueError(f"splits must be exactly {sorted(ROLES)}")
    known: dict[str, dict] = {}
    summary = {}
    for name, entry in splits.items():
        if entry.get("role") != ROLES[name]:
            violations.append(f"{name}: role must be {ROLES[name]}")
        path = _resolve(entry["asset"], roots)
        status = "unverified_private"
        ids = None
        if path is not None:
            if sha256_file(path) != entry["sha256"]:
                violations.append(f"{name}: asset hash differs from the sealed value")
                status = "hash_mismatch"
            else:
                ids = load_ids(path, normalized_hash)
                status = "verified"
                if ids["records"] != entry["records"]:
                    violations.append(f"{name}: record count differs from manifest")
                if len(ids["base_problem_ids"]) != entry["base_problems"]:
                    violations.append(f"{name}: base problem count differs from manifest")
        else:
            warnings.append(f"{name}: asset not present locally; sealed hash/count only")
        if ids is not None:
            known[name] = ids
        summary[name] = {"status": status, "base_problems": entry["base_problems"],
                         "records": entry["records"], "sha256": entry["sha256"]}
    names = list(known)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for key in KEYS:
                overlap = set(known[a][key]) & set(known[b][key])
                if overlap:
                    violations.append(f"{a} and {b} share {key}: {sorted(overlap)[:5]}")
    if splits["final_assessment"].get("inspected_in_development"):
        violations.append("final_assessment was inspected during development")
    if splits["development_assessment"].get("role") != "development":
        violations.append("development_assessment must be labelled development")
    unverified = [n for n, s in summary.items() if s["status"] == "unverified_private"]
    if unverified:
        warnings.append(
            f"disjointness NOT verified for {unverified}: private assets absent from this checkout"
        )
    final_count = splits["final_assessment"]["base_problems"]
    limited = final_count < TARGET_FINAL
    if limited:
        warnings.append(
            f"final assessment has {final_count} base problems (target {TARGET_FINAL}): "
            "limited evidence, wide uncertainty"
        )
    return {"status": "failed" if violations else "passed", "violations": violations,
            "warnings": warnings, "splits": summary, "final_base_problems": final_count,
            "target_final_base_problems": TARGET_FINAL, "limited_evidence": limited}
