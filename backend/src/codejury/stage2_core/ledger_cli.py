"""Independent CPU bookkeeping smoke; no model or candidate execution."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .budgets import CAPS, BudgetAccount, BudgetExceeded, zero_usage
from .contract_check import REPO_ROOT, check
from .contracts import cache_key, source_hash
from .leases import ComputeLease, LeaseBusy
from .ledger import Ledger


def self_test() -> dict:
    checks = []

    def require(condition, name):
        if not condition:
            raise RuntimeError("Self-test failed: " + name)
        checks.append(name)

    def fixture(name):
        return json.loads((REPO_ROOT / f"contracts/stage2-fixtures/{name}.json").read_text())

    require(check(REPO_ROOT / "contracts")["synthetic_fixtures"] == 49, "frozen_contract")
    with TemporaryDirectory(prefix="codejury-stage2-ledger-") as temporary:
        root = Path(temporary)
        ledger = Ledger(root / "runtime")
        snapshot = fixture("snapshot-running")
        ledger.create_run(
            "fixture-run",
            snapshot["problem"],
            mode="fixture",
            profile=CAPS,
            model_configs=[
                c["model_config_hash"] for c in snapshot["candidates"] if c["model_config_hash"]
            ],
            final_executions=4,
        )
        fields = set(fixture("candidate-revision-draft"))
        for candidate in snapshot["candidates"]:
            draft = {key: value for key, value in candidate.items() if key in fields}
            ledger.commit_candidate("fixture-run", draft)
        for test in snapshot["tests"]:
            ledger.add_test("fixture-run", test)
        request = fixture("tool-evaluate-request")
        request["remaining_budget"] = ledger.accounts["fixture-run"].remaining()
        request["remaining_budget"]["elapsed_ms"] -= 1000
        ledger.dispatch_tool(request)
        result = fixture("tool-evaluate-result")
        ledger.settle_tool(result)
        require(
            ledger.snapshot("fixture-run")["resource_usage"]["function_executions"]
            == result["usage"]["function_executions"],
            "synthetic_delta_accounted_once",
        )
        try:
            ledger.settle_tool(result)
        except ValueError:
            checks.append("duplicate_result_rejected")
        else:
            raise RuntimeError("Duplicate result was accepted")
        source = snapshot["problem"]["source"]
        require(ledger.read_object(source_hash(source)).decode() == source, "immutable_source")
        key = cache_key(source_hash(source), snapshot["tests"][0], "a" * 64, "b" * 64, "c" * 64)
        ledger.cache_put(key, result["executions"][0])
        require(
            Ledger(ledger.directory).cache_get(key) == result["executions"][0], "exact_cache_reopen"
        )
        reopened = Ledger(ledger.directory)
        require(reopened.recover() == ["fixture-run"], "restart_recovery")
        recovered = reopened.snapshot("fixture-run")
        require(
            recovered["status"] == "infrastructure_error"
            and recovered["decision"]["selected_candidate_id"] is None,
            "no_patch_after_restart",
        )
        path = root / "compute.lock"
        with ComputeLease(path, owner="self-test", job_id="one", kind="runtime"):
            try:
                ComputeLease(path, owner="self-test", job_id="two", kind="training").acquire()
            except LeaseBusy:
                checks.append("exclusive_compute")
            else:
                raise RuntimeError("Two compute jobs acquired the lease")
        with ComputeLease(path, owner="self-test", job_id="three", kind="benchmark"):
            checks.append("released_compute_reacquired")
        clock = [1.0]
        budget = BudgetAccount(
            {**CAPS, "function_executions": 10}, final_executions=4, clock=lambda: clock[0]
        )
        ceiling = {**dict.fromkeys(CAPS, 0), "elapsed_ms": 1000, "function_executions": 7}
        try:
            budget.dispatch("overflow", ceiling)
        except BudgetExceeded:
            checks.append("final_verification_reserved")
        else:
            raise RuntimeError("Final qualification reserve was spent")
        ceiling["function_executions"] = 6
        budget.dispatch("bounded", ceiling)
        clock[0] += 0.5
        budget.settle("bounded", {**zero_usage(), "function_executions": 6, "elapsed_ms": 200})
        require(budget.usage()["elapsed_ms"] == 500, "monotonic_wall_accounting")
    return {
        "status": "passed",
        "checks": checks,
        "scope": "CPU bookkeeping with synthetic tool results; no candidate execution",
        "real_inference": False,
        "real_sandbox_calls": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["self-test"])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = self_test()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
