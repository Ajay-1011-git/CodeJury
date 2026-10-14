"""Offline negative overlap check; never returns development targets or tests."""

import ast
import json
from difflib import SequenceMatcher
from pathlib import Path

from codejury.models.worker import file_hash
from codejury.training.data import assert_disjoint, normalized


class OverlapError(ValueError):
    def __init__(self, near):
        self.near = near
        super().__init__("New procedural training targets overlap dev ASTs: " + json.dumps(near))


def normalized_interface(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            node.name = "solve"
    return normalized(ast.unparse(tree))


def check_logic_split(corpus, benchmark):
    corpus, benchmark = Path(corpus), Path(benchmark)
    # Project identity/reference fields immediately. Hidden test values are neither
    # inspected nor returned nor exported. This is a rejection-only split guard.
    fields = ("base_problem_id", "family_id", "split", "correct_source")
    train = [
        {key: row[key] for key in fields}
        for row in map(json.loads, (corpus / "records.jsonl").read_text().splitlines())
    ]
    dev = [
        {key: row[key] for key in fields}
        for row in map(json.loads, (benchmark / "private/scoring.jsonl").read_text().splitlines())
    ]
    if any(r["split"] != "train" for r in train) or any(
        r["split"] != "development_benchmark" for r in dev
    ):
        raise ValueError("Unexpected split in overlap guard")
    assert_disjoint(train + dev, identity_only=True)
    bases = {r["base_problem_id"]: r for r in train}
    near = []
    for row in bases.values():
        norm = normalized_interface(row["correct_source"])
        for other in dev:
            similarity = SequenceMatcher(
                None, norm, normalized_interface(other["correct_source"]), autojunk=False
            ).ratio()
            if similarity >= 0.90:
                near.append({"train": row["base_problem_id"], "dev": other["base_problem_id"]})
    if near:
        raise OverlapError(near)
    return {
        "status": "passed",
        "train_records_hash": file_hash(corpus / "records.jsonl"),
        "development_scoring_hash": file_hash(benchmark / "private/scoring.jsonl"),
        "train_bases": len(bases),
        "dev_bases": len(dev),
        "overlapping_base_ids": [],
        "overlapping_families": [],
        "near_duplicates": [],
        "near_duplicate_threshold": 0.90,
        "function_names_canonicalized": True,
        "sealed_assessment_opened": False,
        "development_tests_or_repairs_exported": False,
        "scope": (
            "Rejection-only identity/family/normalized-reference guard; "
            "no dev examples used for training."
        ),
    }


def filter_logic_split(source, out, benchmark):
    """Conservatively remove whole train bases with similar control-flow ASTs.

    No target is rewritten and no development test or output is admitted.
    The original execution-filtered export remains intact and hash-bound.
    """
    import shutil

    from ..data import write_report
    from ..registry import local_path

    source, out = Path(source).resolve(), Path(out).resolve()
    if local_path("artifacts") not in out.parents:
        raise ValueError("Filtered exports must remain in ignored artifacts")
    manifest = json.loads((source / "manifest.json").read_text())
    if any(file_hash(source / name) != digest for name, digest in manifest["files"].items()):
        raise ValueError("Original execution-filtered corpus changed")
    try:
        check_logic_split(source, benchmark)
        overlaps = []
    except OverlapError as error:
        overlaps = error.near
    excluded = {r["train"] for r in overlaps}
    records = list(map(json.loads, (source / "records.jsonl").read_text().splitlines()))
    chats = list(map(json.loads, (source / "train.jsonl").read_text().splitlines()))
    if len(records) != len(chats):
        raise ValueError("SFT/record order identity mismatch")
    pairs = [
        (r, c) for r, c in zip(records, chats, strict=True) if r["base_problem_id"] not in excluded
    ]
    if len(pairs) < 40:
        raise ValueError("Conservative exclusions leave fewer than 40 training examples")
    out.mkdir(parents=True, exist_ok=False)
    for name, values in (
        ("records.jsonl", [p[0] for p in pairs]),
        ("train.jsonl", [p[1] for p in pairs]),
    ):
        (out / name).write_text(
            "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in values)
        )
    for name in ("valid.jsonl", "generator.py", "decisions.json"):
        shutil.copyfile(source / name, out / name)
    shutil.copyfile(Path(__file__), out / "filter.py")
    proof = check_logic_split(out, benchmark)
    write_report(out / "dev-disjoint.json", proof)
    manifest.update(
        version="stage2.logic-corpus.filtered.v1",
        derived_from={"path": str(source), "manifest_hash": file_hash(source / "manifest.json")},
        conservative_exclusions=overlaps,
        filter_hash=file_hash(out / "filter.py"),
        files={
            name: file_hash(out / name)
            for name in (
                "train.jsonl",
                "valid.jsonl",
                "records.jsonl",
                "decisions.json",
                "generator.py",
                "filter.py",
                "dev-disjoint.json",
            )
        },
        splits={
            **manifest["splits"],
            "train": {
                "records": len(pairs),
                "base_problems": len({p[0]["base_problem_id"] for p in pairs}),
            },
        },
        composed_records=sum(len(p[0]["provenance"]["mutations"]) > 1 for p in pairs),
    )
    write_report(out / "manifest.json", manifest)
    return manifest
