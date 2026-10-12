from fastapi.testclient import TestClient
from test_api_lifecycle import FixtureWorker

from codejury.api.app import create_app
from codejury.storage import Store


def test_static_mount_preserves_api_and_does_not_serve_backend(tmp_path):
    with TestClient(create_app(Store(tmp_path), FixtureWorker())) as client:
        assert "CodeJury" in client.get("/").text
        assert "javascript" in client.get("/src/app.mjs").headers["content-type"]
        assert client.get("/health").json()["schema_version"] == "stage1.v1"
        assert client.get("/examples").status_code == 200
        assert client.get("/backend/config/model.yaml").status_code == 404


def test_api_remains_available_without_web(tmp_path):
    with TestClient(
        create_app(Store(tmp_path), FixtureWorker(), web_dir=tmp_path / "absent")
    ) as client:
        assert client.get("/").json()["service"] == "codejury-stage1"
        assert client.get("/health").status_code == 200
