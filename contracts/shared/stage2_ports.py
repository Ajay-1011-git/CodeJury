"""Frozen Stage 2 Python interfaces. No model/tool implementations live here."""
from typing import Any, Protocol
from threading import Event

Record = dict[str, Any]

class ModelPort(Protocol):
    def generate(self, request: Record, cancel: Event) -> Record:
        """ModelRequest -> ModelResponse; validates both sides, actual usage only."""
        ...

class ToolPort(Protocol):
    def call(self, request: Record, cancel: Event) -> Record:
        """ToolRequest -> ToolResult; no candidate execution on the host."""
        ...

class RolloutPort(Protocol):
    def continue_episode(self, request: Record, cancel: Event) -> Record:
        """RolloutRequest -> RolloutResult; training-only isolated fork, no hidden labels."""
        ...

class BaselinePort(Protocol):
    def run(self, request: Record, cancel: Event) -> Record:
        """MethodRequest -> MethodResult; commits answer before external hidden scoring."""
        ...
