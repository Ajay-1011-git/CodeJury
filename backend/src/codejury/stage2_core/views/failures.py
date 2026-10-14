"""Project one registered authoritative failure without inventing an oracle."""

REVISION_INSTRUCTION = (
    "Change the parent implementation to address the concrete failure. "
    "The revision must change behavior on the failing input and preserve all interfaces. "
    "Do not repeat the parent source. An observed output is not an expected value."
)


def first_failure(rows):
    for row in rows:
        if row["oracle_status"] != "authoritative":
            continue
        reasons = []
        if row["outcome"] in {"fail", "error", "timeout"}:
            reasons.append("execution_failure")
        if any(
            effect["mutated"] or effect.get("before_hash") != effect.get("after_hash")
            for effect in row["input_effects"]
        ):
            reasons.append("input_mutation")
        if row["exception"] is not None:
            reasons.append("exception")
        if not reasons:
            continue
        oracle = row["oracle_spec"]
        value = {
            "execution_id": row["execution_id"],
            "test_id": row["test_id"],
            "inputs": row["inputs"],
            "actual": row["actual_output"],
            "exception": row["exception"],
            "outcome": row["outcome"],
            "failure_reasons": reasons,
            "input_effects": row["input_effects"],
            "oracle": oracle,
            "related_inputs": row["related_inputs"],
        }
        # A property violation can be concrete without having a literal expected
        # value. Preserve the registered property instead of guessing an answer.
        if oracle["kind"] == "literal":
            value["expected"] = oracle["expected"]
        return value
    return None
