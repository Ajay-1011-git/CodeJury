import copy
import json
import runpy

import pytest

from codejury.contracts import REPO_ROOT
from codejury.runner import Result
from codejury.training import data
from codejury.training.data import assert_disjoint, chat_record, normalized, prompt_view


@pytest.fixture
def record():
    return {
        "record_id": "example",
        "base_problem_id": "example",
        "family_id": "sum-family",
        "split": "train",
        "contract": "Return the sum of integers.",
        "domain": [
            {"kind": "list_integer", "min": -10, "max": 10, "min_length": 0, "max_length": 10}
        ],
        "buggy_source": "def solve(values):\n    return 0\n",
        "correct_source": "def solve(values):\n    return sum(values)\n",
        "visible_tests": [{"test_id": "visible", "args": [[1, 2]], "expected": 3}],
        "assessment_tests": [{"test_id": "hidden", "args": [[3]], "expected": 3}],
        "failure_evidence": [
            {
                "test_id": "visible",
                "args": [[1, 2]],
                "result": {
                    "actual_output": 0,
                    "exception_type": None,
                    "input_mutated": False,
                    "duration_ms": 0,
                    "trace": [],
                    "trace_truncated": False,
                },
            }
        ],
        "response_target": {
            "source": "def solve(values):\n    return sum(values)\n",
            "diagnosis": "Fix return corruption.",
            "assumptions": [],
        },
        "provenance": {"kind": "synthetic"},
    }


def test_prompt_target_separation(record):
    assert_disjoint([record])
    chat = chat_record(record)
    prompt = json.loads(chat["messages"][1]["content"])
    assert "correct_source" not in prompt
    assert "assessment_tests" not in prompt
    assert "hidden" not in chat["messages"][1]["content"]
    assert json.loads(chat["messages"][-1]["content"])["source"] == record["correct_source"]
    assert prompt == prompt_view(record)


@pytest.mark.parametrize("field", ["base_problem_id", "family_id", "correct_source"])
def test_split_overlap_rejected(record, field):
    other = copy.deepcopy(record)
    other.update(split="validation", base_problem_id="different", family_id="different")
    if field != "correct_source":
        other["correct_source"] = "def solve(values):\n    return len(values)\n"
        other["response_target"]["source"] = other["correct_source"]
        other[field] = record[field]
    with pytest.raises(ValueError, match="leaks"):
        assert_disjoint([record, other])


def test_alpha_renaming_does_not_hide_near_duplicate():
    assert normalized("def solve(items):\n    return sum(items)\n") == normalized(
        "def solve(values):\n    return sum(values)\n"
    )


@pytest.mark.parametrize("split", ["assessment", "stage2_final"])
def test_sealed_targets_cannot_enter_sft(record, split):
    record["split"] = split
    with pytest.raises(ValueError, match="cannot be exported"):
        chat_record(record)


def test_target_mismatch_and_hidden_failure_rejected(record):
    record["response_target"]["source"] = "def solve(values):\n    return 1\n"
    with pytest.raises(ValueError, match="Completion"):
        assert_disjoint([record])
    record["response_target"]["source"] = record["correct_source"]
    record["failure_evidence"][0]["args"] = [[3]]
    with pytest.raises(ValueError, match="Hidden failure"):
        assert_disjoint([record])


def test_reference_in_failure_rejected(record):
    record["failure_evidence"][0]["result"]["trace"] = [record["correct_source"]]
    with pytest.raises(ValueError, match="Reference source leaked"):
        assert_disjoint([record])


def test_catalog_counts_and_family_partition():
    bases = runpy.run_path(str(REPO_ROOT / "backend/data/train_source/catalog.py"))["catalog"]()
    counts = {
        split: sum(row["split"] == split for row in bases)
        for split in ("train", "validation", "assessment", "stage2_final")
    }
    assert counts == {"train": 40, "validation": 10, "assessment": 10, "stage2_final": 10}
    mapping = {}
    for base in bases:
        assert base["family_id"] not in mapping or mapping[base["family_id"]] == base["split"]
        mapping[base["family_id"]] = base["split"]


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("bad_reference", "reference failed"),
        ("correct_bug", "bug does not fail"),
        ("changed_evidence", "evidence mismatch"),
    ],
)
def test_executable_validation_rejects_bad_records(
    record, monkeypatch, tmp_path, mode, reason, capsys
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    monkeypatch.setattr(data, "load_records", lambda _: ({}, [record]))

    class TestRunner:
        image = "test-only"

        def execute(self, source, name, args):
            reference = "sum" in source
            value = sum(args[0]) if reference else 0
            if mode == "bad_reference" and reference:
                value = -99
            if mode == "correct_bug" and not reference:
                value = sum(args[0])
            if mode == "changed_evidence" and not reference:
                value = 1
            return Result(value, None, False, 0, [], False)

    with pytest.raises(ValueError, match="records rejected"):
        data.validate_data(manifest, TestRunner())
    assert reason in capsys.readouterr().out
