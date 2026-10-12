"""Allowlisted runtime views. No corpus or hidden-assessment reader exists here."""

import json
from dataclasses import dataclass

from codejury.stage2_core.contracts import canonical_json, checked, json_hash

VIEW_VERSION = "stage2.views.v1"
REPAIR_FORMAT = {
    "source": "complete Python target/helper bundle",
    "diagnosis": "brief diagnosis",
    "assumptions": [],
    "requirement_ids": [],
    "suspected_sites": [],
    "suggested_families": [],
}


def visible_problem(problem):
    problem = checked(problem, "Problem")
    return {
        k: problem[k]
        for k in (
            "function_name",
            "signature",
            "contract_text",
            "domain_schema",
            "helper_interfaces",
            "requirements",
            "allowed_dependencies",
            "input_codec_version",
        )
    }


def visible_tests(tests):
    result = []
    for test in tests:
        test = checked(test, "TestCase")
        result.append(
            {
                k: test[k]
                for k in (
                    "test_id",
                    "inputs",
                    "related_inputs",
                    "oracle_spec",
                    "oracle_status",
                    "requirement_ids",
                    "domain_valid",
                )
            }
        )
    return result


def evidence(executions, tests, candidates, *, trace_reader=None):
    """Join registered facts; never derive a guessed expected value from an output."""
    tests = {t["test_id"]: checked(t, "TestCase") for t in tests}
    candidates = {c["candidate_id"]: checked(c, "Candidate") for c in candidates}
    result = []
    for row in executions:
        row = checked(row, "Execution")
        if row["test_id"] not in tests or row["candidate_id"] not in candidates:
            raise ValueError("Evidence refers to unregistered test or candidate")
        test, candidate = tests[row["test_id"]], candidates[row["candidate_id"]]
        item = {
            **row,
            "candidate_source_hash": candidate["source_hash"],
            "inputs": test["inputs"],
            "related_inputs": test["related_inputs"],
            "oracle_spec": test["oracle_spec"],
            "oracle_status": test["oracle_status"],
            "requirement_ids": test["requirement_ids"],
        }
        if row["trace_ref"] is not None and trace_reader is not None:
            # Exact bounded trace bytes, with truncation disclosed, never synthesized.
            raw = trace_reader(row["trace_ref"])
            item["trace"] = raw[:8192].decode("utf-8", errors="replace")
            item["view_trace_truncated"] = len(raw) > 8192
        result.append(item)
    return result


def prompt(role, payload):
    if role in {"fixer_a", "fixer_b"}:
        instruction = (
            "Repair the supplied buggy bundle."
            if role == "fixer_a"
            else "Independently reconstruct the complete bundle from the interfaces."
        )
        instruction += " Preserve every interface. Return only JSON with these exact fields: "
        instruction += json.dumps(REPAIR_FORMAT) + ". No Markdown."
    elif role == "critic":
        instruction = (
            "Propose a bounded CriticDraft experiment using only approved requirements "
            "and property templates. Never invent literal expectations. Return JSON."
        )
    elif role == "judge":
        instruction = (
            "Choose one available action in this frozen state. Return only JudgeDraft "
            "JSON: state_id, action_option_id, evidence_ids, rationale."
        )
    else:
        raise ValueError("Unsupported role view")
    return instruction + "\nRuntime-visible facts:\n" + canonical_json(payload).decode()


@dataclass(frozen=True)
class InitialViews:
    a: str
    b: str
    view_config_hash: str


def freeze_initial(problem, tests, *, original_evidence=()):
    base = {"problem": visible_problem(problem), "tests": visible_tests(tests)}
    a = {
        **base,
        "buggy_source": problem["source"],
        "evidence": [checked(e, "Execution") for e in original_evidence],
    }
    return InitialViews(
        prompt("fixer_a", a),
        prompt("fixer_b", base),
        json_hash({"version": VIEW_VERSION, "repair_format": REPAIR_FORMAT}),
    )


def revision(role, problem, tests, candidate, executions, *, trace_reader=None):
    candidate = checked(candidate, "Candidate")
    if (
        role not in {"fixer_a", "fixer_b"}
        or candidate["origin"] not in {role, role + "_revision"}
        or candidate["problem_id"] != problem["problem_id"]
    ):
        raise ValueError("Revision role/parent mismatch")
    if any(e["candidate_id"] != candidate["candidate_id"] for e in executions):
        raise ValueError("Revision evidence must concern this exact parent")
    return prompt(
        role,
        {
            "problem": visible_problem(problem),
            "tests": visible_tests(tests),
            "parent": candidate,
            "evidence": evidence(executions, tests, [candidate], trace_reader=trace_reader),
        },
    )


def critic(problem, tests, candidates, executions, *, trace_reader=None):
    problem = checked(problem, "Problem")
    approved = [r for r in problem["requirements"] if r["approval_status"] == "approved"]
    candidates = [checked(c, "Candidate") for c in candidates]
    if any(c["problem_id"] != problem["problem_id"] for c in candidates):
        raise ValueError("Critic candidate problem mismatch")
    return prompt(
        "critic",
        {
            "problem": visible_problem(problem),
            "approved_registry": approved,
            "candidates": candidates,
            "tests": visible_tests(tests),
            "evidence": evidence(executions, tests, candidates, trace_reader=trace_reader),
        },
    )


def judge(state, tests, candidates, executions):
    state = checked(state, "StateSnapshot")
    candidates = [checked(c, "Candidate") for c in candidates]
    if any(c["problem_id"] != state["problem_id"] for c in candidates):
        raise ValueError("Judge candidate problem mismatch")
    # Deterministic bounded summaries; original and candidate bodies stay private here.
    facts = evidence(executions, tests, candidates)
    payload = {
        "state": state,
        "visible_evidence": facts[:20],
        "omitted_evidence_count": max(0, len(facts) - 20),
    }
    result = prompt("judge", payload)
    if len(result.encode()) > 64000:
        raise ValueError("Judge view exceeds bound; reduce visible summaries explicitly")
    return result
