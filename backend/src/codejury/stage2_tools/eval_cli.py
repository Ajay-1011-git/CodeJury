# ruff: noqa: E501
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
    train = {
        "role": "training",
        "asset": assets["train"]["path"],
        "sha256": splits.sha256_file(train_path),
        "base_problems": len(ids["base_problem_ids"]),
        "records": ids["records"],
        "visibility": "public_training_pool",
        **{k: ids[k] for k in splits.KEYS},
    }  # noqa: E501

    def sealed(split, role, **extra):
        a = assets[split]
        return {
            "role": role,
            "asset": a["path"],
            "sha256": a["sha256"],
            "base_problems": a["base_problems"],
            "records": a["records"],
            "visibility": "private_local_ignored",
            **extra,
        }

    return {
        "schema": "stage2-split-manifest.v1",
        "dataset_id": "stage2-tools-v1",
        "derived_from": {
            "manifest": "data/manifests/stage1.json",
            "sha256": hashlib.sha256(stage1_bytes).hexdigest(),
            "stage1_seal_sha256": stage1["seal_sha256"],
        },
        "splits": {
            "train": train,
            "validation": sealed("validation", "validation"),
            "development_assessment": sealed(
                "assessment",
                "development",
                note="Stage 1 assessment was inspected during Stage 1 work: development data only.",
            ),
            "final_assessment": sealed(
                "stage2_final",
                "final",
                inspected_in_development=False,
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


def _read_records(results: Path) -> list[dict]:
    path = results / "per_run.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def cmd_smoke(args) -> int:
    """Harness logic check on SYNTHETIC fixtures. Never evidence of quality or learning."""
    from .evaluation import Harness, analyze, fixtures, load_config, parity, write_analysis

    if args.mode != "fixture":
        print(json.dumps({"status": "refused", "reason": "smoke supports only --mode fixture"}))
        return 2
    config = load_config(args.config)
    if config["split"] == "final_assessment":
        print(json.dumps({"status": "refused", "reason": "smoke never touches the final split"}))
        return 2
    harness = Harness(
        config,
        fixtures.FixtureBaselinePort(),
        fixtures.FixtureScorer(),
        mode="fixture",
        out_dir=args.out,
    )
    tasks = fixtures.tasks()
    eligibility = harness.preflight(tasks)
    records = harness.run(tasks)
    result = analyze(
        config, records, manifest_hash=None, dataset_id="fixture-smoke", mode="fixture"
    )
    write_analysis(result, args.out / "smoke-report.json")
    audit = parity.audit(config, records)
    (args.out / "run-meta.json").write_text(
        json.dumps(
            {
                "mode": "fixture",
                "label": fixtures.LABEL,
                "config": config,
                "dataset_id": "fixture-smoke",
                "commit_digest": harness.commit_digest,
                "parity": audit,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(
        json.dumps(
            {
                "mode": "fixture",
                "label": fixtures.LABEL,
                "status": result["report"]["status"],
                "research_outcome": result["report"]["research_outcome"],
                "parity_ok": audit["ok"],
                "eligibility": eligibility["eligible"],
            },
            indent=2,
        )
    )
    return 0 if audit["ok"] else 1


def cmd_run(args) -> int:
    """Real benchmark; needs the live ports (pending without the native stack)."""
    from .evaluation import Harness, analyze, load_config, write_analysis
    from .evaluation.tasks import SandboxScorer, load_tasks
    from .runner import InfrastructureError
    from .runner.docker import DockerSandbox

    config = load_config(args.config)
    if args.split != config["split"]:
        print(json.dumps({"status": "refused", "reason": "--split differs from the config split"}))
        return 2
    try:
        import os

        from codejury.stage2_core.factory import make_baseline_port, make_model_port

        from .factory import make_tool_port

        eval_dir = Path(os.environ["CODEJURY_STAGE2_EVAL_DIR"])
        core_config = REPO_ROOT / "backend/config/stage2_core/runtime.yaml"
        tools = make_tool_port(core_config.with_name("../stage2_tools/runtime.yaml").resolve())
        model = make_model_port(core_config)
        port = make_baseline_port(core_config, model, tools)
        scorer = SandboxScorer(DockerSandbox(REPO_ROOT / "backend/config/stage2_tools/runner.yaml"))
        tasks = load_tasks(eval_dir / f"{args.split}.jsonl")
    except (ImportError, KeyError, OSError, InfrastructureError) as exc:
        print(
            json.dumps(
                {"status": "pending_native", "reason": f"{type(exc).__name__}: {exc}"}, indent=2
            )
        )
        return 3
    manifest = Path(REPO_ROOT / "backend" / config["manifest"])
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    harness = Harness(config, port, scorer, mode="live", out_dir=args.out)
    harness.preflight(tasks)
    records = harness.run(harness.eligible)
    (args.out / "run-meta.json").write_text(
        json.dumps(
            {
                "mode": "live",
                "config": config,
                "manifest_hash": manifest_hash,
                "dataset_id": args.split,
                "commit_digest": harness.commit_digest,
            },
            indent=2,
            sort_keys=True,
        )
    )
    result = analyze(
        config, records, manifest_hash=manifest_hash, dataset_id=args.split, mode="live"
    )
    write_analysis(result, args.out / "benchmark-report.json")
    print(json.dumps({"status": result["report"]["status"]}))
    return 0


def cmd_analyze(args) -> int:
    from .evaluation import analyze, write_analysis

    meta = json.loads((args.results / "run-meta.json").read_text())
    records = _read_records(args.results)
    result = analyze(
        meta["config"],
        records,
        manifest_hash=meta.get("manifest_hash"),
        dataset_id=meta.get("dataset_id", meta["config"]["split"]),
        mode=meta["mode"],
    )
    write_analysis(result, args.out)
    print(
        json.dumps(
            {
                "status": result["report"]["status"],
                "research_outcome": result["report"]["research_outcome"],
            },
            indent=2,
        )
    )
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
    sm = sub.add_parser("smoke")
    sm.add_argument("--config", required=True, type=Path)
    sm.add_argument("--mode", required=True)
    sm.add_argument("--out", required=True, type=Path)
    sm.set_defaults(func=cmd_smoke)
    r = sub.add_parser("run")
    r.add_argument("--config", required=True, type=Path)
    r.add_argument("--split", required=True)
    r.add_argument("--out", required=True, type=Path)
    r.set_defaults(func=cmd_run)
    a = sub.add_parser("analyze")
    a.add_argument("--results", required=True, type=Path)
    a.add_argument("--out", required=True, type=Path)
    a.set_defaults(func=cmd_analyze)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
