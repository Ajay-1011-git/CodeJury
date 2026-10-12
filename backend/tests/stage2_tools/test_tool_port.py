import copy
import threading

import pytest
from hostsandbox import FixtureHostSandbox

from codejury.stage2_tools.codec import sha256_text, validate
from codejury.stage2_tools.port import ResultError, ToolPortImpl, verify_result
from codejury.stage2_tools.runner import InfrastructureError

OPS = ["validate", "evaluate", "search", "audit", "investigate"]


def port():
    return ToolPortImpl(FixtureHostSandbox())


def call(request, p=None, cancel=None):
    return (p or port()).call(request, cancel or threading.Event())


@pytest.fixture
def req(fixture):
    return {op: fixture(f"tool-{op}-request") for op in OPS}


def test_all_five_operations_return_schema_valid_verified_results(req):
    for op in OPS:
        result = call(req[op])
        validate(result, "ToolResult")
        assert result["status"] == "ok", (op, result["error"], result["warnings"])
        verify_result(req[op], result)
        assert result["request_id"] == req[op]["request_id"]


def test_validate_returns_receipt_only(req):
    r = call(req["validate"])
    assert r["validation"]["valid"] is True and r["validation"]["signature"] == "sum_values(values)"
    assert not (r["candidates"] or r["tests"] or r["executions"] or r["mutants"])
    assert r["usage"]["function_executions"] == 0
    bad = copy.deepcopy(req["validate"])
    bad["parameters"]["source"] = "import os\ndef sum_values(values):\n    return 1\n"
    r = call(bad)
    assert r["status"] == "ok" and r["validation"]["valid"] is False
    assert r["validation"]["error"]["code"] == "invalid_source"


def test_evaluate_reports_only_performed_executions_and_usage(req):
    r = call(req["evaluate"])
    n_c, n_t = (
        len(req["evaluate"]["parameters"]["candidates"]),
        len(req["evaluate"]["parameters"]["tests"]),
    )
    assert len(r["executions"]) == n_c * n_t == r["usage"]["function_executions"]
    assert r["candidates"] == [] and r["mutants"] == []
    ids = [e["execution_id"] for e in r["executions"]]
    assert ids == [f"tool-evaluate-e{i:03d}" for i in range(len(ids))]


def test_search_returns_drafts_with_exact_lineage(req):
    r = call(req["search"])
    assert r["status"] == "ok"
    for c in r["candidates"]:
        assert c["origin"] == "ast_search" and c["model_config_hash"] is None
        assert c["candidate_id"].startswith("tool-search-c")
    assert r["usage"]["search_candidates"] >= len(r["candidates"])


def test_audit_returns_probes_and_gaps_never_candidates(req):
    r = call(req["audit"])
    assert r["candidates"] == [] and r["executions"] == [] and r["mutants"]
    assert r["usage"]["audit_mutants"] == len(r["mutants"])
    assert r["usage"]["function_executions"] > 0
    for g in r["audit_gaps"]:
        assert g["candidate_source_hash"] == req["audit"]["parameters"]["candidate"]["source_hash"]


def test_investigate_admits_authorised_failure_and_gives_rows_for_targets(req):
    r = call(req["investigate"])
    assert r["status"] == "ok" and r["tests"]
    assert all(t["oracle_status"] == "authoritative" for t in r["tests"])
    assert {e["candidate_id"] for e in r["executions"]} == {"c-a", "c-b"}
    assert r["candidates"] == [] and r["mutants"] == [] and r["audit_gaps"] == []


# ---- bad requests -----------------------------------------------------------------------


def mutate(request, path, value):
    out = copy.deepcopy(request)
    node = out
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return out


def test_structural_and_identity_rejections(req):
    base = req["evaluate"]
    bad = copy.deepcopy(base)
    bad["surprise"] = 1
    assert call(bad)["status"] == "invalid_input"
    bad = mutate(base, ["request_id"], "")
    r = call(bad)
    assert r["status"] == "invalid_input" and r["request_id"] == "invalid-request"
    assert call({"not": "a request"})["status"] == "invalid_input"
    assert call(mutate(base, ["id_prefix"], "x" * 101))["status"] == "invalid_input"
    assert call(mutate(base, ["problem", "source_hash"], "0" * 64))["status"] == "invalid_input"
    assert (
        call(mutate(base, ["problem", "signature"], "other(values)"))["status"] == "invalid_input"
    )
    assert call(mutate(base, ["parameters", "candidates", 0, "source_hash"], "0" * 64))[
        "status"
    ] == ("invalid_input")
    assert call(mutate(base, ["parameters", "candidates", 0, "problem_id"], "other"))["status"] == (
        "invalid_input"
    )
    dup = copy.deepcopy(base)
    dup["parameters"]["candidates"][1]["candidate_id"] = "c-a"
    assert "Duplicate candidate" in call(dup)["error"]["message"]
    wrong_version = mutate(base, ["schema_version"], "stage2.v0")
    assert call(wrong_version)["status"] == "invalid_input"


def test_unauthorised_authoritative_claim_is_rejected(req):
    forged = copy.deepcopy(req["evaluate"])
    test = forged["parameters"]["tests"][0]
    test["oracle_source"] = "model"
    test["provenance"] = "critic"
    r = call(forged)
    assert r["status"] == "invalid_input" and "authority" in r["error"]["message"]
    out_of_domain = copy.deepcopy(req["evaluate"])
    out_of_domain["parameters"]["tests"][0]["inputs"] = [[999]]
    assert call(out_of_domain)["status"] == "invalid_input"  # claims domain_valid true


def test_audit_binds_every_probe_and_gap_to_the_requested_suite_and_source(req):
    # The core owns the frozen hard-suite hash; the tool echoes it and never re-derives it.
    other = mutate(req["audit"], ["parameters", "suite_hash"], "1" * 64)
    r = call(other)
    assert r["status"] == "ok" and r["mutants"]
    assert {m["suite_hash"] for m in r["mutants"]} == {"1" * 64}
    assert {g["suite_hash"] for g in r["audit_gaps"]} == {"1" * 64}
    wrong_source = copy.deepcopy(req["audit"])
    wrong_source["parameters"]["candidate"]["source"] += "# edited\n"
    assert call(wrong_source)["status"] == "invalid_input"  # hash no longer matches the source


def test_budget_exhaustion_and_cancel(req):
    r = call(mutate(req["evaluate"], ["remaining_budget", "function_executions"], 0))
    assert r["status"] == "budget_exhausted" and r["executions"] == []
    r = call(mutate(req["evaluate"], ["remaining_budget", "function_executions"], 1))
    assert r["status"] == "budget_exhausted" and len(r["executions"]) == 1
    assert r["usage"]["function_executions"] == 1
    cancel = threading.Event()
    cancel.set()
    r = call(req["evaluate"], cancel=cancel)
    assert (
        r["status"] == "cancelled"
        and r["executions"] == []
        and r["usage"]["function_executions"] == 0
    )
    r = call(mutate(req["search"], ["remaining_budget", "search_candidates"], 0))
    assert r["status"] == "budget_exhausted" and r["candidates"] == []


def test_infrastructure_loss_is_never_a_semantic_result(req):
    class Down:
        runtime_hash = "c" * 64

        def run(self, job, cancel=None):
            raise InfrastructureError("vm down")

    r = call(req["evaluate"], ToolPortImpl(Down()))
    assert r["status"] == "infrastructure_error" and r["error"]["code"] == "infrastructure_error"
    assert r["executions"] == [] and r["candidates"] == []
    validate(r, "ToolResult")


def test_verifier_rejects_evidence_that_breaks_the_contract(req):
    search_req = req["search"]
    good = call(search_req)
    assert good["candidates"], "fixture search is expected to find the one-line fix"

    def broken(change):
        bad = copy.deepcopy(good)
        change(bad)
        with pytest.raises(ResultError):
            verify_result(search_req, bad)

    broken(lambda r: r["candidates"][0]["edits"][0].__setitem__("parent_source_hash", "0" * 64))
    broken(lambda r: r["candidates"][0].__setitem__("candidate_id", "other-c000"))
    broken(lambda r: r["executions"][0].__setitem__("candidate_id", "ghost"))
    broken(lambda r: r.__setitem__("request_id", "other"))
    broken(lambda r: r["usage"].__setitem__("function_executions", 0))
    broken(lambda r: r["usage"].__setitem__("output_tokens", 1))
    broken(lambda r: r["mutants"].append({}))
    broken(lambda r: r["candidates"][0].__setitem__("origin", "fixer_a"))


def test_live_factory_imports_no_fake_and_fails_closed(monkeypatch, tmp_path):
    import ast
    from pathlib import Path

    import codejury.stage2_tools.factory as factory

    tree = ast.parse(Path(factory.__file__).read_text())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any("hostsandbox" in m or "test" in m or "fixture" in m for m in imported)
    monkeypatch.delenv("CODEJURY_STAGE2_RUNNER_IMAGE", raising=False)
    config = Path(factory.__file__).resolve().parents[3] / "config/stage2_tools/runtime.yaml"
    with pytest.raises(InfrastructureError):
        factory.make_tool_port(config)
    monkeypatch.setenv("CODEJURY_STAGE2_RUNNER_IMAGE", "sha256:" + "b" * 64)
    live = factory.make_tool_port(config)
    assert live.mode == "live" and type(live.sandbox).__name__ == "DockerSandbox"


def test_request_does_not_leak_through_hash_helper():
    assert sha256_text("x") == sha256_text("x") and len(sha256_text("x")) == 64
