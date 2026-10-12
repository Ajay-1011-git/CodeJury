"""Oracle admission: who may reject a patch, and the verdict logic for executed tests.

Only user/reviewed_contract approval authorizes executable expectations. A model-proposed
literal, an inferred relation or an observation is never hard evidence, even when it agrees with
a training reference.
"""

from ..codec import typed_equal, value_hash
from ..domains import check_args, validate_arg_domains
from .registry import (
    METAMORPHIC,
    TEMPLATES,
    expected_output,
    relation_inputs_valid,
    template_compatible,
)

AUTHORIZING_SOURCES = {"user", "reviewed_contract"}


class OracleError(ValueError):
    pass


def _approved_by_template(requirements: list[dict]) -> dict[str, dict]:
    return {
        r["requirement_id"]: r
        for r in requirements
        if r["approval_status"] == "approved" and r["property_template_id"]
    }


def check_requirements(requirements: list[dict], domain_schema: list[dict]) -> None:
    ids = set()
    for req in requirements:
        if req["requirement_id"] in ids:
            raise OracleError(f"Duplicate requirement {req['requirement_id']}")
        ids.add(req["requirement_id"])
        approved = req["approval_status"] == "approved"
        if approved and req["source"] not in AUTHORIZING_SOURCES:
            raise OracleError("Only user/reviewed_contract requirements can be approved")
        template = req["property_template_id"]
        if template is None:
            continue
        if template not in TEMPLATES:
            if approved:
                raise OracleError(f"Approved requirement uses unregistered template {template}")
            continue
        if req["parameters"] not in ({}, None):
            raise OracleError(f"Template {template} takes no parameters")
        if approved and not template_compatible(template, domain_schema):
            raise OracleError(f"Template {template} is incompatible with the argument domains")


def build_supplied_tests(run: dict) -> list[dict]:
    """Authoritative literal TestCases from the user's supplied tests."""
    tests = []
    for t in run["supplied_tests"]:
        reason = check_args(run["domain_schema"], t["inputs"])
        tests.append(
            {
                "schema_version": "stage2.v1",
                "test_id": t["test_id"],
                "input_codec_version": "json.v1",
                "inputs": t["inputs"],
                "related_inputs": None,
                "oracle_spec": {"kind": "literal", "expected": t["expected"]},
                "oracle_status": "authoritative" if reason is None else "rejected",
                "oracle_source": "user",
                "domain_valid": reason is None,
                "requirement_ids": t["requirement_ids"],
                "provenance": "supplied",
            }
        )
    return tests


def check_intake(run: dict) -> None:
    """Reject malformed or contradictory authoritative inputs before any run is scheduled."""
    validate_arg_domains(run["domain_schema"])
    check_requirements(run["requirements"], run["domain_schema"])
    approved = _approved_by_template(run["requirements"])
    known = {r["requirement_id"] for r in run["requirements"]}
    seen_ids, seen_inputs = set(), {}
    for test in run["supplied_tests"]:
        if test["test_id"] in seen_ids:
            raise OracleError(f"Duplicate supplied test {test['test_id']}")
        seen_ids.add(test["test_id"])
        reason = check_args(run["domain_schema"], test["inputs"])
        if reason:
            raise OracleError(f"Supplied test {test['test_id']} is outside the domain: {reason}")
        unknown = set(test["requirement_ids"]) - known
        if unknown:
            raise OracleError(
                f"Test {test['test_id']} cites unknown requirements {sorted(unknown)}"
            )
        key = value_hash(test["inputs"])
        if key in seen_inputs and not typed_equal(seen_inputs[key], test["expected"]):
            raise OracleError("Supplied tests give contradictory expectations for one input")
        seen_inputs[key] = test["expected"]
        cited = test["requirement_ids"] or list(approved)
        for req_id in cited:
            req = approved.get(req_id)
            if req is None or not template_compatible(
                req["property_template_id"], run["domain_schema"]
            ):
                continue
            reference = expected_output(req["property_template_id"], test["inputs"])
            if not typed_equal(reference, test["expected"]):
                raise OracleError(
                    f"Supplied expectation for {test['test_id']} contradicts approved "
                    f"requirement {req_id}"
                )


def oracle_version(oracle_spec: dict) -> str:
    kind = oracle_spec["kind"]
    if kind == "property":
        return (
            TEMPLATES[oracle_spec["property_id"]].version
            if (oracle_spec["property_id"] in TEMPLATES)
            else "unregistered"
        )
    if kind == "metamorphic":
        rel = METAMORPHIC.get(oracle_spec["relation_id"])
        return rel.version if rel else "unregistered"
    return value_hash(oracle_spec)


def suite_hash(tests: list[dict]) -> str:
    """Hash of the exact test inputs, oracle specs/versions and statuses, order-independent."""
    rows = sorted(
        (
            {
                "id": t["test_id"],
                "inputs": t["inputs"],
                "related": t["related_inputs"],
                "oracle": t["oracle_spec"],
                "version": oracle_version(t["oracle_spec"]),
                "status": t["oracle_status"],
            }
            for t in tests
        ),
        key=lambda r: r["id"],
    )
    return value_hash(rows)


def _basis(test: dict, requirements: list[dict], template_ids: set[str]) -> bool:
    approved = _approved_by_template(requirements)
    cited = test["requirement_ids"]
    return any(
        req_id in approved and approved[req_id]["property_template_id"] in template_ids
        for req_id in cited
    )


def admit_test(test: dict, problem: dict) -> dict:
    """Return the test with its status settled by the gate, or raise OracleError."""
    out = dict(test)
    reason = check_args(problem["domain_schema"], test["inputs"])
    out["domain_valid"] = reason is None
    spec = test["oracle_spec"]
    kind = spec["kind"]
    known = {r["requirement_id"] for r in problem["requirements"]}
    if set(test["requirement_ids"]) - known:
        raise OracleError("Test cites unknown requirements")
    if kind == "metamorphic":
        if test["related_inputs"] is None:
            raise OracleError("Metamorphic tests require related_inputs")
        if check_args(problem["domain_schema"], test["related_inputs"]):
            raise OracleError("related_inputs are outside the domain")
        if spec["relation_id"] not in METAMORPHIC or not relation_inputs_valid(
            spec["relation_id"], test["inputs"], test["related_inputs"]
        ):
            raise OracleError("related_inputs do not instantiate a registered relation")
    elif test["related_inputs"] is not None:
        raise OracleError("Only metamorphic tests may carry related_inputs")
    if not out["domain_valid"]:
        out["oracle_status"] = "rejected"
        return out
    authorizing = test["oracle_source"] in AUTHORIZING_SOURCES
    if kind == "literal":
        # Supplied literals are the only authoritative literals; model literals stay proposed.
        ok = authorizing and test["provenance"] == "supplied"
        out["oracle_status"] = "authoritative" if ok else "proposed"
    elif kind == "property":
        template = spec["property_id"]
        ok = (
            authorizing
            and template in TEMPLATES
            and template_compatible(template, problem["domain_schema"])
            and _basis(test, problem["requirements"], {template})
        )
        out["oracle_status"] = "authoritative" if ok else "proposed"
    elif kind == "metamorphic":
        relation = METAMORPHIC.get(spec["relation_id"])
        ok = bool(
            authorizing
            and relation
            and _basis(test, problem["requirements"], set(relation.templates))
        )
        out["oracle_status"] = "authoritative" if ok else "proposed"
    elif kind == "observation":
        out["oracle_status"] = "observation_only"
    else:
        raise OracleError("Unknown oracle kind")
    return out


def judge(test: dict, outputs: list) -> str:
    """Verdict for a test given executed outputs (two for relations): pass/fail/observed."""
    if test["oracle_status"] != "authoritative":
        return "observed"
    spec = test["oracle_spec"]
    kind = spec["kind"]
    if kind == "literal":
        return "pass" if typed_equal(outputs[0], spec["expected"]) else "fail"
    if kind == "property":
        reference = expected_output(spec["property_id"], test["inputs"])
        return "pass" if typed_equal(outputs[0], reference) else "fail"
    if kind == "metamorphic":
        return "pass" if len(outputs) == 2 and typed_equal(outputs[0], outputs[1]) else "fail"
    return "observed"
