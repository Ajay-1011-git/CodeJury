"""Synthetic corpus integrity checks; never open local final assessment data."""

import copy
import hashlib
import json

import pytest

from codejury.stage2_core.contracts import json_hash
from codejury.stage2_core.data import (
    final_pool_metadata,
    learning_example,
    load_stage1,
    validate_records,
)


def record(split="train"):
    source = (
        "def solve(values):\n    return sum(values)\n"
        if split == "train"
        else ("def solve(values):\n    return sum(x*x for x in values)\n")
    )
    return {
        "record_id": split + "-variant",
        "base_problem_id": split + "-base",
        "family_id": split + "-family",
        "split": split,
        "provenance": {
            "author": "CPU fixture",
            "license": "Fixture only",
            "external_benchmark": False,
            "kind": "synthetic",
            "mutation": "return0",
        },
        "contract": "Sum integers" if split == "train" else "Sum squared integers",
        "domain": [
            {"kind": "list_integer", "min": -10, "max": 10, "min_length": 0, "max_length": 8}
        ],
        "buggy_source": "def solve(values):\n    return 0\n",
        "correct_source": source,
        "visible_tests": [
            {"test_id": "v", "args": [[2]], "expected": 2 if split == "train" else 4}
        ],
        "assessment_tests": [{"test_id": "OFFLINE_TEST_SENTINEL", "args": [[7]], "expected": 7}],
        "failure_evidence": [],
        "response_target": {"source": source, "diagnosis": "Fix", "assumptions": []},
    }


def manifest(tmp_path):
    assets = []
    for split, path in [
        ("train", "train_source/train.jsonl"),
        ("validation", "private/validation.jsonl"),
    ]:
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(record(split)).encode() + b"\n"
        file.write_bytes(content)
        assets.append(
            {
                "path": path,
                "split": split,
                "sha256": hashlib.sha256(content).hexdigest(),
                "records": 1,
                "base_problems": 1,
            }
        )
    # Deliberately missing files: train/validation loader must never open them.
    assets.extend(
        {
            "path": "private/" + split + ".jsonl",
            "split": split,
            "sha256": "a" * 64,
            "records": 100,
            "base_problems": 50,
        }
        for split in ("assessment", "stage2_final")
    )
    value = {"dataset_id": "cpu-fixture", "assets": assets, "seal_sha256": json_hash(assets)}
    path = tmp_path / "manifests/source.json"
    path.parent.mkdir()
    path.write_text(json.dumps(value))
    return path


def test_loader_excludes_final_assets_before_content_access(tmp_path):
    _, rows = load_stage1(manifest(tmp_path))
    assert len(rows) == 2 and {r["split"] for r in rows} == {"train", "validation"}


def test_views_omit_reference_targets_and_offline_tests():
    row = record()
    example = learning_example(row)
    assert "OFFLINE_TEST_SENTINEL" not in example["a_prompt"] + example["b_prompt"]
    assert row["correct_source"] not in example["a_prompt"] + example["b_prompt"]
    assert '"buggy_source"' in example["a_prompt"] and '"buggy_source"' not in example["b_prompt"]
    assert example["target"]["source"] == row["correct_source"]
    assert example["provenance"] == row["provenance"]
    assert learning_example(row) == example  # stable record identities across exports


@pytest.mark.parametrize("identity", ["base_problem_id", "family_id", "correct_source"])
def test_cross_split_base_family_and_renamed_ast_leaks_rejected(identity):
    a, b = record(), record("validation")
    b[identity] = a[identity]
    if identity == "correct_source":
        b[identity] = a[identity].replace("values", "other")
        b["response_target"]["source"] = b[identity]
    with pytest.raises(ValueError, match="leak"):
        validate_records([a, b])


@pytest.mark.parametrize("field", ["split", "license", "extra", "duplicate"])
def test_invalid_provenance_and_schema_rejected(field):
    rows = [record(), record("validation")]
    if field == "split":
        rows[0]["split"] = "stage2_final"
    elif field == "license":
        rows[0]["provenance"]["license"] = ""
    elif field == "extra":
        rows[0]["hidden_reference"] = "x"
    else:
        rows.append(copy.deepcopy(rows[0]))
    with pytest.raises(ValueError):
        validate_records(rows)


def test_hash_tampering_refused(tmp_path):
    path = manifest(tmp_path)
    file = tmp_path / "train_source/train.jsonl"
    file.write_bytes(file.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash"):
        load_stage1(path)


def test_manifest_cannot_disguise_final_asset_as_training(tmp_path):
    path = manifest(tmp_path)
    value = json.loads(path.read_text())
    value["assets"][0]["path"] = "private/stage2_final.jsonl"
    value["seal_sha256"] = json_hash(value["assets"])
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="allowlisted"):
        load_stage1(path)


def test_sft_target_must_be_the_reference_checked_in_the_sandbox():
    row = record()
    row["response_target"]["source"] = "def solve(values):\n    return 999\n"
    with pytest.raises(ValueError, match="sandbox-validated"):
        validate_records([row])


def test_checkpoint_selection_refuses_regressions_and_ignores_training_loss():
    from codejury.stage2_core.training.fixer_a.select import non_regressing, rank

    baseline = {
        "solved": 2,
        "incorrect_accepted": 0,
        "malformed": 2,
        "input_tokens": 1000,
        "output_tokens": 1000,
        "train_loss": 0.1,
    }
    improved = {**baseline, "solved": 3, "malformed": 0, "train_loss": 50.0}
    assert non_regressing(improved, baseline)
    assert rank(improved) < rank(baseline)
    assert not non_regressing({**improved, "incorrect_accepted": 1}, baseline)
    assert not non_regressing({**improved, "malformed": 3}, baseline)
    assert not non_regressing({**improved, "solved": 1}, baseline)


@pytest.mark.parametrize("mutation", [None, "hash", "inspected", "count"])
def test_benchmark_public_seal_is_checked_without_opening_final_files(tmp_path, mutation):
    import yaml

    source_path = manifest(tmp_path)
    source = json.loads(source_path.read_text())
    asset = next(a for a in source["assets"] if a["split"] == "stage2_final")
    public = {
        "schema": "stage2-split-manifest.v1",
        "derived_from": {
            "manifest": str(source_path),
            "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "stage1_seal_sha256": source["seal_sha256"],
        },
        "splits": {
            "final_assessment": {
                "asset": asset["path"],
                "sha256": asset["sha256"],
                "role": "final",
                "inspected_in_development": False,
                "base_problems": asset["base_problems"],
                "records": asset["records"],
            }
        },
    }
    if mutation == "hash":
        public["derived_from"]["sha256"] = "0" * 64
    elif mutation == "inspected":
        public["splits"]["final_assessment"]["inspected_in_development"] = True
    elif mutation == "count":
        public["splits"]["final_assessment"]["records"] = 100.0
    path = tmp_path / "public-seal.json"
    path.write_text(json.dumps(public))
    settings = {
        "version": "stage2.fixer-a-validation.v1",
        "source_manifest": str(source_path),
        "runtime_config": "unused",
        "report_directory": "unused",
        "stage2_final_seal": str(path),
        "max_new_tokens": 1024,
        "seed": 17,
        "training_enabled": False,
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(settings))
    if mutation:
        with pytest.raises(ValueError):
            final_pool_metadata(config_path)
    else:
        receipt = final_pool_metadata(config_path)
        assert receipt["final_contents_opened"] is False
        assert receipt["final_base_problems"] == 50 and receipt["limited_evidence"]
        assert not (tmp_path / "private/stage2_final.jsonl").exists()


@pytest.mark.parametrize("mutation", ["pilot", "batch", "nan", "seed", "checkpoint"])
def test_refresh_refuses_unsafe_or_inconsistent_recipe(mutation):
    from codejury.stage2_core.training.fixer_a.refresh import recipe

    settings = {
        "seed": 17,
        "refresh": {
            "reference_proof": "unused",
            "pilot_steps": 20,
            "steps": 100,
            "save_every": 50,
            "batch_size": 1,
            "max_seq_length": 768,
            "learning_rate": 0.00005,
            "grad_checkpoint": True,
            "seed": 17,
        },
    }
    assert recipe(settings) == settings["refresh"]
    key, value = {
        "pilot": ("pilot_steps", True),
        "batch": ("batch_size", 2),
        "nan": ("learning_rate", float("nan")),
        "seed": ("seed", 29),
        "checkpoint": ("save_every", 30),
    }[mutation]
    settings["refresh"][key] = value
    with pytest.raises(ValueError):
        recipe(settings)


@pytest.mark.parametrize("mutation", ["identity", "reload", "updates", "steps", "phase"])
def test_full_training_refuses_unmatched_or_failed_pilot_before_native_load(tmp_path, mutation):
    from codejury.stage2_core.training.fixer_a.refresh import verify_pilot

    proof = {
        "status": "pilot_verified",
        "phase": "pilot",
        "job_identity": "a" * 64,
        "completed_steps": 20,
        "reload_verified": True,
        "updates_verified": True,
        # Deliberately nonexistent registry: failed proof must be rejected first.
        "registry_path": str(tmp_path / "MUST_NOT_OPEN"),
    }
    key, value = {
        "identity": ("job_identity", "b" * 64),
        "reload": ("reload_verified", False),
        "updates": ("updates_verified", False),
        "steps": ("completed_steps", 9),
        "phase": ("phase", "full"),
    }[mutation]
    proof[key] = value
    path = tmp_path / "pilot.json"
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="pilot/save/reload"):
        verify_pilot(path, "a" * 64, 20)
