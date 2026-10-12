"""Live factory. Imports no test double; fails closed when the real sandbox is unavailable."""

from pathlib import Path

import yaml

from .port import ToolPortImpl
from .runner.docker import DockerSandbox


def make_tool_port(config_path: Path | str) -> ToolPortImpl:
    config_path = Path(config_path)
    settings = yaml.safe_load(config_path.read_text())
    runner_config = config_path.with_name(settings["runner_config"])
    sandbox = DockerSandbox(runner_config)  # raises InfrastructureError without a built image
    return ToolPortImpl(sandbox)
