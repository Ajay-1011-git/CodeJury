"""Trusted policy/counter tests, never native quality or learning evidence."""

import json
from threading import Event

from codejury.stage2_core.baselines.controllers import (
    GeneralController,
    RepairBaseline,
    SampleBaseline,
)
from codejury.stage2_core.budgets import zero_usage
from codejury.stage2_core.candidates import CandidatePool
from codejury.stage2_core.controller import records

from .test_candidates import fixture
from .test_controller import GOOD, POSITIVE, RAW, ScriptedModel, controller, run


def test_a_feedback_baseline_revises_actual_failure_and_never_dispatches_critic(tmp_path):
    model = ScriptedModel({"fixer_a": POSITIVE})
    control = controller(tmp_path, model=model, cls=RepairBaseline)
    tests = fixture("snapshot-running")["tests"]
    tests.append(
        {
            **tests[0],
            "test_id": "negative",
            "inputs": [[-1]],
            "oracle_spec": {"kind": "literal", "expected": -1},
        }
    )
    snapshot = control.run(fixture("problem"), tests, cancel=Event())
    assert snapshot["status"] == "supported_patch"
    assert [r["purpose"] for r in model.requests] == ["repair", "revise"]
    assert all(r["role"] == "fixer_a" for r in model.requests)
    assert not snapshot["audit_gaps"] and not snapshot["probe_mutants"]
    assert records(control.ledger, control.run_id, "final")[0]["decision"]["verification_scope"]


def test_sampling_baseline_charges_every_attempt_and_stops_at_shared_cap(tmp_path):
    model = ScriptedModel({"fixer_a": GOOD})
    control = controller(tmp_path, model=model, cls=SampleBaseline)
    result = run(control)
    assert result["status"] == "supported_patch"
    assert result["resource_usage"]["learned_candidates"] == len(model.requests) == 8
    assert all(r["role"] == "fixer_a" for r in model.requests)


def test_raw_repair_keeps_physical_identity_and_charges_one_malformed_attempt(tmp_path):
    class RawRepair:
        def generate(self, request, cancel):
            assert request["role"] == "raw"
            response = fixture("model-response")
            response.update(
                request_id=request["request_id"],
                role="raw",
                text="malformed",
                usage={**zero_usage(), "input_tokens": 10, "output_tokens": 20},
                **RAW,
            )
            return response

    control = controller(tmp_path)
    control.admit(fixture("problem"), fixture("snapshot-running")["tests"], cancel=Event(), seed=11)
    ledger, run_id = control.ledger, control.run_id
    pool = CandidatePool(
        ledger,
        run_id,
        RawRepair(),
        {"raw": RAW},
        model_roles={"fixer_a": "raw", "fixer_b": "raw"},
    )
    original = pool.original()
    assert (
        pool.generate(
            "fixer_a", pool.views.a, parent=original, seed=11, cancel=Event(), max_attempts=1
        )
        is None
    )
    snapshot = ledger.snapshot(run_id)
    assert snapshot["resource_usage"]["learned_candidates"] == 1
    with ledger.connection() as db:
        rows = list(db.execute("SELECT body FROM requests WHERE run_id=?", (run_id,)))
    assert len(rows) == 1 and json.loads(rows[0]["body"])["role"] == "raw"


def test_general_allocates_its_first_action_and_preserves_physical_role(tmp_path):
    from stage2_tools.hostsandbox import FixtureHostSandbox

    from codejury.stage2_core.ledger import Ledger
    from codejury.stage2_tools.port import ToolPortImpl

    identity = {
        "adapter_hash": "7" * 64,
        "model_config_hash": "6" * 64,
        "model_revision_hash": "c" * 64,
    }

    class FixtureGeneral:
        def __init__(self):
            self.requests = []

        def generate(self, request, cancel):
            self.requests.append(request)
            payload = json.JSONDecoder().raw_decode(
                request["prompt"].split("Runtime-visible facts:\n")[1]
            )[0]
            if payload.get("view_format") == "judge-summary.v2":
                state = payload["state"]
                priorities = {
                    "select": 0,
                    "audit": 1,
                    "criticize": 2,
                    "generate": 3,
                    "search": 4,
                    "abstain": 5,
                }
                selected = min(
                    state["available_actions"], key=lambda o: priorities[o["action"]["kind"]]
                )
                answer = {
                    "state_id": state["state_id"],
                    "action_option_id": selected["option_id"],
                    "evidence_ids": [],
                    "rationale": "Trusted General policy fixture",
                }
            elif "Mode: " in request["prompt"]:
                answer = {
                    "mode": request["prompt"].split("Mode: ")[1].split("\n")[0],
                    "requirement_ids": ["sum-all"],
                    "generator_spec": None,
                    "concrete_inputs": [[[-1]]],
                    "oracle_spec": {
                        "kind": "property",
                        "property_id": "sum_ints",
                        "parameters": {},
                    },
                    "target_candidate_ids": [c["candidate_id"] for c in payload["candidates"]],
                    "rationale": "Trusted General test fixture",
                }
            else:
                answer = {**fixture("repair-draft"), "source": GOOD}
            response = fixture("model-response")
            response.update(
                request_id=request["request_id"],
                role="general",
                text=json.dumps(answer),
                usage={**zero_usage(), "input_tokens": 10, "output_tokens": 20},
                **identity,
            )
            return response

    model = FixtureGeneral()
    control = GeneralController(
        Ledger(tmp_path),
        model,
        ToolPortImpl(FixtureHostSandbox()),
        {"general": identity},
        manifest_hash="a" * 64,
        runtime_hash=FixtureHostSandbox.runtime_hash,
        mode="fixture",
        model_roles={"fixer_a": "general", "fixer_b": "general"},
        critic_role="general",
    )
    result = run(control)
    assert result["status"] == "supported_patch"
    assert all(r["role"] == "general" for r in model.requests)
    assert '"judge-summary.v2"' in model.requests[0]["prompt"]
    assert result["resource_usage"]["learned_candidates"] == 1
    assert result["resource_usage"]["judge_decisions"] >= 1
    assert all(
        c["model_config_hash"] == identity["model_config_hash"]
        for c in result["candidates"]
        if c["origin"] != "original"
    )
