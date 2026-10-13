"""Trusted task-shape guards only; no native or fake live training evidence."""

import copy
import json
from pathlib import Path

import pytest

from codejury.stage2_core.registry import local_path
from codejury.stage2_core.training.general import chat, configuration, validate, validate_row


def test_general_task_tag_and_target_schema_must_agree():
    repair = json.loads(local_path("../contracts/stage2-fixtures/repair-draft.json").read_text())
    row = {
        "component": "fixer_a",
        "task": "repair",
        "chat": {**chat("Trusted synthetic shape test", repair), "task_tag": "repair"},
    }
    validate_row(row)
    wrong = {**row, "task": "action"}
    with pytest.raises(ValueError, match="task-tag"):
        validate_row(wrong)
    wrong = copy.deepcopy(row)
    wrong["chat"]["messages"][1]["role"] = "assistant"
    with pytest.raises(ValueError, match="chat prefix"):
        validate_row(wrong)


def test_general_validator_refuses_fixture_or_final_corpus_before_export_read(tmp_path):
    manifest = tmp_path / "manifest.json"
    for mode, final in (("fixture", False), ("live", True)):
        manifest.write_text(
            json.dumps(
                {"role": "general", "runtime_mode": mode, "contains_final_assessment": final}
            )
        )
        with pytest.raises(ValueError, match="final-free"):
            validate(tmp_path)


def test_tools_and_core_general_entrypoints_share_one_configuration():
    backend = Path(__file__).parents[2]
    assert configuration(backend / "config/stage2_tools/training/general.yaml") == configuration(
        backend / "config/stage2_core/training/general.yaml"
    )
