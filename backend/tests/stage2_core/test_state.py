"""CPU contract/state checks; fixture sources are parsed, never executed."""

import copy
import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from jsonschema import ValidationError

from codejury.stage2_core.budgets import CAPS, BudgetAccount, BudgetExceeded, zero_usage
from codejury.stage2_core.contract_check import REPO_ROOT, check
from codejury.stage2_core.contracts import (
    CheckedBaselinePort,
    CheckedModelPort,
    CheckedRolloutPort,
    CheckedToolPort,
    cache_key,
    canonical_json,
    checked,
    json_hash,
    source_hash,
)
from codejury.stage2_core.leases import ComputeLease, LeaseBusy
from codejury.stage2_core.ledger import Ledger

FIXTURES = REPO_ROOT / "contracts/stage2-fixtures"


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def draft(candidate):
    fields = set(fixture("candidate-revision-draft"))
    return {key: value for key, value in candidate.items() if key in fields}


@pytest.fixture
def ledger(tmp_path):
    store = Ledger(tmp_path / "runtime")
    snapshot = fixture("snapshot-running")
    store.create_run(
        "fixture-run",
        fixture("problem"),
        mode="fixture",
        profile=CAPS,
        model_configs=[
            c["model_config_hash"] for c in snapshot["candidates"] if c["model_config_hash"]
        ]
        + [
            fixture("candidate-revision-draft")["model_config_hash"],
            fixture("model-response")["model_config_hash"],
        ],
        final_executions=4,
    )
    for candidate in snapshot["candidates"]:
        store.commit_candidate("fixture-run", draft(candidate))
    for test in snapshot["tests"]:
        store.add_test("fixture-run", test)
    known_tests = {t["test_id"] for t in snapshot["tests"]}
    for test in fixture("tool-search-request")["parameters"]["tests"]:
        if test["test_id"] not in known_tests:
            store.add_test("fixture-run", test)
    return store


def dispatch(ledger, operation):
    request = fixture(f"tool-{operation}-request")
    request["remaining_budget"] = ledger.accounts["fixture-run"].remaining()
    request["remaining_budget"]["elapsed_ms"] -= 1000
    ledger.dispatch_tool(request)
    return request


def test_canonical_hash_is_stable_and_type_sensitive():
    assert json_hash({"é": [1, False], "a": None}) == json_hash({"a": None, "é": [1, False]})
    assert json_hash([False]) != json_hash([0])
    assert source_hash("def f():\n    return 1\n") != source_hash("def f():\n    return 1\n\n")
    for invalid in ({1: "x"}, (1, 2), {"x": float("nan")}, {"x": object()}):
        with pytest.raises(ValueError):
            canonical_json(invalid)


@pytest.mark.parametrize(
    "field,value",
    [
        ("learned_candidates", False),
        ("input_tokens", 1.0),
        ("output_tokens", -1),
        ("hidden_reference", "sentinel"),
    ],
)
def test_costs_reject_noninteger_and_hidden_fields(field, value):
    with pytest.raises(ValidationError):
        checked({**zero_usage(), field: value}, "ResourceUsage")


def test_frozen_assets_and_original_schema(tmp_path):
    assert check(REPO_ROOT / "contracts")["synthetic_fixtures"] == 49
    copied = tmp_path / "contracts"
    import shutil

    shutil.copytree(REPO_ROOT / "contracts", copied)
    (copied / "stage2.schema.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        check(copied)


@pytest.mark.parametrize(
    "wrapper,method,request_name,response_name",
    [
        (CheckedModelPort, "generate", "model-request", "model-response"),
        (CheckedToolPort, "call", "tool-search-request", "tool-search-result"),
        (CheckedRolloutPort, "continue_episode", "rollout-request", "rollout-result"),
        (CheckedBaselinePort, "run", "method-request", "method-result"),
    ],
)
def test_boundaries_validate_both_sides_and_propagate_cancel(
    wrapper, method, request_name, response_name
):
    cancel = Event()

    class Port:
        def respond(self, request, token):
            assert token is cancel
            self.request = request
            return self.response

    port = Port()
    setattr(port, method, port.respond)
    port.response = fixture(response_name)
    request = fixture(request_name)
    original = copy.deepcopy(request)
    checked_port = wrapper(port)
    assert getattr(checked_port, method)(request, cancel) == port.response
    assert request == original
    port.response["request_id"] = "wrong-request"
    with pytest.raises(ValueError, match="request ID"):
        getattr(checked_port, method)(request, cancel)
    port.response = fixture(response_name)
    port.response["hidden_reference"] = "never allowed"
    with pytest.raises(ValidationError):
        getattr(checked_port, method)(request, cancel)
    cancel.set()
    with pytest.raises(InterruptedError):
        getattr(checked_port, method)(request, cancel)


def test_candidate_identity_hash_parent_and_model_provenance(ledger):
    candidate = fixture("candidate-revision-draft")
    ledger.commit_candidate("fixture-run", candidate)
    assert ledger.records("fixture-run", "candidates")[-1]["eligibility"] == "pending"
    with pytest.raises(ValueError, match="Duplicate candidate"):
        ledger.commit_candidate("fixture-run", candidate)
    invalid = {**candidate, "candidate_id": "other", "source_hash": "0" * 64}
    with pytest.raises(ValueError, match="hash"):
        ledger.commit_candidate("fixture-run", invalid)
    with pytest.raises(ValueError, match="Unknown parent"):
        ledger.commit_candidate(
            "fixture-run", {**candidate, "candidate_id": "other", "parent_id": "missing"}
        )
    with pytest.raises(ValueError, match="Stale parent"):
        ledger.commit_candidate(
            "fixture-run", {**candidate, "candidate_id": "other"}, expected_parent_hash="0" * 64
        )
    with pytest.raises(ValueError, match="configuration"):
        ledger.commit_candidate(
            "fixture-run", {**candidate, "candidate_id": "other", "model_config_hash": "0" * 64}
        )
    with pytest.raises(ValidationError):
        ledger.commit_candidate("fixture-run", {**candidate, "eligibility": "eligible"})


def test_source_and_record_immutability_survive_reopen(ledger):
    before = ledger.records("fixture-run", "candidates")
    reopened = Ledger(ledger.directory)
    assert reopened.records("fixture-run", "candidates") == before
    source = before[0]["source"]
    assert reopened.read_object(source_hash(source)).decode() == source
    with reopened.connection() as db, pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.execute("UPDATE records SET body='{}'")
    with reopened.connection() as db, pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("DELETE FROM events")
    stored = reopened.artifacts / source_hash(source)
    stored.chmod(0o600)
    stored.write_text("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        reopened.read_object(source_hash(source))


def test_concurrent_content_addressed_writes_are_atomic(ledger):
    content = b"concurrent immutable trace artifact" * 10000
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: ledger.put_object(content), range(20)))
    assert len(set(results)) == 1
    assert ledger.read_object(results[0]) == content


def test_model_attempts_and_reported_usage_survive_restart(ledger):
    request = fixture("model-request")
    request["remaining_budget"] = ledger.accounts["fixture-run"].remaining()
    request["remaining_budget"]["elapsed_ms"] -= 1000
    ledger.dispatch_model(request)
    response = fixture("model-response")
    ledger.settle_model(response)
    actual = ledger.snapshot("fixture-run")["resource_usage"]
    assert actual["learned_candidates"] == 1
    assert actual["output_tokens"] == response["usage"]["output_tokens"]
    restored = Ledger(ledger.directory).snapshot("fixture-run")["resource_usage"]
    assert {k: v for k, v in restored.items() if k != "elapsed_ms"} == {
        k: v for k, v in actual.items() if k != "elapsed_ms"
    }
    assert restored["elapsed_ms"] <= actual["elapsed_ms"]
    with pytest.raises(ValueError, match="duplicate"):
        ledger.settle_model(response)
    with pytest.raises(ValueError, match="Duplicate"):
        ledger.dispatch_model(request)


def test_invalid_judge_choice_still_charges_dispatch_attempt(ledger):
    request = fixture("model-request")
    request.update(role="judge", purpose="action_choice", max_new_tokens=192)
    request["remaining_budget"] = ledger.accounts["fixture-run"].remaining()
    request["remaining_budget"]["elapsed_ms"] -= 1000
    ledger.dispatch_model(request)
    assert ledger.snapshot("fixture-run")["resource_usage"]["judge_decisions"] == 1
    assert (
        Ledger(ledger.directory).snapshot("fixture-run")["resource_usage"]["judge_decisions"] == 1
    )


def test_concurrent_events_order_and_nonmonotonic_rejection(ledger):
    last = len(ledger.events("fixture-run"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(
            pool.map(
                lambda i: ledger.append_event("fixture-run", "action_refused", str(i)), range(20)
            )
        )
    events = ledger.events("fixture-run")
    assert [e["event_id"] for e in events] == list(range(1, last + 21))
    for seq in (last, last + 100):
        with pytest.raises(ValueError, match="nonmonotonic"):
            ledger.append_event("fixture-run", "action_refused", "bad", event_id=seq)


def test_two_edit_sources_reconstruct_and_missing_intermediate_rejected(ledger):
    candidate = draft(fixture("candidate-search"))
    parent = ledger.records("fixture-run", "candidates")[0]
    first = copy.deepcopy(fixture("tool-search-result")["candidates"][0])
    # Second byte edit changes the harmless zero to remove subtraction entirely.
    intermediate = first["source"]
    final = intermediate.replace(" - 0", " + 0")
    second = {
        "location": {"lineno": 3, "col_offset": 31, "end_lineno": 3, "end_col_offset": 32},
        "operator_family": "arithmetic",
        "before": "-",
        "after": "+",
        "parent_source_hash": source_hash(intermediate),
        "result_source_hash": source_hash(final),
    }
    candidate.update(
        candidate_id="two-edit",
        parent_id=parent["candidate_id"],
        source=final,
        source_hash=source_hash(final),
        edits=[first["edits"][0], second],
    )
    source = {
        "schema_version": "stage2.v1",
        "source": intermediate,
        "source_hash": source_hash(intermediate),
    }
    with pytest.raises(ValueError, match="Missing intermediate"):
        ledger.commit_candidate("fixture-run", candidate)
    ledger.commit_candidate("fixture-run", candidate, edit_sources=[source])
    assert ledger.read_object(source_hash(intermediate)).decode() == intermediate
    assert ledger.records("fixture-run", "candidates")[-1]["edits"] == candidate["edits"]


@pytest.mark.parametrize("operation", ["validate", "evaluate", "search", "audit", "investigate"])
def test_five_tool_handshakes_commit_only_pending_candidates(ledger, operation):
    dispatch(ledger, operation)
    ledger.settle_tool(fixture(f"tool-{operation}-result"))
    assert all(c["eligibility"] == "pending" for c in ledger.records("fixture-run", "candidates"))
    checked(ledger.snapshot("fixture-run"), "RunSnapshot")
    with pytest.raises(ValueError, match="duplicate"):
        ledger.settle_tool(fixture(f"tool-{operation}-result"))
    with pytest.raises(ValueError, match="Duplicate request"):
        dispatch(ledger, operation)


@pytest.mark.parametrize("damage", ["hash", "parent", "reference", "prefix", "cost", "receipt"])
def test_bad_tool_result_rolls_back_whole_transaction(ledger, damage):
    dispatch(ledger, "search")
    before = ledger.records("fixture-run", "candidates")
    events = ledger.events("fixture-run")
    result = fixture("tool-search-result")
    if damage == "hash":
        result["candidates"][0]["source_hash"] = "0" * 64
    elif damage == "parent":
        result["candidates"][0]["parent_id"] = "missing"
    elif damage == "reference":
        result["executions"][0]["test_id"] = "unknown"
    elif damage == "prefix":
        result["candidates"][0]["candidate_id"] = "outside-prefix"
    elif damage == "cost":
        result["usage"]["function_executions"] = 1
    elif damage == "receipt":
        result["validation"] = fixture("tool-validate-result")["validation"]
    with pytest.raises(ValueError):
        ledger.settle_tool(result)
    assert ledger.records("fixture-run", "candidates") == before
    assert ledger.events("fixture-run")[:-1] == events
    assert ledger.events("fixture-run")[-1]["type"] == "action_refused"
    assert (
        ledger.accounts["fixture-run"].usage()["function_executions"]
        == result["usage"]["function_executions"]
    )
    assert ledger.accounts["fixture-run"].faulted
    assert (
        Ledger(ledger.directory).snapshot("fixture-run")["resource_usage"]["function_executions"]
        == result["usage"]["function_executions"]
    )


@pytest.mark.parametrize("reported_calls", [1, 7])
def test_relation_two_call_cost_and_extra_shrink_calls(ledger, reported_calls):
    test = copy.deepcopy(ledger.records("fixture-run", "tests")[0])
    test.update(
        test_id="relation",
        related_inputs=[[3, 2]],
        oracle_source="reviewed_contract",
        oracle_spec={
            "kind": "metamorphic",
            "relation_id": "permutation_invariant",
            "parameters": {},
        },
    )
    ledger.add_test("fixture-run", test)
    request = fixture("tool-evaluate-request")
    request["request_id"] = "relation-request"
    request["id_prefix"] = "relation-request"
    request["parameters"]["tests"] = [test]
    request["remaining_budget"] = ledger.accounts["fixture-run"].remaining()
    request["remaining_budget"]["elapsed_ms"] -= 1000
    ledger.dispatch_tool(request)
    result = fixture("tool-evaluate-result")
    result["request_id"] = "relation-request"
    result["executions"] = result["executions"][:1]
    execution = result["executions"][0]
    execution.update(execution_id="relation-request-e0", test_id="relation")
    execution["input_effects"].append({**execution["input_effects"][0], "call_index": 1})
    result["usage"]["function_executions"] = reported_calls
    if reported_calls == 1:
        with pytest.raises(ValueError, match="omit relation"):
            ledger.settle_tool(result)
        assert ledger.accounts["fixture-run"].faulted
    else:
        # Two relation calls plus five actual shrink/replay probe costs are charged.
        ledger.settle_tool(result)
    assert ledger.accounts["fixture-run"].usage()["function_executions"] == reported_calls


def test_no_model_oracles_and_no_unknown_test_references(ledger):
    test = copy.deepcopy(ledger.records("fixture-run", "tests")[0])
    test.update(test_id="invented", oracle_source="model")
    with pytest.raises(ValueError, match="cannot be authoritative"):
        ledger.add_test("fixture-run", test)
    test.update(oracle_source="user", requirement_ids=["unknown"])
    with pytest.raises(ValueError, match="unknown requirement"):
        ledger.add_test("fixture-run", test)
    test.update(
        oracle_source="reviewed_contract",
        requirement_ids=["sum-all"],
        oracle_spec={"kind": "property", "property_id": "sort_ascending_ints", "parameters": {}},
    )
    with pytest.raises(ValueError, match="matching requirement"):
        ledger.add_test("fixture-run", test)


def test_budget_final_reserve_attempts_invalid_choices_and_duplicate_delta():
    ticks = [10.0]
    account = BudgetAccount(
        {**CAPS, "function_executions": 10}, final_executions=4, clock=lambda: ticks[0]
    )
    ceiling = {**dict.fromkeys(CAPS, 0), "elapsed_ms": 900000, "function_executions": 7}
    with pytest.raises(BudgetExceeded, match="final reserve"):
        account.dispatch("too-much", ceiling)
    ceiling["function_executions"] = 6
    account.dispatch("tool", ceiling, attempts={"judge_decisions": 1})
    assert account.usage()["judge_decisions"] == 1  # Invalid choice still consumes an attempt.
    ticks[0] += 2
    account.settle("tool", {**zero_usage(), "function_executions": 6, "elapsed_ms": 1900})
    assert account.usage()["elapsed_ms"] == 2000  # Wall clock, not sum of tool durations.
    with pytest.raises(ValueError, match="duplicate"):
        account.settle("tool", zero_usage())
    ceiling.update(function_executions=4, elapsed_ms=890000)
    account.dispatch("final", ceiling, final=True)
    account.settle("final", {**zero_usage(), "function_executions": 4})
    assert account.usage()["function_executions"] == 10


@pytest.mark.parametrize("value", [False, -1, 1.0, 99999])
def test_malformed_or_excessive_usage_stops_further_dispatch(value):
    account = BudgetAccount(final_executions=0)
    ceiling = {**CAPS, "elapsed_ms": 890000, "output_tokens": 10}
    account.dispatch("model", ceiling)
    with pytest.raises((ValueError, ValidationError)):
        account.settle("model", {**zero_usage(), "output_tokens": value})
    with pytest.raises(BudgetExceeded, match="Untrusted"):
        account.dispatch("next", {**dict.fromkeys(CAPS, 0), "elapsed_ms": 1})


def test_exact_cache_keys_change_with_every_identity_and_survive_restart(ledger):
    test = ledger.records("fixture-run", "tests")[0]
    args = [source_hash("source"), test, "a" * 64, "b" * 64, "c" * 64]
    key = cache_key(*args)
    execution = fixture("tool-evaluate-result")["executions"][0]
    ledger.cache_put(key, execution)
    assert Ledger(ledger.directory).cache_get(key) == execution
    for index in range(5):
        other = copy.deepcopy(args)
        other[index] = {**test, "inputs": [[9]]} if index == 1 else "d" * 64
        assert ledger.cache_get(cache_key(*other)) is None
    with pytest.raises(ValueError, match="conflict"):
        ledger.cache_put(key, {**execution, "actual_output": 900})


def test_actual_process_crash_discards_partial_event_and_recovers_run(ledger):
    before = len(ledger.events("fixture-run"))
    dispatch(ledger, "search")
    script = """
import os, sqlite3, sys
db = sqlite3.connect(sys.argv[1])
db.execute('BEGIN IMMEDIATE')
db.execute('INSERT INTO events VALUES (?,?,?)', ('fixture-run',999,'{}'))
os._exit(0)
"""
    subprocess.run([sys.executable, "-c", script, str(ledger.path)], check=True)
    reopened = Ledger(ledger.directory)
    assert len(reopened.events("fixture-run")) == before
    assert reopened.recover() == ["fixture-run"]
    assert reopened.recover() == []
    snapshot = reopened.snapshot("fixture-run")
    assert snapshot["status"] == "infrastructure_error"
    assert snapshot["decision"]["selected_candidate_id"] is None
    with pytest.raises(ValueError, match="cannot resume"):
        reopened.dispatch_tool(fixture("tool-search-request"))


def test_competing_process_compute_leases_and_real_stale_owner_recovery(tmp_path):
    path = tmp_path / "compute.lock"
    script = """
import sys
from pathlib import Path
from codejury.stage2_core.leases import ComputeLease
lease = ComputeLease(Path(sys.argv[1]), owner='child', job_id='training', kind='training')
lease.acquire()
print('locked', flush=True)
sys.stdin.readline()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout.readline().strip() == "locked"
        for kind in ("runtime", "training", "teacher", "benchmark"):
            with pytest.raises(LeaseBusy):
                ComputeLease(path, owner="parent", job_id=kind, kind=kind).acquire()
        pid = child.pid
        child.kill()
        child.wait(timeout=5)
        assert json.loads(path.read_text())["pid"] == pid  # Metadata remains stale.
        with ComputeLease(path, owner="parent", job_id="after-crash", kind="runtime"):
            assert json.loads(path.read_text())["pid"] == os.getpid()
            with pytest.raises(LeaseBusy):
                ComputeLease(path, owner="second", job_id="other", kind="teacher").acquire()
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)


def test_cancel_and_stale_pid_metadata_are_not_lock_authority(tmp_path):
    path = tmp_path / "compute.lock"
    path.write_text(json.dumps({"pid": os.getpid(), "owner": "old-job"}))
    cancel = Event()
    lease = ComputeLease(path, owner="ajay", job_id="current", kind="runtime", cancel=cancel)
    with lease:
        cancel.set()
        with pytest.raises(InterruptedError):
            lease.check_cancel()
    with pytest.raises(InterruptedError):
        lease.acquire()
    assert path.exists()  # Stable inode remains available to future jobs.
