import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "handoff_check", Path(__file__).resolve().parents[2] / "tools/stage2_tools/handoff_check.py"
)
hc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hc)


def test_missing_artifacts_are_never_a_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(hc, "ART", tmp_path)
    for gate in (hc.gate_critic_data, hc.gate_benchmark, hc.gate_joint):
        assert gate()[0] != hc.PASSED
    assert hc.gate_card("critic")[0] == hc.MISSING


def test_fixture_data_and_fixture_report_stay_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(hc, "ART", tmp_path)
    (tmp_path / "critic" / "data").mkdir(parents=True)
    (tmp_path / "critic" / "data" / "manifest.json").write_text(
        json.dumps({"fixture": True, "counts": {"records": 3}})
    )
    assert hc.gate_critic_data()[0] == hc.PENDING


def test_not_started_card_is_pending_and_bad_card_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(hc, "ART", tmp_path)
    (tmp_path / "critic").mkdir()
    card = tmp_path / "critic" / "card.json"
    card.write_text(json.dumps({"role": "critic"}))
    assert hc.gate_card("critic")[0] == hc.FAILED


def test_render_lists_every_open_gate_and_blocks_release():
    rows = [
        {"gate": "A", "status": hc.PASSED, "evidence": "ok"},
        {"gate": "B", "status": hc.MISSING, "evidence": "none"},
    ]
    text = hc.render(rows)
    assert "NOT final-releasable" in text and "- B: missing" in text
    assert "NOT final-releasable" not in hc.render(rows[:1])


def test_owner_path_pattern():
    ok = [
        "web/stage2.html",
        "backend/src/codejury/stage2_tools/critic_cli.py",
        "backend/tests/stage2_tools/test_x.py",
        "backend/config/stage2_tools/training/critic.yaml",
    ]
    bad = [
        "backend/src/codejury/api/app.py",
        "contracts/stage2.schema.json",
        "backend/pyproject.toml",
    ]
    assert all(hc.OWNED.match(p) for p in ok)
    assert not any(hc.OWNED.match(p) for p in bad)
