"""Live BaselinePort with frozen method hashes, truthful physical roles and committed outputs."""

import copy
import json
from dataclasses import replace
from pathlib import Path
from threading import Event
from uuid import uuid4

from codejury.stage2_tools.evaluation.config import config_hash, plan, resource_caps

from ..candidates import CandidatePool
from ..contracts import checked, json_hash
from ..controller import FixedController, record
from ..controller.learned import LearnedController
from ..data import write_report
from ..intake import prepare
from ..ledger import Ledger, encode
from ..model_worker import NativeModelPort
from ..registry import Registry, local_path
from ..rollouts import run_result
from .controllers import (
    AuditAtEndController,
    GeneralController,
    NoGapController,
    NoSearchController,
    RepairBaseline,
    SampleBaseline,
)
from .prompted import PromptedController


class SameViewController(LearnedController):
    def initial_candidates(self):
        # This named ablation deliberately overrides the reconstruction channel view.
        # Physical ModelRequest/Response.role remains fixer_b, with its real control hash.
        self.pool.views = replace(
            self.pool.views,
            b=self.pool.views.a,
            view_config_hash=json_hash({"ablation": "B-same-view", "prompt": self.pool.views.a}),
        )
        record(
            self.ledger,
            self.run_id,
            "view_override",
            "same-view",
            {
                "method": "B-same-view",
                "physical_role": "fixer_b",
                "input_view": "targeted_repair",
                "prompt_hash": json_hash(self.pool.views.a),
            },
        )
        return super().initial_candidates()


def raw_commit(control, problem, tests, seed, cancel, caps):
    """B0 commits an unverified prediction. It never claims executed verification scope."""
    control.admit(problem, tests, cancel=cancel, seed=seed, limits=caps)
    pool = CandidatePool(
        control.ledger,
        control.run_id,
        control.model,
        control.identities,
        model_roles={"fixer_a": "raw", "fixer_b": "raw"},
    )
    original = pool.original()
    candidate = pool.generate(
        "fixer_a", pool.views.a, parent=original, seed=seed, cancel=cancel, max_attempts=1
    )
    status = "cancelled" if cancel.is_set() else "supported_patch" if candidate else "unresolved"
    snapshot = control.ledger.snapshot(control.run_id)
    snapshot.update(
        status=status,
        phase="finished",
        policy_mode="fixed",
        model_manifest_hash=control.manifest_hash,
        termination_reason="Unverified raw one-shot prediction committed; no tool/test claims.",
        decision=checked(
            {
                "schema_version": "stage2.v1",
                "selected_candidate_id": candidate["candidate_id"]
                if candidate and not cancel.is_set()
                else None,
                "verification_scope": [],
                "unresolved_requirements": [r["requirement_id"] for r in problem["requirements"]],
                "evidence_ids": [],
                "reason": "Raw prediction; no executed qualification",
                "suite_hash": None,
            },
            "Decision",
        ),
    )
    snapshot = checked(snapshot, "RunSnapshot")
    with control.ledger.connection() as db:
        db.execute(
            "INSERT INTO controller_records VALUES (?,?,?,?)",
            (control.run_id, "final", "final", encode(snapshot)),
        )
        db.execute(
            "UPDATE runs SET status=?,reason=? WHERE id=?",
            (status, snapshot["termination_reason"], control.run_id),
        )
        control.ledger._event(db, control.run_id, "run_finished", snapshot["termination_reason"])
    return snapshot


class BaselinePort:
    mode = "live"

    def __init__(self, config, model, tool, directory, *, variants=None):
        from codejury.stage2_tools.port import ToolPortImpl
        from codejury.stage2_tools.runner.docker import DockerSandbox

        if not (
            isinstance(model, NativeModelPort)
            and isinstance(tool, ToolPortImpl)
            and isinstance(tool.sandbox, DockerSandbox)
        ):
            raise ValueError("Live research factory requires actual native and isolated ports")
        self.config, self.base_registry, self.settings = config, model.registry, model.settings
        self.model, self.tool, self.directory = model, tool, Path(directory)
        self.variants = variants or {}
        self.allowed = {
            (entry["method"], config_hash(config, entry["method"], entry["regime"])): resource_caps(
                config, entry["regime"]
            )
            for entry in plan(config)
        }
        # Fail before any assessment file is opened, rather than fabricating method results.
        if (
            not self.base_registry.readiness()["ready"]
            or self.base_registry.record["adapters"]
            .get("general", {})
            .get("card", {})
            .get("status")
            != "completed"
        ):
            raise ValueError("Freeze four completed roles and the real general comparator first")
        if set(self.variants) != {"B-unweighted", "B-same-view"}:
            raise ValueError("Both measured, frozen B control registries are required")
        for registry in self.variants.values():
            if registry.base["base_revision_hash"] != self.base_registry.base["base_revision_hash"]:
                raise ValueError("Control base differs from the shared frozen base")
        self.directory.mkdir(parents=True, exist_ok=True)

    def preflight(self):
        self.tool.sandbox.ready()
        self.model.start(Event())

    def close(self):
        self.model.close()

    def _model(self, registry):
        if self.model.closed or self.model.registry.manifest_hash != registry.manifest_hash:
            self.model.close()
            self.model = NativeModelPort(registry, self.settings)
        return self.model

    def run(self, request, cancel):
        request = checked(request, "MethodRequest")
        key = request["method"], request["config_hash"]
        if key not in self.allowed or request["resource_caps"] != self.allowed[key]:
            raise ValueError("Method hash/caps do not match the registered frozen experiment")
        method = request["method"]
        registry = self.variants.get(method, self.base_registry)
        model = self._model(registry)
        from codejury.stage2_tools.port import ToolPortImpl

        tool = ToolPortImpl(self.tool.sandbox, contracts=self.tool.contracts)
        problem, tests = prepare(request["input"])
        ledger = Ledger(self.directory / ("method-" + uuid4().hex))
        identities = {r: registry.identity(r) for r in ["raw", *registry.record["adapters"]]}
        options = {}
        cls = {
            "B0": FixedController,
            "B1": RepairBaseline,
            "B2": SampleBaseline,
            "B3": GeneralController,
            "B4": PromptedController,
            "CJ": LearnedController,
            "B-unweighted": LearnedController,
            "B-same-view": SameViewController,
            "Generic-Critic": LearnedController,
            "No-search": NoSearchController,
            "No-gap-feedback": NoGapController,
            "Audit-at-end": AuditAtEndController,
            "Fixed-Judge": FixedController,
        }[method]
        if method == "B4":
            options = {"model_roles": {"fixer_a": "raw", "fixer_b": "raw"}, "critic_role": "raw"}
        elif method == "B3":
            options = {
                "model_roles": {"fixer_a": "general", "fixer_b": "general"},
                "critic_role": "general",
            }
        elif method == "Generic-Critic":
            options = {"critic_role": "raw"}
        control = cls(
            ledger,
            model,
            tool,
            identities,
            manifest_hash=registry.manifest_hash,
            runtime_hash=tool.sandbox.runtime_hash,
            mode="live",
            **options,
        )
        record_profile = {
            "method": method,
            "method_config_hash": request["config_hash"],
            "caps": request["resource_caps"],
            "registry_hash": registry.manifest_hash,
            "baseline_source_hash": json_hash(
                {p.name: p.read_text() for p in sorted(Path(__file__).parent.glob("*.py"))}
            ),
        }
        write_report(ledger.directory / "method-freeze.json", record_profile)
        if method == "B0":
            snapshot = raw_commit(
                control, problem, tests, request["input"]["seed"], cancel, request["resource_caps"]
            )
        else:
            snapshot = control.run(
                problem,
                tests,
                cancel=cancel,
                seed=request["input"]["seed"],
                limits=request["resource_caps"],
            )
        selected = snapshot["decision"]["selected_candidate_id"]
        candidate = next((c for c in snapshot["candidates"] if c["candidate_id"] == selected), None)
        result = checked(
            {
                "schema_version": "stage2.v1",
                "request_id": request["request_id"],
                "method": method,
                "runtime_mode": "live",
                "final_result": run_result(snapshot),
                "selected_source": candidate["source"] if candidate else None,
                "selected_source_hash": candidate["source_hash"] if candidate else None,
                "candidate_pool": snapshot["candidates"],
                "config_hash": request["config_hash"],
            },
            "MethodResult",
        )
        write_report(ledger.directory / "commitment.json", result)
        return result


def control_registries(main, paths, out):
    """Actual trained control bytes are combined with the unchanged released other roles."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    result = {}
    for method, cfg in paths.items():
        training = json.loads(local_path(cfg["training_report"]).read_text())
        if (
            training["phase"] != "full"
            or training["completed_steps"] < cfg["step"]
            or not training["updates_verified"]
            or not training["reload_verified"]
            or training["role"] != "fixer_b"
        ):
            raise ValueError("A real full native B control/save/reload is required")
        checkpoint = next(
            c["registry_path"] for c in training["candidates"] if c["step"] == cfg["step"]
        )
        source = Registry(Path(checkpoint))
        if source.base["base_revision_hash"] != main.base["base_revision_hash"]:
            raise ValueError("B control does not share the frozen base")
        record_value = copy.deepcopy(main.record)
        record_value["adapters"]["fixer_b"] = source.record["adapters"]["fixer_b"]
        target = out / (method + ".json")
        write_report(target, record_value)
        result[method] = Registry(target)
    return result
