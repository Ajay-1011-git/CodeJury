"""Predeclared paired development diagnostic; repeated seeds remain clustered."""

from codejury.dev_bench import SEEDS, summarize

DIAGNOSTIC_IDS = (
    "balanced_parentheses",
    "transpose_ragged",
    "chunk_list",
    "interleave_unequal",
    "sliding_window_sums",
    "word_frequencies",
    "bracket_types",
    "edit_distance",
    "max_subarray",
    "interval_union",
    "three_sum_unique",
    "grid_paths",
)
DIAGNOSTIC_TIERS = {base: "T2" if index < 6 else "T3" for index, base in enumerate(DIAGNOSTIC_IDS)}


def paired_comparison(before, after):
    expected = {(base, seed) for base in DIAGNOSTIC_IDS for seed in SEEDS}

    def population(rows, *, full):
        if full:
            rows = [
                r
                for r in rows
                if r["method"] == "J-current" and r["base_problem_id"] in DIAGNOSTIC_IDS
            ]
        keys = [(r["base_problem_id"], r["seed"]) for r in rows]
        if (
            set(keys) != expected
            or len(keys) != len(expected)
            or any(r["method"] != "J-current" for r in rows)
        ):
            raise ValueError("Incomplete or repeated paired diagnostic population")
        if any(r["tier"] != DIAGNOSTIC_TIERS[r["base_problem_id"]] for r in rows):
            raise ValueError("Paired diagnostic differs from the predeclared tiers")
        return dict(zip(keys, rows))

    old, new = population(before, full=True), population(after, full=False)
    if any(old[key]["tier"] != new[key]["tier"] for key in expected):
        raise ValueError("Paired diagnostic tier changed")
    transitions = [
        {
            "base_problem_id": base,
            "seed": seed,
            "before": old[(base, seed)]["outcome"],
            "after": new[(base, seed)]["outcome"],
        }
        for base in DIAGNOSTIC_IDS
        for seed in SEEDS
    ]
    old_summary, new_summary = summarize(list(old.values())), summarize(list(new.values()))
    # Gate each seed and tier too: an aggregate win must not conceal a tier loss.
    failures = []
    for a, b in zip(old_summary, new_summary):
        if b["solved"] < a["solved"] or b["outcomes"].get("wrong_accepted", 0) > a["outcomes"].get(
            "wrong_accepted", 0
        ):
            failures.append({"seed": a["seed"], "tier": a["tier"]})
    return {
        "status": "paired_development_diagnostic",
        "base_problems": 12,
        "runs_per_condition": 36,
        "seeds": list(SEEDS),
        "eligible_for_default": not failures,
        "gate_failures": failures,
        "before": old_summary,
        "after": new_summary,
        "transitions": transitions,
        "scope": "Combined local A checkpoint and concrete-failure revision changes; "
        "no separate causal attribution or full-population improvement claim.",
        "intervals": "Wilson per seed; twelve independent bases, not 36.",
    }
