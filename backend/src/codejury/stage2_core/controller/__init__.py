"""fixed-v1 controller. Runtime inputs contain no reference source or offline assessment."""

import json
from pathlib import Path
from uuid import uuid4

from jsonschema import ValidationError

from ..budgets import CAPS, BudgetExceeded
from ..candidates import (
    CandidatePool,
    hard_suite,
    incumbent,
    parse_draft,
    qualification,
    validated_tests,
)
from ..contracts import (
    CheckedModelPort,
    CheckedToolPort,
    checked,
    json_hash,
    source_hash,
)
from ..intake import validate_source
from ..ledger import encode
from ..views import revision
from .bootstrap import critic_input_prompt, reviewed_proposal

# Freeze loaded implementation bytes once. Later disk edits cannot relabel an already
# imported controller. Tool implementation bytes are captured alongside sandbox identity.
CONTROLLER_SOURCE_HASH = json_hash(
    {p.name: source_hash(p.read_text()) for p in sorted(Path(__file__).parent.glob("*.py"))}
)
VIEWS_SOURCE_HASH = source_hash(
    (Path(__file__).resolve().parents[1] / "views/__init__.py").read_text()
)
EXECUTION_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_FILES = (
    "budgets/__init__.py",
    "candidates/__init__.py",
    "contracts/__init__.py",
    "intake/__init__.py",
    "ledger/__init__.py",
    "leases/__init__.py",
    "model_worker/__init__.py",
    "model_worker/engine.py",
    "model_worker/native.py",
    "registry/__init__.py",
)
EXECUTION_SOURCE_HASH = json_hash(
    {name: source_hash((EXECUTION_ROOT / name).read_text()) for name in EXECUTION_FILES}
)
TOOLS_ROOT = Path(__file__).resolve().parents[2] / "stage2_tools"
RUNTIME_TOOL_PARTS = {
    "codec",
    "factory.py",
    "domains",
    "oracles",
    "runner",
    "search",
    "auditor",
    "investigation",
    "port",
}
TOOLS_SOURCE_HASH = json_hash(
    {
        path.relative_to(TOOLS_ROOT).as_posix(): source_hash(path.read_text())
        for path in sorted(TOOLS_ROOT.rglob("*.py"))
        if path.relative_to(TOOLS_ROOT).parts[0] in RUNTIME_TOOL_PARTS
    }
)

POLICY = {
    "version": "fixed-v1",
    "max_actions": 8,
    "audit_mutants": 4,
    "search_candidates": 8,
    "investigation_inputs": 8,
    "final_reserve": 128,
    "critic_format": "critic-shape-v3",
    "priority": [
        "new_counterexample",
        "local_search",
        "one_resample",
        "disagreement",
        "audit",
        "challenge",
        "select",
        "abstain",
    ],
}
DRAFT_FIELDS = (
    "schema_version",
    "candidate_id",
    "problem_id",
    "parent_id",
    "origin",
    "generation_view",
    "source",
    "source_hash",
    "diagnosis",
    "assumptions",
    "requirement_ids",
    "model_config_hash",
    "edits",
)


def ident(prefix):
    return prefix + "-" + uuid4().hex


def draft(candidate):
    return checked({k: candidate[k] for k in DRAFT_FIELDS}, "CandidateDraft")


def challenge_key(snapshot, suite, targets):
    # Observations can expose disagreement without changing the authoritative hard suite.
    return suite, tuple(targets), json_hash(snapshot["tests"])


def record(ledger, run_id, kind, identifier, body):
    with ledger.connection() as db:
        ledger._run(db, run_id, active=True)
        db.execute(
            "INSERT INTO controller_records VALUES (?,?,?,?)",
            (run_id, kind, identifier, encode(body)),
        )


def records(ledger, run_id, kind):
    with ledger.connection() as db:
        return [
            json.loads(r[0])
            for r in db.execute(
                "SELECT body FROM controller_records WHERE run_id=? AND kind=? ORDER BY rowid",
                (run_id, kind),
            )
        ]


class TraceArchivePort:
    """Preserve the tools' exact codec bytes before the ledger validates trace references."""

    def __init__(self, port, ledger):
        self.port, self.ledger = port, ledger

    def call(self, request, cancel):
        result = CheckedToolPort(self.port).call(request, cancel)
        evaluator = getattr(self.port, "last_evaluator", None)
        traces = getattr(evaluator, "traces", {})
        from codejury.stage2_tools.codec import canonical

        for execution in result["executions"]:
            digest = execution["trace_ref"]
            if digest is not None:
                if digest in traces:
                    actual = self.ledger.put_object(canonical(traces[digest]).encode())
                    if actual != digest:
                        raise ValueError("Tool trace hash mismatch")
                self.ledger.read_object(digest)
        return result


class Stopped(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


class FixedController:
    policy_mode = "fixed"
    gap_feedback = True

    def __init__(
        self,
        ledger,
        model_port,
        tool_port,
        identities,
        *,
        manifest_hash,
        runtime_hash,
        mode="fixture",
        critic_bootstrap="raw",
        model_roles=None,
        critic_role=None,
    ):
        self.ledger, self.model = ledger, model_port
        self.tool = TraceArchivePort(tool_port, ledger)
        self.identities, self.manifest_hash = identities, manifest_hash
        self.runtime_hash, self.mode = runtime_hash, mode
        if critic_bootstrap not in {"raw", "reviewed"}:
            raise ValueError("Unknown Critic bootstrap mode")
        self.critic_bootstrap = critic_bootstrap
        self.model_roles = dict(model_roles) if model_roles is not None else None
        self.critic_role = critic_role
        if critic_role not in {None, "critic", "raw", "general"}:
            raise ValueError("Unknown Critic model binding")
        if mode == "live":
            from codejury.stage2_tools.port import ToolPortImpl
            from codejury.stage2_tools.runner.docker import DockerSandbox

            from ..model_worker import NativeModelPort

            if not (
                isinstance(model_port, NativeModelPort)
                and isinstance(tool_port, ToolPortImpl)
                and isinstance(tool_port.sandbox, DockerSandbox)
            ):
                raise ValueError("Live collection requires actual native MLX and Docker ports")
        elif mode != "fixture":
            raise ValueError("Explicit collection mode required")

    def check_running(self):
        if self.cancel.is_set():
            raise Stopped("cancelled", "Collection cancelled")
        if not self.account.remaining(final=True)["elapsed_ms"]:
            raise Stopped("unresolved", "Episode wall budget exhausted")
        with self.ledger.connection() as db:
            rows = db.execute(
                "SELECT status,response FROM requests WHERE run_id=?", (self.run_id,)
            ).fetchall()
        for row in rows:
            if row["status"] != "settled":
                raise Stopped("infrastructure_error", "Unsettled or refused transport")
            result = json.loads(row["response"])
            status = result["status"]
            if status != "ok":
                terminal = (
                    "cancelled"
                    if status == "cancelled"
                    else "unresolved"
                    if status in {"budget_exhausted", "invalid_input"}
                    else "infrastructure_error"
                )
                raise Stopped(terminal, "Transport ended with " + status)

    def tool_call(self, parameters):
        self.check_running()
        request_id = ident("tool")
        request = checked(
            {
                "schema_version": "stage2.v1",
                "request_id": request_id,
                "id_prefix": request_id,
                "run_id": self.run_id,
                "problem": self.problem,
                "parameters": parameters,
                "remaining_budget": self.account.remaining(),
            },
            "ToolRequest",
        )
        self.ledger.dispatch_tool(request)
        result = self.tool.call(request, self.cancel)
        self.ledger.settle_tool(result)
        self.check_running()
        return result

    def evaluate_all(self):
        self.check_running()
        snapshot = self.ledger.snapshot(self.run_id)
        tests, _ = hard_suite(self.problem, snapshot["tests"])
        for candidate in snapshot["candidates"]:
            if not validate_source(
                self.ledger, self.run_id, self.tool, candidate["source"], tests, self.cancel
            ):
                self.check_running()
                continue
            current = {
                e["test_id"]
                for e in snapshot["executions"]
                if e["candidate_id"] == candidate["candidate_id"]
                and e["runtime_hash"] == self.runtime_hash
            }
            missing = [t for t in tests if t["test_id"] not in current]
            if missing:
                self.tool_call(
                    {
                        "operation": "evaluate",
                        "candidates": [draft(candidate)],
                        "tests": missing,
                        "stop_on_first_hard_failure": False,
                    }
                )
        self.check_running()

    def state(self):
        snapshot = self.ledger.snapshot(self.run_id)
        projected = qualification(self.ledger, self.run_id, runtime_hash=self.runtime_hash)
        candidates = projected["candidates"]
        hard, _ = hard_suite(self.problem, snapshot["tests"])
        hard_ids = {t["test_id"] for t in hard}
        rows = [
            e
            for e in snapshot["executions"]
            if e["test_id"] in hard_ids and e["runtime_hash"] == self.runtime_hash
        ]
        visible_ids = {
            t["test_id"]
            for t in snapshot["tests"]
            if t["domain_valid"] and t["oracle_status"] != "rejected"
        }
        behaviour_rows = [
            e
            for e in snapshot["executions"]
            if e["test_id"] in visible_ids and e["runtime_hash"] == self.runtime_hash
        ]
        summaries, groups = [], {}
        for candidate in candidates:
            own = [e for e in rows if e["candidate_id"] == candidate["candidate_id"]]
            summaries.append(
                {
                    k: candidate[k]
                    for k in ("candidate_id", "origin", "eligibility", "source_hash", "assumptions")
                }
                | {
                    "hard_passes": len({e["test_id"] for e in own if e["outcome"] == "pass"}),
                    "hard_failures": len({e["test_id"] for e in own if e["outcome"] != "pass"}),
                }
            )
            if candidate["eligibility"] == "eligible":
                by_test = {
                    e["test_id"]: [e["test_id"], e["actual_output"], e["outcome"]]
                    for e in behaviour_rows
                    if e["candidate_id"] == candidate["candidate_id"]
                }
                key = json_hash(sorted(by_test.values(), key=lambda v: v[0]))
                groups.setdefault(key, []).append(candidate["candidate_id"])
        selected = incumbent(projected, self.problem["source"])
        state = {
            "schema_version": "stage2.v1",
            "state_id": ident("state"),
            "problem_id": self.problem["problem_id"],
            "candidate_summaries": summaries,
            "behaviour_groups": list(groups.values()),
            "authoritative_counterexample_ids": [
                e["execution_id"] for e in rows if e["outcome"] != "pass"
            ],
            "audit_gap_ids": [
                g["gap_id"]
                for g in snapshot["audit_gaps"]
                if g["suite_hash"] == projected["suite_hash"]
            ],
            "unresolved_requirement_ids": [
                r["requirement_id"]
                for r in self.problem["requirements"]
                if r["approval_status"] != "approved"
            ],
            "previous_action_ids": [a["action_id"] for a in self.actions],
            "remaining_budget": self.account.remaining(),
            "available_actions": [],
            "incumbent_candidate_id": selected,
            "suite_hash": projected["suite_hash"],
        }
        state["available_actions"] = self.options(state, snapshot, candidates)
        # Menu identifiers are local to this exact state. The Judge must also return
        # the unique state_id, so a choice from an older state remains invalid.
        for index, option in enumerate(state["available_actions"], 1):
            option["option_id"] = f"option-{index:02d}"
        return checked(state, "StateSnapshot"), candidates

    def option(self, kind, targets, params, reason, state):
        remaining = state["remaining_budget"]
        cost = {**dict.fromkeys(CAPS, 0), "elapsed_ms": remaining["elapsed_ms"]}
        if kind in {"generate", "revise", "criticize"}:
            cost.update(
                input_tokens=remaining["input_tokens"],
                output_tokens=min(512 if kind == "criticize" else 2048, remaining["output_tokens"]),
            )
        if kind in {"generate", "revise"}:
            cost["learned_candidates"] = min(2, remaining["learned_candidates"])
        if kind in {"search", "audit", "criticize"}:
            cost["function_executions"] = remaining["function_executions"]
        if kind == "search":
            cost["search_candidates"] = min(
                POLICY["search_candidates"], remaining["search_candidates"]
            )
        if kind == "audit":
            cost["audit_mutants"] = params["max_mutants"]
        action = checked(
            {
                "schema_version": "stage2.v1",
                "action_id": ident("action"),
                "kind": kind,
                "target_ids": targets,
                "requirement_ids": [
                    r["requirement_id"]
                    for r in self.problem["requirements"]
                    if r["approval_status"] == "approved"
                ],
                "evidence_ids": state["authoritative_counterexample_ids"] + state["audit_gap_ids"],
                "parameters": {"kind": kind, **params},
                "requested_budget": cost,
                "rationale": reason,
            },
            "InvestigationAction",
        )
        return checked(
            {
                "schema_version": "stage2.v1",
                "option_id": ident("option"),
                "action": action,
                "prerequisite_summary": reason,
            },
            "ActionOption",
        )

    def options(self, state, snapshot, candidates):
        options = []

        def add(kind, targets, params, reason):
            options.append(self.option(kind, targets, params, reason, state))

        budget, suite = state["remaining_budget"], state["suite_hash"]
        eligible = [c for c in candidates if c["eligibility"] == "eligible"]
        terminal_slot = len(self.actions) >= POLICY["max_actions"] - 1
        unresolved = bool(state["unresolved_requirement_ids"])
        if not terminal_slot and not unresolved and budget["elapsed_ms"]:
            # New authoritative failures revise only their responsible learned parent.
            supplied = set(self.problem["supplied_test_ids"])
            for c in candidates:
                role = c["origin"].removesuffix("_revision")
                failed_new = any(
                    e["candidate_id"] == c["candidate_id"]
                    and e["test_id"] not in supplied
                    and e["outcome"] != "pass"
                    and e["execution_id"] in state["authoritative_counterexample_ids"]
                    for e in snapshot["executions"]
                )
                if (
                    failed_new
                    and role in {"fixer_a", "fixer_b"}
                    and c["candidate_id"] not in self.revised
                    and budget["learned_candidates"] >= 1
                    and budget["output_tokens"] >= 1024
                ):
                    add("revise", [c["candidate_id"]], {"role": role}, "New hard counterexample")
            if not eligible:
                for c in candidates:
                    supported = validated_tests(
                        self.ledger,
                        self.run_id,
                        c["source"],
                        self.problem["signature"],
                        snapshot["tests"],
                    )
                    if (
                        supported
                        and c["origin"] != "ast_search"
                        and c["candidate_id"] not in self.searched
                        and budget["search_candidates"]
                        and budget["function_executions"]
                    ):
                        add(
                            "search",
                            [c["candidate_id"]],
                            {
                                "sites": [],
                                "families": [
                                    "comparison",
                                    "boundary_constant",
                                    "boolean_negation",
                                    "arithmetic",
                                    "variable_reference",
                                ],
                                "depth": 1,
                            },
                            "Local AST sites after failed hard checks",
                        )
                        break
                if (
                    not self.resampled
                    and budget["learned_candidates"]
                    and budget["output_tokens"] >= 1024
                ):
                    add(
                        "generate",
                        [self.original["candidate_id"]],
                        {"role": "fixer_b", "count": 1},
                        "One independent resample after local search",
                    )
            else:
                targets = [c["candidate_id"] for c in eligible][:8]
                disagreement = len(state["behaviour_groups"]) > 1
                key = challenge_key(snapshot, suite, targets)
                if disagreement and key not in self.challenged and budget["output_tokens"] >= 512:
                    add(
                        "criticize",
                        targets,
                        {"mode": "discriminate"},
                        "Consequential eligible disagreement",
                    )
                for c in eligible:
                    if (
                        (c["source_hash"], suite) not in self.audited
                        and budget["audit_mutants"]
                        and budget["function_executions"]
                    ):
                        add(
                            "audit",
                            [c["candidate_id"]],
                            {"max_mutants": min(POLICY["audit_mutants"], budget["audit_mutants"])},
                            "Audit each eligible source on the current suite",
                        )
                if (
                    not disagreement
                    and key not in self.challenged
                    and budget["output_tokens"] >= 512
                    and budget["function_executions"]
                ):
                    add(
                        "criticize",
                        targets,
                        {"mode": "audit_gap" if state["audit_gap_ids"] else "challenge_agreement"},
                        "Challenge shared agreement; survivors are test gaps",
                    )
        ready = (
            eligible
            and not unresolved
            and len(state["behaviour_groups"]) == 1
            and all((c["source_hash"], suite) in self.audited for c in eligible)
            and challenge_key(snapshot, suite, [c["candidate_id"] for c in eligible[:8]])
            in self.challenged
        )
        if ready:
            add(
                "select",
                [state["incumbent_candidate_id"]],
                {"candidate_id": state["incumbent_candidate_id"]},
                "Current hard suite and required challenges completed",
            )
        add(
            "abstain",
            [],
            {"reason": "Ambiguity, no qualified candidate, or required checks cannot fit"},
            "Safe terminal option",
        )
        return options[:20]

    def choose(self, state):
        return state["available_actions"][0]

    def criticize(self, action, snapshot):
        targets = [c for c in snapshot["candidates"] if c["candidate_id"] in action["target_ids"]]
        if (
            self.critic_role is None
            and "critic" not in self.identities
            and self.critic_bootstrap == "reviewed"
        ):
            proposal = reviewed_proposal(
                self.problem, action["target_ids"], action["parameters"]["mode"], self.seed
            )
            identifier = ident("reviewed-bootstrap")
            record(
                self.ledger,
                self.run_id,
                "critic_mode",
                identifier,
                {"request_id": identifier, "mode": "reviewed_bootstrap", "proposal": proposal},
            )
            return self.investigate_proposal(proposal, action, snapshot, targets)
        prompt = critic_input_prompt(
            self.problem,
            snapshot["tests"],
            targets,
            [e for e in snapshot["executions"] if e["candidate_id"] in action["target_ids"]],
            action["parameters"]["mode"],
            self.seed,
            gaps=snapshot["audit_gaps"] if self.gap_feedback else (),
            trace_reader=self.ledger.read_object,
        )
        role = self.critic_role or ("critic" if "critic" in self.identities else "raw")
        request = checked(
            {
                "schema_version": "stage2.v1",
                "request_id": ident("critic"),
                "run_id": self.run_id,
                "role": role,
                "purpose": "test_proposal" if role == "critic" else "baseline",
                "prompt": prompt,
                "seed": self.seed,
                "max_new_tokens": 512,
                "remaining_budget": self.account.remaining(),
            },
            "ModelRequest",
        )
        record(
            self.ledger,
            self.run_id,
            "critic_mode",
            request["request_id"],
            {
                "request_id": request["request_id"],
                "mode": "trained"
                if role == "critic"
                else "general_baseline"
                if role == "general"
                else "raw_bootstrap",
                "model_role": role,
            },
        )
        self.ledger.dispatch_model(request)
        response = CheckedModelPort(self.model).generate(request, self.cancel)
        self.ledger.settle_model(response)
        self.check_running()
        if any(
            response[k] != self.identities[role][k]
            for k in ("adapter_hash", "model_config_hash", "model_revision_hash")
        ):
            raise ValueError("Critic model provenance changed")
        try:
            proposal = parse_draft(response["text"], "CriticDraft")
            if (
                proposal["mode"] != action["parameters"]["mode"]
                or set(proposal["target_candidate_ids"]) != set(action["target_ids"])
                or not set(proposal["requirement_ids"]) <= set(action["requirement_ids"])
                or (proposal["generator_spec"] is None) == (proposal["concrete_inputs"] is None)
            ):
                raise ValueError("Critic proposal scope mismatch")
        except (ValueError, ValidationError, RecursionError):
            self.ledger.append_event(
                self.run_id,
                "action_refused",
                "Malformed or out-of-scope Critic draft",
                action_id=action["action_id"],
            )
            # A refused challenge cannot authorize selection.
            return False
        return self.investigate_proposal(proposal, action, snapshot, targets)

    def investigate_proposal(self, proposal, action, snapshot, targets):
        proposal = checked(proposal, "CriticDraft")
        if (
            proposal["mode"] != action["parameters"]["mode"]
            or set(proposal["target_candidate_ids"]) != set(action["target_ids"])
            or not set(proposal["requirement_ids"]) <= set(action["requirement_ids"])
        ):
            raise ValueError("Investigation proposal is outside the chosen action")
        proposal = checked(
            {
                "schema_version": "stage2.v1",
                "proposal_id": ident("proposal"),
                **{k: v for k, v in proposal.items() if k != "mode"},
            },
            "TestProposal",
        )
        self.tool_call(
            {
                "operation": "investigate",
                "proposal": proposal,
                "candidates": [draft(c) for c in targets],
                "existing_tests": snapshot["tests"],
                "max_inputs": POLICY["investigation_inputs"],
            }
        )
        return True

    def execute(self, state, option):
        self.check_running()
        if option not in state["available_actions"]:
            raise ValueError("Action was not offered in this frozen state")
        current, _ = self.state()
        if (
            current["suite_hash"] != state["suite_hash"]
            or current["candidate_summaries"] != state["candidate_summaries"]
            or current["previous_action_ids"] != state["previous_action_ids"]
            or current["audit_gap_ids"] != state["audit_gap_ids"]
            or not any(
                all(
                    fresh["action"][k] == option["action"][k]
                    for k in ("kind", "target_ids", "parameters")
                )
                for fresh in current["available_actions"]
            )
        ):
            raise ValueError("Stale action state")
        action = option["action"]
        self.actions.append(action)
        record(self.ledger, self.run_id, "action", action["action_id"], action)
        self.ledger.append_event(
            self.run_id, "action_selected", action["rationale"], action_id=action["action_id"]
        )
        snapshot = self.ledger.snapshot(self.run_id)
        by_id = {c["candidate_id"]: c for c in snapshot["candidates"]}
        kind = action["kind"]
        if kind == "select":
            # Release the held reserve only for a complete final sandbox replay.
            self.account.reserve_final(0)
            self.tool_call(
                {
                    "operation": "evaluate",
                    "candidates": [draft(by_id[action["parameters"]["candidate_id"]])],
                    "tests": hard_suite(self.problem, snapshot["tests"])[0],
                    "stop_on_first_hard_failure": False,
                }
            )
            return self.finish(
                "supported_patch", action["rationale"], state, action["parameters"]["candidate_id"]
            )
        if kind == "abstain":
            return self.finish("unresolved", action["parameters"]["reason"], state)
        if kind == "search":
            parent = by_id[action["target_ids"][0]]
            self.searched.add(parent["candidate_id"])
            self.tool_call(
                {
                    "operation": "search",
                    "parents": [draft(parent)],
                    "tests": snapshot["tests"],
                    **{k: v for k, v in action["parameters"].items() if k != "kind"},
                    "candidate_limit": action["requested_budget"]["search_candidates"],
                }
            )
        elif kind == "audit":
            parent = by_id[action["target_ids"][0]]
            self.tool_call(
                {
                    "operation": "audit",
                    "candidate": draft(parent),
                    "tests": snapshot["tests"],
                    "max_mutants": action["parameters"]["max_mutants"],
                    "suite_hash": state["suite_hash"],
                }
            )
            self.audited.add((parent["source_hash"], state["suite_hash"]))
        elif kind == "criticize":
            if not self.criticize(action, snapshot):
                raise Stopped(
                    "unresolved", "Critic challenge refused; selection prerequisites unmet"
                )
            self.challenged.add(challenge_key(snapshot, state["suite_hash"], action["target_ids"]))
        elif kind in {"generate", "revise"}:
            role = action["parameters"]["role"]
            parent = by_id[action["target_ids"][0]]
            if kind == "revise":
                self.revised.add(parent["candidate_id"])
                prompt = revision(
                    role,
                    self.problem,
                    snapshot["tests"],
                    parent,
                    [
                        e
                        for e in snapshot["executions"]
                        if e["candidate_id"] == parent["candidate_id"]
                    ],
                    trace_reader=self.ledger.read_object,
                )
            else:
                self.resampled = True
                prompt = self.pool.views.a if role == "fixer_a" else self.pool.views.b
            self.pool.generate(
                role,
                prompt,
                parent=parent,
                seed=self.seed + 1,
                cancel=self.cancel,
                revise=kind == "revise",
            )
        self.evaluate_all()
        record(
            self.ledger,
            self.run_id,
            "outcome",
            action["action_id"],
            {
                "action_id": action["action_id"],
                "status": "completed",
                "resource_usage": self.account.usage(),
                "suite_hash": self.state()[0]["suite_hash"],
            },
        )
        return None

    def finish(self, status, reason, state=None, selected=None):
        snapshot = self.ledger.snapshot(self.run_id)
        projected = qualification(self.ledger, self.run_id, runtime_hash=self.runtime_hash)
        if selected is not None:
            self.check_running()
            if (
                state is None
                or state["suite_hash"] != projected["suite_hash"]
                or not any(
                    c["candidate_id"] == selected and c["eligibility"] == "eligible"
                    for c in projected["candidates"]
                )
            ):
                raise ValueError("Cannot select stale or ineligible source")
            fresh, _ = self.state()
            if not any(
                o["action"]["kind"] == "select"
                and o["action"]["parameters"]["candidate_id"] == selected
                for o in fresh["available_actions"]
            ):
                raise ValueError("Selection prerequisites no longer hold")
        if self.actions and not any(
            r["action_id"] == self.actions[-1]["action_id"]
            for r in records(self.ledger, self.run_id, "outcome")
        ):
            record(
                self.ledger,
                self.run_id,
                "outcome",
                self.actions[-1]["action_id"],
                {
                    "action_id": self.actions[-1]["action_id"],
                    "status": status,
                    "reason": reason,
                    "resource_usage": self.account.usage(),
                    "suite_hash": projected["suite_hash"],
                },
            )
        if status in {"cancelled", "infrastructure_error"}:
            projected["candidates"] = [
                {**c, "eligibility": "pending", "verification_suite_hash": None}
                if c["eligibility"] == "eligible"
                else c
                for c in projected["candidates"]
            ]
        snapshot.update(
            policy_mode=self.policy_mode,
            status=status,
            phase="finished",
            candidates=projected["candidates"],
            actions=self.actions,
            model_manifest_hash=self.manifest_hash,
            suite_hash=projected["suite_hash"],
            termination_reason=reason,
            decision=checked(
                {
                    "schema_version": "stage2.v1",
                    "selected_candidate_id": selected,
                    "verification_scope": [
                        t["test_id"]
                        for t in snapshot["tests"]
                        if t["oracle_status"] == "authoritative"
                    ]
                    if selected
                    else [],
                    "unresolved_requirements": []
                    if selected
                    else [r["requirement_id"] for r in self.problem["requirements"]],
                    "evidence_ids": [
                        e["execution_id"]
                        for e in snapshot["executions"]
                        if e["candidate_id"] == selected
                    ],
                    "reason": reason,
                    "suite_hash": projected["suite_hash"],
                },
                "Decision",
            ),
        )
        snapshot = checked(snapshot, "RunSnapshot")
        with self.ledger.connection() as db:
            self.ledger._run(db, self.run_id, active=True)
            db.execute(
                "INSERT INTO controller_records VALUES (?,?,?,?)",
                (self.run_id, "final", "final", encode(snapshot)),
            )
            self.ledger._event(db, self.run_id, "run_finished", reason)
            db.execute(
                "UPDATE runs SET status=?,reason=? WHERE id=?", (status, reason, self.run_id)
            )
            db.execute(
                "UPDATE checkpoints SET usage=? WHERE run_id=?",
                (encode(self.account.usage()), self.run_id),
            )
        return snapshot

    def admit(self, problem, tests, *, cancel, seed=17, provenance=None, limits=None):
        self.problem = checked(problem, "Problem")
        self.run_id, self.cancel, self.seed = ident("run"), cancel, seed
        self.actions, self.audited, self.challenged = [], set(), set()
        self.searched, self.revised, self.resampled = set(), set(), False
        profile = {
            "policy": POLICY,
            "caps": limits if limits is not None else CAPS,
            "runtime_hash": self.runtime_hash,
            "model_manifest_hash": self.manifest_hash,
            "controller_source_hash": CONTROLLER_SOURCE_HASH,
            "views_source_hash": VIEWS_SOURCE_HASH,
            "execution_source_hash": EXECUTION_SOURCE_HASH,
            "critic_bootstrap": self.critic_bootstrap,
            "repair_model_bindings": self.model_roles,
            "critic_model_binding": self.critic_role,
            "gap_feedback": self.gap_feedback,
            "policy_mode": self.policy_mode,
            "tools_source_hash": TOOLS_SOURCE_HASH,
        }
        self.ledger.create_run(
            self.run_id,
            self.problem,
            mode=self.mode,
            profile=profile,
            model_configs=[i["model_config_hash"] for i in self.identities.values()],
            limits=limits,
            final_executions=POLICY["final_reserve"],
        )
        self.account = self.ledger.accounts[self.run_id]
        record(
            self.ledger,
            self.run_id,
            "metadata",
            "metadata",
            {
                "policy": POLICY,
                "profile": profile,
                "model_manifest_hash": self.manifest_hash,
                "model_identities": self.identities,
                "runtime_hash": self.runtime_hash,
                "provenance": provenance,
                "mode": self.mode,
                "seed": seed,
            },
        )
        for test in tests:
            self.ledger.add_test(self.run_id, test)
        return self.run_id

    def run(self, problem, tests, *, cancel, seed=17, provenance=None, limits=None, admitted=False):
        if not admitted:
            self.admit(
                problem, tests, cancel=cancel, seed=seed, provenance=provenance, limits=limits
            )
        else:
            snapshot = self.ledger.snapshot(self.run_id)
            if (
                self.problem != problem
                or snapshot["problem"] != problem
                or snapshot["tests"] != tests
                or self.cancel is not cancel
                or self.seed != seed
                or snapshot["status"] not in {"running", "queued"}
            ):
                raise ValueError("Admitted run identity or inputs changed before dispatch")
            with self.ledger.connection() as db:
                db.execute("UPDATE runs SET status='running' WHERE id=?", (self.run_id,))
        try:
            self.check_running()
            from codejury.stage2_tools.oracles import OracleError
            from codejury.stage2_tools.oracles.gate import check_intake

            try:
                check_intake(
                    {
                        **self.problem,
                        "supplied_tests": [
                            {
                                "test_id": t["test_id"],
                                "inputs": t["inputs"],
                                "expected": t["oracle_spec"]["expected"],
                                "requirement_ids": t["requirement_ids"],
                            }
                            for t in tests
                        ],
                    }
                )
            except (OracleError, KeyError) as exc:
                raise Stopped("invalid_input", "Supplied tests or contract conflict") from exc
            if not validate_source(
                self.ledger, self.run_id, self.tool, self.problem["source"], tests, cancel
            ):
                self.check_running()
                raise Stopped("invalid_input", "Semantic intake refused")
            self.pool = CandidatePool(
                self.ledger, self.run_id, self.model, self.identities, model_roles=self.model_roles
            )
            self.original = self.pool.original()
            self.evaluate_all()  # reproduce before independent generation
            self.initial_candidates()
            self.evaluate_all()
            while len(self.actions) < POLICY["max_actions"]:
                self.check_running()
                state, _ = self.state()
                self.freeze_episode(state)
                result = self.execute(state, self.choose(state))
                if result is not None:
                    return result
            raise Stopped("unresolved", "Fixed action limit reached")
        except Stopped as exc:
            return self.finish(exc.status, exc.reason)
        except (BudgetExceeded, InterruptedError) as exc:
            return self.finish("cancelled" if cancel.is_set() else "unresolved", str(exc))
        except Exception as exc:
            self.finish("infrastructure_error", type(exc).__name__ + ": controller failed closed")
            raise

    def initial_candidates(self):
        return self.pool.initial_pair(seed=self.seed, cancel=self.cancel, original=self.original)

    def freeze_episode(self, state):
        episode = self.episode(state)
        with self.ledger.connection() as db:
            request_ids = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM requests WHERE run_id=? ORDER BY rowid", (self.run_id,)
                )
            ]
            event_id = db.execute(
                "SELECT MAX(seq) FROM events WHERE run_id=?", (self.run_id,)
            ).fetchone()[0]
        record(self.ledger, self.run_id, "state", state["state_id"], state)
        record(self.ledger, self.run_id, "episode", state["state_id"], episode)
        record(
            self.ledger,
            self.run_id,
            "episode_anchor",
            state["state_id"],
            {
                "episode_hash": json_hash(episode),
                "request_ids": request_ids,
                "last_event_id": event_id,
                "remaining_budget": state["remaining_budget"],
            },
        )
        return episode

    def episode(self, state):
        snapshot = self.ledger.snapshot(self.run_id)
        projected = qualification(self.ledger, self.run_id, runtime_hash=self.runtime_hash)
        return checked(
            {
                "schema_version": "stage2.v1",
                "run_id": self.run_id,
                "problem": self.problem,
                "candidates": projected["candidates"],
                **{
                    k: snapshot[k]
                    for k in ("tests", "executions", "audit_gaps", "probe_mutants", "edit_sources")
                },
                "actions": list(self.actions),
                "state": state,
                "model_manifest_hash": self.manifest_hash,
                "profile_hash": snapshot["profile_hash"],
            },
            "EpisodeBundle",
        )
