"""Frozen wire validation; submitted source is always data, never imported."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_SHA256 = "5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df"
REPO_ROOT = Path(__file__).resolve().parents[4]


class ContractError(ValueError):
    """Missing or invalid frozen contract assets."""


def load_schema(contracts: Path | str | None = None) -> dict:
    directory = Path(contracts) if contracts is not None else REPO_ROOT / "contracts"
    path = directory / "stage1-api.schema.json"
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"Cannot read frozen schema: {path}") from exc
    if hashlib.sha256(content).hexdigest() != SCHEMA_SHA256:
        raise ContractError("Frozen schema checksum mismatch")
    schema = json.loads(content)
    Draft202012Validator.check_schema(schema)
    return schema


def validator(definition: str, contracts: Path | str | None = None) -> Draft202012Validator:
    schema = load_schema(contracts)
    if definition not in schema["$defs"]:
        raise ContractError(f"Unknown wire definition: {definition}")
    return Draft202012Validator({**schema, "$ref": f"#/$defs/{definition}"})


def validate(instance: object, definition: str, contracts: Path | str | None = None) -> None:
    validator(definition, contracts).validate(instance)
