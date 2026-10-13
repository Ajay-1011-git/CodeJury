"""CPU-checkable parts of S2.08: selection, card freezing and export manifests.

Nothing here trains a model. Training, save/reload and measured role evaluation need MLX hardware
and are pending (see docs/stage2_tools/critic-card.md).
"""

import pytest

from codejury.stage2_tools.critic_training.cards import CardError, build_card, export_manifest
from codejury.stage2_tools.critic_training.selection import SelectionError, select

POLICY = {"min_format_validity": 0.95, "min_domain_validity": 0.9, "max_false_rejection": 0.05}
H = "a" * 64
BASE = {"base_revision_hash": H, "tokenizer_hash": H, "quantization_hash": H, "topology_hash": H}


def metrics(**kw):
    base = {
        "format_validity": 0.99,
        "domain_validity": 0.95,
        "counterexample_yield": 0.5,
        "false_rejection_rate": 0.01,
        "gap_challenge_benefit": 0.2,
        "cost_tokens": 1000,
    }
    return {**base, **kw}


def test_selection_ignores_loss_and_ranks_measured_yield():
    rows = [
        {"step": 100, "metrics": metrics(counterexample_yield=0.4), "validation_loss": 0.1},
        {"step": 200, "metrics": metrics(counterexample_yield=0.6), "validation_loss": 9.0},
    ]
    assert select(rows, POLICY)["selected_step"] == 200


def test_selection_rejects_unmeasured_invalid_and_false_rejecting_checkpoints():
    rows = [
        {"step": 1, "metrics": metrics(gap_challenge_benefit=None)},
        {"step": 2, "metrics": metrics(false_rejection_rate=0.2, counterexample_yield=0.9)},
        {"step": 3, "metrics": metrics(format_validity=0.5)},
        {"step": 4, "metrics": metrics(domain_validity=0.1)},
    ]
    out = select(rows, POLICY)
    assert out["selected_step"] is None and not any(c["eligible"] for c in out["checkpoints"])
    assert "not measured" in out["checkpoints"][0]["reason"]
    with pytest.raises(SelectionError):
        select([rows[0], rows[0]], POLICY)


def test_selection_tie_breaks_on_false_rejection_then_cost():
    rows = [
        {"step": 1, "metrics": metrics(false_rejection_rate=0.03)},
        {"step": 2, "metrics": metrics(false_rejection_rate=0.01)},
    ]
    assert select(rows, POLICY)["selected_step"] == 2


def card(tmp_path, **kw):
    weights = tmp_path / "adapters.bin"
    weights.write_bytes(b"real-weight-bytes")
    args = dict(
        adapter_path=weights,
        base=BASE,
        data_manifest_hash=H,
        config_hash=H,
        train_base_problems=3,
        train_records=9,
        log=[{"step": 10, "train_loss": 1.2, "validation_loss": None}],
        reload_verified=True,
        evaluation_summary="measured",
    )
    return build_card("critic", "completed", **{**args, **kw})


def test_completed_card_needs_real_evidence(tmp_path):
    c = card(tmp_path)
    assert c["steps"] == 10 and len(c["adapter_hash"]) == 64
    with pytest.raises(CardError):
        card(tmp_path, reload_verified=False)
    with pytest.raises(CardError):
        card(tmp_path, log=[])
    with pytest.raises(CardError):
        card(tmp_path, adapter_path=tmp_path / "missing.bin")
    with pytest.raises(CardError):
        card(tmp_path, data_manifest_hash=None)


def test_not_started_card_cannot_claim_training(tmp_path):
    ok = build_card(
        "critic",
        "not_started",
        adapter_path=None,
        base=BASE,
        data_manifest_hash=None,
        config_hash=H,
        train_base_problems=0,
        train_records=0,
        log=[],
        reload_verified=False,
        evaluation_summary="not run",
    )
    assert ok["adapter_hash"] is None and ok["steps"] == 0
    with pytest.raises(CardError):
        build_card(
            "critic",
            "not_started",
            adapter_path=None,
            base=BASE,
            data_manifest_hash=None,
            config_hash=H,
            train_base_problems=0,
            train_records=0,
            log=[{"step": 1, "train_loss": 1, "validation_loss": None}],
            reload_verified=False,
            evaluation_summary="x",
        )


def test_export_manifest_hashes_files_and_refuses_git(tmp_path):
    out = tmp_path / "critic"
    out.mkdir()
    (out / "adapters.bin").write_bytes(b"abc")
    m = export_manifest("critic", out, exchange_id="x", base_revision_hash=H, records=9, bases=3)
    assert m["kind"] == "critic_adapter" and m["files"][0]["size_bytes"] == 3
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "w").mkdir()
    (repo / "w" / "a.bin").write_bytes(b"1")
    with pytest.raises(CardError):
        export_manifest(
            "critic", repo / "w", exchange_id="x", base_revision_hash=H, records=1, bases=1
        )
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(CardError):
        export_manifest("critic", empty, exchange_id="x", base_revision_hash=H, records=1, bases=1)
