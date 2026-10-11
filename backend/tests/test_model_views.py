import json

import pytest
from jsonschema import ValidationError

from codejury.contracts import REPO_ROOT
from codejury.models.views import parse_critic, parse_repair, repair_view


@pytest.fixture
def request_body():
    return json.loads((REPO_ROOT / "contracts/fixtures/run-create.json").read_text())


def test_only_visible_view_fields(request_body):
    view = repair_view(request_body, [])
    assert set(view) == {"request", "failure_evidence"}
    assert "assessment_tests" not in json.dumps(view) and "correct_source" not in json.dumps(view)
    with pytest.raises(ValidationError):
        repair_view({**request_body, "teacher_target": "secret"}, [])
    with pytest.raises(ValueError, match="visible"):
        repair_view(request_body, [{"correct_source": "secret"}])


@pytest.mark.parametrize(
    "text",
    [
        "{}",
        "[]",
        '{"source":"import os","diagnosis":"","assumptions":[]}',
        '{"source":"def wrong(x): return x","diagnosis":"","assumptions":[]}',
        chr(96) * 3 + "json\n{}\n" + chr(96) * 3,
    ],
)
def test_malformed_model_repair_is_rejected(request_body, text):
    with pytest.raises(ValueError):
        parse_repair(text, request_body)


def test_valid_repair_and_no_unapproved_critic_property(request_body):
    source = "def unique(values):\n    return list(dict.fromkeys(values))\n"
    assert (
        parse_repair(
            json.dumps({"source": source, "diagnosis": "preserve order", "assumptions": []}),
            request_body,
        )["source"]
        == source
    )
    with pytest.raises(ValueError, match="unapproved"):
        parse_critic(
            '{"property_id":"sum_ints","family":"general","reason":"invented"}',
            "unique_preserve_order_ints",
        )
    assert (
        parse_critic('{"property_id":null,"family":"empty","reason":"observation"}', None)[
            "property_id"
        ]
        is None
    )


@pytest.mark.parametrize(
    "body",
    [
        {"property_id": None, "family": [], "reason": "invalid"},
        {"property_id": None, "family": "general", "reason": 9},
        {"property_id": None, "family": "general", "reason": "", "expected": 10},
    ],
)
def test_bad_critic_fields_cannot_gain_authority(body):
    with pytest.raises(ValueError):
        parse_critic(json.dumps(body), None)


def test_hidden_test_id_cannot_enter_view(request_body):
    failure = {
        "test_id": "sealed",
        "args": [[3, 1, 3, 2]],
        "result": {
            "actual_output": [1, 2, 3],
            "exception_type": None,
            "input_mutated": False,
            "duration_ms": 0,
            "trace": [],
            "trace_truncated": False,
        },
    }
    with pytest.raises(ValueError, match="supplied visible"):
        repair_view(request_body, [failure])
