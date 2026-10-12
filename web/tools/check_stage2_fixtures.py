#!/usr/bin/env python3
"""Validate every stage2 fixture (and the frozen schema hash) for the UI.

  python3 web/tools/check_stage2_fixtures.py --contracts contracts

Needs the `jsonschema` package that the backend already depends on.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA_SHA256 = "ee62388479918f0e33d4085d530dc210356ed104afe6170b1ff03687e53b6ee6"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts", type=Path, default=Path("contracts"))
    args = parser.parse_args()
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("jsonschema is required (the backend environment provides it)", file=sys.stderr)
        return 2
    schema_bytes = (args.contracts / "stage2.schema.json").read_bytes()
    if hashlib.sha256(schema_bytes).hexdigest() != SCHEMA_SHA256:
        print("stage2.schema.json differs from the frozen checksum", file=sys.stderr)
        return 1
    schema = json.loads(schema_bytes)
    fixtures = args.contracts / "stage2-fixtures"
    manifest = json.loads((fixtures / "fixture-manifest.json").read_text())
    if manifest.get("synthetic") is not True:
        print("fixture manifest must declare synthetic data", file=sys.stderr)
        return 1
    failures = 0
    for entry in manifest["fixtures"]:
        record = json.loads((fixtures / entry["filename"]).read_text())
        validator = Draft202012Validator({**schema, "$ref": f"#/$defs/{entry['definition']}"})
        errors = sorted(validator.iter_errors(record), key=lambda e: list(map(str, e.path)))
        if errors:
            failures += 1
            print(f"FAIL {entry['filename']}: {errors[0].message[:160]}")
    print(json.dumps({"fixtures": len(manifest["fixtures"]), "failures": failures,
                      "synthetic": True}))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
