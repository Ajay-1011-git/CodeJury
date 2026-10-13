"""Label-side target validation: every positive target is execution-filtered offline.

A Critic target counts as a valid counterexample only when, run through the same Investigator the
runtime uses, it yields an authoritative test that a target candidate fails while the TRAINING
reference (label side) passes. Model-invented literals stay proposed and are never accepted as
counterexamples, even when empirically correct.
"""

import copy
import threading

from ...codec import errors, value_hash
from ...domains import check_args
from ...investigation.engine import InvestigationError, Investigator
from ...oracles import OracleError, expected_output, template_compatible
from ...runner import Evaluator, hard_rejection

NO_OBJECTION_RATIONALE = (
    "No authorized failure was found in the visible evidence; this is an observation proposal "
    "to look at general inputs, not proof that the candidates are correct."
)


def no_objection(bundle: dict, mode: str) -> dict:
    """A schema-valid general observation proposal; never a null/null proposal source."""
    targets = [c["candidate_id"] for c in bundle["candidates"] if c["origin"] != "original"][:8]
    draft = {
        "mode": mode,
        "requirement_ids": [],
        "generator_spec": {"family": "general", "argument_index": 0, "parameters": {}, "seed": 0},
        "concrete_inputs": None,
        "oracle_spec": {
            "kind": "observation",
            "hypothesis": "General inputs show no difference from the stated contract.",
        },
        "target_candidate_ids": targets,
        "rationale": NO_OBJECTION_RATIONALE,
    }
    return draft


def _proposal(draft: dict, pid: str) -> dict:
    return {
        "schema_version": "stage2.v1",
        "proposal_id": pid,
        "requirement_ids": draft["requirement_ids"],
        "generator_spec": draft["generator_spec"],
        "concrete_inputs": draft["concrete_inputs"],
        "oracle_spec": draft["oracle_spec"],
        "rationale": draft["rationale"],
        "target_candidate_ids": draft["target_candidate_ids"],
    }


def validate_draft(sandbox, bundle: dict, draft: dict, reference_source: str, *, budget: int = 400):
    """(valid, reason, stats). Executes through `sandbox`; never host-executes anything itself."""
    problems = errors(draft, "CriticDraft")
    if problems:
        return False, f"schema: {problems[0]}", {}
    if (draft["generator_spec"] is None) == (draft["concrete_inputs"] is None):
        return False, "exactly one of generator_spec/concrete_inputs is required", {}
    if draft["oracle_spec"]["kind"] in ("literal", "observation"):
        return (
            False,
            f"{draft['oracle_spec']['kind']} oracle cannot be an authorized counterexample",
            {},
        )
    problem = bundle["problem"]
    candidates = [c for c in bundle["candidates"] if c["origin"] != "original"]
    ev = Evaluator(
        sandbox, problem, id_prefix="lbl", max_executions=budget, cancel=threading.Event()
    )
    try:
        out = Investigator(
            ev,
            problem,
            _proposal(draft, "label"),
            candidates,
            bundle["tests"],
            max_inputs=32,
            id_prefix="lbl",
        ).run()
    except (InvestigationError, OracleError) as exc:
        return False, f"investigation: {exc}", {}
    authoritative = [
        t for t in out.tests if t["oracle_status"] == "authoritative" and t["domain_valid"]
    ]
    if not authoritative:
        return False, "no authoritative domain-valid test was admitted", {"admitted": 0}
    by_id = {t["test_id"]: t for t in authoritative}
    failing = [
        e
        for e in out.executions
        if e["test_id"] in by_id and hard_rejection(e, by_id[e["test_id"]])
    ]
    if not failing:
        return (
            False,
            "no target candidate fails an authoritative test",
            {"admitted": len(authoritative)},
        )
    reference = {"candidate_id": "reference", "source": reference_source}
    rows = Evaluator(
        sandbox, problem, id_prefix="ref", max_executions=budget, cancel=threading.Event()
    ).evaluate(reference, authoritative, check=False)
    if len(rows) != len(authoritative) or any(hard_rejection(r, by_id[r["test_id"]]) for r in rows):
        return False, "reference solution does not pass the authoritative tests", {}
    return True, "ok", {"admitted": len(authoritative), "failures": len(failing)}


# -- invalid / conflicting proposal variants (synthetic, runtime-visible) -----------------------
def _bump(domain: dict, value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value + 1_000_000
    if isinstance(value, list) and value:
        return [_bump(domain.get("item_domain", {}), value[0]), *value[1:]]
    return value


def invalid_variants(bundle: dict, draft: dict) -> list[dict]:
    """Pending proposals the gate must reject, each with the gate's own reason."""
    problem, out = bundle["problem"], []
    schema = problem["domain_schema"]
    base_inputs = (
        draft["concrete_inputs"] or [[a for a in [_sample(s["domain"]) for s in schema]]]
    )[0]
    bad = [_bump(schema[0]["domain"], base_inputs[0]), *base_inputs[1:]]
    reason = check_args(schema, bad)
    if reason:
        out.append(
            _pending(
                "out_of_domain",
                {**_cd(draft), "concrete_inputs": [bad], "generator_spec": None},
                reason,
            )
        )
    out.append(
        _pending(
            "unregistered_property",
            {
                **_cd(draft),
                "oracle_spec": {
                    "kind": "property",
                    "property_id": "sort_descending_ints",
                    "parameters": {},
                },
            },
            "property template sort_descending_ints is not in the reviewed registry",
        )
    )
    for req in problem["requirements"]:
        if (
            req["approval_status"] == "approved"
            and req["property_template_id"]
            and template_compatible(req["property_template_id"], schema)
        ):
            ref = expected_output(req["property_template_id"], base_inputs)
            wrong = (
                ref + 1
                if isinstance(ref, int) and not isinstance(ref, bool)
                else [*ref, 0]
                if isinstance(ref, list)
                else None
            )
            if wrong is not None:
                out.append(
                    _pending(
                        "conflicting_literal",
                        {
                            **_cd(draft),
                            "concrete_inputs": [base_inputs],
                            "generator_spec": None,
                            "oracle_spec": {"kind": "literal", "expected": wrong},
                        },
                        f"literal expectation contradicts approved {req['requirement_id']}",
                    )
                )
            break
    return out


def _cd(draft: dict) -> dict:
    return copy.deepcopy(draft)


def _pending(kind: str, proposal: dict, reason: str) -> dict:
    return {
        "kind": kind,
        "proposal": proposal,
        "gate_reason": reason,
        "proposal_hash": value_hash(proposal),
    }


def _sample(domain: dict):
    k = domain["kind"]
    if k == "integer":
        return domain["min"]
    if k == "list":
        return []
    if k == "boolean":
        return False
    if k == "string":
        return ""
    return None
