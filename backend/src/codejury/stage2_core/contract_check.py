"""Check the frozen Stage 2 assets separately from original Stage 1 fixtures."""

import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_HASH = "ee62388479918f0e33d4085d530dc210356ed104afe6170b1ff03687e53b6ee6"
STAGE1_HASH = "5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df"
PORTS_HASH = "524d0c0a5970fa6c46ee3137d1fa2c5b5bd13a0fa6e40d2f9abef66c6d157cd4"


def read_asset(path: Path) -> bytes:
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError(f"Missing or symlink contract asset: {path.name}")
    return path.read_bytes()


@lru_cache(maxsize=2)
def _schema(content: bytes) -> dict:
    schema = json.loads(content)
    Draft202012Validator.check_schema(schema)
    return schema


def load_schema(contracts: Path | None = None) -> dict:
    directory = contracts if contracts is not None else REPO_ROOT / "contracts"
    content = read_asset(directory / "stage2.schema.json")
    if hashlib.sha256(content).hexdigest() != SCHEMA_HASH:
        raise ValueError("Stage 2 schema checksum mismatch")
    # Fresh copy prevents a caller mutating the shared validation schema.
    return json.loads(json.dumps(_schema(content)))


def validate(record, definition: str, contracts: Path | None = None) -> None:
    schema = load_schema(contracts)
    if definition not in schema["$defs"]:
        raise ValueError(f"Unknown Stage 2 definition: {definition}")
    Draft202012Validator({**schema, "$ref": f"#/$defs/{definition}"}).validate(record)


def check(directory: Path) -> dict:
    schema = load_schema(directory)
    checksum = read_asset(directory / "STAGE2-SHA256SUMS").decode().split()
    if checksum != [SCHEMA_HASH, "stage2.schema.json"]:
        raise ValueError("Stage 2 checksum file mismatch")
    for relative in ("stage1-api.schema.json", "legacy/stage1-v1-api.schema.json"):
        if hashlib.sha256(read_asset(directory / relative)).hexdigest() != STAGE1_HASH:
            raise ValueError("Original Stage 1 schema changed")
    port = read_asset(directory / "shared/stage2_ports.py")
    # Compare against the published, untouched build pack and the importable interface.
    published = REPO_ROOT / "CodeJury-Stage2-Build-Pack/contracts/shared/stage2_ports.py"
    installed = REPO_ROOT / "backend/src/codejury/stage2_ports.py"
    if (
        hashlib.sha256(port).hexdigest() != PORTS_HASH
        or port != read_asset(published)
        or port != read_asset(installed)
    ):
        raise ValueError("Frozen Python ports differ")
    fixture_dir = directory / "stage2-fixtures"
    manifest = json.loads(read_asset(fixture_dir / "fixture-manifest.json"))
    if manifest.get("synthetic") is not True:
        raise ValueError("Fixture manifest must disclose synthetic data")
    seen = set()
    for entry in manifest["fixtures"]:
        name = entry["filename"]
        if Path(name).name != name or name in seen or not name.endswith(".json"):
            raise ValueError("Invalid or duplicate fixture path")
        seen.add(name)
        validate(json.loads(read_asset(fixture_dir / name)), entry["definition"], directory)
    if {p.name for p in fixture_dir.iterdir()} != seen | {"fixture-manifest.json"}:
        raise ValueError("Unlisted fixture assets")
    for name in seen | {"fixture-manifest.json"}:
        packaged = REPO_ROOT / "CodeJury-Stage2-Build-Pack/contracts/fixtures" / name
        if read_asset(fixture_dir / name) != read_asset(packaged):
            raise ValueError(f"Frozen fixture differs: {name}")
    return {
        "status": "passed",
        "schema_sha256": SCHEMA_HASH,
        "ports_sha256": hashlib.sha256(port).hexdigest(),
        "definitions": len(schema["$defs"]),
        "synthetic_fixtures": len(seen),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts", type=Path, default=REPO_ROOT / "contracts")
    args = parser.parse_args()
    print(json.dumps(check(args.contracts), indent=2))


if __name__ == "__main__":
    main()
