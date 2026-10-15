"""Post-hoc code-only audit of saved raw replies; no generation or training.

Remove one exact outer Markdown fence, parse JSON, and take its source field
unchanged. Commit every extracted source before loading development scoring data.
The original strict-protocol baseline remains unchanged.
"""

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codejury.dev_bench import (
    ROOT, SEEDS, execute_tests, file_hash, load_runtime, load_scoring, passes,
    read_jsonl, summarize,
)
from codejury.stage2_core.registry import local_path
from codejury.stage2_tools.factory import make_tool_port


def extract_source(text):
    """No code edits, prose extraction, repair, retries or outcome-based selection."""
    if not isinstance(text, str):
        raise ValueError("Missing reply")
    text = text.strip()
    fenced = re.fullmatch(r"```(?:json)?[ \t]*\n(.*)\n```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    body = json.loads(text, object_pairs_hook=unique)
    if not isinstance(body, dict) or not isinstance(body.get("source"), str):
        raise ValueError("No single JSON source field")
    return body["source"]


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    baseline = read_jsonl(args.baseline / "results.jsonl")
    original_summary = json.loads((args.baseline / "summary.json").read_text())
    if file_hash(args.baseline / "results.jsonl") != original_summary["results_sha256"]:
        raise ValueError("Baseline results hash changed")
    protocol = original_summary["protocol"]
    if not protocol["full_population"] or len(baseline) != 900:
        raise ValueError("Complete baseline required")
    runtime = {r["base_problem_id"]: r for r in load_runtime()}
    if file_hash(ROOT / "runtime.jsonl") != protocol["runtime_sha256"]:
        raise ValueError("Runtime data changed")
    sandbox = make_tool_port(local_path("../integration/stage2/tools.yaml")).sandbox
    if sandbox.runtime_hash != protocol["runtime_hash"]:
        raise ValueError("Sandbox differs from the original experiment")
    sandbox.ready()
    args.out.mkdir(parents=True, exist_ok=False)
    write(args.out / "protocol.json", {
        "version": "codejury.raw-code-audit.v1",
        "baseline_results_sha256": file_hash(args.baseline / "results.jsonl"),
        "script_sha256": file_hash(Path(__file__)),
        "runtime_sha256": protocol["runtime_sha256"],
        "scoring_sha256": protocol["scoring_sha256"],
        "runner_runtime_hash": sandbox.runtime_hash,
        "extraction": "One optional outer json/unlabelled Markdown fence; parse JSON; "
                      "take source string verbatim. Ignore metadata schema failures. "
                      "No source edits, new sampling or hidden-outcome selection.",
        "scope": "Post-hoc code-only audit, not a replacement preregistered baseline. "
                 "Raw remains one-shot; jury uses multiple roles, tools and more compute.",
        "cache": "Identical source bytes for the same deterministic base execute once; "
                 "reuse outcomes for repeated seed records, disclosed in summary.",
        "sealed_assessment_opened": False,
    })
    commitments = []
    for row in baseline:
        if row["method"] != "B-base":
            continue
        with sqlite3.connect(f"file:{Path(row['ledger_directory']) / 'ledger.sqlite3'}?mode=ro", uri=True) as db:
            calls = db.execute(
                "SELECT body,response FROM requests WHERE definition='ModelRequest' ORDER BY rowid"
            ).fetchall()
        if len(calls) != 1 or json.loads(calls[0][0])["role"] != "raw":
            raise ValueError("Raw baseline must contain exactly one raw call")
        response = json.loads(calls[0][1])
        source, error = None, None
        try:
            if response["status"] != "ok":
                raise ValueError("Non-ok raw response")
            source = extract_source(response.get("text"))
        except (ValueError, TypeError) as exc:
            error = type(exc).__name__
        commitments.append({
            "base_problem_id": row["base_problem_id"], "seed": row["seed"],
            "tier": row["tier"], "method": "B-base-code-only-audit",
            "source": source, "extraction_error": error,
            "reply_sha256": hashlib.sha256((response.get("text") or "").encode()).hexdigest(),
        })
    expected = {(base, seed) for base in runtime for seed in SEEDS}
    if len(commitments) != 300 or {(r["base_problem_id"], r["seed"]) for r in commitments} != expected:
        raise ValueError("Incomplete extraction population")
    commitment_path = args.out / "commitments.jsonl"
    commitment_path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in commitments))
    print(f"Committed all 300 source extractions; {sum(r['source'] is not None for r in commitments)} parseable.", flush=True)
    # Only now open the unsealed development scorer. No reference is used to edit proposals.
    if file_hash(ROOT / "private/scoring.jsonl") != protocol["scoring_sha256"]:
        raise ValueError("Development scorer changed")
    scoring = load_scoring()
    cache, results = {}, []
    calls, reused = 0, 0
    for index, row in enumerate(commitments, 1):
        key = row["base_problem_id"], row["source"]
        if key in cache:
            outcome, detail = cache[key]
            reused += 1
        else:
            outcome, detail = "invalid", None
            if row["source"] is not None:
                create = runtime[row["base_problem_id"]]["run_create"]
                tests = create["supplied_tests"] + scoring[row["base_problem_id"]]["hidden_tests"]
                try:
                    executed = execute_tests(sandbox, row["source"], create, tests)
                    calls += len(executed)
                    outcome = "solved" if all(passes(r, t) for r, t in zip(executed, tests, strict=True)) else "incorrect"
                    detail = {"tests": len(tests), "passed": sum(passes(r, t) for r, t in zip(executed, tests, strict=True))}
                except ValueError as exc:
                    detail = {"static_rejection": type(exc).__name__}
            cache[key] = outcome, detail
        result = {k: v for k, v in row.items() if k != "source"}
        result.update(outcome=outcome, detail=detail)
        results.append(result)
        with (args.out / "results.jsonl").open("a") as stream:
            stream.write(json.dumps(result, sort_keys=True) + "\n")
        if index % 25 == 0:
            print(f"Scored {index}/300; unique proposals {len(cache)}; Docker function calls {calls}.", flush=True)
    jury = {(r["base_problem_id"], r["seed"]): r for r in baseline if r["method"] == "J-current"}
    report = {
        "version": "codejury.raw-code-audit.v1", "status": "complete",
        "protocol": json.loads((args.out / "protocol.json").read_text()),
        "commitments_sha256": file_hash(commitment_path),
        "results_sha256": file_hash(args.out / "results.jsonl"),
        "runs": 300, "unique_base_source_pairs": len(cache), "reused_records": reused,
        "docker_function_calls": calls,
        "extraction_failures": sum(r["source"] is None for r in commitments),
        "summary": summarize(results),
        "paired": [{
            "seed": seed,
            "raw_only_solved": sum(a["outcome"] == "solved" and jury[(a["base_problem_id"], seed)]["outcome"] != "solved" for a in results if a["seed"] == seed),
            "jury_only_solved": sum(a["outcome"] != "solved" and jury[(a["base_problem_id"], seed)]["outcome"] == "solved" for a in results if a["seed"] == seed),
        } for seed in SEEDS],
    }
    write(args.out / "summary.json", report)
    print(json.dumps(report["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()
