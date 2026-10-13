"""Actual research policies. Model roles stay truthful in every request/response."""

from ..candidates import incumbent, validated_tests
from ..controller import POLICY, FixedController
from ..controller.learned import LearnedController


class RepairBaseline(FixedController):
    sample_to_cap = False

    def initial_candidates(self):
        return self.pool.generate(
            "fixer_a", self.pool.views.a, parent=self.original, seed=self.seed, cancel=self.cancel
        )

    def options(self, state, snapshot, candidates):
        options = []
        remaining = state["remaining_budget"]
        nonterminal = len(self.actions) < POLICY["max_actions"] - 1
        a = [c for c in candidates if c["origin"] in {"fixer_a", "fixer_a_revision"}]
        failures = set(state["authoritative_counterexample_ids"])
        if nonterminal and remaining["learned_candidates"] and remaining["output_tokens"] >= 1024:
            for candidate in a:
                if (
                    candidate["candidate_id"] not in self.revised
                    and any(
                        e["candidate_id"] == candidate["candidate_id"]
                        and e["execution_id"] in failures
                        for e in snapshot["executions"]
                    )
                    and (self.sample_to_cap or not self.revised)
                ):
                    options.append(
                        self.option(
                            "revise",
                            [candidate["candidate_id"]],
                            {"role": "fixer_a"},
                            "A feedback from actual hard failures",
                            state,
                        )
                    )
                    break
            if self.sample_to_cap:
                options.append(
                    self.option(
                        "generate",
                        [self.original["candidate_id"]],
                        {"role": "fixer_a", "count": 1},
                        "Additional A sample within the shared attempt cap",
                        state,
                    )
                )
        chosen = incumbent({"candidates": candidates}, self.problem["source"])
        if chosen is not None and not state["unresolved_requirement_ids"]:
            options.append(
                self.option(
                    "select",
                    [chosen],
                    {"candidate_id": chosen},
                    "A source passed the complete current user suite",
                    state,
                )
            )
        options.append(
            self.option(
                "abstain",
                [],
                {"reason": "No supported A repair within this baseline"},
                "Safe terminal option",
                state,
            )
        )
        return options


class SampleBaseline(RepairBaseline):
    sample_to_cap = True


class GeneralController(LearnedController):
    decision_role = "general"

    def initial_candidates(self):
        # The single agent chooses whether to repair, reconstruct or search first.
        return None

    def options(self, state, snapshot, candidates):
        offered = super().options(state, snapshot, candidates)
        remaining = state["remaining_budget"]
        if len(self.actions) >= POLICY["max_actions"] - 1:
            return offered
        extra = []
        if remaining["learned_candidates"] and remaining["output_tokens"] >= 1024:
            for role in ("fixer_a", "fixer_b"):
                extra.append(
                    self.option(
                        "generate",
                        [self.original["candidate_id"]],
                        {"role": role, "count": 1},
                        "General agent may allocate another repair/reconstruction",
                        state,
                    )
                )
        if remaining["search_candidates"] and remaining["function_executions"]:
            parents = [c for c in candidates if c["origin"] != "ast_search"][:3]
            for parent in parents:
                if parent["candidate_id"] in self.searched or not validated_tests(
                    self.ledger,
                    self.run_id,
                    parent["source"],
                    self.problem["signature"],
                    snapshot["tests"],
                ):
                    continue
                extra.append(
                    self.option(
                        "search",
                        [parent["candidate_id"]],
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
                        "General agent may allocate the common local search tool",
                        state,
                    )
                )
        semantic = set()
        result = []
        from ..contracts import json_hash

        for option in [*extra, *offered]:
            key = json_hash({k: option["action"][k] for k in ("kind", "target_ids", "parameters")})
            if key not in semantic:
                semantic.add(key)
                result.append(option)
        terminal = next(o for o in result if o["action"]["kind"] == "abstain")
        return [*[o for o in result if o != terminal][:19], terminal]


class NoSearchController(LearnedController):
    def options(self, state, snapshot, candidates):
        return [
            o
            for o in super().options(state, snapshot, candidates)
            if o["action"]["kind"] != "search"
        ]


class NoGapController(LearnedController):
    gap_feedback = False

    def options(self, state, snapshot, candidates):
        options = super().options(state, snapshot, candidates)
        for option in options:
            if (
                option["action"]["kind"] == "criticize"
                and option["action"]["parameters"]["mode"] == "audit_gap"
            ):
                option["action"]["parameters"]["mode"] = "challenge_agreement"
        return options


class AuditAtEndController(LearnedController):
    def options(self, state, snapshot, candidates):
        options = super().options(state, snapshot, candidates)
        if any(
            o["action"]["kind"] in {"revise", "search", "generate", "criticize"} for o in options
        ):
            options = [o for o in options if o["action"]["kind"] != "audit"]
        order = {
            "revise": 0,
            "search": 1,
            "generate": 2,
            "criticize": 3,
            "audit": 4,
            "select": 5,
            "abstain": 6,
        }
        return sorted(options, key=lambda o: order[o["action"]["kind"]])
