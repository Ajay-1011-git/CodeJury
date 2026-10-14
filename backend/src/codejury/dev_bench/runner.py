"Sequential native baselines; commit every selection before opening scoring data."

import json
import threading
import time
from pathlib import Path
from uuid import uuid4

from jsonschema import ValidationError

from codejury.dev_bench import (
    METHODS,
    SEEDS,
    execute_tests,
    file_hash,
    load_runtime,
    load_scoring,
    passes,
    read_jsonl,
    summarize,
)
from codejury.stage2_core.baselines import raw_commit
from codejury.stage2_core.baselines.controllers import RepairBaseline
from codejury.stage2_core.budgets import CAPS
from codejury.stage2_core.candidates import incumbent, parse_draft
from codejury.stage2_core.contracts import json_hash
from codejury.stage2_core.controller import FixedController
from codejury.stage2_core.controller.learned import LearnedController
from codejury.stage2_core.factory import make_model_port
from codejury.stage2_core.intake import prepare
from codejury.stage2_core.ledger import Ledger
from codejury.stage2_core.registry import local_path
from codejury.stage2_tools.factory import make_tool_port
from codejury.stage2_tools.port import ToolPortImpl
from codejury.stage2_tools.runner.base import InfrastructureError


class BestOfN(RepairBaseline):
    """One trained A model, eight blind attempts, supplied-suite selection only.

    v1's greedy sampler is retained; repeated candidates are disclosed, not
    relabelled as temperature samples. No revisions, search, Critic or Judge.
"""

    def initial_candidates(self):
        generated = []
        for attempt in range(CAPS["learned_candidates"]):
            if (
                not self.account.remaining()["learned_candidates"]
                or not self.account.remaining()["output_tokens"]
            ):
                break
            candidate = self.pool.generate(
                "fixer_a",
                self.pool.views.a,
                parent=self.original,
                seed=self.seed + attempt,
                cancel=self.cancel,
                max_attempts=1,
            )
            if candidate:
                generated.append(candidate)
        return generated

    def options(self, state, snapshot, candidates):
        chosen = incumbent({"candidates": candidates}, self.problem["source"])
        options = []
        if chosen and not state["unresolved_requirement_ids"]:
            options.append(
                self.option(
                    "select",
                    [chosen],
                    {"candidate_id": chosen},
                    "Best supplied-suite-qualified single-model candidate",
                    state,
                )
            )
        options.append(
            self.option(
                "abstain",
                [],
                {"reason": "No supplied-suite-qualified candidate"},
                "Safe terminal option",
                state,
            )
        )
        return options


def output_validity(ledger, run_id):
    roles = {}
    with ledger.connection() as db:
        rows = db.execute(
            (
                "SELECT body,response FROM requests WHERE run_id=? AND defini"
                "tion='ModelRequest' ORDER BY rowid"
            ),
            (run_id,),
        ).fetchall()
    for row in rows:
        request = json.loads(row["body"])
        response = json.loads(row["response"]) if row["response"] else {}
        counts = roles.setdefault(
            request["role"], {"calls": 0, "malformed": 0, "transport_failures": 0}
        )
        counts["calls"] += 1
        if response.get("status") != "ok":
            counts["transport_failures"] += 1
            continue
        definition = (
            "JudgeDraft"
            if request["role"] == "judge"
            else "CriticDraft"
            if request["role"] == "critic"
            else "RepairDraft"
        )
        try:
            parse_draft(response.get("text"), definition)
        except (ValueError, TypeError, ValidationError):
            counts["malformed"] += 1
    return roles


def run_method(row, method, seed, model, base_tool, out):
    create = {**row["run_create"], "seed": seed}
    problem, tests = prepare(create)
    ledger = Ledger(out / "ledgers" / ("method-" + uuid4().hex))
    identities = {
        r: model.registry.identity(r) for r in ["raw", *model.registry.record["adapters"]]
    }
    tool = ToolPortImpl(base_tool.sandbox, contracts=base_tool.contracts)
    cls = {"B-base": FixedController, "B-single": BestOfN, "J-current": LearnedController}[method]
    control = cls(
        ledger,
        model,
        tool,
        identities,
        manifest_hash=model.registry.manifest_hash,
        runtime_hash=tool.sandbox.runtime_hash,
        mode="live",
    )
    cancel = threading.Event()
    # Each method retains the same runtime caps; scorer costs are recorded separately.
    timer = threading.Timer(CAPS["elapsed_ms"] / 1000, cancel.set)
    timer.daemon = True
    timer.start()
    started = time.monotonic()
    error = None
    try:
        if method == "B-base":
            snapshot = raw_commit(control, problem, tests, seed, cancel, CAPS)
        else:
            snapshot = control.run(problem, tests, cancel=cancel, seed=seed, limits=CAPS)
    except Exception as exc:
        error = type(exc).__name__
        snapshot = ledger.snapshot(control.run_id) if hasattr(control, "run_id") else None
    finally:
        timer.cancel()
    selected = snapshot["decision"]["selected_candidate_id"] if snapshot else None
    candidate = (
        next((c for c in snapshot["candidates"] if c["candidate_id"] == selected), None)
        if snapshot
        else None
    )
    proposals = [c for c in snapshot["candidates"] if c["origin"] != "original"] if snapshot else []
    record = {
        "version": "codejury.dev-bench.result.v1",
        "base_problem_id": row["base_problem_id"],
        "family_id": row["family_id"],
        "tier": row["tier"],
        "method": method,
        "seed": seed,
        "runtime_mode": "live",
        "status": snapshot["status"] if snapshot else "infrastructure_error",
        "selected_source": candidate["source"] if candidate else None,
        "selected_source_hash": candidate["source_hash"] if candidate else None,
        "unverified_prediction": method == "B-base",
        "resource_caps": CAPS,
        "resource_usage": ledger.accounts[control.run_id].usage()
        if hasattr(control, "run_id")
        else None,
        "wall_clock_s": time.monotonic() - started,
        "native_peak_memory_scope": "MLX allocator only; VM and total system peak are not measured",
        "output_validity": output_validity(ledger, control.run_id)
        if hasattr(control, "run_id")
        else {},
        "candidates": len(proposals),
        "unique_candidate_sources": len({c["source_hash"] for c in proposals}),
        "ledger_directory": str(ledger.directory),
        "error_type": error,
    }
    return record


def categorize(record, correct):
    if record["error_type"] or record["status"] == "infrastructure_error":
        return "infrastructure"
    if record["status"] == "invalid_input":
        return "invalid"
    if record["selected_source"] is not None:
        if correct:
            return "solved"
        return "unresolved" if record["unverified_prediction"] else "wrong_accepted"
    counts = record["output_validity"]
    if counts and all(c["calls"] == c["malformed"] for c in counts.values()):
        return "invalid"
    return "unresolved"


def score_records(records, runtime, scoring, sandbox):
    lookup = {r["base_problem_id"]: r for r in runtime}
    for record in records:
        result = {
            **record,
            "outcome": None,
            "hidden_correct": None,
            "scoring_executions": 0,
            "scoring_error_type": None,
        }
        if record["selected_source"] is not None:
            row = lookup[record["base_problem_id"]]
            tests = scoring[record["base_problem_id"]]["hidden_tests"]
            if record["unverified_prediction"]:
                tests = row["run_create"]["supplied_tests"] + tests
            try:
                rows = execute_tests(sandbox, record["selected_source"], row["run_create"], tests)
                result["scoring_executions"] = len(rows)
                result["hidden_correct"] = all(passes(r, t) for r, t in zip(rows, tests))
            except (InfrastructureError, OSError) as exc:
                result["scoring_error_type"] = type(exc).__name__
                result["outcome"] = "infrastructure"
            except ValueError as exc:
                # Static/signature refusal is an invalid prediction, never a sandbox pass.
                result["scoring_error_type"] = type(exc).__name__
                result["outcome"] = "invalid"
        result["outcome"] = result["outcome"] or categorize(record, result["hidden_correct"])
        yield result


def run_benchmark(directory, out, *, methods=METHODS, seeds=SEEDS, ids=None, resume=False):
    directory, out = Path(directory), Path(out)
    runtime = load_runtime(directory)  # ONLY runtime-visible material in the method phase.
    if ids is not None:
        unknown = set(ids) - {r["base_problem_id"] for r in runtime}
        if unknown:
            raise ValueError("Unknown problem IDs")
        runtime = [r for r in runtime if r["base_problem_id"] in ids]
    validation = json.loads((directory / "validation.json").read_text())
    if (
        validation["rejected"]
        or validation["bases"] < 60
        or validation["runtime_sha256"] != file_hash(directory / "runtime.jsonl")
        or validation["scoring_sha256"] != file_hash(directory / "private/scoring.jsonl")
    ):
        raise ValueError("Current successful Docker validation of at least 60 bases required")
    out.mkdir(parents=True, exist_ok=True)
    tool = make_tool_port(local_path("../integration/stage2/tools.yaml"))
    tool.sandbox.ready()
    if tool.sandbox.runtime_hash != validation["runtime_hash"]:
        raise ValueError("Sandbox differs from benchmark validation")
    with make_model_port(local_path("config/stage2_core/runtime.yaml")) as model:
        if not model.registry.readiness()["ready"]:
            raise ValueError("Current jury requires four completed roles")
        freeze = {
            "version": "codejury.dev-bench.protocol.v1",
            "runtime_sha256": validation["runtime_sha256"],
            "scoring_sha256": validation["scoring_sha256"],
            "model_registry_hash": model.registry.manifest_hash,
            "runtime_hash": tool.sandbox.runtime_hash,
            "runner_sha256": file_hash(__file__),
            "methods": list(methods),
            "seeds": list(seeds),
            "base_problem_ids": [r["base_problem_id"] for r in runtime],
            "caps": CAPS,
            "sampler": "v1 greedy, unmodified",
            "B-single": (
                "trained fixer_a, up to eight blind attempts, no schema retry"
                ", supplied-test selector"
            ),
            "B-base": (
                "raw one-shot, unverified prediction; incorrect predictions c"
                "ount unsolved, never wrong accepted"
            ),
            "memory_scope": "per-generation native MLX allocator; total Mac/VM peak unknown",
            "full_population": ids is None and tuple(methods) == METHODS and tuple(seeds) == SEEDS,
        }
        freeze_path = out / "protocol.json"
        if resume:
            if json.loads(freeze_path.read_text()) != freeze:
                raise ValueError("Resume protocol changed")
            committed = read_jsonl(out / "commitments.jsonl")
        else:
            with freeze_path.open("x") as handle:
                handle.write(json.dumps(freeze, indent=2) + "\n")
            committed = []
        plan = [
            (method, row["base_problem_id"], seed)
            for row in runtime
            for method in methods
            for seed in seeds
        ]
        keys = [(r["method"], r["base_problem_id"], r["seed"]) for r in committed]
        if keys != plan[: len(keys)]:
            raise ValueError("Commitments are not a unique prefix of the frozen plan")
        # One resident process and one global compute lease; all methods sequential.
        model.start(threading.Event())
        with (out / "commitments.jsonl").open("a" if resume else "x") as handle:
            for row in runtime:
                for method in methods:
                    for seed in seeds:
                        key = method, row["base_problem_id"], seed
                        if key in keys:
                            continue
                        if (
                            file_hash(directory / "runtime.jsonl") != freeze["runtime_sha256"]
                            or file_hash(__file__) != freeze["runner_sha256"]
                        ):
                            raise ValueError("Benchmark or runner changed during execution")
                        record = run_method(row, method, seed, model, tool, out)
                        record["protocol_hash"] = json_hash(freeze)
                        handle.write(json.dumps(record, sort_keys=True) + "\n")
                        handle.flush()
                        committed.append(record)
                        print(
                            json.dumps(
                                {
                                    "committed": len(committed),
                                    "total": len(plan),
                                    "base": row["base_problem_id"],
                                    "method": method,
                                    "seed": seed,
                                    "status": record["status"],
                                    "wall_clock_s": round(record["wall_clock_s"], 2),
                                }
                            ),
                            flush=True,
                        )
        # Release compute before scoring. No hidden outcome can steer any method.
    scoring = load_scoring(directory)
    if file_hash(directory / "private/scoring.jsonl") != freeze["scoring_sha256"]:
        raise ValueError("Scoring tests changed during methods")
    results_path = out / "results.jsonl"
    if resume and results_path.exists():
        results = read_jsonl(results_path)
        result_keys = [(r["method"], r["base_problem_id"], r["seed"]) for r in results]
        if result_keys != plan[: len(result_keys)]:
            raise ValueError("Scores are not a unique prefix of the frozen plan")
    else:
        results = []
    with results_path.open("a" if resume else "x") as handle:
        for result in score_records(committed[len(results) :], runtime, scoring, tool.sandbox):
            handle.write(json.dumps(result, sort_keys=True) + "\n")
            handle.flush()
            results.append(result)
            print(
                json.dumps(
                    {"scored": len(results), "total": len(plan), "outcome": result["outcome"]}
                ),
                flush=True,
            )
    report = {
        "protocol": freeze,
        "summary": summarize(results),
        "commitments_sha256": file_hash(out / "commitments.jsonl"),
        "results_sha256": file_hash(results_path),
    }
    (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))
    return report
