"""Fair, sealed benchmark runner.

Phase 1 commits every run's selected source/hash (and the candidate pool) to an append-only log
with NO access to hidden data. Phase 2 scores selections once against the hidden tests. Phase 3
scores candidate pools for secondary diagnostics, only after every commitment exists. Methods
never receive repair feedback derived from hidden outcomes, and the request a method sees is
byte-identical across methods for a task/seed apart from the method id and its frozen caps.
"""

import hashlib
import json
import threading
import time
from pathlib import Path

from ..codec import errors, sha256_text, value_hash
from . import config as cfg
from .tasks import EvalTask, static_eligibility, visible_hash

SIX = (
    "solved",
    "incorrect_accepted",
    "unresolved",
    "invalid_input",
    "infrastructure_error",
    "cancelled",
)


class HarnessError(RuntimeError):
    pass


def categorize(status: str, correct: bool | None) -> str:
    if status == "supported_patch":
        return "solved" if correct else "incorrect_accepted"
    if status in ("unresolved", "invalid_input", "infrastructure_error", "cancelled"):
        return status
    return "infrastructure_error"  # queued/running is never a terminal method answer


class Harness:
    def __init__(
        self, config: dict, baseline_port, scorer, *, mode: str, out_dir: Path, clock=time.monotonic
    ):
        if mode not in ("fixture", "live"):
            raise HarnessError("mode must be fixture or live")
        if config["profile"] == "final" and mode == "fixture":
            raise HarnessError("The final assessment rejects fixture results")
        self.config = config
        self.port = baseline_port
        self.scorer = scorer
        self.mode = mode
        self.out = Path(out_dir)
        self.clock = clock
        self.out.mkdir(parents=True, exist_ok=True)

    # -- preflight ------------------------------------------------------------------------
    def preflight(self, tasks: list[EvalTask]) -> dict:
        """Frozen exclusion rule, applied before any method runs; reports both populations."""
        eligible, excluded = [], []
        for task in tasks:
            reason = static_eligibility(task)
            if reason is None and hasattr(self.scorer, "reference_ok"):
                if not self.scorer.reference_ok(task):
                    reason = "reference solution fails its own hidden tests"
            (excluded if reason else eligible).append((task, reason))
        report = {
            "original_population": len(tasks),
            "eligible": len(eligible),
            "excluded": [{"task_id": t.task_id, "reason": r} for t, r in excluded],
            "by_kind": {
                k: sum(1 for t, _ in eligible if t.kind == k)
                for k in sorted({t.kind for t, _ in eligible})
            },
        }
        (self.out / "eligibility.json").write_text(json.dumps(report, indent=2, sort_keys=True))
        self.eligible = [t for t, _ in eligible]
        return report

    # -- phase 1: commit ------------------------------------------------------------------
    def request_for(self, task: EvalTask, method: str, regime: str | None, seed: int) -> dict:
        run_create = {**task.run_create, "seed": seed}
        request = {
            "schema_version": "stage2.v1",
            "request_id": f"{method}-{task.task_id}-{seed}"[:120],
            "method": method,
            "input": run_create,
            "config_hash": cfg.config_hash(self.config, method, regime),
            "resource_caps": cfg.resource_caps(self.config, regime),
        }
        problems = errors(request, "MethodRequest")
        if problems:
            raise HarnessError(f"invalid MethodRequest: {problems[0]}")
        return request

    def commit_all(self, tasks: list[EvalTask], plan: list[dict], seeds: list[int]) -> list[dict]:
        log = self.out / "commitments.jsonl"
        if log.exists():
            raise HarnessError("commitments.jsonl exists: a sealed run is never overwritten")
        records = []
        regimes = self.config["regimes"]
        with log.open("w") as handle:
            for entry in plan:
                for task in tasks:
                    for seed in seeds:
                        record = self._run_one(task, entry, seed, regimes)
                        records.append(record)
                        handle.write(json.dumps(record, sort_keys=True) + "\n")
        self.commit_digest = hashlib.sha256(log.read_bytes()).hexdigest()
        return records

    def _run_one(self, task, entry, seed, regimes) -> dict:
        method, regime = entry["method"], entry["regime"]
        request = self.request_for(task, method, regime, seed)
        cancel = threading.Event()
        cutoff = (regimes[regime]["cutoff_ms"] if regime else self.config["safety_limit_ms"]) / 1000
        timer = threading.Timer(cutoff, cancel.set)
        timer.daemon = True
        timer.start()
        started = self.clock()
        try:
            result = self.port.run(request, cancel)
            problems = errors(result, "MethodResult")
            if problems:
                raise HarnessError(f"invalid MethodResult: {problems[0]}")
            if result["request_id"] != request["request_id"] or result["method"] != method:
                raise HarnessError("MethodResult does not answer its request")
            if result["config_hash"] != request["config_hash"]:
                raise HarnessError("MethodResult config_hash differs from the frozen method config")
            if self.mode == "live" and result["runtime_mode"] != "live":
                raise HarnessError("Fixture results are rejected in live mode")
            if self.mode == "fixture" and result["runtime_mode"] != "fixture":
                raise HarnessError("Fixture smoke runs must report runtime_mode=fixture")
            status = result["final_result"]["status"]
            selected, selected_hash = result["selected_source"], result["selected_source_hash"]
            if selected is not None and sha256_text(selected) != selected_hash:
                raise HarnessError("selected_source_hash does not match selected_source")
            usage = result["final_result"]["resource_usage"]
            pool = [
                {
                    "candidate_id": c["candidate_id"],
                    "origin": c["origin"],
                    "source": c["source"],
                    "source_hash": c["source_hash"],
                }
                for c in result["candidate_pool"]
            ]
        except HarnessError:
            raise
        except Exception as exc:  # noqa: BLE001 - infrastructure/method failures stay in the denominator
            status, selected, selected_hash, pool = "infrastructure_error", None, None, []
            usage = None
            result = {"runtime_mode": self.mode}
            error = f"{type(exc).__name__}: {exc}"[:200]
        else:
            error = None
        finally:
            timer.cancel()
        wall_ms = int((self.clock() - started) * 1000)
        if cancel.is_set() and status == "supported_patch":
            status, selected, selected_hash = "cancelled", None, None  # past the cutoff
        return {
            "task_id": task.task_id,
            "family_id": task.family_id,
            "kind": task.kind,
            "method": method,
            "regime": regime,
            "budget": entry["budget"],
            "seed": seed,
            "status": status,
            "selected_source": selected,
            "selected_source_hash": selected_hash,
            "pool": pool,
            "usage": usage,
            "wall_ms": wall_ms,
            "runtime_mode": result["runtime_mode"],
            "request_hash": value_hash(request["input"]),
            "config_hash": request["config_hash"],
            "visible_hash": visible_hash(task),
            "error": error,
        }

    # -- phase 2/3: score -------------------------------------------------------------------
    def score_all(self, records: list[dict], tasks: list[EvalTask]) -> list[dict]:
        log = self.out / "commitments.jsonl"
        if hashlib.sha256(log.read_bytes()).hexdigest() != self.commit_digest:
            raise HarnessError("Commitments changed before scoring")
        by_id = {t.task_id: t for t in tasks}
        scored = []
        for record in records:
            correct = None
            if record["selected_source"] is not None:
                correct = self.scorer.score(by_id[record["task_id"]], record["selected_source"])
            scored.append(
                {**record, "correct": correct, "category": categorize(record["status"], correct)}
            )
        # Secondary pool diagnostics only now that every final selection is committed.
        cache: dict[tuple[str, str], bool] = {}
        for record in scored:
            task = by_id[record["task_id"]]
            flags = {}
            for cand in record["pool"]:
                key = (task.task_id, cand["source_hash"])
                if key not in cache:
                    cache[key] = bool(self.scorer.score(task, cand["source"]))
                flags[cand["candidate_id"]] = {"origin": cand["origin"], "correct": cache[key]}
            record["pool_scores"] = flags
            record["pool_has_correct"] = any(f["correct"] for f in flags.values())
        out = self.out / "per_run.jsonl"
        out.write_text(
            "".join(
                json.dumps(
                    {k: v for k, v in r.items() if k not in ("selected_source",)}, sort_keys=True
                )
                + "\n"
                for r in scored
            )
        )
        return scored

    def run(
        self, tasks: list[EvalTask], plan: list[dict] | None = None, seeds: list[int] | None = None
    ) -> list[dict]:
        plan = plan if plan is not None else cfg.plan(self.config)
        seeds = seeds or self.config["seeds"]
        records = self.commit_all(tasks, plan, seeds)
        return self.score_all(records, tasks)
