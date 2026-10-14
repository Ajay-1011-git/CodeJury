"""Sequential local trial, queued behind the complete baseline; no downloads/cloud."""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codejury.stage2_core.data import write_report
from codejury.stage2_core.registry import Registry, local_path
from codejury.stage2_core.training.fixer_a import evaluate
from codejury.stage2_core.training.fixer_a.select import select
from codejury.stage2_core.training.roles import train
from codejury.stage2_core.training.split_guard import check_logic_split

RECIPE = {
    "pilot_steps": 10,
    "steps": 100,
    "save_every": 50,
    "batch_size": 1,
    "max_seq_length": 2048,
    "learning_rate": 0.00005,
    "grad_checkpoint": True,
    "seed": 17,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--deadline-utc", required=True)
    args = parser.parse_args()
    deadline = datetime.fromisoformat(args.deadline_utc)
    if deadline.tzinfo is None:
        parser.error("Declare a timezone-aware UTC deadline")
    out = args.out.resolve()
    if local_path("artifacts") not in out.parents:
        parser.error("Private native trial must stay in ignored artifacts")
    corpus = args.corpus.resolve()
    manifest_path = corpus / "manifest.json"
    corpus_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    disjoint = check_logic_split(corpus, local_path("data/dev_bench"))
    registry_path = local_path("artifacts/stage2_core/judge-learning/selected-v2/registry.json")
    registry = Registry(registry_path)
    out.mkdir(parents=True, exist_ok=False)
    write_report(
        out / "protocol.json",
        {
            "version": "stage2.logic-trial.v1",
            "recipe": RECIPE,
            "corpus_manifest_hash": corpus_hash,
            "dev_disjoint": disjoint,
            "registry_hash": registry.manifest_hash,
            "wait_for": str(args.baseline.resolve() / "summary.json"),
            "deadline_utc": deadline.isoformat(),
            "selection": (
                "Existing full 20-variant/10-base executed validation gate; solved "
                "count, wrong acceptance and malformed output must not regress. No "
                "loss ranking."
            ),
            "automatic_default_switch": False,
            "scope": "Bounded same-base, same-topology A-only trial; other roles remain unchanged.",
        },
    )
    print("Queued local training behind the complete 900-run baseline.", flush=True)
    summary = args.baseline / "summary.json"
    acceptance = args.baseline / "phase0-accepted.json"
    while not summary.is_file() or not acceptance.is_file():
        if datetime.now(timezone.utc) >= deadline:
            write_report(
                out / "not_started.json", {"status": "deadline_reached", "training_started": False}
            )
            print(
                "Deadline reached before compute became available; training not started.",
                flush=True,
            )
            return 1
        time.sleep(15)
    if datetime.now(timezone.utc) >= deadline:
        write_report(
            out / "not_started.json", {"status": "deadline_reached", "training_started": False}
        )
        return 1
    accepted = json.loads(acceptance.read_text())
    if (
        accepted.get("status") != "accepted"
        or accepted.get("summary_sha256") != hashlib.sha256(summary.read_bytes()).hexdigest()
        or not accepted.get("commit")
    ):
        raise ValueError("Matching completed/committed Phase 0 acceptance is required")
    baseline = json.loads(summary.read_text())
    if (
        baseline["protocol"]["full_population"] is not True
        or len((args.baseline / "results.jsonl").read_text().splitlines()) != 900
    ):
        raise ValueError("A complete scored full baseline is required")
    if (
        hashlib.sha256(manifest_path.read_bytes()).hexdigest() != corpus_hash
        or Registry(registry_path).manifest_hash != registry.manifest_hash
    ):
        raise ValueError("Queued data or initialization changed")
    print("Baseline complete. Starting the local verified pilot.", flush=True)
    if check_logic_split(corpus, local_path("data/dev_bench")) != disjoint:
        raise ValueError("Queued overlap proof changed")
    runtime = local_path("config/stage2_core/runtime.yaml")
    config = local_path("config/stage2_core/training/fixer_a.yaml")
    train("fixer_a", corpus, registry_path, runtime, RECIPE, out / "pilot", phase="pilot")
    full = train(
        "fixer_a",
        corpus,
        registry_path,
        runtime,
        RECIPE,
        out / "full",
        phase="full",
        pilot=out / "pilot/report.json",
    )
    evaluate(
        config,
        out / "validation-baseline",
        registry_path=registry_path,
        all_variants=True,
        roles=("fixer_a",),
    )
    candidates = []
    for checkpoint in full["candidates"]:
        candidate_out = out / f"validation-step-{checkpoint['step']}"
        evaluate(
            config,
            candidate_out,
            registry_path=checkpoint["registry_path"],
            all_variants=True,
            roles=("fixer_a",),
        )
        candidates.append(candidate_out / "report.json")
    result = select(config, out / "validation-baseline/report.json", candidates, out / "selected")
    print(json.dumps(result, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
