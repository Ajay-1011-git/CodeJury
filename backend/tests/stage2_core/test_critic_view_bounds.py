"""Bound growing runtime context without discarding canonical qualification evidence."""

import json

from codejury.stage2_core.contracts import checked
from codejury.stage2_core.controller.bootstrap import critic_input_prompt
from codejury.stage2_core.views import evidence

from .test_candidates import fixture


def test_large_observation_history_is_explicitly_bounded_and_recent_facts_join():
    snapshot = fixture("snapshot-running")
    problem = snapshot["problem"]
    template = snapshot["tests"][0]
    observations = [
        checked(
            {
                **template,
                "test_id": f"observation-{i}",
                "oracle_status": "observation_only",
                "oracle_source": "model",
                "oracle_spec": {"kind": "observation", "hypothesis": "Compare"},
            },
            "TestCase",
        )
        for i in range(100)
    ]
    candidates = snapshot["candidates"]
    base = fixture("tool-evaluate-result")["executions"][0]
    executions = [
        {
            **base,
            "execution_id": f"e-{i}",
            "candidate_id": candidates[0]["candidate_id"],
            "test_id": observations[i]["test_id"],
            "outcome": "observed",
        }
        for i in range(100)
    ]
    prompt = critic_input_prompt(
        problem, [template, *observations], candidates, executions, "challenge_agreement", 17
    )
    payload = json.JSONDecoder().raw_decode(prompt.split("Runtime-visible facts:\n")[1])[0]
    assert len(payload["tests"]) == 8 and len(payload["evidence"]) == 4
    assert {e["test_id"] for e in payload["evidence"]} <= {t["test_id"] for t in payload["tests"]}
    assert template["test_id"] in {t["test_id"] for t in payload["tests"]}
    assert "Omitted registered tests: 93" in prompt
    assert "Omitted execution summaries: 96" in prompt
    assert len(observations) == 100  # The view did not mutate canonical tests.


def test_trace_limit_discloses_actual_truncation_before_slicing():
    snapshot = fixture("snapshot-running")
    execution = fixture("tool-evaluate-result")["executions"][0]
    execution.update(
        candidate_id=snapshot["candidates"][0]["candidate_id"],
        test_id=snapshot["tests"][0]["test_id"],
        trace_ref="a" * 64,
    )
    rows = evidence(
        [execution],
        snapshot["tests"],
        snapshot["candidates"],
        trace_reader=lambda _: b"x" * 2000,
        trace_byte_limit=512,
    )
    assert len(rows[0]["trace"]) == 512 and rows[0]["view_trace_truncated"] is True
