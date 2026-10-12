import copy
import importlib.util
import json

import pytest

from codejury.api.types import queued
from codejury.contracts import REPO_ROOT
from codejury.contracts.intake import source_hash
from codejury.controller.loop import Episode

spec = importlib.util.spec_from_file_location(
    "episode_export", REPO_ROOT / "backend/tools/export_episode.py"
)
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def episode():
    request = json.loads((REPO_ROOT / "contracts/fixtures/run-create.json").read_text())
    snapshot = queued("fixture-episode", mode="fixture")
    snapshot["candidates"] = [
        {
            "candidate_id": "original",
            "parent_id": None,
            "origin": "original",
            "source": request["source"],
            "source_sha256": source_hash(request["source"]),
            "diagnosis": "Baseline",
            "diff": "",
            "eligibility": "rejected",
            "rejection_reason": "Original",
        }
    ]
    snapshot["tests"] = [Episode.supplied(request["supplied_tests"][0])]
    snapshot["executions"] = [
        {
            "execution_id": "e1",
            "candidate_id": "original",
            "test_id": "order",
            "outcome": "fail",
            "actual_output": [1, 2, 3],
            "exception_type": None,
            "input_mutated": False,
            "duration_ms": 1,
            "trace": [],
            "trace_truncated": False,
        }
    ]
    return {
        "request": request,
        "snapshot": snapshot,
        "actions": [{"action": "generate", "source": "fixed_stage1_policy", "role": "fixer_a"}],
    }


def test_visible_export_has_stable_ids_and_drops_offline_fields():
    body = episode()
    body["assessment_tests"] = [{"secret": "hidden marker"}]
    body["correct_source"] = "hidden reference marker"
    body["actions"][0]["offline_reference"] = "hidden marker"
    result = export.visible_episode(body)
    assert "hidden marker" not in json.dumps(result)
    assert "hidden reference marker" not in json.dumps(result)
    assert result["problem_id"].startswith("visible-")
    assert result["actions"][0]["action_id"] == "fixture-episode:action-1"
    assert result["outcomes"][0]["outcome_id"] == "fixture-episode:e1"
    assert result["runtime_mode"] == "fixture"


def test_unknown_authoritative_test_rejected():
    body = episode()
    t = copy.deepcopy(body["snapshot"]["tests"][0])
    t["test_id"] = "private"
    body["snapshot"]["tests"].append(t)
    with pytest.raises(ValueError):
        export.visible_episode(body)


def test_nested_offline_counterexample_content_rejected():
    body = episode()
    body["actions"] = [
        {
            "action": "property_exploration",
            "source": "property_engine",
            "counterexample": {
                "args": [[0, 0]],
                "actual_output": [0, 0],
                "expected": [0],
                "property_id": "unique_preserve_order_ints",
                "oracle_status": "authoritative",
                "hidden_tests": "secret",
            },
        }
    ]
    with pytest.raises(ValueError):
        export.visible_episode(body)


def test_train_join_rejects_assessment_and_unknown_ids():
    body = episode()
    body["request"]["source"] = body["request"]["source"].replace("def unique(", "def solve(")
    body["request"]["function_name"] = "solve"
    body["snapshot"]["candidates"][0].update(
        source=body["request"]["source"], source_sha256=source_hash(body["request"]["source"])
    )
    record = {
        "split": "train",
        "base_problem_id": "train-1",
        "family_id": "train-family",
        "buggy_source": body["request"]["source"],
        "contract": body["request"]["contract_text"],
        "domain": body["request"]["input_domain"],
        "visible_tests": body["request"]["supplied_tests"],
        "assessment_tests": [{"test_id": "training-private-1"}],
    }
    # Exact same visible request requires no inferred approved property in training records.
    body["request"]["approved_property"] = None
    visible = export.visible_episode(body)
    joined = export.join_training_ids([visible], [record])
    assert joined[0]["split"] == "train" and joined[0]["base_problem_id"] == "train-1"
    record["split"] = "assessment"
    with pytest.raises(ValueError):
        export.join_training_ids([visible], [record])
    record["split"] = "train"
    record["contract"] = "Other task"
    with pytest.raises(ValueError):
        export.join_training_ids([visible], [record])


def test_read_only_train_loader_does_not_open_assessment():
    rows = export.train_records(REPO_ROOT / "backend/data/manifests/stage1.json")
    assert len(rows) == 80 and {r["split"] for r in rows} == {"train"}
    assert len({r["base_problem_id"] for r in rows}) == 40


def test_export_refuses_overwrite_and_keeps_fixture_label(tmp_path):
    (tmp_path / "fixture-episode-episode.json").write_text(json.dumps(episode()))
    out = tmp_path / "visible.jsonl"
    result = export.export_runtime(tmp_path, out)
    assert result["episodes"] == 1 and result["runtime_modes"] == ["fixture"]
    with pytest.raises(FileExistsError):
        export.export_runtime(tmp_path, out)


def test_mining_injections_cannot_claim_live(tmp_path):
    with pytest.raises(ValueError, match="labelled fixture"):
        export.mine_train(
            "unused", "unused", tmp_path / "mine.jsonl", model=object(), runner=object()
        )
