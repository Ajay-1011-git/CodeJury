"""Foundation boundary tests, including fail-closed frozen assets."""

import json
import sys

import pytest
from jsonschema import ValidationError

from codejury.contracts import REPO_ROOT, ContractError, load_schema, validate
from codejury.contracts.check import check


def test_python_runtime():
    assert sys.version_info[:2] == (3, 11)


def test_contract_inventory_and_fixture_manifest():
    assert len(load_schema()["$defs"]) == 19
    assert check(REPO_ROOT / "contracts") > 0


def test_missing_or_changed_schema_fails_closed(tmp_path):
    with pytest.raises(ContractError, match="Cannot read"):
        load_schema(tmp_path)
    (tmp_path / "stage1-api.schema.json").write_text("{}")
    with pytest.raises(ContractError, match="checksum"):
        load_schema(tmp_path)


def test_required_nullable_field_and_unknown_field():
    fixture = json.loads((REPO_ROOT / "contracts/fixtures/error.json").read_text())
    validate(fixture, "Error")
    with pytest.raises(ValidationError):
        validate({**fixture, "extra": True}, "Error")
    field = next(iter(fixture))
    del fixture[field]
    with pytest.raises(ValidationError):
        validate(fixture, "Error")


def test_unknown_definition():
    with pytest.raises(ContractError, match="Unknown wire"):
        validate({}, "MadeUp")


def test_fixture_manifest_cannot_escape_directory(tmp_path):
    (tmp_path / "stage1-api.schema.json").write_bytes(
        (REPO_ROOT / "contracts/stage1-api.schema.json").read_bytes()
    )
    (tmp_path / "fixture-manifest.json").write_text('{"../secret.json": "Error"}')
    with pytest.raises(ContractError, match="inside fixtures"):
        check(tmp_path)
