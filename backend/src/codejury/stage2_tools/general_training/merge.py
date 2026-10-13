"""Merge authorized TRAINING records from the four role datasets into one tagged distribution."""

ROLES = ("fixer_a", "fixer_b", "critic", "judge")
TASK_TAG = {
    "fixer_a": "repair",
    "fixer_b": "repair",
    "critic": "test",
    "judge": "action",
}


class MergeError(ValueError):
    pass


def merge(role_sets: dict[str, dict]) -> dict:
    """`role_sets[role] = {"split": ..., "runtime_mode": ..., "records": [...]}` of real records.

    Each record carries record_id, base_problem_id, view, tokens. Output keeps split/target/view
    provenance and tags every example with its task family. Validation/final data is refused.
    """
    if set(role_sets) != set(ROLES):
        raise MergeError("All four role datasets must be frozen before the general merge")
    modes = {s["runtime_mode"] for s in role_sets.values()}
    if len(modes) != 1:
        raise MergeError("Role datasets mix fixture and real data")
    merged, seen = [], set()
    for role in ROLES:
        block = role_sets[role]
        if block["split"] != "train":
            raise MergeError(f"{role} dataset is {block['split']!r}; only TRAINING data may merge")
        for rec in block["records"]:
            key = (role, rec["record_id"])
            if key in seen:
                raise MergeError(f"Duplicate record {key}")
            seen.add(key)
            merged.append(
                {
                    "source_role": role,
                    "task_tag": TASK_TAG[role],
                    "record_id": rec["record_id"],
                    "base_problem_id": rec["base_problem_id"],
                    "view": rec.get("view"),
                    "split": "train",
                    "tokens": rec["tokens"],
                }
            )
    return {
        "runtime_mode": modes.pop(),
        "records": merged,
        "examples": len(merged),
        "tokens": sum(r["tokens"] for r in merged),
        "base_problems": len({r["base_problem_id"] for r in merged}),
        "by_task": {
            t: sum(1 for r in merged if r["task_tag"] == t) for t in sorted(set(TASK_TAG.values()))
        },
    }
