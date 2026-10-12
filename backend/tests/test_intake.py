import copy
import json

import pytest
from jsonschema import ValidationError

from codejury.contracts import REPO_ROOT
from codejury.contracts.intake import IntakeError, validate_json, validate_request, validate_test


@pytest.fixture
def request_body():
    return json.loads((REPO_ROOT / "contracts/fixtures/run-create.json").read_text())


def test_valid_seed(request_body):
    validate_request(request_body)


@pytest.mark.parametrize("value", [True, 1.0, [True], [1001], list(range(31))])
def test_out_of_domain_inputs(request_body, value):
    request_body["supplied_tests"][0]["args"] = [value]
    with pytest.raises(IntakeError):
        validate_request(request_body)


def test_duplicate_test_ids(request_body):
    request_body["supplied_tests"] *= 2
    with pytest.raises(IntakeError, match="Duplicate"):
        validate_request(request_body)


@pytest.mark.parametrize(
    "source",
    [
        "import os\ndef unique(values):\n    return values\n",
        "def unique(values):\n    import os\n    return values\n",
        "@print\ndef unique(values):\n    return values\n",
        "def unique(values=[]):\n    return values\n",
        "def unique(values):\n    def helper():\n        return 1\n    return values\n",
        "def unique(values):\n    global x\n    return values\n",
        "print('host side effect')\ndef unique(values):\n    return values\n",
    ],
)
def test_unsupported_source_is_parsed_never_executed(request_body, source, capsys):
    request_body["source"] = source
    with pytest.raises(IntakeError):
        validate_request(request_body)
    assert capsys.readouterr().out == ""


def test_supplied_oracle_conflict(request_body):
    request_body["supplied_tests"][0]["expected"] = [1, 2, 3]
    with pytest.raises(IntakeError, match="conflicts"):
        validate_request(request_body)


@pytest.mark.parametrize("value", [1.0, float("nan"), 2**53, (1,), {1: 2}])
def test_json_subset(value):
    with pytest.raises(IntakeError):
        validate_json(value)


def test_json_depth():
    value = None
    for _ in range(10):
        value = [value]
    with pytest.raises(IntakeError, match="nesting"):
        validate_json(value)


def test_unknown_wire_fields(request_body):
    request_body["hidden_tests"] = []
    with pytest.raises(ValidationError):
        validate_request(request_body)


def test_model_cannot_promote_literal(request_body):
    test = {
        "test_id": "invented",
        "args": [[1]],
        "expected": [2],
        "oracle_kind": "literal",
        "property_id": None,
        "oracle_status": "authoritative",
        "oracle_source": "model",
        "requirement_id": None,
        "provenance": "critic",
        "reason": "proposed",
    }
    with pytest.raises(IntakeError, match="supplied user"):
        validate_test(test, request_body)
    test["oracle_status"] = "proposed"
    validate_test(test, request_body)
    altered = copy.deepcopy(test)
    altered.update(
        oracle_kind="property",
        property_id="sum_ints",
        expected=None,
        oracle_source="reviewed_contract",
    )
    with pytest.raises(IntakeError, match="approved"):
        validate_test(altered, request_body)
