"""Actual isolated alternative continuations from anchored canonical pre-action states."""

import json
from pathlib import Path

from ..budgets import CAPS, COUNTERS, BudgetExceeded
from ..candidates import CandidatePool
from ..contracts import checked, json_hash
from ..controller import (
    POLICY,
    FixedController,
    Stopped,
    TraceArchivePort,
    challenge_key,
    ident,
    record,
    records,
)
from ..ledger import KINDS, Ledger, encode
from ..views import freeze_initial


def run_result(snapshot):
    decision = snapshot["decision"]
    return checked(
        {
            "schema_version": "stage2.v1",
            "run_id": snapshot["run_id"],
            "status": snapshot["status"],
            "selected_candidate_id": decision["selected_candidate_id"],
            "verification_scope": decision["verification_scope"],
            "unresolved_requirements": decision["unresolved_requirements"],
            "evidence_ids": decision["evidence_ids"],
            "resource_usage": snapshot["resource_usage"],
            "termination_reason": snapshot["termination_reason"],
        },
        "RunResult",
    )


def restore(parent, episode, controller, seed):
    """Import historical facts as inherited receipts, never charge them as fresh work."""
    episode = checked(episode, "EpisodeBundle")
    parent_id, state = episode["run_id"], episode["state"]
    anchors = records(parent, parent_id, "episode_anchor")
    anchor = next((a for a in anchors if a["episode_hash"] == json_hash(episode)), None)
    if anchor is None or anchor["remaining_budget"] != state["remaining_budget"]:
        raise ValueError("An exact frozen pre-action anchor is required; no inferred history")
    metadata = records(parent, parent_id, "metadata")
    if len(metadata) != 1:
        raise ValueError("Unique immutable parent metadata required")
    meta = metadata[0]
    if (
        meta["model_manifest_hash"] != controller.manifest_hash
        or meta["runtime_hash"] != controller.runtime_hash
        or meta["mode"] != controller.mode
    ):
        raise ValueError("Rollout cannot change parent model/sandbox identities")
    inherited = []
    with parent.connection() as db:
        for request_id in anchor["request_ids"]:
            row = db.execute(
                "SELECT * FROM requests WHERE run_id=? AND id=?", (parent_id, request_id)
            ).fetchone()
            if (
                row is None
                or row["status"] != "settled"
                or json.loads(row["response"])["status"] != "ok"
            ):
                raise ValueError("Incomplete anchored receipt")
            inherited.append(dict(row))
    known = {e["state"]["state_id"]: e for e in records(parent, parent_id, "episode")}
    if known.get(state["state_id"]) != episode:
        raise ValueError("Episode was not frozen in this parent ledger")
    controller.problem = episode["problem"]
    controller.run_id, controller.seed = ident("fork"), seed
    limits = meta["profile"]["caps"]
    remaining = state["remaining_budget"]
    if any(remaining[k] > limits[k] for k in CAPS):
        raise ValueError("Fork cannot expand parent budget")
    destination = controller.ledger
    destination.create_run(
        controller.run_id,
        controller.problem,
        mode=controller.mode,
        profile={
            "parent_profile_hash": episode["profile_hash"],
            "episode_hash": json_hash(episode),
            "continuation_policy": "fixed-v1",
        },
        model_configs=[i["model_config_hash"] for i in controller.identities.values()],
        limits=limits,
        final_executions=POLICY["final_reserve"],
    )
    controller.account = destination.accounts[controller.run_id]
    for execution in episode["executions"]:
        if execution["trace_ref"]:
            destination.put_object(parent.read_object(execution["trace_ref"]))
    fields = {
        "candidates": "candidates",
        "tests": "tests",
        "executions": "executions",
        "mutants": "probe_mutants",
        "gaps": "audit_gaps",
        "edit_sources": "edit_sources",
    }
    imported = {}
    for kind, field in fields.items():
        _, key = KINDS[kind]
        wanted = {r[key] for r in episode[field]}
        imported[kind] = [r for r in parent.records(parent_id, kind) if r[key] in wanted]
        if {r[key] for r in imported[kind]} != wanted:
            raise ValueError("Episode contains facts not registered by its parent")
        for row in imported[kind]:
            if "source" in row:
                destination.put_object(row["source"].encode())
    events = parent.events(parent_id)
    with destination.connection() as db:
        for event in events[1 : anchor["last_event_id"]]:
            inherited_event = {**event, "run_id": controller.run_id}
            checked(inherited_event, "Event")
            db.execute(
                "INSERT INTO events VALUES (?,?,?)",
                (controller.run_id, event["event_id"], encode(inherited_event)),
            )
        for kind, rows in imported.items():
            for row in rows:
                destination._insert(db, controller.run_id, kind, row)
        for row in inherited:
            # Original request bodies/IDs remain exact. These SQL associations denote
            # inherited historical receipts, not a new dispatch or new model generation.
            db.execute(
                "INSERT INTO requests VALUES (?,?,?,?,?,?,?)",
                (
                    controller.run_id,
                    row["id"],
                    row["definition"],
                    row["body"],
                    row["status"],
                    row["response"],
                    row["usage"],
                ),
            )
    account = controller.account
    for key in COUNTERS:
        spent = (
            limits[key]
            - remaining[key]
            - (POLICY["final_reserve"] if key == "function_executions" else 0)
        )
        if spent < 0:
            raise ValueError("Invalid inherited reserve/cost accounting")
        account.used[key] = spent
    account.started -= (limits["elapsed_ms"] - remaining["elapsed_ms"]) / 1000
    account.settled = set(anchor["request_ids"])
    controller.actions = list(episode["actions"])
    controller.audited, controller.challenged = set(), set()
    controller.searched, controller.revised, controller.resampled = set(), set(), False
    candidates = {c["candidate_id"]: c for c in episode["candidates"]}
    controller.original = next(c for c in imported["candidates"] if c["origin"] == "original")
    controller.pool = CandidatePool(
        destination, controller.run_id, controller.model, controller.identities
    )
    controller.pool.views = freeze_initial(
        controller.problem,
        [t for t in episode["tests"] if t["test_id"] in controller.problem["supplied_test_ids"]],
    )
    controller.pool._initial_started = True
    for index, action in enumerate(controller.actions):
        before = next(
            (
                e
                for e in known.values()
                if len(e["actions"]) == index and e["actions"] == controller.actions[:index]
            ),
            None,
        )
        if before is None:
            raise ValueError("Prior action lacks its exact pre-action state")
        suite = before["state"]["suite_hash"]
        if action["kind"] == "audit":
            for target in action["target_ids"]:
                controller.audited.add((candidates[target]["source_hash"], suite))
        elif action["kind"] == "criticize":
            controller.challenged.add(challenge_key(before, suite, action["target_ids"]))
        elif action["kind"] == "search":
            controller.searched.update(action["target_ids"])
        elif action["kind"] == "revise":
            controller.revised.update(action["target_ids"])
        elif action["kind"] == "generate":
            controller.resampled = True
        record(destination, controller.run_id, "action", action["action_id"], action)
    prior_ids = {a["action_id"] for a in controller.actions}
    for outcome in records(parent, parent_id, "outcome"):
        if outcome["action_id"] in prior_ids:
            record(destination, controller.run_id, "outcome", outcome["action_id"], outcome)
    record(
        destination,
        controller.run_id,
        "fork_parent",
        "parent",
        {
            "source_run_id": parent_id,
            "source_state_id": state["state_id"],
            "episode_hash": json_hash(episode),
            "inherited_request_ids": anchor["request_ids"],
            "remaining_budget": remaining,
            "seed": seed,
            "continuation_policy": "fixed-v1",
        },
    )
    return controller


class RolloutPort:
    def __init__(
        self,
        parent,
        directory,
        model,
        tool,
        identities,
        *,
        manifest_hash,
        runtime_hash,
        mode="live",
    ):
        self.parent, self.directory, self.model, self.tool = parent, Path(directory), model, tool
        self.identities, self.manifest_hash, self.runtime_hash, self.mode = (
            identities,
            manifest_hash,
            runtime_hash,
            mode,
        )

    def continue_episode(self, request, cancel):
        request = checked(request, "RolloutRequest")
        episode = request["episode"]
        if request["remaining_budget"] != episode["state"]["remaining_budget"]:
            raise ValueError("All alternatives must start with the exact parent budget")
        option = next(
            (
                o
                for o in episode["state"]["available_actions"]
                if o["option_id"] == request["forced_option_id"]
            ),
            None,
        )
        if option is None:
            raise ValueError("Forced option was not actually offered")
        ledger = Ledger(self.directory / ident("continuation"))
        self.last_ledger_directory = ledger.directory
        from codejury.stage2_tools.port import ToolPortImpl

        tool = self.tool.port if isinstance(self.tool, TraceArchivePort) else self.tool
        isolated_tool = ToolPortImpl(tool.sandbox, contracts=tool.contracts)
        control = FixedController(
            ledger,
            self.model,
            isolated_tool,
            self.identities,
            manifest_hash=self.manifest_hash,
            runtime_hash=self.runtime_hash,
            mode=self.mode,
        )
        control.cancel = cancel
        parent_hash = json_hash(self.parent.snapshot(episode["run_id"]))
        restore(self.parent, episode, control, request["seed"])
        try:
            result = control.execute(episode["state"], option)
            while result is None and len(control.actions) < POLICY["max_actions"]:
                state, _ = control.state()
                control.freeze_episode(state)
                result = control.execute(state, control.choose(state))
            if result is None:
                raise Stopped("unresolved", "Fixed continuation action limit reached")
        except Stopped as exc:
            result = control.finish(exc.status, exc.reason)
        except (BudgetExceeded, InterruptedError) as exc:
            result = control.finish("cancelled" if cancel.is_set() else "unresolved", str(exc))
        if parent_hash != json_hash(self.parent.snapshot(episode["run_id"])):
            raise RuntimeError("Continuation changed its immutable parent")
        selected = result["decision"]["selected_candidate_id"]
        candidate = next((c for c in result["candidates"] if c["candidate_id"] == selected), None)
        return checked(
            {
                "schema_version": "stage2.v1",
                "request_id": request["request_id"],
                "final_result": run_result(result),
                "selected_source": candidate["source"] if candidate else None,
                "selected_source_hash": candidate["source_hash"] if candidate else None,
                "episode": episode,
            },
            "RolloutResult",
        )
