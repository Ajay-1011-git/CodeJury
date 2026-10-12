"""Evaluation CLI: split validation now; benchmark smoke/run/analyze are added by S2.09/S2.12."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .evaluation import splits

REPO_ROOT = Path(__file__).resolve().parents[4]


def build_manifest(stage1_path: Path, backend: Path) -> dict:
    """Stage 2 manifest from the Stage 1 seal plus the public train pool actually on disk."""
    from .domains import normalized_hash

    stage1_bytes = stage1_path.read_bytes()
    stage1 = json.loads(stage1_bytes)
    assets = {a["split"]: a for a in stage1["assets"]}
    train_path = backend / "data" / assets["train"]["path"]
    ids = splits.load_ids(train_path, normalized_hash)
    train = {"role": "training", "asset": assets["train"]["path"], "sha256": splits.sha256_file(train_path),
             "base_problems": len(ids["base_problem_ids"]), "records": ids["records"],
             "visibility": "public_training_pool", **{k: ids[k] for k in splits.KEYS}}  # noqa: E501

    def sealed(split, role, **extra):
        a = assets[split]
        return {"role": role, "asset": a["path"], "sha256": a["sha256"],
                "base_problems": a["base_problems"], "records": a["records"],
                "visibility": "private_local_ignored", **extra}

    return {
        "schema": "stage2-split-manifest.v1",
        "dataset_id": "stage2-tools-v1",
        "derived_from": {"manifest": "data/manifests/stage1.json",
                         "sha256": hashlib.sha256(stage1_bytes).hexdigest(),
                         "stage1_seal_sha256": stage1["seal_sha256"]},
        "splits": {
            "train": train,
            "validation": sealed("validation", "validation"),
            "development_assessment": sealed(
                "assessment", "development",
                note="Stage 1 assessment was inspected during Stage 1 work: development data only.",
            ),
            "final_assessment": sealed(
                "stage2_final", "final", inspected_in_development=False,
                note="Previously authored sealed pool; ids are held privately by the benchmark owner.",
            ),
        },
        "target_final_base_problems": splits.TARGET_FINAL,
        "limited_evidence_note": "Counts are actual, never padded; variants and seeds are not "
        "independent base problems.",
    }


def cmd_validate(args) -> int:
    manifest_path = args.manifest
    manifest = json.loads(manifest_path.read_text())
    roots = splits.default_roots(manifest_path)
    report = splits.validate_manifest(manifest, roots)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


def cmd_build(args) -> int:
    backend = args.backend
    manifest = build_manifest(backend / "data/manifests/stage1.json", backend)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="eval_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate-splits")
    v.add_argument("--manifest", required=True, type=Path)
    v.set_defaults(func=cmd_validate)
    b = sub.add_parser("build-manifest")
    b.add_argument("--backend", type=Path, default=REPO_ROOT / "backend")
    b.add_argument("--out", required=True, type=Path)
    b.set_defaults(func=cmd_build)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
