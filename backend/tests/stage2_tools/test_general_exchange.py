"""CPU checks for S2.10: merge provenance and opportunity-parity audit. No model is trained."""

import json

import pytest

from codejury.stage2_tools import general_exchange_cli as general_cli
from codejury.stage2_tools.general_training.audit import audit
from codejury.stage2_tools.general_training.merge import ROLES, MergeError, merge


def sets(mode="fixture", split="train"):
    return {
        r: {
            "split": split,
            "runtime_mode": mode,
            "records": [
                {"record_id": f"{r}-{i}", "base_problem_id": f"bp{i}", "view": "v", "tokens": 100}
                for i in range(2)
            ],
        }
        for r in ROLES
    }


def test_merge_tags_tasks_and_keeps_provenance():
    m = merge(sets())
    assert m["examples"] == 8 and m["tokens"] == 800 and m["base_problems"] == 2
    assert m["by_task"] == {"action": 2, "repair": 4, "test": 2}
    assert {r["split"] for r in m["records"]} == {"train"}


def test_merge_refuses_non_train_mixed_modes_missing_roles_and_duplicates():
    with pytest.raises(MergeError):
        merge(sets(split="validation"))
    mixed = sets()
    mixed["judge"]["runtime_mode"] = "real"
    with pytest.raises(MergeError):
        merge(mixed)
    partial = sets()
    del partial["judge"]
    with pytest.raises(MergeError):
        merge(partial)
    dup = sets()
    dup["critic"]["records"].append(dup["critic"]["records"][0])
    with pytest.raises(MergeError):
        merge(dup)


def run(examples, tokens, steps, measured=True):
    return {
        "examples": examples,
        "tokens_seen": tokens,
        "optimizer_steps": steps,
        "measured": measured,
    }


def test_audit_uses_actual_tokens_and_flags_disparity():
    roles = {r: run(10, 1000, 50) for r in ROLES}
    assert audit(roles, run(40, 4000, 200), 0.1)["comparable"] is True
    # same example count as roles' sum but far fewer tokens actually seen -> not comparable
    out = audit(roles, run(40, 1500, 200), 0.1)
    assert out["comparable"] is False and out["ratio_general_to_roles"]["tokens_seen"] < 0.5


def test_audit_never_passes_unmeasured():
    roles = {r: run(10, 1000, 50) for r in ROLES}
    assert audit(roles, run(40, 4000, 200, measured=False), 0.1)["status"] == "not_measured"
    roles["critic"] = {"examples": 10}
    out = audit(roles, run(40, 4000, 200), 0.1)
    assert out["status"] == "not_measured" and out["comparable"] is None


def test_cli_validate_pending_then_ok_and_train_pending(tmp_path, capsys):
    cfg = tmp_path / "g.yaml"
    cfg.write_text(
        "schema: stage2-general-config.v1\nparity_tolerance: 0.1\n"
        "role_manifests_dir: x\nout_dir: y\n"
    )
    assert general_cli.main(["validate", "--config", str(cfg), "--manifests", str(tmp_path)]) == 3
    for r, block in sets().items():
        (tmp_path / f"{r}.json").write_text(json.dumps(block))
    assert general_cli.main(["validate", "--config", str(cfg), "--manifests", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out.split("\n", 1)[1])
    assert out["opportunity_audit"]["status"] == "not_measured"
    assert general_cli.main(["train"]) == 3 and general_cli.main(["evaluate"]) == 3
