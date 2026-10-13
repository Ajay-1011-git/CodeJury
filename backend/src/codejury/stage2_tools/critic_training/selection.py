"""Checkpoint selection from measured role metrics. Loss is deliberately not an input."""

METRICS = (
    "format_validity",
    "domain_validity",
    "counterexample_yield",
    "false_rejection_rate",
    "gap_challenge_benefit",
    "cost_tokens",
)


class SelectionError(ValueError):
    pass


def _problem(row: dict, policy: dict) -> str | None:
    metrics = row.get("metrics") or {}
    missing = [m for m in METRICS if metrics.get(m) is None]
    if missing:
        return f"not measured: {', '.join(missing)}"
    if metrics["format_validity"] < policy["min_format_validity"]:
        return "format validity below floor"
    if metrics["domain_validity"] < policy["min_domain_validity"]:
        return "domain validity below floor"
    if metrics["false_rejection_rate"] > policy["max_false_rejection"]:
        return "false rejection of correct candidates above cap"
    return None


def select(checkpoints: list[dict], policy: dict) -> dict:
    """Pick the best eligible checkpoint, or none. Every checkpoint is reported with its reason."""
    steps = [c["step"] for c in checkpoints]
    if len(set(steps)) != len(steps):
        raise SelectionError("Duplicate checkpoint steps")
    report, eligible = [], []
    for row in checkpoints:
        why = _problem(row, policy)
        report.append({"step": row["step"], "eligible": why is None, "reason": why or "ok"})
        if why is None:
            eligible.append(row)
    if not eligible:
        return {"selected_step": None, "checkpoints": report, "note": "no checkpoint is eligible"}
    best = min(
        eligible,
        key=lambda r: (
            -r["metrics"]["counterexample_yield"],
            r["metrics"]["false_rejection_rate"],
            -r["metrics"]["gap_challenge_benefit"],
            r["metrics"]["cost_tokens"],
            r["step"],
        ),
    )
    return {
        "selected_step": best["step"],
        "checkpoints": report,
        "note": "ranked on measured role metrics",
    }
