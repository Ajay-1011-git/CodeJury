"""Independent check of the frozen stage2.v1 contract assets (read-only)."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .codec import errors, validate
from .codec.wire import REPO_ROOT, SCHEMA_SHA256
from .port.verify import ResultError, verify_result

STAGE1_SHA256 = "5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df"
PORTS_SHA256 = "524d0c0a5970fa6c46ee3137d1fa2c5b5bd13a0fa6e40d2f9abef66c6d157cd4"
TOOL_PAIRS = ("validate", "evaluate", "search", "audit", "investigate")


def _bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing or symlinked asset: {path}")
    return path.read_bytes()


def check(contracts: Path) -> dict:
    sha = lambda data: hashlib.sha256(data).hexdigest()  # noqa: E731
    schema_bytes = _bytes(contracts / "stage2.schema.json")
    if sha(schema_bytes) != SCHEMA_SHA256:
        raise ValueError("stage2.schema.json checksum differs from the frozen value")
    if _bytes(contracts / "STAGE2-SHA256SUMS").decode().split() != [
        SCHEMA_SHA256,
        "stage2.schema.json",
    ]:
        raise ValueError("STAGE2-SHA256SUMS does not record the frozen schema")
    for relative in ("stage1-api.schema.json", "legacy/stage1-v1-api.schema.json"):
        if sha(_bytes(contracts / relative)) != STAGE1_SHA256:
            raise ValueError(f"Original Stage 1 schema changed: {relative}")
    ports = _bytes(contracts / "shared/stage2_ports.py")
    installed = _bytes(REPO_ROOT / "backend/src/codejury/stage2_ports.py")
    if sha(ports) != PORTS_SHA256 or ports != installed:
        raise ValueError("Frozen Python ports differ between contracts/ and the backend copy")
    fixtures = contracts / "stage2-fixtures"
    manifest = json.loads(_bytes(fixtures / "fixture-manifest.json"))
    if manifest.get("synthetic") is not True:
        raise ValueError("Fixture manifest must disclose synthetic data")
    checked = 0
    for entry in manifest["fixtures"]:
        problems = errors(
            json.loads(_bytes(fixtures / entry["filename"])), entry["definition"], contracts
        )
        if problems:
            raise ValueError(f"{entry['filename']}: {problems[0]}")
        checked += 1
    pairs, notes = 0, []
    for op in TOOL_PAIRS:
        request = json.loads(_bytes(fixtures / f"tool-{op}-request.json"))
        result = json.loads(_bytes(fixtures / f"tool-{op}-result.json"))
        validate(request, "ToolRequest", contracts)
        try:
            verify_result(request, result, contracts)
            pairs += 1
        except ResultError as exc:
            notes.append(f"{op}: {exc}")
    return {
        "status": "passed",
        "schema_sha256": SCHEMA_SHA256,
        "ports_sha256": PORTS_SHA256,
        "definitions": len(json.loads(schema_bytes)["$defs"]),
        "synthetic_fixtures_validated": checked,
        "tool_fixture_pairs_conformant": pairs,
        "tool_fixture_pair_notes": notes,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="contract_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check")
    c.add_argument("--contracts", type=Path, default=REPO_ROOT / "contracts")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(check(args.contracts), indent=2))
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
