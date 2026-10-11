import os

import pytest

from codejury.models.cli import smoke
from codejury.models.worker import BACKEND

pytestmark = [
    pytest.mark.mac,
    pytest.mark.skipif(
        os.getenv("CODEJURY_MODEL_TESTS") != "1",
        reason="Enable CODEJURY_MODEL_TESTS=1 for real MLX adapter smoke",
    ),
]


def test_actual_adapter_reload_and_clean_switch():
    report = smoke(BACKEND / "config/model.yaml")
    assert report["adapter_sha256"] and report["switch_verified"]
    assert report["candidate_valid"]
