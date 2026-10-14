"""Turn records from stored calls and sandbox events. No invented agent dialogue."""

import json
from difflib import unified_diff


def parsed(text):
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def diff(before, after):
    if not before or not after:
        return ""
    return "".join(
        unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="parent",
            tofile="revision",
        )
    )[:48000]


def turn_records(snapshot, events, calls, interpreter=None):
    """Use model call order and durable event order; attach exact registered evidence."""
    candidates = snapshot.get("candidates", [])
    by_id = {c["candidate_id"]: c for c in candidates}
    tests = {t["test_id"]: t for t in snapshot.get("tests", [])}
    executions = {e["execution_id"]: e for e in snapshot.get("executions", [])}
    candidate_events = {
        e["payload"].get("candidate_id"): e["event_id"]
        for e in events
        if e["type"] == "candidate_created"
    }
    action_events = [e for e in events if e["type"] in {"action_selected", "action_refused"}]
    call_turns = []
    seen_candidates = set()
    cursor = 0
    for index, call in enumerate(calls):
        # A dispatched request has not produced dialogue. Its durable request
        # remains in the raw transcript; only actual replies enter the chat.
        if not isinstance(call.get("text"), str) or not call["text"].strip():
            continue
        body = parsed(call.get("text"))
        role = call.get("role")
        candidate = next(
            (
                c
                for c in candidates
                if c["candidate_id"] not in seen_candidates
                and c["origin"].startswith(role or "none")
                and c["source"].strip() == str(body.get("source", "")).strip()
            ),
            None,
        )
        event = 0
        if candidate:
            seen_candidates.add(candidate["candidate_id"])
            event = candidate_events.get(candidate["candidate_id"], 0)
            cursor = max(cursor, event)
        elif role == "judge":
            # State-bound menu ids identify this action; do not infer a spoken claim
            # from the menu summary. The claim stays the actual model rationale.
            options = {o.get("option_id"): o for o in call.get("options", [])}
            chosen = options.get(body.get("action_option_id"))
            matching = next(
                (
                    e
                    for e in action_events
                    if e["event_id"] > cursor
                    and chosen
                    and e["payload"].get("message") == chosen.get("summary")
                ),
                None,
            )
            if matching:
                event = matching["event_id"]
                cursor = event
        elif role == "critic":
            event = cursor + 0.5
        else:
            event = cursor + 0.1
        kind = (
            "revision"
            if call.get("purpose") == "revise"
            else "proposal"
            if role in {"fixer_a", "fixer_b", "raw", "general"}
            else "challenge"
            if role == "critic"
            else "verdict"
            if body.get("action_option_id")
            and next(
                (
                    o
                    for o in call.get("options", [])
                    if o.get("option_id") == body["action_option_id"]
                    and o.get("kind") in {"select", "abstain"}
                ),
                None,
            )
            else "rebuttal"
        )
        claim = (
            body.get("diagnosis")
            if role in {"fixer_a", "fixer_b", "raw", "general"}
            else body.get("rationale")
        )
        claim = claim if isinstance(claim, str) else call.get("text") or ""
        parent = by_id.get(candidate.get("parent_id")) if candidate else None
        call_turns.append(
            {
                "_order": event,
                "_call_index": index,
                "role": role,
                "kind": kind,
                "claim": claim,
                "evidence": None,
                "patch_diff": diff(parent["source"], candidate["source"])
                if parent and candidate
                else "",
                "tokens": call.get("output_tokens"),
                "request_id": call.get("request_id"),
                "candidate_id": candidate["candidate_id"] if candidate else None,
                "raw_reply": call.get("text"),
                "status": call.get("status"),
            }
        )
    # Calls without a committed proposal remain visible, including malformed attempts.
    # Their order is anchored to their next committed call when one exists.
    next_order = None
    for turn in reversed(call_turns):
        if turn["_order"] > 0 and (turn.get("candidate_id") or turn["role"] == "judge"):
            next_order = turn["_order"]
        elif next_order is not None:
            turn["_order"] = next_order - 0.01
    turns = call_turns
    for event in events:
        if event["type"] == "execution_completed":
            for identifier in event["payload"].get("evidence_ids", []):
                execution = executions.get(identifier)
                if not execution or execution["outcome"] not in {"fail", "error", "timeout"}:
                    continue
                test = tests.get(execution["test_id"])
                if not test:
                    continue
                spec = test["oracle_spec"]
                turns.append(
                    {
                        "_order": event["event_id"],
                        "_call_index": -1,
                        "role": "tools",
                        "kind": "counterexample",
                        "claim": event["payload"].get("message", ""),
                        "evidence": {
                            "exec_id": identifier,
                            "candidate_id": execution["candidate_id"],
                            "test_id": execution["test_id"],
                            "input": test["inputs"],
                            "expected": spec.get("expected"),
                            "property_template_id": spec.get("property_id"),
                            "actual": execution["actual_output"],
                            "exception": execution.get("exception"),
                            "tier": test["oracle_status"],
                            "outcome": execution["outcome"],
                        },
                        "patch_diff": "",
                        "tokens": 0,
                        "raw_reply": None,
                    }
                )
        elif event["type"] == "action_refused":
            turns.append(
                {
                    "_order": event["event_id"],
                    "_call_index": -1,
                    "role": "controller",
                    "kind": "rebuttal",
                    "claim": event["payload"].get("message", ""),
                    "evidence": None,
                    "patch_diff": "",
                    "tokens": 0,
                    "raw_reply": None,
                }
            )
        elif event["type"] == "run_finished":
            turns.append(
                {
                    "_order": event["event_id"],
                    "_call_index": -1,
                    "role": "controller",
                    "kind": "verdict",
                    "claim": snapshot.get("decision", {}).get("reason")
                    or event["payload"].get("message", ""),
                    "evidence": None,
                    "patch_diff": "",
                    "tokens": 0,
                    "raw_reply": None,
                }
            )
    turns.sort(key=lambda t: (t["_order"], t["_call_index"]))
    if interpreter:
        turns.insert(
            0,
            {
                "role": "interpreter",
                "kind": "proposal",
                "claim": interpreter.get("text") or "",
                "label": "Interpreter (cloud, spec only)",
                "evidence": None,
                "patch_diff": "",
                "tokens": interpreter.get("output_tokens"),
                "raw_reply": interpreter.get("text"),
                "request_id": interpreter.get("request_hash"),
            },
        )
    return [
        {k: v for k, v in {"turn": i + 1, **turn}.items() if not k.startswith("_")}
        for i, turn in enumerate(turns)
    ]
