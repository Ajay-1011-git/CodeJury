"""Synthetic corpus integrity checks; never open local final assessment data."""

import copy
import hashlib
import json

import pytest

from codejury.stage2_core.contracts import json_hash
from codejury.stage2_core.data import learning_example, load_stage1, validate_records


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
