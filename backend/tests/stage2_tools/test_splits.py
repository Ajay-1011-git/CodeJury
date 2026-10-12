import json

import pytest

from codejury.stage2_tools.eval_cli import build_manifest
from codejury.stage2_tools.evaluation.splits import ROLES, sha256_file, validate_manifest


def write(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def row(base, family, source="def f(x):\n    return x\n"):
    return {"base_problem_id": base, "family_id": family, "correct_source": source}


def manifest_for(tmp_path, assets):
    splits = {}
    for name in ROLES:
        path = tmp_path / f"{name}.jsonl"
        write(path, assets[name])
        bases = {r["base_problem_id"] for r in assets[name]}
        splits[name] = {
            "role": ROLES[name],
            "asset": path.name,
            "sha256": sha256_file(path),
            "base_problems": len(bases),
            "records": len(assets[name]),
        }
    return {"splits": splits}


def disjoint():
    return {
        "train": [row("a", "fa", "def f(x):\n    return x + 1\n")],
        "validation": [row("b", "fb", "def f(x):\n    return x + 2\n")],
        "development_assessment": [row("c", "fc", "def f(x):\n    return x + 3\n")],
        "final_assessment": [
            row("d", "fd", "def f(x):\n    return x + 4\n"),
            row("d", "fd", "def f(x):\n    return x + 4\n"),
        ],
    }


def test_disjoint_verified_splits_pass_and_flag_limited_evidence(tmp_path):
    report = validate_manifest(manifest_for(tmp_path, disjoint()), [tmp_path])
    assert report["status"] == "passed" and report["limited_evidence"] is True
    assert {s["status"] for s in report["splits"].values()} == {"verified"}
    assert report["final_base_problems"] == 1  # two records of one base problem are one problem


@pytest.mark.parametrize("key,value", [("base", "a"), ("family", "fa"), ("cluster", None)])
def test_overlap_in_any_dimension_fails(tmp_path, key, value):
    assets = disjoint()
    leaked = dict(assets["final_assessment"][0])
    if key == "base":
        leaked["base_problem_id"] = value
    elif key == "family":
        leaked["family_id"] = value
    else:
        leaked["correct_source"] = assets["train"][0]["correct_source"]  # near-duplicate source
    assets["final_assessment"] = [leaked]
    report = validate_manifest(manifest_for(tmp_path, assets), [tmp_path])
    assert report["status"] == "failed" and any(
        "final_assessment" in v for v in report["violations"]
    )


def test_hash_count_and_role_tampering_detected(tmp_path):
    m = manifest_for(tmp_path, disjoint())
    m["splits"]["train"]["sha256"] = "0" * 64
    assert any("hash differs" in v for v in validate_manifest(m, [tmp_path])["violations"])
    m = manifest_for(tmp_path, disjoint())
    m["splits"]["validation"]["records"] = 99
    assert any("record count" in v for v in validate_manifest(m, [tmp_path])["violations"])
    m = manifest_for(tmp_path, disjoint())
    m["splits"]["final_assessment"]["inspected_in_development"] = True
    assert any("inspected" in v for v in validate_manifest(m, [tmp_path])["violations"])
    m = manifest_for(tmp_path, disjoint())
    m["splits"]["development_assessment"]["role"] = "final"
    assert validate_manifest(m, [tmp_path])["status"] == "failed"


def test_absent_private_assets_are_unverified_not_verified(tmp_path):
    m = manifest_for(tmp_path, disjoint())
    (tmp_path / "final_assessment.jsonl").unlink()
    report = validate_manifest(m, [tmp_path])
    assert report["splits"]["final_assessment"]["status"] == "unverified_private"
    assert any("NOT verified" in w for w in report["warnings"])


def test_unsafe_paths_and_missing_splits_rejected(tmp_path):
    m = manifest_for(tmp_path, disjoint())
    m["splits"]["train"]["asset"] = "../escape.jsonl"
    with pytest.raises(ValueError, match="Unsafe"):
        validate_manifest(m, [tmp_path])
    with pytest.raises(ValueError, match="exactly"):
        validate_manifest({"splits": {"train": {}}}, [tmp_path])


def test_shipped_manifest_matches_stage1_seal_and_public_pool(tmp_path):
    import shutil

    from .conftest import BACKEND

    manifest = json.loads((BACKEND / "data/stage2_tools/manifests/stage2.json").read_text())
    rebuilt = build_manifest(BACKEND / "data/manifests/stage1.json", BACKEND)
    assert manifest == rebuilt
    # The shared CPU test must not depend on or open an owner's real private holdout.
    train = tmp_path / "train_source"
    train.mkdir()
    shutil.copyfile(BACKEND / "data/train_source/train.jsonl", train / "train.jsonl")
    report = validate_manifest(manifest, [tmp_path])
    assert report["status"] == "passed" and report["splits"]["train"]["status"] == "verified"
    assert report["splits"]["final_assessment"]["status"] == "unverified_private"


def test_normalized_clusters_ignore_empty_new_python_ast_metadata(monkeypatch):
    import ast

    from codejury.stage2_tools.domains import normalized_hash
    source = "def f(x):\n    return x + 1\n"
    expected = normalized_hash(source)
    tree = ast.parse(source)
    function = tree.body[0]
    function._fields = (*function._fields, "type_params")
    function.type_params = []
    monkeypatch.setattr(ast, "parse", lambda _: tree)
    assert normalized_hash(source) == expected
