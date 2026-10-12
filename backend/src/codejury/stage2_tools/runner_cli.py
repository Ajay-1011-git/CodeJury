"""Runner self-test. Real sandbox only: with no VM/image every check is reported pending."""

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from .domains import analyze_source
from .runner import Evaluator, InfrastructureError
from .runner.docker import DockerSandbox


def _problem(source, name="f", deps=(), helpers=()):
    info = analyze_source(source, name, list(helpers), list(deps))
    return {
        "function_name": name, "signature": info.signature, "helper_interfaces": list(helpers),
        "allowed_dependencies": list(deps), "domain_schema": [], "requirements": [],
    }  # fmt: skip


def _lit(test_id, inputs, expected):
    return {
        "test_id": test_id, "inputs": inputs, "related_inputs": None,
        "oracle_spec": {"kind": "literal", "expected": expected},
        "oracle_status": "authoritative", "oracle_source": "user", "domain_valid": True,
        "requirement_ids": [], "provenance": "supplied",
    }  # fmt: skip


def checks(sandbox, config_path):
    out = {}

    def ev(problem, **kw):
        return Evaluator(sandbox, problem, id_prefix="st", max_executions=200, **kw)

    def run(source, tests, deps=(), helpers=(), check=True, **kw):
        e = ev(_problem(source, deps=deps, helpers=helpers) if check else
               {"function_name": "f", "allowed_dependencies": list(deps)}, **kw)
        return e, e.evaluate({"candidate_id": "c", "source": source}, tests, check=check)

    sum_src = "def f(v):\n    t = 0\n    for x in v:\n        t += x\n    return t\n"
    helper = [{"name": "pair", "signature": "pair(a, b)", "contract_text": "gcd"}]
    gcd_src = ("from math import gcd\ndef pair(a, b):\n    return gcd(a, b)\n"
               "def f(v):\n    r = 0\n    for x in v:\n        r = pair(r, x)\n    return r\n")  # fmt: skip
    _, rows = run(gcd_src, [_lit("t", [[12, 18]], 6)], ["math.gcd"], helper)
    out["helper_allowlist_execution"] = rows[0]["outcome"] == "pass"
    nested = "def f(v):\n    return {'a': [[1, None], True]}\n"
    _, rows = run(nested, [_lit("t", [[1]], {"a": [[1, None], True]})])
    out["nested_json"] = rows[0]["outcome"] == "pass"
    meta = {**_lit("m", [[1, 2]], 0), "related_inputs": [[2, 1]],
            "oracle_spec": {"kind": "metamorphic", "relation_id": "permutation_invariant",
                            "parameters": {}}}  # fmt: skip
    e, rows = run(sum_src, [meta])
    out["relation_costs_two"] = e.used == 2
    _, rows = run("def f(v):\n    v.append(1)\n    return 0\n", [_lit("t", [[1]], 0)])
    out["input_mutation_detected"] = rows[0]["input_effects"][0]["mutated"] is True
    _, rows = run("def f(v):\n    return ['x' * 7000] * 20\n", [_lit("t", [[1]], 0)])
    out["output_overflow_error"] = rows[0]["outcome"] == "error"
    _, rows = run("def f(v):\n    while True:\n        pass\n", [_lit("t", [[1]], 0)])
    out["infinite_loop_timeout"] = rows[0]["outcome"] == "timeout"
    _, rows = run("def f(v):\n    return [[0] * 5000 for _ in range(100000)]\n",
                  [_lit("t", [[1]], 0)])  # fmt: skip
    out["memory_bomb_contained"] = rows[0]["outcome"] in {"error", "timeout"}
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()
    e, rows = run("def f(v):\n    while True:\n        pass\n", [_lit("t", [[1]], 0)],
                  cancel=cancel, call_timeout_s=30)  # fmt: skip
    out["cancel_kills_job"] = rows == [] and e.cancelled
    probe = sandbox.argv("codejury-s2-probe-net")
    probe = probe[: probe.index(sandbox.image) + 1] + [
        "python", "-c",
        "import socket,sys\ntry:\n socket.create_connection(('1.1.1.1',53),2)\nexcept OSError:\n"
        " sys.exit(0)\nsys.exit(9)",
    ]  # fmt: skip
    subprocess.run(probe, capture_output=True, check=True, timeout=20)
    net = subprocess.run(sandbox.docker("start", "-a", "codejury-s2-probe-net"),
                         capture_output=True, timeout=20)  # fmt: skip
    subprocess.run(sandbox.docker("rm", "-f", "codejury-s2-probe-net"), capture_output=True)
    out["network_denied"] = net.returncode == 0
    inspected = _inspect(sandbox)
    out["isolation_inspection"] = bool(inspected)
    out["mount_denied"] = inspected["mounts"] == []
    os.environ[sandbox.config["image_env"]] = "sha256:" + "0" * 64
    try:
        DockerSandbox(config_path).ready()
        out["missing_image"] = False
    except InfrastructureError:
        out["missing_image"] = True
    finally:
        os.environ[sandbox.config["image_env"]] = sandbox.image
    return out


def _inspect(sandbox):
    name = "codejury-s2-probe-inspect"
    subprocess.run(sandbox.argv(name), capture_output=True, check=True, timeout=20)
    try:
        return sandbox.inspect_job(name)
    finally:
        subprocess.run(sandbox.docker("rm", "-f", name), capture_output=True)


def self_test(config, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"mode": "native_sandbox", "config": str(config), "checks": {}}
    try:
        sandbox = DockerSandbox(config)
        report["environment"] = sandbox.ready()
        report["mount_evidence"] = _inspect(sandbox)
        report["runtime_hash"] = sandbox.runtime_hash
        report["checks"] = checks(sandbox, config)
        report["overall"] = "passed" if all(report["checks"].values()) else "failed"
    except (InfrastructureError, OSError, subprocess.SubprocessError) as exc:
        names = ["helper_allowlist_execution", "nested_json", "relation_costs_two",
                 "input_mutation_detected", "output_overflow_error", "infinite_loop_timeout",
                 "memory_bomb_contained", "cancel_kills_job", "network_denied",
                 "isolation_inspection", "mount_denied", "missing_image"]  # fmt: skip
        report["checks"] = {name: "pending_native" for name in names}
        report["overall"] = "pending_native"
        report["reason"] = f"{type(exc).__name__}: {exc}"
    (out_dir / "runner-self-test.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="runner_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("self-test")
    st.add_argument("--config", required=True, type=Path)
    st.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    report = self_test(args.config, args.out)
    print(json.dumps({"overall": report["overall"], "checks": report["checks"]}, indent=2))
    return {"passed": 0, "pending_native": 3}.get(report["overall"], 1)


if __name__ == "__main__":
    sys.exit(main())
