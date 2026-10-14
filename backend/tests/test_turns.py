"""Conversation projections use exact stored statements and evidence."""

from codejury.api.turns import turn_records


def fixture():
    original = {
        "candidate_id": "c-o",
        "origin": "original",
        "source": "def f(x):\n    return 0\n",
        "parent_id": None,
    }
    a = {
        "candidate_id": "c-a",
        "origin": "fixer_a",
        "source": "def f(x):\n    return 1\n",
        "parent_id": "c-o",
    }
    revised = {
        "candidate_id": "c-r",
        "origin": "fixer_a_revision",
        "source": "def f(x):\n    return x\n",
        "parent_id": "c-a",
    }
    test = {
        "test_id": "t-one",
        "inputs": [2],
        "oracle_status": "authoritative",
        "oracle_spec": {"kind": "literal", "expected": 2},
    }
    execution = {
        "execution_id": "e-one",
        "candidate_id": "c-a",
        "test_id": "t-one",
        "outcome": "fail",
        "actual_output": 1,
        "exception": None,
    }
    snap = {
        "candidates": [original, a, revised],
        "tests": [test],
        "executions": [execution],
        "decision": {"reason": "Passed approved checks"},
    }

    def event(i, kind, **payload):
        return {"event_id": i, "type": kind, "payload": payload}

    events = [
        event(1, "candidate_created", candidate_id="c-o"),
        event(2, "candidate_created", candidate_id="c-a"),
        event(
            3, "execution_completed", evidence_ids=["e-one"], message="Sandbox evidence committed"
        ),
        event(4, "candidate_created", candidate_id="c-r"),
        event(5, "run_finished", message="Passed approved checks"),
    ]
    calls = [
        {
            "role": "fixer_a",
            "purpose": "repair",
            "request_id": "m-one",
            "text": '{"source":"def f(x):\\n    return 1\\n","diagnosis":"Wrong constant"}',
            "output_tokens": 12,
        },
        {
            "role": "fixer_a",
            "purpose": "revise",
            "request_id": "m-two",
            "text": '{"source":"def f(x):\\n    return x\\n","diagnosis":"Use argument"}',
            "output_tokens": 14,
        },
    ]
    return snap, events, calls


def test_projection_preserves_claims_execution_values_and_parent_diff():
    snap, events, calls = fixture()
    turns = turn_records(snap, events, calls)
    assert [t["kind"] for t in turns] == ["proposal", "counterexample", "revision", "verdict"]
    assert [t["turn"] for t in turns] == [1, 2, 3, 4]
    assert turns[0]["claim"] == "Wrong constant"
    assert turns[1]["evidence"]["expected"] == 2
    assert turns[1]["evidence"]["actual"] == 1
    assert turns[1]["evidence"]["exec_id"] == "e-one"
    assert "-    return 1" in turns[2]["patch_diff"]
    assert "+    return x" in turns[2]["patch_diff"]
    assert turns[2]["tokens"] == 14
    assert turns[3]["role"] == "controller"
    assert turns[3]["claim"] == snap["decision"]["reason"]


def test_missing_model_text_never_becomes_invented_dialogue():
    snap, events, calls = fixture()
    calls[0]["text"] = "not valid JSON"
    turns = turn_records(snap, events, calls)
    assert any(t["claim"] == "not valid JSON" for t in turns)
    assert all(
        t["claim"]
        in {
            "not valid JSON",
            "Use argument",
            "Sandbox evidence committed",
            "Passed approved checks",
        }
        for t in turns
    )


def test_cloud_interpretation_is_separate_and_labelled():
    snap, events, calls = fixture()
    interpreted = {"text": '{"requirements":["Include negatives"]}', "request_hash": "abc"}
    turns = turn_records(snap, events, calls, interpreted)
    assert turns[0]["role"] == "interpreter"
    assert turns[0]["label"] == "Interpreter (cloud, spec only)"
    assert turns[0]["claim"] == interpreted["text"]
    assert turns[0]["tokens"] is None
    interpreted["output_tokens"] = 44
    assert turn_records(snap, events, calls, interpreted)[0]["tokens"] == 44


def test_property_expected_value_remains_unknown_not_guessed():
    snap, events, calls = fixture()
    snap["tests"][0]["oracle_spec"] = {"kind": "property", "property_id": "sum_ints"}
    turn = next(t for t in turn_records(snap, events, calls) if t["kind"] == "counterexample")
    assert turn["evidence"]["expected"] is None
    assert turn["evidence"]["property_template_id"] == "sum_ints"


def test_refusals_are_actual_controller_records_in_the_conversation():
    snap, events, calls = fixture()
    message = "Refused revision: unchanged parent source"
    events.append({"event_id": 6, "type": "action_refused", "payload": {"message": message}})
    turn = turn_records(snap, events, calls)[-1]
    assert turn["role"] == "controller" and turn["claim"] == message
    assert turn["kind"] == "rebuttal" and turn["tokens"] == 0


def test_pending_and_empty_model_requests_do_not_appear_as_spoken_turns():
    snap, events, calls = fixture()
    calls.insert(
        0, {"role": "judge", "purpose": "action_choice", "text": None, "status": "dispatched"}
    )
    calls.append({"role": "judge", "text": "", "status": "ok"})
    turns = turn_records(snap, events, calls)
    assert len(turns) == 4
    assert all(turn["claim"] for turn in turns)
