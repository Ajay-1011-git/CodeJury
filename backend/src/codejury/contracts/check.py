"""Validate the checksum and every explicitly declared synthetic fixture."""

import argparse
import json
from pathlib import Path

from jsonschema import ValidationError

from . import SCHEMA_SHA256, ContractError, load_schema, validate


def check(contracts: Path) -> int:
    load_schema(contracts)
    fixtures = contracts / "fixtures"
    manifest = json.loads((contracts / "fixture-manifest.json").read_text())
    if not isinstance(manifest, dict) or not manifest:
        raise ContractError("Fixture manifest must be a nonempty filename-to-definition mapping")
    for filename, definition in sorted(manifest.items()):
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ContractError("Fixture filename must stay inside fixtures/")
        if not isinstance(definition, str):
            raise ContractError("Fixture definitions must be strings")
        path = fixtures / filename
        if path.is_symlink():
            raise ContractError("Fixture symlinks are forbidden")
        validate(json.loads(path.read_text()), definition, contracts)
        print(f"PASS {filename}: {definition}")
    unlisted = {path.name for path in fixtures.glob("*.json")} - manifest.keys()
    if unlisted:
        raise ContractError(f"Unlisted fixtures: {sorted(unlisted)}")
    print(f"PASS schema SHA-256 {SCHEMA_SHA256}; {len(manifest)} fixtures")
    return len(manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contracts", type=Path)
    args = parser.parse_args()
    try:
        check(args.contracts)
    except (ContractError, ValidationError, OSError, ValueError, TypeError) as exc:
        print(f"FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
