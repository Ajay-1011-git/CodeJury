"""Actual alternative executions of trusted fixtures; not native learning evidence."""

from threading import Event

import pytest

from codejury.stage2_core.contracts import json_hash
from codejury.stage2_core.controller import records
from codejury.stage2_core.rollouts import RolloutPort

from .test_controller import controller, run


def port(control, tmp_path):
    return RolloutPort(
        control.ledger,
        tmp_path / "forks",
        control.model,
        control.tool,
        control.identities,
        manifest_hash=control.manifest_hash,
        runtime_hash=control.runtime_hash,
        mode="fixture",
    )


def request(episode, option):
    return {
        "schema_version": "stage2.v1",
        "request_id": "alternative",
        "episode": episode,
        "forced_option_id": option["option_id"],
        "seed": 23,
        "continuation_policy": "fixed-v1",
        "remaining_budget": episode["state"]["remaining_budget"],
    }


def test_real_fixture_alternatives_have_distinct_runs_and_immutable_parent(tmp_path):
    control = controller(tmp_path / "parent")
    final = run(control)
    parent_hash = json_hash(final)
    episode = records(control.ledger, final["run_id"], "episode")[0]
    rollout = port(control, tmp_path)
    audit = next(o for o in episode["state"]["available_actions"] if o["action"]["kind"] == "audit")
    abstain = next(
        o for o in episode["state"]["available_actions"] if o["action"]["kind"] == "abstain"
    )
    first = rollout.continue_episode(request(episode, audit), Event())
    second = rollout.continue_episode(request(episode, abstain), Event())
    assert first["final_result"]["status"] == "supported_patch"
    assert second["final_result"]["status"] == "unresolved"
    assert first["final_result"]["run_id"] != second["final_result"]["run_id"] != final["run_id"]
    assert second["selected_source"] is None
    assert json_hash(control.ledger.snapshot(final["run_id"])) == parent_hash


def test_budget_expansion_and_unknown_options_are_refused_before_fork(tmp_path):
    control = controller(tmp_path / "parent")
    final = run(control)
    episode = records(control.ledger, final["run_id"], "episode")[0]
    rollout = port(control, tmp_path)
    req = request(episode, episode["state"]["available_actions"][0])
    with pytest.raises(ValueError, match="exact parent budget"):
        rollout.continue_episode(
            {**req, "remaining_budget": {**req["remaining_budget"], "output_tokens": 10000}},
            Event(),
        )
    with pytest.raises(ValueError, match="actually offered"):
        rollout.continue_episode({**req, "forced_option_id": "invented"}, Event())


def test_anchored_history_does_not_import_future_tests_or_requests(tmp_path):
    from codejury.stage2_core.controller import FixedController
    from codejury.stage2_core.ledger import Ledger
    from codejury.stage2_core.rollouts import restore

    control = controller(tmp_path / "parent")
    final = run(control)
    episode = records(control.ledger, final["run_id"], "episode")[0]
    anchor = records(control.ledger, final["run_id"], "episode_anchor")[0]
    fork = FixedController(
        Ledger(tmp_path / "restored"),
        control.model,
        control.tool,
        control.identities,
        manifest_hash=control.manifest_hash,
        runtime_hash=control.runtime_hash,
        mode="fixture",
    )
    fork.cancel = Event()
    restore(control.ledger, episode, fork, 23)
    snapshot = fork.ledger.snapshot(fork.run_id)
    assert snapshot["tests"] == episode["tests"]
    assert len(snapshot["tests"]) < len(final["tests"])
    with fork.ledger.connection() as db:
        inherited = [
            r[0]
            for r in db.execute(
                "SELECT id FROM requests WHERE run_id=? ORDER BY rowid", (fork.run_id,)
            )
        ]
    assert inherited == anchor["request_ids"]
    assert (
        fork.account.remaining()["function_executions"]
        == episode["state"]["remaining_budget"]["function_executions"]
    )
