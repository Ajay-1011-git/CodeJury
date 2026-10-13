import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

from codejury.stage2_core import registry
from codejury.stage2_core.teacher.continue_training import write_config

SPEC = importlib.util.spec_from_file_location(
    "training_snapshot",
    Path(__file__).resolve().parents[2] / "tools/stage2_core/training_snapshot.py",
)
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)


def archive(tmp_path, *, corrupt=False, missing=False):
    name = "backend/artifacts/teacher/budget.bin"
    original = b"immutable-ledger-bytes"
    manifest = {
        "version": "codejury.training-snapshot.v1",
        "original_root": "/Users/original/CodeJury",
        "source_files": {},
        "files": {name: {"size": len(original), "sha256": hashlib.sha256(original).hexdigest()}},
    }
    path = tmp_path / "snapshot.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        contents = {snapshot.MANIFEST: json.dumps(manifest).encode()}
        if not missing:
            contents[name] = b"x" * len(original) if corrupt else original
        for key, value in contents.items():
            info = tarfile.TarInfo(key)
            info.size = len(value)
            tar.addfile(info, io.BytesIO(value))
    return path, name, original


def test_restore_keeps_identical_bytes_and_can_repeat(tmp_path):
    path, name, original = archive(tmp_path)
    checkout = tmp_path / "checkout"
    assert snapshot.verify(path, checkout, restore=True)["restored"]
    assert (checkout / name).read_bytes() == original
    snapshot.verify(path, checkout, restore=True)


@pytest.mark.parametrize("reason", ["corrupt", "missing"])
def test_restore_rejects_incomplete_or_changed_archive_before_writing(tmp_path, reason):
    path, _, _ = archive(tmp_path, **{reason: True})
    checkout = tmp_path / "checkout"
    with pytest.raises(ValueError):
        snapshot.verify(path, checkout, restore=True)
    assert not checkout.exists()


def test_restore_refuses_different_existing_training(tmp_path):
    path, name, _ = archive(tmp_path)
    checkout = tmp_path / "checkout"
    target = checkout / name
    target.parent.mkdir(parents=True)
    target.write_bytes(b"other-experiment")
    with pytest.raises(ValueError, match="overwrite"):
        snapshot.verify(path, checkout, restore=True)
    assert target.read_bytes() == b"other-experiment"


def test_relocation_preserves_configs_and_does_not_remap_neighbor(tmp_path, monkeypatch):
    original = Path("/Users/original/CodeJury")
    monkeypatch.setenv("CODEJURY_STAGE2_ORIGINAL_ROOT", str(original))
    monkeypatch.setattr(registry, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(registry, "BACKEND", tmp_path / "backend")
    assert registry.local_path(original / "backend/artifacts/a") == tmp_path / "backend/artifacts/a"
    neighbor = Path("/Users/original/CodeJury-other/backend/artifacts/a")
    assert registry.local_path(neighbor) == neighbor
    cfg = tmp_path / "preserved.yaml"
    cfg.write_text("registry: /Users/original/CodeJury/backend/artifacts/a\nsteps: 100\n")
    before = cfg.read_bytes()
    write_config(cfg, {"registry": str(tmp_path / "backend/artifacts/a"), "steps": 100})
    assert cfg.read_bytes() == before
    with pytest.raises(ValueError, match="configuration changed"):
        write_config(cfg, {"registry": str(tmp_path / "backend/artifacts/a"), "steps": 200})
