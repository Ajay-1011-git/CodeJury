import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND / "src"))
FIXTURES = BACKEND.parent / "contracts" / "stage2-fixtures"


@pytest.fixture
def fixture():
    def load(name):
        return json.loads((FIXTURES / f"{name}.json").read_text())

    return load


def int_list(lo=-10, hi=10, n_min=0, n_max=8):
    return {
        "kind": "list",
        "item_domain": {"kind": "integer", "min": lo, "max": hi},
        "min_length": n_min,
        "max_length": n_max,
    }


def make_problem(source, function_name, domain=None, requirements=None, helpers=None, deps=None):
    from codejury.stage2_tools.codec import sha256_text
    from codejury.stage2_tools.domains import analyze_source

    domain = domain or [{"name": "values", "domain": int_list()}]
    info = analyze_source(source, function_name, helpers or [], deps or [])
    return {
        "schema_version": "stage2.v1",
        "problem_id": "p-test",
        "source_hash": sha256_text(source),
        "source": source,
        "function_name": function_name,
        "signature": info.signature,
        "contract_text": "test contract",
        "domain_schema": domain,
        "helper_interfaces": helpers or [],
        "requirements": requirements or [],
        "supplied_test_ids": [],
        "allowed_dependencies": deps or [],
        "resource_profile": "mac-standard-v1",
        "input_codec_version": "json.v1",
    }


def requirement(req_id, template=None, approved=True, source="reviewed_contract"):
    return {
        "schema_version": "stage2.v1",
        "requirement_id": req_id,
        "description": f"requirement {req_id}",
        "source": source,
        "approval_status": "approved" if approved else "proposed",
        "property_template_id": template,
        "parameters": {},
    }


def literal_test(test_id, inputs, expected, reqs=(), status="authoritative"):
    return {
        "schema_version": "stage2.v1",
        "test_id": test_id,
        "input_codec_version": "json.v1",
        "inputs": inputs,
        "related_inputs": None,
        "oracle_spec": {"kind": "literal", "expected": expected},
        "oracle_status": status,
        "oracle_source": "user",
        "domain_valid": True,
        "requirement_ids": list(reqs),
        "provenance": "supplied",
    }
