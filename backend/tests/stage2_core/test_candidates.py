"""Transport fixtures only: cost, provenance, current-suite qualification."""

import copy
import json
from threading import Event

import pytest
from jsonschema import ValidationError

from codejury.stage2_core.budgets import CAPS, zero_usage
from codejury.stage2_core.candidates import (
    CandidatePool,
    incumbent,
    parse_draft,
    qualification,
)
from codejury.stage2_core.contract_check import REPO_ROOT
from codejury.stage2_core.contracts import source_hash
from codejury.stage2_core.intake import validate_source
from codejury.stage2_core.ledger import Ledger


def fixture(name):
    return json.loads((REPO_ROOT / f"contracts/stage2-fixtures/{name}.json").read_text())


class FixtureTools:
    def call(self, request, cancel):
        result = fixture("tool-validate-result")
        result["request_id"] = request["request_id"]
        return result


class FixtureModel:
    def __init__(self, texts):
        self.texts = iter(texts)
        self.requests = []

    def generate(self, request, cancel):
        self.requests.append(copy.deepcopy(request))
        role = request["role"]
        result = fixture("model-response")
        result.update(
            request_id=request["request_id"],
            role=role,
            text=next(self.texts),
            **IDENTITIES[role],
            usage={**zero_usage(), "input_tokens": 10, "output_tokens": 5},
        )
        return result


IDENTITIES = {
    role: {
        "adapter_hash": char * 64,
        "model_config_hash": config * 64,
        "model_revision_hash": "c" * 64,
    }
    for role, char, config in [("fixer_a", "a", "d"), ("fixer_b", "b", "e")]
}


@pytest.fixture
def store(tmp_path):
    ledger = Ledger(tmp_path / "ledger")
    ledger.create_run(
        "fixture-run",
        fixture("problem"),
        mode="fixture",
        profile=CAPS,
        model_configs=[i["model_config_hash"] for i in IDENTITIES.values()],
    )
    for test in fixture("snapshot-running")["tests"]:
        ledger.add_test("fixture-run", test)
    validate_source(
        ledger,
        "fixture-run",
        FixtureTools(),
        fixture("problem")["source"],
        ledger.records("fixture-run", "tests"),
        Event(),
    )
    return ledger


@pytest.mark.parametrize(
    "text",
    ["```json\n{}\n```", "prose", "{}", '{"source":1}', '{"source":"x","source":"y"}', '{"x":NaN}'],
)
def test_strict_parse_rejects_malformed_or_duplicate_json(text):
    with pytest.raises((ValueError, ValidationError)):
        parse_draft(text)


def test_initial_pair_format_retry_is_charged_and_b_is_independent(store):
    valid = json.dumps(fixture("repair-draft"))
    model = FixtureModel(["prose", valid, valid])
    pool = CandidatePool(store, "fixture-run", model, IDENTITIES)
    pair = pool.initial_pair(seed=11, cancel=Event())
    assert pair["fixer_a"]["eligibility"] == "pending"
    assert store.accounts["fixture-run"].usage()["learned_candidates"] == 3
    assert store.accounts["fixture-run"].usage()["output_tokens"] == 15
    assert model.requests[-1]["prompt"] == pool.views.b
    assert "buggy_source" not in model.requests[-1]["prompt"]
    assert len(store.records("fixture-run", "candidates")) == 3
    assert len(pool.alternatives()) == 2  # same A/B source, every attempt still stored
    with pytest.raises(ValueError, match="already"):
        pool.initial_pair(seed=11, cancel=Event())


def test_two_bad_responses_fail_honestly_without_fallback(store):
    model = FixtureModel(["bad", "bad"])
    pool = CandidatePool(store, "fixture-run", model, IDENTITIES)
    original = pool.original()
    assert pool.generate("fixer_a", pool.views.a, parent=original, seed=1, cancel=Event()) is None
    assert store.accounts["fixture-run"].usage()["learned_candidates"] == 2
    assert len(store.records("fixture-run", "candidates")) == 1


def test_same_adapter_cannot_impersonate_b(store):
    identities = copy.deepcopy(IDENTITIES)
    identities["fixer_b"]["adapter_hash"] = identities["fixer_a"]["adapter_hash"]
    with pytest.raises(ValueError, match="distinct"):
        CandidatePool(store, "fixture-run", FixtureModel([]), identities)


def evaluate(store, candidates, tests, *, outcome="pass", mutated=False):
    from uuid import uuid4

    identifier = "eval-" + uuid4().hex
    request = fixture("tool-evaluate-request")
    fields = set(fixture("candidate-revision-draft"))
    request.update(
        request_id=identifier,
        id_prefix=identifier,
        remaining_budget=store.accounts["fixture-run"].remaining(),
    )
    request["parameters"]["candidates"] = [{k: c[k] for k in fields} for c in candidates]
    request["parameters"]["tests"] = tests
    store.dispatch_tool(request)
    result = fixture("tool-evaluate-result")
    result.update(request_id=identifier, executions=[])
    for i, candidate in enumerate(candidates):
        for j, test in enumerate(tests):
            row = fixture("tool-evaluate-result")["executions"][0]
            row.update(
                execution_id=f"{identifier}-e{i}-{j}",
                candidate_id=candidate["candidate_id"],
                test_id=test["test_id"],
                outcome=outcome,
            )
            row["input_effects"][0]["mutated"] = mutated
            result["executions"].append(row)
    result["usage"]["function_executions"] = len(result["executions"])
    store.settle_tool(result)


def generate_pair(store):
    valid = json.dumps(fixture("repair-draft"))
    pair = CandidatePool(store, "fixture-run", FixtureModel([valid, valid]), IDENTITIES)
    return pair.initial_pair(seed=1, cancel=Event())


RUNTIME = fixture("tool-evaluate-result")["executions"][0]["runtime_hash"]


def test_all_hard_tests_and_semantic_receipt_required_for_incumbent(store):
    pair = generate_pair(store)
    tests = store.records("fixture-run", "tests")
    a, b = pair["fixer_a"], pair["fixer_b"]
    evaluate(store, [a, b], tests)
    projection = qualification(store, "fixture-run", runtime_hash=RUNTIME)
    assert incumbent(projection, fixture("problem")["source"]) is None
    validate_source(store, "fixture-run", FixtureTools(), a["source"], tests, Event())
    projection = qualification(store, "fixture-run", runtime_hash=RUNTIME)
    assert incumbent(projection, fixture("problem")["source"]) == a["candidate_id"]
    assert store.records("fixture-run", "candidates")[1]["eligibility"] == "pending"
    changed = copy.deepcopy(tests[0])
    changed.update(test_id="t-new")
    changed["inputs"] = [[-1]]
    changed["oracle_spec"]["expected"] = -1
    store.add_test("fixture-run", changed)
    stale = qualification(store, "fixture-run", runtime_hash=RUNTIME)
    assert stale["suite_hash"] != projection["suite_hash"]
    assert incumbent(stale, fixture("problem")["source"]) is None


@pytest.mark.parametrize("fault", ["mutation", "failure", "runtime"])
def test_bad_hard_evidence_or_runtime_never_qualifies(store, fault):
    a = generate_pair(store)["fixer_a"]
    tests = store.records("fixture-run", "tests")
    validate_source(store, "fixture-run", FixtureTools(), a["source"], tests, Event())
    evaluate(
        store,
        [a],
        tests,
        outcome="fail" if fault == "failure" else "pass",
        mutated=fault == "mutation",
    )
    projection = qualification(
        store, "fixture-run", runtime_hash="f" * 64 if fault == "runtime" else RUNTIME
    )
    assert incumbent(projection, fixture("problem")["source"]) is None


def test_stale_parent_and_changed_signatures_rejected(store):
    a = generate_pair(store)["fixer_a"]
    fields = set(fixture("candidate-revision-draft"))
    draft = {k: a[k] for k in fields}
    draft.update(
        candidate_id="revision",
        parent_id=a["candidate_id"],
        origin="fixer_a_revision",
        generation_view="feedback_revision",
    )
    with pytest.raises(ValueError, match="Stale"):
        store.commit_candidate("fixture-run", draft, expected_parent_hash="0" * 64)
    draft["source"] = "def sum_values(other):\n    return 0\n"
    draft["source_hash"] = source_hash(draft["source"])
    with pytest.raises(ValueError, match="signatures"):
        store.commit_candidate("fixture-run", draft)


def test_dispatch_tightens_wall_time_without_charging_it_twice():
    from codejury.stage2_core.budgets import BudgetAccount

    now = [0.0]
    account = BudgetAccount(clock=lambda: now[0])
    ceiling = account.remaining()
    now[0] = 0.010
    account.dispatch("drift", ceiling)
    assert account.pending["drift"]["ceiling"]["elapsed_ms"] == 899990
    assert account.usage()["elapsed_ms"] == 10


def test_invalid_a_source_still_attempts_initial_b(store):
    repair = fixture("repair-draft")
    repair["source"] = "not python"
    valid = json.dumps(fixture("repair-draft"))
    model = FixtureModel([json.dumps(repair), valid])
    pair = CandidatePool(store, "fixture-run", model, IDENTITIES).initial_pair(
        seed=1, cancel=Event()
    )
    assert pair["fixer_a"] is None and pair["fixer_b"] is not None
    assert len(model.requests) == 2


def test_frozen_views_reject_changed_test_pool(store):
    pool = CandidatePool(store, "fixture-run", FixtureModel([]), IDENTITIES)
    test = store.records("fixture-run", "tests")[0]
    store.add_test("fixture-run", {**test, "test_id": "late"})
    with pytest.raises(ValueError, match="stale"):
        pool.initial_pair(seed=1, cancel=Event())
