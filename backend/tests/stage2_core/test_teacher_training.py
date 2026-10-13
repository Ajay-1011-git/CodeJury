import pytest

from codejury.stage2_core.teacher.collect import settings, source
from codejury.stage2_core.teacher.compare import decision
from codejury.stage2_core.teacher.export import mix
from codejury.stage2_core.training.fixer_a.refresh import verify_pilot


def outcome(record, *, solved=False, wrong=False, malformed=False):
    return {
        "record_id": record,
        "solved": solved,
        "accepted": solved or wrong,
        "incorrect_accepted": wrong,
        "malformed": malformed,
    }


def test_strict_executable_improvement_required():
    baseline = [outcome("one", solved=True), outcome("two")]
    assert decision(baseline, {"same": baseline})["selected"] is None
    assert decision(baseline, {"worse": [outcome("one"), outcome("two")]})["selected"] is None
    assert (
        decision(baseline, {"unsafe": [outcome("one", solved=True), outcome("two", wrong=True)]})[
            "selected"
        ]
        is None
    )
    result = decision(
        baseline, {"better": [outcome("one", solved=True), outcome("two", solved=True)]}
    )
    assert result["selected"] == "better"
    assert result["paired_wins"] == ["two"]
    assert result["paired_losses"] == []


def test_new_wrong_acceptance_blocks_higher_solve_count():
    baseline = [outcome(str(i)) for i in range(3)]
    result = decision(
        baseline,
        {
            "unsafe": [
                outcome("0", solved=True),
                outcome("1", solved=True),
                outcome("2", wrong=True),
            ]
        },
    )
    assert result["selected"] is None


def test_mix_is_actual_60_40_replay_with_train_only_provenance():
    _, rows, _ = source(settings("config/stage2_core/teacher.yaml"))
    existing = [r for r in rows if r["split"] == "train"]
    teacher = existing[:20]
    result = mix(existing, teacher)
    assert len(result) == 100
    assert sum(r["origin"] == "groq_verified" for r in result) == 40
    assert sum(r["origin"] == "existing_verified" for r in result) == 60
    assert len({r["base_problem_id"] for r in result if r["origin"] == "existing_verified"}) == 40
    with pytest.raises(ValueError):
        mix(existing, [{**r, "split": "validation"} for r in teacher])
    assert result == mix(existing, teacher)


def test_full_training_cannot_reuse_wrong_or_failed_pilot(tmp_path):
    import json

    path = tmp_path / "pilot.json"
    path.write_text(
        json.dumps(
            {
                "phase": "pilot",
                "status": "pilot_verified",
                "job_identity": "old_data",
                "completed_steps": 20,
                "reload_verified": True,
                "updates_verified": True,
            }
        )
    )
    with pytest.raises(ValueError, match="Matching successful"):
        verify_pilot(path, "new_data", 20)


def test_incomplete_episode_transport_is_quarantined_without_rewriting_raw(tmp_path):
    import json
    import sqlite3

    from codejury.stage2_core.teacher.continue_training import learning_reports

    database = tmp_path / "ledger.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE requests(run_id TEXT,status TEXT,response TEXT)")
        db.executemany(
            "INSERT INTO requests VALUES(?,?,?)",
            [
                ("complete", "settled", json.dumps({"status": "ok"})),
                ("over_context", "settled", json.dumps({"status": "budget_exhausted"})),
            ],
        )
    path = tmp_path / "train.json"
    original = {
        "model_manifest_hash": "test_only",
        "runs": [{"run_id": "complete"}, {"run_id": "over_context"}],
    }
    path.write_text(json.dumps(original))
    before = path.read_bytes()
    derived = learning_reports(tmp_path, [path])
    assert path.read_bytes() == before
    assert json.loads(derived[0].read_text())["runs"] == [{"run_id": "complete"}]
    audit = json.loads((tmp_path / "learning-exclusions.json").read_text())
    assert audit["excluded_count"] == 1
    assert audit["excluded"][0]["response_statuses"] == ["budget_exhausted"]
    assert learning_reports(tmp_path, [path]) == derived
