"""Classify an episode into the Critic situation it teaches (label side may be consulted)."""

from ...codec import value_hash

SITUATIONS = (
    "near_correct_revision",
    "mutation_gap",
    "shared_incorrect_agreement",
    "disagreement",
    "correct_candidate",
)
SITUATION_MODE = {
    "near_correct_revision": "validate_revision",
    "mutation_gap": "audit_gap",
    "shared_incorrect_agreement": "challenge_agreement",
    "disagreement": "discriminate",
}


def learned(bundle: dict) -> list[dict]:
    return [c for c in bundle["candidates"] if c["origin"] != "original"]


def behaviour_groups(bundle: dict) -> list[list[str]]:
    """Candidates grouped by identical typed output on every executed test (runtime-visible)."""
    rows: dict[str, dict[str, str]] = {}
    for e in bundle["executions"]:
        rows.setdefault(e["candidate_id"], {})[e["test_id"]] = value_hash(
            [e["actual_output"], e["outcome"]]
        )
    groups: dict[str, list[str]] = {}
    for c in learned(bundle):
        groups.setdefault(
            value_hash([[k, v] for k, v in sorted(rows.get(c["candidate_id"], {}).items())]), []
        ).append(c["candidate_id"])
    return list(groups.values())


def classify(bundle: dict, truth: dict[str, bool]) -> list[str]:
    """Every situation that applies, in priority order. `truth` maps candidate_id -> correct."""
    cands = [c for c in learned(bundle) if c["candidate_id"] in truth]
    if not cands:
        return []
    wrong = [c for c in cands if not truth[c["candidate_id"]]]
    found = []
    if any(c["origin"] in ("revision", "search") and c in wrong for c in cands):
        found.append("near_correct_revision")
    gaps = {g["candidate_id"] for g in bundle["audit_gaps"]}
    if bundle["audit_gaps"] and any(c["candidate_id"] in gaps for c in cands):
        found.append("mutation_gap")
    groups = behaviour_groups(bundle)
    if len(wrong) >= 2 and len(groups) == 1:
        found.append("shared_incorrect_agreement")
    if wrong and len(groups) > 1:
        found.append("disagreement")
    if not wrong:
        found.append("correct_candidate")
    return found
