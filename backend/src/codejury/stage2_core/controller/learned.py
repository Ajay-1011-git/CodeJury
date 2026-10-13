"""Learned menu selection; every decision remains subject to the canonical core guards."""

from jsonschema import ValidationError

from ..candidates import parse_draft
from ..contracts import CheckedModelPort, checked
from ..views import judge
from . import FixedController, ident, record


def choice(draft, state, visible_execution_ids):
    draft = checked(draft, "JudgeDraft")
    evidence = (
        set(state["authoritative_counterexample_ids"])
        | set(state["audit_gap_ids"])
        | set(visible_execution_ids)
    )
    if draft["state_id"] != state["state_id"] or not set(draft["evidence_ids"]) <= evidence:
        raise ValueError("Stale state or unregistered Judge evidence")
    selected = next(
        (o for o in state["available_actions"] if o["option_id"] == draft["action_option_id"]), None
    )
    if selected is None:
        raise ValueError("Judge choice was not offered")
    return selected


class LearnedController(FixedController):
    policy_mode = "learned"
    decision_role = "judge"

    def choose(self, state):
        role = self.decision_role
        if role not in self.identities or not self.identities[role]["adapter_hash"]:
            raise ValueError("Learned policy requires a genuine Judge adapter")
        snapshot = self.ledger.snapshot(self.run_id)
        ids = {c["candidate_id"] for c in snapshot["candidates"]}
        executions = [e for e in snapshot["executions"] if e["candidate_id"] in ids]
        view_state = {
            **state,
            "authoritative_counterexample_ids": state["authoritative_counterexample_ids"][:12],
            "audit_gap_ids": state["audit_gap_ids"][:12] if self.gap_feedback else [],
        }
        prompt = judge(view_state, snapshot["tests"], snapshot["candidates"], executions)
        shown = [e["execution_id"] for e in executions[:6]]
        refused = []
        for attempt in range(2):
            remaining = self.account.remaining()
            if remaining["judge_decisions"] < 1 or remaining["output_tokens"] < 192:
                break
            request = checked(
                {
                    "schema_version": "stage2.v1",
                    "request_id": ident("judge"),
                    "run_id": self.run_id,
                    "role": role,
                    "purpose": "action_choice" if role == "judge" else "baseline",
                    "prompt": prompt,
                    "seed": self.seed,
                    "max_new_tokens": 192,
                    "remaining_budget": remaining,
                },
                "ModelRequest",
            )
            self.ledger.dispatch_model(request, decision_attempt=True)
            response = CheckedModelPort(self.model).generate(request, self.cancel)
            self.ledger.settle_model(response)
            self.check_running()
            if any(
                response[k] != self.identities[role][k]
                for k in ("adapter_hash", "model_config_hash", "model_revision_hash")
            ):
                raise ValueError("Judge response identity differs from frozen adapter")
            try:
                draft = parse_draft(response["text"], "JudgeDraft")
                option = choice(draft, view_state, shown)
                # Judge generation consumes resources; recheck that the chosen semantic
                # action is still offered at the current remaining budget.
                fresh, _ = self.state()
                if not any(
                    all(
                        o["action"][k] == option["action"][k]
                        for k in ("kind", "target_ids", "parameters")
                    )
                    for o in fresh["available_actions"]
                ):
                    raise ValueError("Judge action no longer meets prerequisites/budget")
                record(
                    self.ledger,
                    self.run_id,
                    "judge_choice",
                    request["request_id"],
                    {
                        "state_id": state["state_id"],
                        "draft": draft,
                        "request_id": request["request_id"],
                        "attempt": attempt,
                        "mode": "learned",
                    },
                )
                return option
            except (ValueError, ValidationError, RecursionError) as exc:
                refused.append(type(exc).__name__)
                self.ledger.append_event(
                    self.run_id, "action_refused", "Invalid Judge draft; guarded choice refused"
                )
                prompt += (
                    "\nFormat retry: preserve the exact state_id and choose one offered option_id."
                )
        fresh, _ = self.state()
        available = [
            o
            for o in state["available_actions"]
            if any(
                all(o["action"][k] == f["action"][k] for k in ("kind", "target_ids", "parameters"))
                for f in fresh["available_actions"]
            )
        ]
        selected = available[0]  # The always-offered abstain guarantees a legal terminal choice.
        record(
            self.ledger,
            self.run_id,
            "judge_choice",
            ident("fixed-fallback"),
            {
                "state_id": state["state_id"],
                "mode": "fixed_fallback",
                "option_id": selected["option_id"],
                "refused": refused,
                "reason": "Judge schema/scope refusal or decision budget exhausted",
            },
        )
        return selected
