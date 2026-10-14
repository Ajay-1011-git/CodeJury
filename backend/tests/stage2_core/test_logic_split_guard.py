"""New training implementations must remain disjoint after procedural rewrites."""

import json

import pytest

from codejury.models.worker import file_hash
from codejury.stage2_core.training.split_guard import check_logic_split, filter_logic_split


def pools(tmp_path, train, dev):
    corpus, benchmark = tmp_path / "corpus", tmp_path / "dev"
    corpus.mkdir()
    (benchmark / "private").mkdir(parents=True)
    (corpus / "records.jsonl").write_text(json.dumps(train) + "\n")
    (benchmark / "private/scoring.jsonl").write_text(json.dumps(dev) + "\n")
    return corpus, benchmark


def row(split, base, family, source):
    return {"split": split, "base_problem_id": base, "family_id": family, "correct_source": source}


def test_guard_returns_identity_proof_without_development_examples(tmp_path):
    train = row("train", "train-one", "train-family", "def solve(x):\n return x * 2\n")
    dev = row(
        "development_benchmark",
        "dev-one",
        "dev-family",
        "def solve(x):\n result = []\n for i in range(x):\n  result.append(i)\n return result\n",
    )
    dev["hidden_tests"] = [{"SECRET_EXPECTED": 999}]
    proof = check_logic_split(*pools(tmp_path, train, dev))
    assert proof["status"] == "passed"
    assert "SECRET_EXPECTED" not in json.dumps(proof)


@pytest.mark.parametrize("field", ["base_problem_id", "family_id", "correct_source"])
def test_cross_split_overlap_is_rejected(tmp_path, field):
    train = row("train", "train-one", "train-family", "def solve(x):\n return x * 2\n")
    dev = row("development_benchmark", "dev-one", "dev-family", "def solve(x):\n return [x]\n")
    dev[field] = train[field]
    with pytest.raises(ValueError, match="leaks"):
        check_logic_split(*pools(tmp_path, train, dev))


def test_changing_the_function_name_cannot_bypass_near_duplicate_rejection(tmp_path):
    train = row("train", "train-one", "train-family", "def another_name(x):\n return x * 2\n")
    dev = row("development_benchmark", "dev-one", "dev-family", "def solve(x):\n return x * 2\n")
    with pytest.raises(ValueError):
        check_logic_split(*pools(tmp_path, train, dev))


def test_filter_rejects_changed_execution_filtered_source_before_export(tmp_path, monkeypatch):
    from codejury.stage2_core.training import split_guard

    monkeypatch.setattr("codejury.stage2_core.registry.local_path", lambda p: tmp_path / p)
    source = tmp_path / "artifacts" / "source"
    source.mkdir(parents=True)
    path = source / "train.jsonl"
    path.write_text("validated fixture bytes\n")
    (source / "manifest.json").write_text(json.dumps({"files": {"train.jsonl": file_hash(path)}}))
    path.write_text("tampered fixture bytes\n")
    out = tmp_path / "artifacts" / "out"
    with pytest.raises(ValueError, match="corpus changed"):
        split_guard.filter_logic_split(source, out, tmp_path / "dev")
    assert not out.exists()


def test_filter_excludes_whole_bases_and_preserves_retained_targets(tmp_path, monkeypatch):

    monkeypatch.setattr("codejury.stage2_core.registry.local_path", lambda p: tmp_path / p)
    source = tmp_path / "artifacts" / "source"
    source.mkdir(parents=True)
    records = [
        row(
            "train",
            "keep",
            "train-family",
            """def solve(x):
 result = []
 for i in range(x):
  result.append(i)
 return result
""",
        )
        for _ in range(40)
    ]
    records += [
        row("train", "drop", "other-family", "def solve(x):\n return x * 3\n") for _ in range(2)
    ]
    for r in records:
        r["provenance"] = {"mutations": [{"kind": "trusted fixture corruption"}]}
    chats = [
        {"messages": [{"role": "assistant", "content": f"trusted fixture {i}"}]} for i in range(42)
    ]
    for name, values in (("records.jsonl", records), ("train.jsonl", chats)):
        (source / name).write_text("".join(json.dumps(r) + "\n" for r in values))
    for name in ("valid.jsonl", "generator.py", "decisions.json"):
        (source / name).write_text("trusted fixture bytes\n")
    manifest = {
        "files": {
            name: file_hash(source / name)
            for name in ("train.jsonl", "records.jsonl", "valid.jsonl")
        },
        "splits": {
            "train": {"records": 42, "base_problems": 2},
            "validation": {"records": 1, "base_problems": 1},
        },
    }
    (source / "manifest.json").write_text(json.dumps(manifest))
    dev = tmp_path / "dev"
    (dev / "private").mkdir(parents=True)
    (dev / "private/scoring.jsonl").write_text(
        json.dumps(
            row("development_benchmark", "d", "dev-family", "def solve(x):\n return x * 2\n")
        )
        + "\n"
    )
    original_hash = file_hash(source / "records.jsonl")
    out = tmp_path / "artifacts" / "out"
    result = filter_logic_split(source, out, dev)
    assert result["splits"]["train"] == {"records": 40, "base_problems": 1}
    assert [json.loads(s) for s in (out / "train.jsonl").read_text().splitlines()] == chats[:40]
    assert file_hash(source / "records.jsonl") == original_hash
    assert file_hash(source / "valid.jsonl") == file_hash(out / "valid.jsonl")
