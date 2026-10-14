"""Spec-only boundary, leak red-team, budget accounting and explicit approval."""

import copy
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from codejury.api.app import create_app
from codejury.intake.guard import validate_text
from codejury.intake.infer import infer
from codejury.intake.interpreter import Interpreter, parse_interpretation, request_body
from codejury.intake.store import VERDICT_LABEL, DraftConflict, DraftStore
from codejury.stage2_core.teacher.budget import Halt, Ledger
from codejury.storage import Store

SOURCE = "def total(values):\n    return 0\n"
PAYLOAD = {
    "source": SOURCE,
    "function_name": "total",
    "description": (
        "Return the sum of all integers in the list, including negatives; empty gives zero."
    ),
}
REPLY = {
    "arg_domains": [
        {
            "param": "values",
            "kind": "integer_list",
            "min": -1000,
            "max": 1000,
            "min_length": 0,
            "max_length": 32,
        }
    ],
    "requirements": [
        {
            "text": "Sum every integer, including negative values.",
            "property_template_id": "sum_ints",
        }
    ],
    "examples": [
        {"inputs_json": "[[]]", "expected_json": "0"},
        {"inputs_json": "[[2,-3,4]]", "expected_json": "3"},
    ],
    "ambiguities": [],
}


def interpreted(source=SOURCE):
    facts = infer(source, "total")
    return {
        "spec": parse_interpretation(json.dumps(REPLY), facts, source),
        "request_hash": "a" * 64,
        "response": json.dumps(REPLY),
        "validator": "accepted",
        "model": "fixture-only",
    }


class FakeInterpreter:
    def interpret(self, facts, description, source):
        self.facts = facts
        return interpreted(source)


def test_ast_facts_are_bounded_and_contain_no_source_body():
    source = (
        "def total(values):\n    result = 0\n    for x in values:\n"
        "        result += x\n    return result\n"
    )
    facts = infer(source, "total")
    assert facts["function"]["signature"] == "total(values)"
    assert "iterated" in facts["arg_domains"][0]["uses"]
    body = request_body(
        {**facts, "source": source, "trace": "SECRET"}, PAYLOAD["description"], "fixture"
    )
    sent = json.loads(body["messages"][1]["content"])
    assert set(sent) == {"function_name", "signature", "description", "ast_facts"}
    assert source not in json.dumps(body)
    assert "result" not in json.dumps(sent)
    assert body["response_format"]["json_schema"]["strict"] is True


@pytest.mark.parametrize(
    "body",
    [
        "return sorted(values)",
        "def total(values): return sum(values)",
        "lambda x: x + 1",
        "x = 3",
        "values += [1]",
        "`return 5`",
        "import os",
        "result == expected",
        "gsk_redTeamSecret123",
    ],
)
def test_code_or_secrets_in_description_never_reach_cloud(body):
    with pytest.raises(ValueError):
        request_body(infer(SOURCE, "total"), body, "fixture")


@pytest.mark.parametrize(
    "field,code",
    [
        ("text", "return sum(values)"),
        ("text", "def total(values): pass"),
        ("text", "lambda values: sorted(values)"),
        ("text", "result = 0"),
        ("text", "```python"),
        ("text", "values * 2"),
    ],
)
def test_response_leak_red_team_rejects_code(field, code):
    reply = copy.deepcopy(REPLY)
    reply["requirements"][0][field] = code
    with pytest.raises(ValueError):
        parse_interpretation(json.dumps(reply), infer(SOURCE, "total"), SOURCE)


@pytest.mark.parametrize("text", ["def total(values): pass", "gsk_redTeamSecret123"])
@pytest.mark.parametrize("location", ["input_key", "expected_key"])
def test_unicode_escaped_dictionary_keys_cannot_leak_code_or_secrets(text, location):
    reply = copy.deepcopy(REPLY)
    encoded = "".join("\\u%04x" % ord(character) for character in text)
    if location == "input_key":
        reply["arg_domains"][0]["kind"] = "integer_dict"
        reply["requirements"][0]["property_template_id"] = None
        reply["examples"] = [{"inputs_json": '[{"' + encoded + '":1}]', "expected_json": "1"}]
    else:
        reply["examples"][0]["expected_json"] = '{"' + encoded + '":1}'
    with pytest.raises(ValueError):
        parse_interpretation(json.dumps(reply), infer(SOURCE, "total"), SOURCE)


def test_decoded_expected_string_is_also_leak_checked():
    reply = copy.deepcopy(REPLY)
    reply["examples"][0]["expected_json"] = json.dumps("return sum(values)")
    with pytest.raises(ValueError):
        parse_interpretation(json.dumps(reply), infer(SOURCE, "total"), SOURCE)


def test_body_overlap_rejected_even_without_python_keywords():
    with pytest.raises(ValueError, match="overlaps"):
        validate_text(
            "alpha beta gamma delta epsilon zeta",
            "def total(values):\n    text = 'alpha beta gamma delta epsilon zeta'\n"
            "    return text\n",
        )


def test_interpreter_example_domains_and_item_counts():
    facts = infer(SOURCE, "total")
    for change in (
        "wrong_param",
        "float_output",
        "wrong_input",
        "too_many_examples",
        "duplicate_key",
    ):
        reply = copy.deepcopy(REPLY)
        if change == "wrong_param":
            reply["arg_domains"][0]["param"] = "other"
        if change == "float_output":
            reply["examples"][0]["expected_json"] = "1.5"
        if change == "wrong_input":
            reply["examples"][0]["inputs_json"] = "[true]"
        if change == "too_many_examples":
            reply["examples"] *= 5
        text = json.dumps(reply)
        if change == "duplicate_key":
            text = text.replace('"ambiguities": []', '"ambiguities": [], "ambiguities": []')
        with pytest.raises(ValueError):
            parse_interpretation(text, facts, SOURCE)


def test_proposed_items_do_not_become_checks_without_explicit_approval(tmp_path):
    store = DraftStore(tmp_path, FakeInterpreter())
    draft = store.create(PAYLOAD)
    assert all(e["tier"] == "corroborated" for e in draft["examples"])
    assert all(r["tier"] == "proposed" for r in draft["requirements"])
    with pytest.raises(ValueError, match="approved domain"):
        store.build(draft["id"], {})
    create, label = store.build(draft["id"], {"approve_all": True})
    assert create["source"] == SOURCE
    assert len(create["supplied_tests"]) == 2
    assert all(r["source"] == "user" for r in create["requirements"])
    assert "user-approved" in label
    _, label = store.build(draft["id"], {"trust_interpreter": True})
    assert label == VERDICT_LABEL


def test_per_item_edits_rejections_and_idempotent_admission(tmp_path):
    store = DraftStore(tmp_path, FakeInterpreter())
    draft = store.create(PAYLOAD)
    decisions = {
        "approve_all": True,
        "items": [{"item_id": "example:example-2", "decision": "reject"}],
    }
    calls = []

    def submit(create):
        calls.append(create)
        return {
            "schema_version": "stage2.v1",
            "run_id": "run-fixture",
            "status": "queued",
            "runtime_mode": "fixture",
        }

    result = store.approve(draft["id"], decisions, submit)
    assert len(calls[0]["supplied_tests"]) == 1
    assert store.approve(draft["id"], decisions, submit) == result
    assert len(calls) == 1
    with pytest.raises(DraftConflict):
        store.approve(draft["id"], {"approve_all": True, "trust_interpreter": True}, submit)
    provenance = store.provenance_for_run("run-fixture")
    assert provenance["interpreter"]["label"] == "Interpreter (cloud, spec only)"


def test_bad_edits_and_contradictions_refused_before_submission(tmp_path):
    store = DraftStore(tmp_path, FakeInterpreter())
    draft = store.create(PAYLOAD)
    with pytest.raises(ValueError):
        store.build(
            draft["id"],
            {
                "approve_all": True,
                "items": [
                    {"item_id": "domain:values", "decision": "edit", "value": {"param": "other"}}
                ],
            },
        )
    with pytest.raises(ValueError, match="contradicts"):
        store.build(
            draft["id"],
            {
                "approve_all": True,
                "items": [
                    {"item_id": "example:example-1", "decision": "edit", "value": {"expected": 5}}
                ],
            },
        )


class FakeConnection:
    def __init__(self, text=None, failure=None):
        self.text = json.dumps(REPLY) if text is None else text
        self.failure = failure
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **body):
        self.calls.append(body)
        if self.failure:
            raise self.failure
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=20, completion_tokens=50),
            choices=[
                SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=self.text))
            ],
        )


def interpreter(tmp_path, connection):
    ledger = Ledger(tmp_path / "budget.sqlite")
    client = Interpreter(
        config={"model": "fixture", "ledger": "unused", "max_cost_usd": 1, "max_in_flight": 1},
        ledger=ledger,
        keys=["fixture-key-not-a-real-credential"],
        connection=connection,
    )
    return client, ledger


def test_cloud_transport_shares_budget_and_caches_only_valid_specs(tmp_path):
    connection = FakeConnection()
    client, ledger = interpreter(tmp_path, connection)
    facts = infer(SOURCE, "total")
    result = client.interpret(facts, PAYLOAD["description"], SOURCE)
    assert result["validator"] == "accepted"
    assert ledger.summary()["attempts"] == 1
    assert ledger.summary()["charged_or_reserved_usd"] > 0
    assert client.interpret(facts, PAYLOAD["description"], SOURCE) == result
    assert len(connection.calls) == 1
    assert SOURCE not in json.dumps(connection.calls)


def test_unknown_usage_halts_future_dispatch(tmp_path):
    connection = FakeConnection(failure=RuntimeError("sensitive failure text"))
    client, ledger = interpreter(tmp_path, connection)
    with pytest.raises(Halt):
        client.interpret(infer(SOURCE, "total"), PAYLOAD["description"], SOURCE)
    assert ledger.summary()["unknown_usage_attempts"] == 1
    with pytest.raises(Halt):
        client.interpret(infer(SOURCE, "total"), PAYLOAD["description"], SOURCE)
    assert len(connection.calls) == 1


def test_rejected_cloud_code_is_counted_but_never_logged(tmp_path):
    reply = copy.deepcopy(REPLY)
    reply["requirements"][0]["text"] = "return sum(values)"
    connection = FakeConnection(text=json.dumps(reply))
    client, ledger = interpreter(tmp_path, connection)
    with pytest.raises(ValueError):
        client.interpret(infer(SOURCE, "total"), PAYLOAD["description"], SOURCE)
    with ledger.connect() as db:
        status, result = db.execute("SELECT status,result FROM attempts").fetchone()
    assert status == "intake_rejected"
    assert "return sum" not in result
    assert json.loads(result)["validator"] == "rejected"


@pytest.mark.parametrize("text", ["def total(values): pass", "gsk_redTeamSecret123"])
def test_rejected_escaped_dictionary_content_is_charged_without_raw_logging(tmp_path, text):
    reply = copy.deepcopy(REPLY)
    encoded = "".join("\\u%04x" % ord(character) for character in text)
    reply["examples"][0]["expected_json"] = '{"' + encoded + '":1}'
    client, ledger = interpreter(tmp_path, FakeConnection(text=json.dumps(reply)))
    with pytest.raises(ValueError):
        client.interpret(infer(SOURCE, "total"), PAYLOAD["description"], SOURCE)
    with ledger.connect() as db:
        status, raw = db.execute("SELECT status,result FROM attempts").fetchone()
    result = json.loads(raw)
    assert status == "intake_rejected" and result["response"] is None
    assert ledger.summary()["attempts"] == 1
    assert ledger.summary()["charged_or_reserved_usd"] > 0


def test_intake_routes_approve_and_dispatch_same_jury_worker(tmp_path):
    from test_stage2_bridge import FixtureWorker, Stage2Worker, stage2_app

    stage2 = stage2_app(tmp_path, Stage2Worker())
    stage2.state.worker.claim = lambda create: {
        "schema_version": "stage2.v1",
        "run_id": "run-fixture",
        "status": "queued",
        "runtime_mode": "fixture",
    }
    dispatched = []
    stage2.state.worker.dispatch = lambda run: dispatched.append(run)
    draft_store = DraftStore(tmp_path / "drafts", FakeInterpreter())
    app = create_app(
        Store(tmp_path / "stage1"),
        FixtureWorker(),
        stage2=stage2,
        intake_store=draft_store,
        web_dir=tmp_path / "no-web",
    )
    with TestClient(app) as client:
        result = client.post("/s2x/intake", json=PAYLOAD)
        assert result.status_code == 200
        identifier = result.json()["id"]
        assert client.post(f"/s2x/intake/{identifier}/approve", json={}).status_code == 422
        accepted = client.post(f"/s2x/intake/{identifier}/approve", json={"approve_all": True})
        assert accepted.status_code == 202
        assert accepted.json()["accepted"]["run_id"] == "run-fixture"
        assert dispatched == ["run-fixture"]
        client.post(f"/s2x/intake/{identifier}/approve", json={"approve_all": True})
        assert dispatched == ["run-fixture"]


def test_plain_language_return_is_supported_but_code_still_stays_local():
    body = request_body(infer(SOURCE, "total"), "return the sum of all integers", "fixture")
    assert "return the sum" in body["messages"][1]["content"]
    with pytest.raises(ValueError):
        request_body(infer(SOURCE, "total"), "return sum(values)", "fixture")


@pytest.mark.parametrize(
    "code",
    ["values - 1", "n / 2", "n < 5", "sorted(values)", "def", "return[1]", "return#comment"],
)
def test_more_expression_leaks_are_refused(code):
    with pytest.raises(ValueError):
        validate_text(code)


def test_cloud_bounds_are_validated_and_preserved():
    reply = copy.deepcopy(REPLY)
    reply["arg_domains"][0].update(min=-20, max=20, min_length=0, max_length=5)
    draft = parse_interpretation(json.dumps(reply), infer(SOURCE, "total"), SOURCE)
    assert draft["arg_domains"][0]["domain"]["item_domain"]["min"] == -20
    assert draft["arg_domains"][0]["domain"]["max_length"] == 5
    reply["arg_domains"][0]["max_length"] = 10000
    with pytest.raises(ValueError):
        parse_interpretation(json.dumps(reply), infer(SOURCE, "total"), SOURCE)


def test_foreign_origins_cannot_spend_interpreter_budget(tmp_path):
    from test_stage2_bridge import FixtureWorker, Stage2Worker, stage2_app

    interpreter = FakeInterpreter()
    draft_store = DraftStore(tmp_path / "drafts", interpreter)
    app = create_app(
        Store(tmp_path / "stage1"),
        FixtureWorker(),
        stage2=stage2_app(tmp_path, Stage2Worker()),
        intake_store=draft_store,
        web_dir=tmp_path / "no-web",
    )
    with TestClient(app) as client:
        response = client.post(
            "/s2x/intake", json=PAYLOAD, headers={"Origin": "https://outside.example"}
        )
        assert response.status_code == 403
        assert not hasattr(interpreter, "facts")
        response = client.post("/s2x/intake", json=PAYLOAD, headers={"Host": "outside.example"})
        assert response.status_code == 403
        assert not hasattr(interpreter, "facts")
        draft = client.post("/s2x/intake", json=PAYLOAD).json()
        response = client.get(f"/s2x/intake/{draft['id']}", headers={"Host": "outside.example"})
        assert response.status_code == 403
        response = client.get("/s2/runs/unknown/transcript", headers={"Host": "outside.example"})
        assert response.status_code == 403


def test_template_conflicts_are_shown_in_the_draft_without_promoting_examples():
    reply = copy.deepcopy(REPLY)
    reply["examples"][1]["expected_json"] = "999"
    spec = parse_interpretation(json.dumps(reply), infer(SOURCE, "total"), SOURCE)
    assert spec["examples"][1]["tier"] == "proposed"
    assert spec["examples"][1]["corroboration"] == []
    assert "Example 2 conflicts" in spec["disagreements"][0]


def test_unicode_example_characters_enter_the_reviewed_finite_domain():
    source = "def reverse(text):\n    result = text\n    return result\n"
    reply = {
        "arg_domains": [
            {
                "param": "text",
                "kind": "string",
                "min": 0,
                "max": 0,
                "min_length": 0,
                "max_length": 64,
            }
        ],
        "requirements": [
            {"text": "Reverse the character order.", "property_template_id": "reverse_string"}
        ],
        "examples": [{"inputs_json": '["é猫🙂"]', "expected_json": '"🙂猫é"'}],
        "ambiguities": [],
    }
    spec = parse_interpretation(json.dumps(reply), infer(source, "reverse"), source)
    alphabet = spec["arg_domains"][0]["domain"]["alphabet"]
    assert set("é猫🙂") <= set(alphabet)
    assert spec["examples"][0]["tier"] == "corroborated"
