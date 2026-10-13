import copy
import json
from types import SimpleNamespace

import pytest

from codejury.stage2_core.data import learning_example
from codejury.stage2_core.teacher.collect import remote_prompt, selected_rows, settings, source
from codejury.stage2_core.teacher.validate import edge_inputs, structural, verify


def training_row():
    _, rows, _ = source(settings("config/stage2_core/teacher.yaml"))
    return copy.deepcopy(selected_rows(rows)[0])


def test_prompt_excludes_private_values():
    row = training_row()
    row["correct_source"] = "PRIVATE_REFERENCE_SENTINEL"
    row["assessment_tests"] = [{"secret": "PRIVATE_ASSESSMENT_SENTINEL"}]
    row["response_target"] = {"secret": "PRIVATE_TARGET_SENTINEL"}
    prompt = remote_prompt(row)
    assert "PRIVATE_" not in prompt
    assert "buggy_source" in prompt
    assert "supplied" not in json.loads(prompt)  # exact runtime projection, not full dataset row


@pytest.mark.parametrize("split", ["validation", "stage2_final", "final_assessment"])
def test_nontraining_rejected(split):
    row = training_row()
    row["split"] = split
    with pytest.raises(ValueError):
        remote_prompt(row)


def test_unique_bases_and_bounded_variants():
    _, rows, _ = source(settings("config/stage2_core/teacher.yaml"))
    selected = selected_rows(rows)
    assert len(selected) == len({r["base_problem_id"] for r in selected}) == 20
    assert all(r["split"] == "train" for r in selected)
    assert len({r["family_id"] for r in selected}) > 1
    assert selected == selected_rows(list(reversed(rows)))


def test_structural_quarantines_scope_signature_assumptions():
    row = training_row()
    draft = learning_example(row)["target"]
    for change in [
        {"source": "def other(x):\n    return x"},
        {"assumptions": ["Invented precondition"]},
        {"requirement_ids": ["unknown"]},
        {"source": 'def solve(x):\n    return open("/etc/passwd").read()'},
    ]:
        with pytest.raises(ValueError):
            structural(row, {**draft, **change})


def test_trusted_failure_or_mutation_rejected():
    row = training_row()
    draft = learning_example(row)["target"]
    # Use known shape independent of the selected operation, with a fake runner only in unit test.
    draft["source"] = row["buggy_source"]
    values = {
        json.dumps(t["args"]): t["expected"] for t in row["visible_tests"] + row["assessment_tests"]
    }

    class Runner:
        def execute_many(self, source_text, name, inputs):
            return [
                SimpleNamespace(
                    actual_output=values.get(json.dumps(args)),
                    exception_type=None,
                    input_mutated=source_text == draft["source"],
                )
                for args in inputs
            ]

    with pytest.raises(ValueError, match="training_test_failure"):
        verify(row, draft, Runner())


def test_edges_obey_reviewed_domains():
    from codejury.contracts.intake import validate_args

    _, rows, _ = source(settings("config/stage2_core/teacher.yaml"))
    for row in selected_rows(rows):
        for args in edge_inputs(row):
            validate_args(args, row["domain"])
