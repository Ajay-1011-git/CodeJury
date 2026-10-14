"""Guard behavior with trusted scripted transports, not training or model quality evidence."""

import json

import pytest

from codejury.stage2_core.budgets import zero_usage
from codejury.stage2_core.contracts import json_hash
from codejury.stage2_core.controller import records
from codejury.stage2_core.controller.learned import LearnedController, choice, parse_judge

from .test_candidates import fixture
from .test_controller import ScriptedModel, controller, run

JUDGE = {"adapter_hash": "e" * 64, "model_config_hash": "d" * 64, "model_revision_hash": "c" * 64}


class ScriptedJudge(ScriptedModel):
    def __init__(self, bad=False, omit=False):
        super().__init__()
        self.bad = bad
        self.omit = omit

    def generate(self, request, cancel):
        if request["role"] != "judge":
            return super().generate(request, cancel)
        self.requests.append(request)
        payload = json.JSONDecoder().raw_decode(
            request["prompt"].split("Runtime-visible facts:\n")[1]
        )[0]
        state = payload["state"]
        draft = {
            "state_id": "stale" if self.bad else state["state_id"],
            "action_option_id": state["available_actions"][0]["option_id"],
            "evidence_ids": [],
            "rationale": "Fixture offered action",
        }
        if self.omit:
            del draft["state_id"]
        response = fixture("model-response")
        response.update(
            request_id=request["request_id"],
            role="judge",
            **JUDGE,
            usage={**zero_usage(), "input_tokens": 10, "output_tokens": 20},
            text=json.dumps(draft),
        )
        return response


def learned(tmp_path, bad=False, omit=False):
    control = controller(tmp_path, ScriptedJudge(bad, omit), cls=LearnedController)
    control.identities["judge"] = JUDGE
    return control


def test_learned_selection_uses_guarded_current_menu_and_charges_decisions(tmp_path):
    control = learned(tmp_path)
    result = run(control)
    assert result["status"] == "supported_patch" and result["policy_mode"] == "learned"
    choices = records(control.ledger, result["run_id"], "judge_choice")
    assert choices and all(c["mode"] == "learned" for c in choices)
    assert result["resource_usage"]["judge_decisions"] == len(choices)


def test_two_refusals_fallback_is_explicit_and_cannot_exceed_eight_attempts(tmp_path):
    control = learned(tmp_path, bad=True)
    result = run(control)
    assert result["status"] == "supported_patch"
    assert result["resource_usage"]["judge_decisions"] == 8
    choices = records(control.ledger, result["run_id"], "judge_choice")
    assert all(c["mode"] == "fixed_fallback" for c in choices)
    assert any(e["type"] == "action_refused" for e in control.ledger.events(result["run_id"]))


def test_unknown_option_and_unregistered_evidence_do_not_modify_state():
    state = fixture("state-snapshot")
    before = json_hash(state)
    draft = {
        "state_id": state["state_id"],
        "action_option_id": state["available_actions"][0]["option_id"],
        "evidence_ids": [],
        "rationale": "fixture",
    }
    assert choice(draft, state, []) in state["available_actions"]
    for change in (
        {"state_id": "stale"},
        {"action_option_id": "unknown"},
        {"evidence_ids": ["invented"]},
    ):
        with pytest.raises(ValueError):
            choice({**draft, **change}, state, [])
    assert json_hash(state) == before


def test_omitted_state_id_is_restored_and_disclosed(tmp_path):
    control = learned(tmp_path, omit=True)
    result = run(control)
    choices = records(control.ledger, result["run_id"], "judge_choice")
    assert choices and all(c["mode"] == "learned" and c["state_id_filled"] for c in choices)


def test_present_wrong_state_id_still_refuses_and_falls_back(tmp_path):
    control = learned(tmp_path, bad=True)
    result = run(control)
    choices = records(control.ledger, result["run_id"], "judge_choice")
    assert all(c["mode"] == "fixed_fallback" for c in choices)


def test_parse_judge_only_forgives_a_state_id_only_omission():
    ok = '{"action_option_id":"o1","evidence_ids":[],"rationale":"r"}'
    draft, repair = parse_judge(ok, "s-1")
    assert repair == "omitted" and draft["state_id"] == "s-1"
    full = '{"state_id":"s-1","action_option_id":"o1","evidence_ids":[],"rationale":"r"}'
    assert parse_judge(full, "s-1")[1] is None
    dangling = '{"action_option_id":"o1","evidence_ids":[],"rationale":"r","}'
    draft, repair = parse_judge(dangling, "s-1")
    assert repair == "dangling_key" and draft["state_id"] == "s-1"
    for bad in (
        '{"action_option_id":"o1","evidence_ids":[]}',
        '{"action_option_id":"o1","evidence_ids":[],"rationale":"r","extra":1}',
        '{"action_option_id":"o1","action_option_id":"o2","evidence_ids":[],"rationale":"r"}',
        '{"action_option_id":"o1","evidence_ids":[],"rationale":"r",',
        '{"action_option_id":"o1","evidence_ids":[],"rationale":"r","state_id":"}',
        '{"action_option_id":"o1","evidence_ids":[],","}',
        '{"action_option_id":"o1","evidence_ids":[],"rationale":"r","x":1,"}',
        "e72e72e72",
        "[]",
    ):
        with pytest.raises(ValueError):
            parse_judge(bad, "s-1")
