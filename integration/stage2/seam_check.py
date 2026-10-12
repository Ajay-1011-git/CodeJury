"""Check the actual owner boundary with public fixture candidates in the real sandbox."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from codejury.stage2_core.budgets import CAPS
from codejury.stage2_core.candidates import qualification
from codejury.stage2_core.contract_check import REPO_ROOT
from codejury.stage2_core.contracts import CheckedToolPort
from codejury.stage2_core.intake import validate_source
from codejury.stage2_core.ledger import Ledger
from codejury.stage2_tools.factory import make_tool_port


def fixture(name):
    return json.loads((REPO_ROOT / f"contracts/stage2-fixtures/{name}.json").read_text())


def check(config):
    tool = make_tool_port(config)
    environment = tool.sandbox.ready()
    with TemporaryDirectory(prefix="codejury-stage2-seam-") as temporary:
        ledger = Ledger(Path(temporary))
        snapshot = fixture("snapshot-running")
        ledger.create_run(
            "fixture-run",
            snapshot["problem"],
            mode="fixture",
            profile=CAPS,
            model_configs=[
                c["model_config_hash"] for c in snapshot["candidates"] if c["model_config_hash"]
            ],
        )
        fields = set(fixture("candidate-revision-draft"))
        for candidate in snapshot["candidates"]:
            ledger.commit_candidate("fixture-run", {k: candidate[k] for k in fields})
        for test in snapshot["tests"]:
            ledger.add_test("fixture-run", test)
        for candidate in snapshot["candidates"]:
            if not validate_source(
                ledger, "fixture-run", tool, candidate["source"], snapshot["tests"], Event()
            ):
                raise ValueError("Native semantic receipt was refused")
        request = fixture("tool-evaluate-request")
        request["remaining_budget"] = ledger.accounts["fixture-run"].remaining()
        ledger.dispatch_tool(request)
        result = CheckedToolPort(tool).call(request, Event())
        ledger.settle_tool(result)
        projected = qualification(ledger, "fixture-run", runtime_hash=tool.sandbox.runtime_hash)
        eligible = [
            c["candidate_id"] for c in projected["candidates"] if c["eligibility"] == "eligible"
        ]
        if result["status"] != "ok" or set(eligible) != {"c-a", "c-b"}:
            raise ValueError("Native ToolPort/core qualification seam failed")
        usage = ledger.snapshot("fixture-run")["resource_usage"]
        if usage["function_executions"] != result["usage"]["function_executions"]:
            raise ValueError("Execution costs were not settled exactly once")
        return {
            "status": "passed",
            "source_mode": "fixture",
            "tool_mode": "native_sandbox",
            "environment": environment,
            "runtime_hash": tool.sandbox.runtime_hash,
            "eligible_fixture_candidates": eligible,
            "actual_function_executions": usage["function_executions"],
            "native_model_generations": 0,
            "training_episode": False,
            "scope": "Synthetic published candidates evaluated by real tools and ledger; "
            "not measured learned A/B episodes or model quality.",
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = check(args.config)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
