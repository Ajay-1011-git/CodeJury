"""Trusted fixtures only. These tests are never training or isolation evidence."""

import json
from threading import Event

import pytest
from stage2_tools.hostsandbox import FixtureHostSandbox

from codejury.stage2_core.budgets import CAPS, zero_usage
from codejury.stage2_core.contracts import checked, json_hash
from codejury.stage2_core.controller import FixedController, TraceArchivePort, records
from codejury.stage2_core.episode_export import export
from codejury.stage2_core.ledger import Ledger
from codejury.stage2_tools.port import ToolPortImpl

from .test_candidates import IDENTITIES, fixture

RAW = {"adapter_hash": None, "model_config_hash": "f" * 64, "model_revision_hash": "c" * 64}
GOOD = "def sum_values(values):\n    return sum(values)\n"
POSITIVE = "def sum_values(values):\n    return sum(v for v in values if v > 0)\n"


class ScriptedModel:
    def __init__(self, sources=None, malformed=False):
        self.sources = sources or {"fixer_a": GOOD, "fixer_b": GOOD}
        self.malformed = malformed
        self.requests = []

    def generate(self, request, cancel):
        self.requests.append(request)
        response = fixture("model-response")
        role = request["role"]
        identity = RAW if role == "raw" else IDENTITIES[role]
        if role == "raw":
            if self.malformed:
                text = "bad draft"
            else:
                payload = json.JSONDecoder().raw_decode(
                    request["prompt"].split("Runtime-visible facts:\n")[1]
                )[0]
                text = json.dumps(
                    {
                        "mode": request["prompt"].split("Mode: ")[-1].split("\n")[0],
                        "requirement_ids": ["sum-all"],
                        "generator_spec": None,
                        "concrete_inputs": [[[-1]]],
                        "oracle_spec": {
                            "kind": "property",
                            "property_id": "sum_ints",
                            "parameters": {},
                        },
                        "target_candidate_ids": [c["candidate_id"] for c in payload["candidates"]],
                        "rationale": "Trusted fixture challenge",
                    }
                )
        else:
            repair = fixture("repair-draft")
            repair["source"] = GOOD if request["purpose"] == "revise" else self.sources[role]
            text = json.dumps(repair)
        response.update(
            request_id=request["request_id"],
            role=role,
            text=text,
            **identity,
            usage={**zero_usage(), "input_tokens": 10, "output_tokens": 20},
        )
        return response


def controller(tmp_path, model=None, tool=None, cls=FixedController):
    ledger = Ledger(tmp_path / "ledger")
    model = model or ScriptedModel()
    tool = tool or ToolPortImpl(FixtureHostSandbox())
    return cls(
        ledger,
        model,
        tool,
        {**IDENTITIES, "raw": RAW},
        manifest_hash="a" * 64,
        runtime_hash=FixtureHostSandbox.runtime_hash,
        mode="fixture",
    )


def run(control, cancel=None, limits=None, source=None):
    problem = fixture("problem")
    if source is not None:
        from codejury.stage2_core.contracts import source_hash

        problem.update(source=source, source_hash=source_hash(source))
    tests = fixture("snapshot-running")["tests"]
    return control.run(problem, tests, cancel=cancel or Event(), limits=limits)


def test_success_preserves_a_and_replays_final_suite(tmp_path):
    control = controller(tmp_path)
    result = run(control)
    assert result["status"] == "supported_patch"
    chosen = next(
        c
        for c in result["candidates"]
        if c["candidate_id"] == result["decision"]["selected_candidate_id"]
    )
    assert chosen["origin"] == "fixer_a"
    assert [a["kind"] for a in result["actions"]] == [
        "audit",
        "criticize",
        "audit",
        "criticize",
        "select",
    ]
    assert len(result["tests"]) == 2
    assert result == control.ledger.snapshot(result["run_id"])
    assert result == Ledger(tmp_path / "ledger").snapshot(result["run_id"])
    episodes = records(control.ledger, result["run_id"], "episode")
    assert len(episodes[0]["tests"]) == 1  # no future test leakage into earlier states
    assert all(checked(e, "EpisodeBundle") for e in episodes)
    raw = records(control.ledger, result["run_id"], "critic_mode")
    assert all(r["mode"] == "raw_bootstrap" for r in raw)
    assert control.account.final_executions == 0


def test_bad_critic_cannot_authorize_selection(tmp_path):
    control = controller(tmp_path, ScriptedModel(malformed=True))
    result = run(control)
    assert result["status"] == "unresolved"
    assert result["decision"]["selected_candidate_id"] is None
    assert any(e["type"] == "action_refused" for e in control.ledger.events(result["run_id"]))


def test_new_counterexample_revises_responsible_parent(tmp_path):
    control = controller(tmp_path, ScriptedModel({"fixer_a": POSITIVE, "fixer_b": GOOD}))
    result = run(control)
    assert "revise" in [a["kind"] for a in result["actions"]]
    a = next(c for c in result["candidates"] if c["origin"] == "fixer_a")
    assert a["eligibility"] == "rejected"
    revision = next(c for c in result["candidates"] if c["origin"] == "fixer_a_revision")
    assert revision["parent_id"] == a["candidate_id"]
    assert result["decision"]["selected_candidate_id"] != a["candidate_id"]


def test_no_eligible_search_then_one_resample_and_abstain(tmp_path):
    source = "def sum_values(values):\n    return 999\n"
    control = controller(tmp_path, ScriptedModel({"fixer_a": source, "fixer_b": source}))
    result = run(control, source=source)
    kinds = [a["kind"] for a in result["actions"]]
    assert kinds[:3] == ["search", "search", "search"]
    assert kinds.count("generate") == 1
    assert kinds[-1] == "abstain"
    assert result["status"] == "unresolved"


def test_cancel_before_dispatch_never_generates(tmp_path):
    control = controller(tmp_path)
    cancel = Event()
    cancel.set()
    result = run(control, cancel)
    assert result["status"] == "cancelled"
    assert not control.model.requests


def test_small_budget_abstains_without_spending_final_reserve(tmp_path):
    control = controller(tmp_path)
    result = run(control, limits={**CAPS, "audit_mutants": 0, "output_tokens": 2048})
    assert result["status"] == "unresolved"
    assert result["resource_usage"]["function_executions"] < 128


def test_live_collection_rejects_fakes(tmp_path):
    with pytest.raises(ValueError, match="actual native"):
        FixedController(
            Ledger(tmp_path),
            ScriptedModel(),
            ToolPortImpl(FixtureHostSandbox()),
            {**IDENTITIES, "raw": RAW},
            manifest_hash="a" * 64,
            runtime_hash="f" * 64,
            mode="live",
        )


def test_export_rejects_fixture_and_nontrain_without_creating_output(tmp_path):
    control = controller(tmp_path)
    result = run(control)
    out = tmp_path / "exchange"
    for split in ("train", "validation", "final_assessment"):
        with pytest.raises(ValueError):
            export(
                control.ledger, [result["run_id"]], out, base_revision_hash="a" * 64, split=split
            )
    assert not out.exists()


def test_unicode_trace_saved_with_tools_codec(tmp_path):
    from codejury.stage2_tools.codec import value_hash

    trace = {"value": "é"}
    digest = value_hash(trace)

    class Port:
        last_evaluator = type("Evaluator", (), {"traces": {digest: trace}})()

        def call(self, request, cancel):
            response = fixture("tool-evaluate-result")
            response["request_id"] = request["request_id"]
            response["executions"][0]["trace_ref"] = digest
            return response

    ledger = Ledger(tmp_path)
    port = TraceArchivePort(Port(), ledger)
    port.call(fixture("tool-evaluate-request"), Event())
    assert json.loads(ledger.read_object(digest)) == trace
    assert digest != json_hash(trace)


def test_stale_suite_action_is_refused(tmp_path):
    class ChangeSuite(FixedController):
        def choose(self, state):
            option = super().choose(state)
            test = fixture("snapshot-running")["tests"][0]
            self.ledger.add_test(
                self.run_id,
                {
                    **test,
                    "test_id": "t-new",
                    "inputs": [[]],
                    "oracle_spec": {"kind": "literal", "expected": 0},
                },
            )
            with pytest.raises(ValueError, match="Stale action"):
                self.execute(state, option)
            # Stop the enclosing run without accepting the stale option.
            from codejury.stage2_core.controller import Stopped

            raise Stopped("unresolved", "Trusted stale-state test")

    control = controller(tmp_path, cls=ChangeSuite)
    result = run(control)
    assert result["decision"]["selected_candidate_id"] is None
    assert not result["actions"]


def test_infrastructure_overrides_eligible_candidates(tmp_path):
    class FailingTool(ToolPortImpl):
        def call(self, request, cancel):
            if request["parameters"]["operation"] == "audit":
                result = fixture("tool-audit-result")
                result.update(
                    request_id=request["request_id"],
                    status="infrastructure_error",
                    mutants=[],
                    audit_gaps=[],
                    executions=[],
                    edit_sources=[],
                    usage=zero_usage(),
                )
                return result
            return super().call(request, cancel)

    control = controller(tmp_path, tool=FailingTool(FixtureHostSandbox()))
    result = run(control)
    assert result["status"] == "infrastructure_error"
    assert result["decision"]["selected_candidate_id"] is None
    assert not any(c["eligibility"] == "eligible" for c in result["candidates"])


def test_conflicting_supplied_contract_rejected_before_models(tmp_path):
    control = controller(tmp_path)
    problem, tests = fixture("problem"), fixture("snapshot-running")["tests"]
    tests[0]["oracle_spec"]["expected"] = 999
    result = control.run(problem, tests, cancel=Event())
    assert result["status"] == "invalid_input"
    assert not control.model.requests


def test_seven_action_shapes_and_clipped_budgets(tmp_path):
    control = controller(tmp_path)
    result = run(control)
    state = records(control.ledger, result["run_id"], "state")[0]
    candidate = result["candidates"][1]["candidate_id"]
    params = {
        "generate": {"role": "fixer_a", "count": 1},
        "criticize": {"mode": "challenge_agreement"},
        "search": {"sites": [], "families": ["comparison"], "depth": 1},
        "audit": {"max_mutants": 1},
        "revise": {"role": "fixer_a"},
        "select": {"candidate_id": candidate},
        "abstain": {"reason": "Fixture limit"},
    }
    for kind, parameters in params.items():
        option = control.option(
            kind, [candidate] if kind != "abstain" else [], parameters, "Trusted shape check", state
        )
        checked(option, "ActionOption")
        assert all(
            v <= state["remaining_budget"][k]
            for k, v in option["action"]["requested_budget"].items()
        )


def test_unknown_property_contract_is_not_given_new_authority():
    from codejury.stage2_core.controller.inputs import training_input

    from .test_corpus import record

    total = {**record(), "contract": "Return the mathematical sum of the integers."}
    problem, _ = training_input(total)
    assert problem["requirements"][0]["property_template_id"] == "sum_ints"
    other = {**record(), "contract": "Return an unspecified transformed list."}
    assert training_input(other)[0]["requirements"][0]["property_template_id"] is None
    with pytest.raises(ValueError):
        training_input({**total, "split": "final_assessment"})


def test_mutation_edits_replay_exact_parent_bytes_and_keep_comments():
    from codejury.stage2_core.ledger import verify_edits
    from codejury.stage2_tools.search.operators import enumerate_edits

    source = "def f(values): # café\n    return sum(v for v in values if v  > 0x0) # keep me\n"
    for proposal in enumerate_edits(source):
        verify_edits(
            {"source": source},
            {"source": proposal.source, "edits": [proposal.edit()]},
            {proposal.result_source_hash: proposal.source},
        )
        assert "# café" in proposal.source and "# keep me" in proposal.source
    nested = "def f(x, y):\n    return 2 * (x * y)\n"
    for proposal in enumerate_edits(nested, ["arithmetic"]):
        verify_edits(
            {"source": nested},
            {"source": proposal.source, "edits": [proposal.edit()]},
            {proposal.result_source_hash: proposal.source},
        )


def test_observed_disagreement_triggers_critic_then_abstains_without_authority(tmp_path):
    class ObservationModel(ScriptedModel):
        def generate(self, request, cancel):
            response = super().generate(request, cancel)
            if request["role"] == "raw":
                proposal = json.loads(response["text"])
                proposal["oracle_spec"] = {"kind": "observation", "hypothesis": "Probe negatives"}
                response["text"] = json.dumps(proposal)
            return response

    control = controller(tmp_path, ObservationModel({"fixer_a": POSITIVE, "fixer_b": GOOD}))
    result = run(control)
    assert result["status"] == "unresolved"
    assert any(a["parameters"].get("mode") == "discriminate" for a in result["actions"])
    assert not any(a["kind"] == "select" for a in result["actions"])
    assert len([t for t in result["tests"] if t["oracle_status"] == "authoritative"]) == 1
    assert not any(c["origin"].endswith("_revision") for c in result["candidates"])


def test_private_training_labels_cannot_be_written_into_exchange(tmp_path):
    from codejury.stage2_core.episode_export.offline import training_labels
    from codejury.stage2_core.registry import local_path

    control = controller(tmp_path)
    target = local_path("artifacts/stage2-exchange/ajay/forbidden-private-labels.json")
    with pytest.raises(ValueError, match="must remain under"):
        training_labels(control.ledger, ["not-dispatched"], control.tool.port, Event(), target)
    assert not target.exists()
