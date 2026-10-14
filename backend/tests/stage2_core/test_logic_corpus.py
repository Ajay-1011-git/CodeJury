"""Train-only data admission and AST corruption boundaries; no native execution."""

import ast
from random import Random
from types import SimpleNamespace

import pytest

from codejury.stage2_core.training.logic_corpus import (
    build,
    correct,
    mutate,
    mutation_sites,
    procedural_sources,
    sample_args,
)


def test_corruptions_preserve_signature_and_change_multiple_disjoint_sites():
    source = "def solve(values):\n result = 0\n for x in values:\n  result += x\n return result\n"
    sites = mutation_sites(source)
    loop = next(s for s in sites if s["kind"] == "missed_last_iteration")
    initial = next(s for s in sites if s["kind"] == "boundary_constant")
    update = next(s for s in sites if s["kind"] == "operator_swap")
    corrupted = mutate(source, [loop, initial])
    original, changed = ast.parse(source).body[0], ast.parse(corrupted).body[0]
    assert ast.dump(original.args) == ast.dump(changed.args)
    assert len(changed.body) == len(original.body)
    assert "result = 1" in corrupted and "list(values)[:-1]" in corrupted
    with pytest.raises(ValueError, match="Overlapping"):
        mutate(source, [loop, update])
    with pytest.raises(ValueError, match="distinct"):
        mutate(source, [initial, initial])


def test_procedural_targets_remain_multiline_and_not_stub_replacements():
    for body in procedural_sources().values():
        assert "for " in body and len(body.splitlines()) >= 4
    assert "range_width" in procedural_sources()
    assert "gcd" not in procedural_sources()  # validation family stays separate


def test_only_pure_type_correct_sandbox_results_can_admit_targets():
    result = SimpleNamespace(exception_type=None, input_mutated=False, actual_output=1)
    assert correct(result, 1)
    assert not correct(result, True)
    result.input_mutated = True
    assert not correct(result, 1)
    result.input_mutated = False
    result.exception_type = "TimeoutError"
    assert not correct(result, 1)


def test_sampling_stays_inside_the_inherited_domain():
    domains = [
        {"kind": "integer", "min": 2, "max": 4},
        {"kind": "list_integer", "min": -2, "max": 2, "min_length": 1, "max_length": 3},
    ]
    rng = Random(17)
    for _ in range(100):
        scalar, items = sample_args(domains, rng)
        assert 2 <= scalar <= 4 and 1 <= len(items) <= 3
        assert all(-2 <= x <= 2 for x in items)
    with pytest.raises(ValueError, match="inherited"):
        sample_args([{"kind": "float"}], rng)


def test_exports_cannot_be_written_outside_private_artifacts(tmp_path):
    with pytest.raises(ValueError, match="ignored artifacts"):
        build(tmp_path / "public", object())


def test_bad_reference_stops_before_any_sft_export(tmp_path, monkeypatch):
    import codejury.stage2_core.training.logic_corpus as module

    monkeypatch.setattr(module, "local_path", lambda p: tmp_path / p)
    row = {
        "base_problem_id": "total",
        "split": "train",
        "correct_source": "def solve(values):\n return sum(values)\n",
        "domain": [{"kind": "list_integer", "min": -2, "max": 2, "min_length": 0, "max_length": 2}],
        "visible_tests": [{"args": [[1]], "expected": 1}],
        "assessment_tests": [{"args": [[2]], "expected": 2}],
    }
    monkeypatch.setattr(module, "load_stage1", lambda p: ({}, [row]))
    monkeypatch.setattr(
        module,
        "procedural_sources",
        lambda: {"total": "result = 0\nfor x in values:\n    result += x\nreturn result"},
    )

    class IncorrectReference:
        def ready(self):
            pass

        def execute_many(self, source, name, args):
            # Explicit trusted fixture failures, no source execution on the host.
            return [
                SimpleNamespace(exception_type=None, input_mutated=False, actual_output=999)
                for _ in args
            ]

    out = tmp_path / "artifacts" / "logic"
    with pytest.raises(ValueError, match="reference failed"):
        build(out, IncorrectReference())
    assert not (out / "train.jsonl").exists()
    assert not (out / "manifest.json").exists()


def test_offline_runtime_view_preserves_training_interface_names():
    import copy

    from codejury.stage2_core.data import learning_example, load_stage1, runtime_example
    from codejury.stage2_core.registry import local_path

    _, rows = load_stage1(local_path("data/manifests/stage1.json"))
    row = copy.deepcopy(rows[0])
    row["buggy_source"] = row["buggy_source"].replace("def solve(", "def total(", 1)
    row["correct_source"] = row["correct_source"].replace("def solve(", "def total(", 1)
    row["response_target"]["source"] = row["correct_source"]
    problem, _ = runtime_example(row)
    example = learning_example(row)
    assert problem["function_name"] == "total"
    assert problem["signature"] == "total(values)"
    assert '"function_name":"total"' in example["a_prompt"]
    assert '"function_name":"total"' in example["b_prompt"]
    assert "def total(values)" in example["target"]["source"]
