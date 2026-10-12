import threading

import pytest
from conftest import int_list, literal_test, make_problem, requirement
from hostsandbox import MODE, FixtureHostSandbox

from codejury.stage2_tools.codec import canonical, typed_equal, validate, value_hash
from codejury.stage2_tools.runner import (
    Cancelled,
    Evaluator,
    InfrastructureError,
    WatchdogTimeout,
    hard_rejection,
)
from codejury.stage2_tools.runner.base import validate_envelope
from codejury.stage2_tools.runner.docker import DockerSandbox

SUM = "def f(values):\n    t = 0\n    for v in values:\n        t += v\n    return t\n"


def evaluator(problem, sandbox=None, **kw):
    return Evaluator(sandbox or FixtureHostSandbox(), problem, id_prefix="x", **{
        "max_executions": 100, **kw})  # fmt: skip


def cand(source, cid="c"):
    return {"candidate_id": cid, "source": source}


def prop(template, inputs, reqs=("r",)):
    return {**literal_test(f"t{value_hash(inputs)[:6]}", inputs, 0, reqs),
            "oracle_spec": {"kind": "property", "property_id": template, "parameters": {}},
            "oracle_source": "reviewed_contract", "provenance": "property_engine"}  # fmt: skip


PROBLEM = make_problem(SUM, "f", requirements=[requirement("r", "sum_ints")])


def test_fixture_label_is_explicit():
    assert FixtureHostSandbox.mode == MODE == "FIXTURE_HOST_EXEC"


def test_pass_fail_and_schema_valid_executions():
    ev = evaluator(PROBLEM)
    tests = [literal_test("ok", [[1, 2]], 3), literal_test("bad", [[1, 2]], 4)]
    rows = ev.evaluate(cand(SUM), tests)
    assert [r["outcome"] for r in rows] == ["pass", "fail"]
    for r in rows:
        validate(r, "Execution")
    assert ev.used == 2 and rows[0]["input_effects"][0]["mutated"] is False
    assert rows[0]["execution_id"] == "x-e000" and rows[1]["execution_id"] == "x-e001"
    assert rows[0]["runtime_hash"] == FixtureHostSandbox.runtime_hash


def test_candidate_cannot_assign_pass_label():
    # Even a candidate that raises or returns anything cannot influence the host verdict.
    wrong = "def f(values):\n    return 'pass'\n"
    rows = evaluator(PROBLEM).evaluate(cand(wrong), [literal_test("t", [[1]], 1)])
    assert rows[0]["outcome"] == "fail" and rows[0]["actual_output"] == "pass"


def test_nested_json_and_helper_allowlist_execution():
    helpers = [{"name": "pair", "signature": "pair(a, b)", "contract_text": "gcd"}]
    src = (
        "from math import gcd as g\nfrom collections import Counter\n\n"
        "def pair(a, b):\n    return g(a, b)\n\n"
        "def f(values):\n    r = 0\n    for v in values:\n        r = pair(r, v)\n"
        "    c = Counter(values)\n    return {'gcd': r, 'seen': [[v, c[v]] for v in sorted(c)],"
        " 'ok': True, 'none': None}\n"
    )
    problem = make_problem(src, "f", requirements=[], helpers=helpers,
                           deps=["math.gcd", "collections.Counter"])  # fmt: skip
    expected = {"gcd": 6, "seen": [[12, 1], [18, 1]], "ok": True, "none": None}
    rows = evaluator(problem).evaluate(cand(src), [literal_test("n", [[12, 18]], expected)])
    assert rows[0]["outcome"] == "pass" and typed_equal(rows[0]["actual_output"], expected)


def test_relation_costs_two_calls_and_reports_both_outputs():
    ev = evaluator(PROBLEM)
    meta = {**literal_test("m", [[1, 2, 3]], 0, ["r"]),
            "oracle_spec": {"kind": "metamorphic", "relation_id": "permutation_invariant",
                            "parameters": {}},
            "related_inputs": [[3, 1, 2]], "oracle_source": "reviewed_contract"}  # fmt: skip
    rows = ev.evaluate(cand(SUM), [meta])
    assert rows[0]["outcome"] == "pass" and ev.used == 2
    assert rows[0]["actual_output"] == {"base": 6, "followup": 6}
    assert [e["call_index"] for e in rows[0]["input_effects"]] == [0, 1]
    order = "def f(values):\n    return values[0]\n"
    rows = evaluator(PROBLEM).evaluate(cand(order), [meta])
    assert rows[0]["outcome"] == "fail"


def test_non_authoritative_tests_are_observed_never_pass():
    obs = {**literal_test("o", [[1, 2]], 99, status="proposed"), "oracle_source": "model"}
    rows = evaluator(PROBLEM).evaluate(cand(SUM), [obs])
    assert rows[0]["outcome"] == "observed" and not hard_rejection(rows[0], obs)


def test_input_mutation_is_detected_and_fails_hard_tests():
    mut = "def f(values):\n    values.append(1)\n    return sum(values) - 1\n"
    t = literal_test("m", [[1, 2]], 3)
    row = evaluator(PROBLEM).evaluate(cand(mut), [t])[0]
    assert row["input_effects"][0]["mutated"] is True
    assert row["input_effects"][0]["before_hash"] != row["input_effects"][0]["after_hash"]
    assert row["outcome"] == "fail"


def test_exception_and_output_codec_violations_are_explicit_errors():
    cases = {
        "def f(values):\n    return values[10]\n": "IndexError",
        "def f(values):\n    return tuple(values)\n": "OutputCodecError",
        "def f(values):\n    return {1}\n": "OutputCodecError",
        "def f(values):\n    return len(values) / 3\n": "OutputCodecError",
        "def f(values):\n    return 2 ** 60 + len(values)\n": "OutputCodecError",
        "from collections import Counter\ndef f(values):\n    return Counter(values)\n":
            "OutputCodecError",
    }  # fmt: skip
    for source, kind in cases.items():
        deps = ["collections.Counter"] if "Counter" in source else []
        problem = make_problem(source, "f", deps=deps)
        row = evaluator(problem).evaluate(cand(source), [literal_test("t", [[1, 2]], 0)])[0]
        assert row["outcome"] == "error" and row["exception"]["type"] == kind, (source, row)


def test_infinite_loop_times_out_without_semantic_confusion():
    loop = "def f(values):\n    while True:\n        pass\n"
    ev = evaluator(PROBLEM, call_timeout_s=0.3)
    rows = ev.evaluate(cand(loop), [literal_test("t", [[1]], 1)])
    assert rows[0]["outcome"] == "timeout" and hard_rejection(rows[0], literal_test("t", [[1]], 1))
    # swallowing the alarm with a bare except cannot hide the loop either
    swallow = "def f(values):\n    while True:\n        try:\n            pass\n        except:\n            pass\n"
    assert evaluator(PROBLEM, call_timeout_s=0.3).evaluate(cand(swallow), [literal_test("t", [[1]], 1)])[0]["outcome"] == "timeout"


def test_unsupported_runtime_surface_is_denied_inside_worker():
    # static analysis normally stops these; check=False simulates a bypass reaching the worker.
    for source in (
        "def f(values):\n    return open('/etc/passwd')\n",
        "import os\ndef f(values):\n    return 1\n",
        "def f(values):\n    return __import__('os')\n",
    ):
        row = evaluator(PROBLEM).evaluate(cand(source), [literal_test("t", [[1]], 1)], check=False)[0]
        assert row["outcome"] == "error", source


def test_static_rejection_runs_nothing():
    ev = evaluator(PROBLEM)
    rows = ev.evaluate(cand("import os\ndef f(values):\n    return 1\n"), [literal_test("t", [[1]], 1)])
    assert rows == [] and ev.used == 0 and "c" in ev.static_rejections


def test_unsupported_source_compile_failure_is_error_row():
    row = evaluator(PROBLEM).evaluate(cand("def f(values:\n"), [literal_test("t", [[1]], 1)], check=False)[0]
    assert row["outcome"] == "error"


def test_trace_is_bounded_hashed_and_sanitized():
    src = "def f(values):\n    t = 0\n    for v in values:\n        t += v\n    return t\n"
    ev = evaluator(PROBLEM)
    row = ev.evaluate(cand(src), [literal_test("t", [[1, 2, 3]], 6)], trace_lines=[4])[0]
    trace = ev.traces[row["trace_ref"]]
    assert row["trace_ref"] == value_hash(trace)
    assert [e["line"] for e in trace] == [4, 4, 4] and trace[2]["locals"]["t"] == 3
    assert row["trace_truncated"] is False
    many = evaluator(PROBLEM).evaluate(cand(src), [literal_test("t", [list(range(10))] , 45)], trace_lines=[4])[0]
    assert many["trace_ref"]
    long_src = "def f(values):\n    t = 0\n    for v in values:\n        t += v\n    return t\n"
    big = evaluator(make_problem(long_src, "f", domain=[{"name": "values", "domain": int_list(0, 5, 0, 60)}]))
    row = big.evaluate(cand(long_src), [literal_test("t", [[1] * 60], 60)], trace_lines=[4])[0]
    assert row["trace_truncated"] is True and len(big.traces[row["trace_ref"]]) <= 32
    assert "/" not in canonical(big.traces[row["trace_ref"]])  # no host paths


def test_budget_exhaustion_returns_only_performed_rows():
    ev = evaluator(PROBLEM, max_executions=3)
    tests = [literal_test(f"t{i}", [[i]], i) for i in range(6)]
    rows = ev.evaluate(cand(SUM), tests)
    assert len(rows) == 3 and ev.used == 3 and ev.exhausted
    assert ev.evaluate(cand(SUM, "d"), tests) == []  # nothing left to spend


def test_relation_not_started_when_only_one_call_remains():
    meta = {**literal_test("m", [[1, 2]], 0, ["r"]),
            "oracle_spec": {"kind": "metamorphic", "relation_id": "permutation_invariant",
                            "parameters": {}},
            "related_inputs": [[2, 1]], "oracle_source": "reviewed_contract"}  # fmt: skip
    ev = evaluator(PROBLEM, max_executions=1)
    assert ev.evaluate(cand(SUM), [meta]) == [] and ev.used == 0 and ev.exhausted


def test_stop_on_first_hard_failure_keeps_chunk_rows_only():
    ev = evaluator(PROBLEM, chunk_calls=2)
    tests = [literal_test("a", [[1]], 9)] + [literal_test(f"t{i}", [[i]], i) for i in range(6)]
    rows = ev.evaluate(cand(SUM), tests, stop_on_first_hard_failure=True)
    assert rows[0]["outcome"] == "fail" and len(rows) == 2 and ev.used == 2


def test_cancel_before_and_during_run():
    cancel = threading.Event()
    cancel.set()
    ev = evaluator(PROBLEM, cancel=cancel)
    assert ev.evaluate(cand(SUM), [literal_test("t", [[1]], 1)]) == [] and ev.cancelled
    cancel = threading.Event()
    loop = "def f(values):\n    while True:\n        pass\n"
    ev = evaluator(PROBLEM, FixtureHostSandbox(wall_s=30), cancel=cancel, call_timeout_s=30)
    threading.Timer(0.4, cancel.set).start()
    assert ev.evaluate(cand(loop), [literal_test("t", [[1]], 1)]) == [] and ev.cancelled
    assert ev.used == 0  # no fabricated usage for the interrupted job


def test_watchdog_isolates_hanging_call_as_timeout():
    class Hang:
        runtime_hash = "e" * 64

        def __init__(self):
            self.real = FixtureHostSandbox()

        def run(self, job, cancel=None):
            if len(job["calls"]) > 1 or job["calls"][0]["inputs"] == [[5]]:
                raise WatchdogTimeout("killed")
            return self.real.run(job, cancel)

    tests = [literal_test("a", [[1]], 1), literal_test("b", [[5]], 5)]
    rows = evaluator(PROBLEM, Hang()).evaluate(cand(SUM), tests)
    assert [r["outcome"] for r in rows] == ["pass", "timeout"]


def test_infrastructure_errors_are_not_semantic_outcomes():
    class Broken:
        runtime_hash = "d" * 64

        def run(self, job, cancel=None):
            raise InfrastructureError("vm down")

    with pytest.raises(InfrastructureError):
        evaluator(PROBLEM, Broken()).evaluate(cand(SUM), [literal_test("t", [[1]], 1)])


def test_envelope_validation_rejects_malformed_rows():
    with pytest.raises(InfrastructureError):
        validate_envelope({"results": []}, 1)
    with pytest.raises(InfrastructureError):
        validate_envelope({"results": [{"status": "ok"}]}, 1)
    with pytest.raises(InfrastructureError):
        validate_envelope("junk", 1)


def test_worker_and_host_canonical_hashes_agree():
    import importlib.util

    from conftest import BACKEND

    spec = importlib.util.spec_from_file_location(
        "entry", BACKEND / "src/codejury/stage2_tools/runner/entry.py"
    )
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    for value in ([1, [2, None]], {"b": True, "a": "é😀"}, [], "x"):
        assert entry.canonical(value) == canonical(value)
        assert entry.digest(value) == value_hash(value)


def test_docker_sandbox_requires_pinned_image_and_builds_hardened_argv(monkeypatch, tmp_path):
    monkeypatch.delenv("CODEJURY_STAGE2_RUNNER_IMAGE", raising=False)
    with pytest.raises(InfrastructureError, match="runner image id"):
        DockerSandbox()
    monkeypatch.setenv("CODEJURY_STAGE2_RUNNER_IMAGE", "sha256:" + "a" * 64)
    sandbox = DockerSandbox(home=tmp_path)
    argv = sandbox.argv("job")
    joined = " ".join(argv)
    for flag in ("--network none", "--read-only", "--cap-drop ALL", "--user 65532:65532",
                 "--security-opt no-new-privileges", "--pull never", "--platform linux/arm64",
                 "--memory 512m", "--pids-limit 64"):  # fmt: skip
        assert flag in joined
    assert "-v" not in argv and "--volume" not in argv and "--mount" not in argv
    assert "--privileged" not in argv and "docker.sock" not in joined
    assert "--context colima-codejury-stage2" in joined
    assert len(sandbox.runtime_hash) == 64
    with pytest.raises(InfrastructureError):  # no VM on a CPU-only machine: infra, not semantics
        sandbox.ready()
