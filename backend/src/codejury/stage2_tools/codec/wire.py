"""Validate records against named definitions of the frozen stage2.v1 schema."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_SHA256 = "ee62388479918f0e33d4085d530dc210356ed104afe6170b1ff03687e53b6ee6"
REPO_ROOT = Path(__file__).resolve().parents[5]


class ContractError(ValueError):
    """Missing, changed or unknown frozen contract assets."""


def schema_hash(contracts: Path | str | None = None) -> str:
    return hashlib.sha256(_read(contracts)).hexdigest()


def _read(contracts: Path | str | None) -> bytes:
    path = (Path(contracts) if contracts is not None else REPO_ROOT / "contracts")
    path = path / "stage2.schema.json"
    try:
        if path.is_symlink():
            raise ContractError("Contract asset must not be a symlink")
        return path.read_bytes()
    except OSError as exc:
        raise ContractError(f"Cannot read Stage 2 schema: {path}") from exc


@lru_cache(maxsize=4)
def _validators(content: bytes) -> tuple[dict, dict]:
    if hashlib.sha256(content).hexdigest() != SCHEMA_SHA256:
        raise ContractError("Stage 2 schema checksum mismatch")
    schema = json.loads(content)
    Draft202012Validator.check_schema(schema)
    return schema, {}


def load_schema(contracts: Path | str | None = None) -> dict:
    schema, _ = _validators(_read(contracts))
    return schema


def validate(record: object, definition: str, contracts: Path | str | None = None) -> None:
    schema, cache = _validators(_read(contracts))
    if definition not in schema["$defs"]:
        raise ContractError(f"Unknown Stage 2 definition: {definition}")
    if definition not in cache:
        cache[definition] = Draft202012Validator({**schema, "$ref": f"#/$defs/{definition}"})
    cache[definition].validate(record)
