"""Native raw/adapter smoke, hashes, clean role switching and actual candidate output."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ..contracts import REPO_ROOT
from ..contracts.intake import validate_request
from ..properties import equal
from ..runner import DockerRunner
from .views import parse_repair, repair_view
from .worker import BACKEND, ModelWorker, file_hash


def public_smoke_request():
    # Separate public mechanics demo. Sum-family overlap with training is disclosed.
    request = json.loads((REPO_ROOT / "contracts/fixtures/run-create.json").read_text())
    request.update(
        source="def total(values):\n    return 0\n",
        function_name="total",
        contract_text="Return the sum of all input integers; an empty input returns zero.",
        approved_property="sum_ints",
        supplied_tests=[{"test_id": "sum-visible", "args": [[2, -4, 7]], "expected": 5}],
    )
    return request


def smoke(config, *, raw=False, adapter=None, request=None):
    request = request or public_smoke_request()
    validate_request(request)
    worker = ModelWorker(config, force_raw=raw, adapter_override=adapter)
    hashes = {
        path.name: file_hash(path)
        for path in worker.cfg["model_dir"].iterdir()
        if path.is_file() and path.suffix in {".json", ".safetensors", ".jinja"}
    }
    evidence = []
    runner = DockerRunner()
    for test in request["supplied_tests"]:
        result = runner.execute(request["source"], request["function_name"], test["args"])
        evidence.append(
            {"test_id": test["test_id"], "args": test["args"], "result": asdict(result)}
        )
    view = repair_view(request, evidence)
    first = worker.generate("fixer_a", view, max_tokens=1024)
    effective = first
    used_retry = False
    report = {
        "raw_loaded": True,
        "model_id": worker.identity["model_id"],
        "model_revision": worker.identity["model_revision"],
        "local_file_sha256": hashes,
        "adapter_sha256": worker.identity["adapter_sha256"],
        "generation": asdict(first),
        "switch_verified": False,
        "candidate_valid": False,
        "demo_note": (
            "Public mechanics demo; sum algorithm family overlaps training. Not scored assessment."
        ),
    }
    try:
        try:
            candidate = parse_repair(first.text, request)
        except ValueError:
            used_retry = True
            effective = worker.generate("fixer_a", view, max_tokens=1024, format_retry=True)
            report["format_retry"] = asdict(effective)
            candidate = parse_repair(effective.text, request)
        report["candidate"] = candidate
        result = runner.execute(
            candidate["source"], request["function_name"], request["supplied_tests"][0]["args"]
        )
        report["candidate_execution"] = asdict(result)
        report["candidate_executable"] = result.exception_type is None and not result.input_mutated
        report["candidate_valid"] = report["candidate_executable"] and equal(
            result.actual_output, request["supplied_tests"][0]["expected"]
        )
    except ValueError as exc:
        report["generation_error"] = str(exc)
    if not raw:
        a_hash = worker.parameter_hash()
        worker.switch("critic")
        raw_hash = worker.parameter_hash()
        worker.switch("fixer_a")
        again_hash = worker.parameter_hash()
        second = worker.generate("fixer_a", view, max_tokens=1024, format_retry=used_retry)
        report["parameter_hashes"] = {"a_first": a_hash, "raw": raw_hash, "a_reloaded": again_hash}
        report["switch_verified"] = (
            a_hash == again_hash and a_hash != raw_hash and effective.text == second.text
        )
        report["reload_generation"] = asdict(second)
    out = BACKEND / "artifacts/training" / ("raw-smoke.json" if raw else "model-smoke.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["smoke"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()
    report = smoke(
        args.config,
        raw=args.raw,
        adapter=args.adapter,
        request=json.loads(args.request.read_text()) if args.request else None,
    )
    return 0 if report["candidate_valid"] and (args.raw or report["switch_verified"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
