"""Synthetic assets test sealed access/projection; never open the actual final asset."""

import hashlib
import json

import pytest

from codejury.stage2_tools.evaluation import sealed
from codejury.stage2_tools.evaluation.config import config_hash, load


def test_readiness_and_final_freeze_refuse_before_reading_any_file(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(ValueError, match="readiness|Native methods"):
        sealed.load(missing, "validation")
    with pytest.raises(ValueError, match="E4 freeze"):
        sealed.load(missing, "final_assessment", methods_ready=True)


def test_sealed_final_projects_only_visible_facts_and_clusters_variants(tmp_path, monkeypatch):
    private = tmp_path / "data" / "private"
    private.mkdir(parents=True)
    source = tmp_path / "data" / "manifests" / "stage1.json"
    source.parent.mkdir()
    source.write_text("{}")
    row = {
        "split": "stage2_final",
        "record_id": "b-2",
        "base_problem_id": "b",
        "family_id": "synthetic",
        "buggy_source": "def solve(x):\n    return 0\n",
        "contract": "Return x plus one.",
        "domain": [{"kind": "integer", "min": 0, "max": 2, "min_length": None, "max_length": None}],
        "visible_tests": [{"test_id": "visible", "args": [0], "expected": 1}],
        "correct_source": "def solve(x):\n    return x + 1\n",
        "assessment_tests": [{"args": [2], "expected": 3}],
        "provenance": {"kind": "synthetic", "author": "fixture", "license": "CC0"},
        "failure_evidence": [],
        "response_target": {
            "source": "def solve(x):\n    return x + 1\n",
            "diagnosis": "Trusted synthetic fixture",
            "assumptions": [],
        },
    }
    raw = (json.dumps(row) + "\n" + json.dumps({**row, "record_id": "b-1"}) + "\n").encode()
    (private / "stage2_final.jsonl").write_bytes(raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "derived_from": {"sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
                "splits": {
                    "final_assessment": {
                        "asset": "private/stage2_final.jsonl",
                        "records": 2,
                        "base_problems": 1,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "inspected_in_development": False,
                    }
                },
            }
        )
    )
    monkeypatch.setattr(sealed, "local_path", lambda p: tmp_path / p)
    monkeypatch.setattr(sealed, "load_stage1", lambda p: ({}, []))
    tasks, population = sealed.load(manifest, "final_assessment", methods_ready=True, frozen=True)
    assert len(tasks) == 1 and tasks[0].task_id == "b"
    assert population["source_records"] == 2 and population["variants_are_not_independent"]
    request = json.dumps(tasks[0].run_create)
    assert "assessment_tests" not in request and "correct_source" not in request
    assert "return x + 1" not in request and '"expected": 3' not in request
    assert tasks[0].hidden["tests"] == [{"inputs": [2], "expected": 3}]
    (private / "stage2_final.jsonl").write_bytes(raw + b"\n")
    with pytest.raises(ValueError, match="bytes differ"):
        sealed.load(manifest, "final_assessment", methods_ready=True, frozen=True)


def test_method_hash_binds_the_declared_sampling_seeds():
    from pathlib import Path

    config = load(Path(__file__).parents[2] / "config/stage2_tools/evaluation-validation.yaml")
    before = config_hash(config, "CJ", "token_matched")
    config["seeds"] = [11, 23, 41]
    assert before != config_hash(config, "CJ", "token_matched")


def test_consumed_final_asset_cannot_be_reopened_with_another_freeze_name(tmp_path, monkeypatch):
    from codejury.stage2_tools.evaluation import freeze

    # This is a synthetic freeze identity, never native readiness or final evidence.
    record = {"final_asset_hash": "synthetic-fixture"}
    monkeypatch.setattr(freeze, "identity", lambda config, port: record)
    monkeypatch.setattr(freeze, "consumed_marker", lambda r: tmp_path / "shared-consumed")
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    first.write_text(json.dumps(record))
    second.write_text(json.dumps(record))
    assert freeze.verify(first, {}, None)
    with pytest.raises(FileExistsError):
        freeze.verify(second, {}, None)
