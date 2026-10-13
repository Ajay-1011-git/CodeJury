"""Explicit reviewed bootstrap, never presented as a learned Critic or a model response."""

from ..candidates import hard_suite
from ..contracts import canonical_json, checked
from ..views import critic


def reviewed_proposal(problem, targets, mode, seed, *, observation=False):
    approved = [r for r in problem["requirements"] if r["approval_status"] == "approved"]
    properties = [r for r in approved if r["property_template_id"]]
    return checked(
        {
            "mode": mode,
            "requirement_ids": [r["requirement_id"] for r in approved],
            "generator_spec": {
                "family": "general",
                "argument_index": 0,
                "parameters": {},
                "seed": seed,
            },
            "concrete_inputs": None,
            "oracle_spec": {
                "kind": "property",
                "property_id": properties[0]["property_template_id"],
                "parameters": {},
            }
            if properties and not observation
            else {
                "kind": "observation",
                "hypothesis": "Compare outputs without asserting unapproved expectations",
            },
            "target_candidate_ids": list(targets),
            "rationale": "Explore the approved property on bounded domain inputs"
            if properties and not observation
            else "No authorized failure is established; retain a bounded observation experiment",
        },
        "CriticDraft",
    )


def critic_input_prompt(
    problem, tests, candidates, executions, mode, seed, *, gaps=(), trace_reader=None
):
    # Bound the shared training/inference view explicitly, never silently truncate tokens.
    selected = executions[-4:]
    current_suite = hard_suite(problem, tests)[1]
    referenced = {e["test_id"] for e in selected}
    prioritized = [t for t in tests if t["test_id"] in referenced]
    prioritized += [t for t in tests if t["oracle_status"] == "authoritative"][:4]
    prioritized += list(reversed(tests))
    visible_tests, seen = [], set()
    for test in prioritized:
        if test["test_id"] not in seen and len(visible_tests) < 8:
            visible_tests.append(test)
            seen.add(test["test_id"])
    result = critic(
        problem,
        visible_tests,
        candidates,
        selected,
        trace_reader=trace_reader,
        trace_byte_limit=512,
    )
    result += "\nOmitted execution summaries: " + str(len(executions) - len(selected))
    result += "\nOmitted registered tests: " + str(len(tests) - len(visible_tests))
    ids = {c["candidate_id"] for c in candidates}
    current_gaps = [
        g
        for g in gaps
        if g["candidate_id"] in ids
        and g["suite_hash"] == current_suite
        and any(
            c["candidate_id"] == g["candidate_id"]
            and c["source_hash"] == g["candidate_source_hash"]
            for c in candidates
        )
    ]
    result += (
        "\nSource-matched audit gaps (survivors are not proof of bugs):\n"
        + canonical_json(current_gaps[:4]).decode()
        + "\nOmitted audit gaps: "
        + str(max(0, len(current_gaps) - 4))
    )
    shape = reviewed_proposal(problem, [c["candidate_id"] for c in candidates], mode, seed)
    return (
        result + "\nReturn only CriticDraft JSON, without Markdown. Preserve all seven fields. "
        "Exactly one of generator_spec/concrete_inputs must be non-null. Mode: "
        + mode
        + "\nRequired output shape (choose a useful experiment; no new literal expectations):\n"
        + canonical_json(shape).decode()
        + "\nRegistered generator families: general, empty, singleton, duplicates, ascending, "
        "descending, boundary, negative, unicode, missing_key, audit_site."
    )
