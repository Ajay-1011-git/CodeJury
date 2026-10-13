import copy
import hashlib
import json

import pytest
from hostsandbox import FixtureHostSandbox

from codejury.stage2_tools.codec import errors, sha256_text
from codejury.stage2_tools.critic_training.data import config as cconfig
from codejury.stage2_tools.critic_training.data import pipeline
from codejury.stage2_tools.critic_training.data.episodes import IntakeError, load_set
from codejury.stage2_tools.critic_training.data.prompt import (
    PromptLeak,
    build_prompt,
    guard_prompt,
)
from codejury.stage2_tools.critic_training.data.situations import classify
from codejury.stage2_tools.critic_training.data.targets import (
    invalid_variants,
    no_objection,
    validate_draft,
)

GOOD = (
    "def sum_values(values):\n    total = 0\n    for v in values:\n"
    "        total += v\n    return total\n"
)
BAD = "def sum_values(values):\n    return sum(v for v in values if v > 0)\n"
BAD2 = "def sum_values(values):\n    return sum(v for v in values if v >= 0) + 0\n"
CONFIG = {
    "schema": "stage2-critic-config.v1",
    "data": {
        "split": "train",
        "mode_priority": ["discriminate", "challenge_agreement", "audit_gap", "validate_revision"],
        "invalid_variants_per_episode": 2,
        "mix_targets": {"correct_candidate_min": 0.25, "invalid_proposal_min": 0.10},
    },
}
DRAFT = {
    "mode": "discriminate",
    "requirement_ids": ["sum-all"],
    "generator_spec": None,
    "concrete_inputs": [[[-1]], [[-2, 1]]],
    "oracle_spec": {"kind": "property", "property_id": "sum_ints", "parameters": {}},
    "target_candidate_ids": ["c-a", "c-b"],
    "rationale": "Negative values separate the candidates.",
}


@pytest.fixture
def base(fixture):
    return fixture("episode-bundle")


def with_sources(base, run_id, src_a, src_b, gaps=False):
    b = copy.deepcopy(base)
    b["run_id"] = run_id
    for cid, src in (("c-a", src_a), ("c-b", src_b)):
        c = next(x for x in b["candidates"] if x["candidate_id"] == cid)
        c["source"], c["source_hash"] = src, sha256_text(src)
    # runtime-visible behaviour: distinct outputs when sources differ
    for e in b["executions"]:
        if e["candidate_id"] in ("c-a", "c-b"):
            src = src_a if e["candidate_id"] == "c-a" else src_b
            e["actual_output"] = 0 if src == BAD else 1
    if not gaps:
        b["audit_gaps"] = []
    return b


def write_set(root, items, mode="fixture", split="train", labels_kind="reviewed"):
    root.mkdir(parents=True, exist_ok=True)
    rows, labels = [], []
    for i, (bundle, truth, drafts, base_id) in enumerate(items):
        name = f"ep{i}.json"
        text = json.dumps(bundle, sort_keys=True)
        (root / name).write_text(text)
        rows.append(
            {
                "path": name,
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "base_problem_id": base_id,
                "family_id": f"fam-{base_id}",
                "provenance": "synthetic",
            }
        )
        labels.append(
            {
                "run_id": bundle["run_id"],
                "reference_source": GOOD,
                "candidate_truth": truth,
                "drafts": drafts,
            }
        )
    (root / "labels.json").write_text(
        json.dumps(
            {"schema": "stage2-critic-labels.v1", "source_kind": labels_kind, "labels": labels}
        )
    )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "stage2-episode-set.v1",
                "runtime_mode": mode,
                "split": split,
                "labels": "labels.json",
                "episodes": rows,
            }
        )
    )
    return root


SPLITS = {
    "splits": {
        "train": {"base_problem_ids": ["bp1", "bp2", "bp3"]},
        "validation": {"base_problem_ids": ["vp1"]},
        "final_assessment": {"base_problem_ids": ["fp1"]},
    }
}


def test_config_rejects_final_and_unknown(tmp_path):
    p = tmp_path / "c.yaml"
    import yaml

    bad = copy.deepcopy(CONFIG)
    bad["data"]["split"] = "final_assessment"
    p.write_text(yaml.safe_dump(bad))
    with pytest.raises(cconfig.ConfigError):
        cconfig.load(p)


def test_situations(base):
    disagree = with_sources(base, "r1", BAD, GOOD)
    truth = {"c-a": False, "c-b": True}
    assert "disagreement" in classify(disagree, truth)
    shared = with_sources(base, "r2", BAD, BAD)
    assert classify(shared, {"c-a": False, "c-b": False})[0] == "shared_incorrect_agreement"
    ok = with_sources(base, "r3", GOOD, GOOD)
    assert classify(ok, {"c-a": True, "c-b": True}) == ["correct_candidate"]
    gap = with_sources(base, "r4", GOOD, GOOD, gaps=True)
    assert "mutation_gap" in classify(gap, {"c-a": True, "c-b": True})


def test_prompt_holds_runtime_view_only_and_guard_catches_leaks(base):
    b = with_sources(base, "r1", BAD, GOOD)
    prompt = build_prompt(b, "discriminate")
    assert "contract_text" in prompt and BAD[:20] in prompt.replace("\\n", "\n")
    guard_prompt(prompt, b, [GOOD, DRAFT["rationale"]])
    with pytest.raises(PromptLeak):
        guard_prompt(prompt + DRAFT["rationale"], b, [DRAFT["rationale"]])
    with pytest.raises(PromptLeak):
        guard_prompt(prompt.replace('"mode"', '"reference_solution"'), b, [])


def test_execution_filter_accepts_valid_and_rejects_the_rest(base):
    sb = FixtureHostSandbox()
    b = with_sources(base, "r1", BAD, BAD2)
    ok, why, stats = validate_draft(sb, b, DRAFT, GOOD)
    assert ok and stats["failures"] >= 1, why
    # a model literal is never an authorized counterexample, even when empirically right
    literal = {**DRAFT, "oracle_spec": {"kind": "literal", "expected": -1}}
    assert not validate_draft(sb, b, literal, GOOD)[0]
    # no failing candidate -> no counterexample
    fine = with_sources(base, "r2", GOOD, GOOD)
    assert not validate_draft(sb, fine, DRAFT, GOOD)[0]
    # a wrong reference cannot validate a draft
    assert not validate_draft(sb, b, DRAFT, BAD)[0]
    # both/neither proposal sources is illegal
    assert not validate_draft(sb, b, {**DRAFT, "concrete_inputs": None}, GOOD)[0]


def test_no_objection_is_valid_observation_never_null_null(base):
    d = no_objection(with_sources(base, "r", GOOD, GOOD), "discriminate")
    assert errors(d, "CriticDraft") == []
    assert d["oracle_spec"]["kind"] == "observation"
    assert (d["generator_spec"] is None) != (d["concrete_inputs"] is None)
    assert "proof" in d["rationale"] and "not proof" in d["rationale"]


def test_invalid_variants_are_really_rejected_by_the_gate(base):
    b = with_sources(base, "r", BAD, BAD2)
    kinds = {v["kind"] for v in invalid_variants(b, DRAFT)}
    assert {"out_of_domain", "unregistered_property", "conflicting_literal"} <= kinds
    sb = FixtureHostSandbox()
    for v in invalid_variants(b, DRAFT):
        assert not validate_draft(sb, b, {**v["proposal"], "target_candidate_ids": ["c-a"]}, GOOD)[
            0
        ]


def test_collect_validate_roundtrip_and_mix(tmp_path, base):
    items = [
        (
            with_sources(base, "r1", BAD, BAD),
            {"c-a": False, "c-b": False},
            [{**DRAFT, "mode": "challenge_agreement"}],
            "bp1",
        ),
        (with_sources(base, "r2", GOOD, GOOD), {"c-a": True, "c-b": True}, [], "bp2"),
        (with_sources(base, "r3", BAD, GOOD), {"c-a": False, "c-b": True}, [DRAFT], "bp3"),
        (
            with_sources(base, "r4", BAD, BAD),
            {"c-a": False, "c-b": False},
            [{**DRAFT, "mode": "challenge_agreement", "concrete_inputs": [[[3]]]}],
            "bp1",
        ),
    ]
    root = write_set(tmp_path / "set", items)
    out = tmp_path / "out"
    m = pipeline.collect(CONFIG, SPLITS, root, FixtureHostSandbox(), out, runtime_mode="fixture")
    c = m["counts"]
    assert m["fixture"] is True and c["no_objection_correct_candidate"] == 1
    assert c["counterexample"] == 2  # r4's draft never fails a candidate -> rejected, with reason
    assert any(r["stage"] == "execution" and r["run_id"] == "r4" for r in m["rejected"])
    assert c["invalid_proposal"] > 0
    assert pipeline.validate(out, SPLITS, runtime_mode="fixture") == []
    # tampering is detected
    lines = (out / "records.jsonl").read_text().splitlines()
    rec = json.loads(lines[0])
    rec["prompt"] += " "
    (out / "records.jsonl").write_text("\n".join([json.dumps(rec), *lines[1:]]) + "\n")
    assert pipeline.validate(out, SPLITS, runtime_mode="fixture")


def test_fixture_and_real_never_mix(tmp_path, base):
    root = write_set(
        tmp_path / "s",
        [(with_sources(base, "r", GOOD, GOOD), {"c-a": True, "c-b": True}, [], "bp1")],
    )
    with pytest.raises(IntakeError):
        load_set(root, SPLITS, split="train", runtime_mode="real")
    real = write_set(
        tmp_path / "t",
        [(with_sources(base, "r", GOOD, GOOD), {"c-a": True, "c-b": True}, [], "bp1")],
        mode="real",
    )
    with pytest.raises(IntakeError):
        load_set(real, SPLITS, split="train", runtime_mode="fixture")


def test_real_intake_enforces_split_hash_and_path_safety(tmp_path, base):
    items = [
        (with_sources(base, "r1", GOOD, GOOD), {"c-a": True, "c-b": True}, [], "fp1"),  # final leak
        (with_sources(base, "r2", GOOD, GOOD), {"c-a": True, "c-b": True}, [], "bp1"),
    ]
    root = write_set(tmp_path / "s", items, mode="real")
    got = load_set(root, SPLITS, split="train", runtime_mode="real")
    assert [e.bundle["run_id"] for e in got.episodes] == ["r2"]
    assert "not in the declared split" in got.rejected[0]["reason"]
    (root / "ep1.json").write_text("{}")
    got = load_set(root, SPLITS, split="train", runtime_mode="real")
    assert any("hash mismatch" in r["reason"] for r in got.rejected)
    idx = json.loads((root / "manifest.json").read_text())
    idx["episodes"][0]["path"] = "../x.json"
    (root / "manifest.json").write_text(json.dumps(idx))
    assert any(
        "Unsafe path" in r["reason"]
        for r in load_set(root, SPLITS, split="train", runtime_mode="real").rejected
    )
    with pytest.raises(IntakeError):
        load_set(root, SPLITS, split="validation", runtime_mode="real")


def test_teacher_drafts_without_sandbox_are_pending_not_accepted(tmp_path, base):
    items = [(with_sources(base, "r1", BAD, GOOD), {"c-a": False, "c-b": True}, [DRAFT], "bp1")]
    root = write_set(tmp_path / "s", items, labels_kind="teacher_filtered")
    m = pipeline.collect(CONFIG, SPLITS, root, None, tmp_path / "o", runtime_mode="fixture")
    assert m["counts"]["records"] == 0 and m["rejected"][0]["stage"] == "execution"


def test_cli_train_evaluate_export_report_pending(capsys):
    from codejury.stage2_tools import critic_cli

    for cmd in ("train", "evaluate", "export"):
        assert critic_cli.main([cmd]) == 3
    assert "pending" in capsys.readouterr().out
