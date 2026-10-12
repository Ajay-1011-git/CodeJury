"""Build the integration image only after checking the existing isolated CodeJury VM."""

import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from codejury.runner import DockerRunner

ROOT = Path(__file__).resolve().parents[2]
CONTEXT = "colima-codejury-stage1"
TAG = "codejury-stage2-integration:local"


def main():
    evidence = DockerRunner().ready()
    with TemporaryDirectory(prefix="codejury-stage2-image-") as temporary:
        directory = Path(temporary)
        shutil.copyfile(ROOT / "integration/stage2/runner/Dockerfile", directory / "Dockerfile")
        shutil.copyfile(
            ROOT / "backend/src/codejury/stage2_tools/runner/entry.py", directory / "entry.py"
        )
        subprocess.run(
            [
                "docker",
                "--context",
                CONTEXT,
                "build",
                "--platform",
                "linux/arm64",
                "-t",
                TAG,
                str(directory),
            ],
            check=True,
        )
    result = subprocess.run(
        ["docker", "--context", CONTEXT, "image", "inspect", "--format", "{{.Id}}", TAG],
        check=True,
        capture_output=True,
        text=True,
    )
    image = result.stdout.strip()
    if not image.startswith("sha256:") or len(image) != 71:
        raise ValueError("Invalid built image identity")
    print(json.dumps({"status": "built", "image_id": image, "vm": evidence}))


if __name__ == "__main__":
    main()
