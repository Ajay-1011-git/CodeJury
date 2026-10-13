"""Aggregate example/token opportunity parity between the general adapter and the four roles.

Parity uses ACTUAL training tokens seen and optimizer steps from real logs, not dataset line counts
or epochs x 4. Unmeasured inputs make the audit "not_measured", never a pass.
"""

from .merge import ROLES

FIELDS = ("examples", "tokens_seen", "optimizer_steps")


def _row(name: str, block: dict) -> dict | None:
    if not all(isinstance(block.get(f), int) and block[f] >= 0 for f in FIELDS):
        return None
    if not block.get("measured"):
        return None
    return {f: block[f] for f in FIELDS}


def audit(role_runs: dict[str, dict], general_run: dict, tolerance: float) -> dict:
    """`*_run` = {examples, tokens_seen, optimizer_steps, measured: bool}."""
    rows = {r: _row(r, role_runs.get(r, {})) for r in ROLES}
    general = _row("general", general_run)
    missing = [r for r, v in rows.items() if v is None] + (["general"] if general is None else [])
    if missing:
        return {"status": "not_measured", "missing": missing, "comparable": None}
    total = {f: sum(v[f] for v in rows.values()) for f in FIELDS}
    ratio = {f: (general[f] / total[f] if total[f] else None) for f in FIELDS}
    comparable = all(r is not None and abs(r - 1) <= tolerance for r in ratio.values())
    return {
        "status": "measured",
        "roles_total": total,
        "general": general,
        "ratio_general_to_roles": ratio,
        "tolerance": tolerance,
        "comparable": comparable,
        "note": "Comparable means every ratio is within tolerance of the four-role aggregate.",
    }
