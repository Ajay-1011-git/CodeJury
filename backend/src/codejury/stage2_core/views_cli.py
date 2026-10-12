"""Disclosed synthetic view audit, with no inference or candidate execution."""

import argparse
import json
from pathlib import Path

from jsonschema import ValidationError

from .candidates import parse_draft
from .contract_check import check
from .intake import prepare
from .views import freeze_initial, judge, revision


def audit(fixtures):
    fixtures = Path(fixtures)
    check(fixtures.parent)
    checks = []

    def fixture(name):
        return json.loads((fixtures / f"{name}.json").read_text())

    def require(condition, name):
        if not condition:
            raise RuntimeError("View audit failed: " + name)
        checks.append(name)

    create = fixture("run-create-helper")
    create["source"] += "\n# ORIGINAL_AND_HELPER_BODY_SENTINEL\n"
    problem, tests = prepare(create)
    views = freeze_initial(problem, tests)
    require(
        "ORIGINAL_AND_HELPER_BODY_SENTINEL" in views.a
        and "ORIGINAL_AND_HELPER_BODY_SENTINEL" not in views.b,
        "body_separation",
    )
    require("pair_gcd(a, b)" in views.b and "return gcd" not in views.b, "helper_interface_only")
    require(tests[0]["test_id"] != create["supplied_tests"][0]["test_id"], "controller_test_ids")
    problem["hidden_reference"] = "HIDDEN_SENTINEL"
    try:
        freeze_initial(problem, tests)
    except ValidationError:
        checks.append("hidden_fields_rejected")
    else:
        raise RuntimeError("Hidden field accepted")
    snapshot = fixture("snapshot-running")
    candidate = next(c for c in snapshot["candidates"] if c["candidate_id"] == "c-a")
    row = fixture("tool-evaluate-result")["executions"][0]
    row.update(actual_output=99, outcome="fail")
    revised = revision("fixer_a", snapshot["problem"], snapshot["tests"], candidate, [row])
    require(
        '"actual_output":99' in revised
        and '"expected":5' in revised
        and '"expected":99' not in revised,
        "observed_feedback_no_guessed_expectation",
    )
    text = judge(fixture("state-snapshot"), snapshot["tests"], snapshot["candidates"], [])
    require("def sum_values" not in text, "bounded_judge_state")
    require(
        parse_draft(json.dumps(fixture("repair-draft"))) == fixture("repair-draft"),
        "strict_repair_contract",
    )
    for definition, name in [("CriticDraft", "critic-draft"), ("JudgeDraft", "judge-draft")]:
        require(parse_draft(json.dumps(fixture(name)), definition) == fixture(name), definition)
    return {
        "status": "passed",
        "runtime_mode": "fixture",
        "native_inference": False,
        "candidate_execution": False,
        "checks": checks,
        "view_config_hash": views.view_config_hash,
        "limitations": [
            "No real Fixer B adapter or Sarvesh ToolPort is installed.",
            "Fixtures prove view contracts, not repair correctness or diversity.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.fixtures)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
