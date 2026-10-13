"""Critic prompt: runtime contract, candidates, evidence and gaps only.

`build_prompt` takes the runtime episode bundle and nothing else, so hidden TRAINING targets,
reference solutions and labels cannot reach it by construction. `guard_prompt` re-checks that.
"""

import json

FORBIDDEN_KEYS = ("reference", "hidden", "truth", "label", "gold", "target_draft")
SYSTEM = (
    "You are the CodeJury Critic. Propose one bounded experiment as a JSON object with keys "
    "mode, requirement_ids, generator_spec, concrete_inputs, oracle_spec, target_candidate_ids, "
    "rationale. Exactly one of generator_spec or concrete_inputs is non-null. Only reviewed "
    "property/metamorphic oracles can authorize a rejection; your own literal expectations stay "
    "proposals. If you found no authorized failure, say so with a general observation proposal "
    "and do not claim proof."
)


class PromptLeak(ValueError):
    pass


def _tests(bundle: dict) -> list[dict]:
    return [
        {
            "test_id": t["test_id"],
            "inputs": t["inputs"],
            "related_inputs": t["related_inputs"],
            "oracle_spec": t["oracle_spec"],
            "oracle_status": t["oracle_status"],
            "provenance": t["provenance"],
        }
        for t in bundle["tests"]
    ]


def view(bundle: dict, mode: str, pending: list[dict] | None = None) -> dict:
    p = bundle["problem"]
    return {
        "mode": mode,
        "problem": {
            "signature": p["signature"],
            "contract_text": p["contract_text"],
            "domain_schema": p["domain_schema"],
            "requirements": [
                {
                    k: r[k]
                    for k in (
                        "requirement_id",
                        "description",
                        "approval_status",
                        "property_template_id",
                    )
                }
                for r in p["requirements"]
            ],
        },
        "candidates": [
            {
                k: c[k]
                for k in (
                    "candidate_id",
                    "origin",
                    "parent_id",
                    "source",
                    "eligibility",
                    "diagnosis",
                    "assumptions",
                )
            }
            for c in bundle["candidates"]
        ],
        "tests": _tests(bundle),
        "executions": [
            {k: e[k] for k in ("candidate_id", "test_id", "outcome", "actual_output")}
            for e in bundle["executions"]
        ],
        "audit_gaps": [
            {
                k: g[k]
                for k in (
                    "gap_id",
                    "candidate_id",
                    "location",
                    "operator_family",
                    "interpretation",
                    "requirement_ids",
                )
            }
            for g in bundle["audit_gaps"]
        ],
        "pending_proposals": pending or [],
    }


def build_prompt(bundle: dict, mode: str, pending: list[dict] | None = None) -> str:
    return json.dumps(view(bundle, mode, pending), sort_keys=True, separators=(",", ":"))


def guard_prompt(prompt: str, bundle: dict, hidden: list[str]) -> None:
    """Raise when a hidden string or label-side key is present in the prompt."""
    visible = {c["source"] for c in bundle["candidates"]} | {bundle["problem"]["source"]}
    for key in FORBIDDEN_KEYS:
        if f'"{key}' in prompt:
            raise PromptLeak(f"Label-side key {key!r} in prompt")
    for text in hidden:
        if text and text not in visible and text in prompt:
            raise PromptLeak("Hidden target text found in prompt")
