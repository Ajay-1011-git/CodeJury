"""Build the runner from a verified Python patch and pin immutable image digests."""

import json
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CONTEXT = "colima-codejury-stage1"


def docker(*args):
    result = subprocess.run(
        ["docker", "--context", CONTEXT, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    return result


def main():
    tag = "python:3.11.16-slim"
    docker("pull", "--platform", "linux/arm64", tag)
    base = json.loads(docker("image", "inspect", tag).stdout)[0]
    assert base["Architecture"] == "arm64"
    digest = base["RepoDigests"][0]
    with tempfile.TemporaryDirectory(prefix="codejury-build-") as directory:
        context = Path(directory)
        context.joinpath("Dockerfile").write_bytes(
            Path(__file__).with_name("Dockerfile").read_bytes()
        )
        context.joinpath("worker.py").write_bytes(
            (ROOT / "backend/src/codejury/runner/worker.py").read_bytes()
        )
        print(
            docker(
                "build",
                "--platform",
                "linux/arm64",
                "--build-arg",
                f"BASE_IMAGE={digest}",
                "-t",
                "codejury-runner:stage1",
                str(context),
            ).stdout
        )
    image = json.loads(docker("image", "inspect", "codejury-runner:stage1").stdout)[0]
    config = {
        "profile": "stage1-demo",
        "context": CONTEXT,
        "image_id": image["Id"],
        "base_image": digest,
    }
    (ROOT / "backend/config/runner.yaml").write_text(yaml.safe_dump(config))
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
