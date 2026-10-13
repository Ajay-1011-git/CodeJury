"""Byte-preserving private training transfer, separate from public adapter snapshots."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = "handoff-metadata/snapshot.json"
ALLOWED = (
    "backend/artifacts/",
    "backend/models/",
    "backend/data/private/",
    "backend/checkpoints/",
    "handoff-metadata/",
)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_name(name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not name.startswith(ALLOWED):
        raise ValueError("Unexpected snapshot member")
    return path


def create(out, images):
    out.mkdir(parents=True, exist_ok=True)
    os.chmod(out, 0o700)
    metadata = out / "handoff-metadata"
    metadata.mkdir(exist_ok=False)
    keys = []
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() in {"GROQ_API_KEY", "groq_api_1", "groq_api_2", "groq_api_3"}:
                value = value.strip().strip("\"'")
                if value:
                    keys.append(value.encode())
    files = {}
    for directory in ("artifacts", "models", "data/private", "checkpoints"):
        for path in sorted((ROOT / "backend" / directory).rglob("*")):
            if path.is_symlink():
                raise ValueError("Snapshot source must not contain symlinks")
            if path.is_file():
                if path.name.startswith(".env"):
                    raise ValueError("Credential file found in snapshot source")
                files[str(path.relative_to(ROOT))] = path
    # The final asset is transferred as opaque bytes; never parse, train on, or score it.
    for name, path in files.items():
        if path.suffix in {".sqlite", ".sqlite3"}:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("SQLite integrity check failed")
        if path.suffix not in {".safetensors", ".gz", ".bin"}:
            with path.open("rb") as stream:
                overlap = b""
                while chunk := stream.read(1024 * 1024):
                    content = overlap + chunk
                    if any(key in content for key in keys):
                        raise ValueError("Credential detected; snapshot stopped")
                    overlap = content[-256:]
    packages = sorted(
        {
            f"{d.metadata['Name']}=={d.version}"
            for d in importlib.metadata.distributions()
            if d.metadata["Name"].lower() != "codejury"
        }
    )
    (metadata / "runtime-requirements.txt").write_text("\n".join(packages) + "\n")
    environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "original_root": str(ROOT),
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "private_transfer_only": True,
        "final_contents_inspected": False,
    }
    (metadata / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    for path in metadata.iterdir():
        files["handoff-metadata/" + path.name] = path
    if images:
        files["handoff-metadata/docker-images.tar.gz"] = images
    manifest = {
        "version": "codejury.training-snapshot.v1",
        **environment,
        "files": {
            name: {"sha256": digest(path), "size": path.stat().st_size}
            for name, path in files.items()
        },
    }
    source_paths = subprocess.check_output(
        [
            "git",
            "ls-files",
            "backend/src",
            "backend/tools",
            "backend/config",
            "contracts",
            "integration",
        ],
        cwd=ROOT,
        text=True,
    ).splitlines()
    manifest["source_files"] = {name: digest(ROOT / name) for name in source_paths}
    (metadata / "snapshot.json").write_text(json.dumps(manifest, indent=2) + "\n")
    archive = out / "codejury-training-private-2026-10-13.tar.gz"
    with archive.open("xb") as raw, tarfile.open(fileobj=raw, mode="w:gz", compresslevel=1) as tar:
        for name, path in files.items():
            tar.add(path, arcname=name, recursive=False)
        tar.add(metadata / "snapshot.json", arcname=MANIFEST, recursive=False)
    os.chmod(archive, 0o600)
    public = out / "codejury-trained-adapters-2026-10-13.tar.gz"
    public_files = {
        name: path
        for name, path in files.items()
        if name.startswith("backend/artifacts/")
        and (path.suffix == ".safetensors" or path.name in {"adapter_config.json", "freeze.json"})
    }
    (out / "adapters-manifest.json").write_text(
        json.dumps(
            {
                "version": "codejury.adapter-snapshot.v1",
                "source_revision": environment["source_revision"],
                "final_project_release": False,
                "private_corpora_included": False,
                "files": {
                    name: {"sha256": digest(path), "size": path.stat().st_size}
                    for name, path in public_files.items()
                },
            },
            indent=2,
        )
        + "\n"
    )
    with public.open("xb") as raw, tarfile.open(fileobj=raw, mode="w:gz", compresslevel=1) as tar:
        for name, path in public_files.items():
            tar.add(path, arcname=name, recursive=False)
        tar.add(out / "adapters-manifest.json", arcname="adapters-manifest.json", recursive=False)
    for path in (archive, public):
        path.with_name(path.name + ".sha256").write_text(digest(path) + "  " + path.name + "\n")
    return {
        "private_archive": str(archive),
        "public_adapters": str(public),
        "files": len(files),
        "adapter_weight_files": sum(p.suffix == ".safetensors" for p in public_files.values()),
    }


def verify(archive, checkout, restore=False):
    with tarfile.open(archive, "r:gz") as tar:
        member = tar.getmember(MANIFEST)
        if not member.isfile() or member.size > 32 * 1024 * 1024:
            raise ValueError("Invalid snapshot manifest")
        manifest = json.load(tar.extractfile(member))
        if manifest.get("version") != "codejury.training-snapshot.v1":
            raise ValueError("Unknown snapshot version")
    expected = manifest["files"]
    for name, wanted in manifest["source_files"].items():
        path = checkout / name
        if path.is_symlink() or digest(path) != wanted:
            raise ValueError("Checkout source differs from snapshot: " + name)
    seen = set()
    with tarfile.open(archive, "r|gz") as tar:
        for member in tar:
            safe_name(member.name)
            if not member.isfile() or member.name in seen:
                raise ValueError("Non-file or duplicate snapshot member")
            seen.add(member.name)
            if member.name == MANIFEST:
                continue
            proof = expected.get(member.name)
            if proof is None or member.size != proof["size"]:
                raise ValueError("Unexpected snapshot file/size")
            stream = tar.extractfile(member)
            if hashlib.file_digest(stream, "sha256").hexdigest() != proof["sha256"]:
                raise ValueError("Snapshot byte identity mismatch")
    if seen != set(expected) | {MANIFEST}:
        raise ValueError("Incomplete snapshot")
    if restore:
        with tarfile.open(archive, "r|gz") as tar:
            for member in tar:
                target = checkout / safe_name(member.name)
                if any(p.is_symlink() for p in (target, *target.parents)):
                    raise ValueError("Snapshot restore forbids symlinks")
                if target.exists():
                    if member.name == MANIFEST:
                        if json.loads(target.read_text()) != manifest:
                            raise ValueError("Existing snapshot manifest differs")
                    elif digest(target) != expected[member.name]["sha256"]:
                        raise ValueError(
                            "Refusing to overwrite existing different bytes: " + member.name
                        )
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as destination, tar.extractfile(member) as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        destination.write(chunk)
                os.chmod(target, 0o600)
    return {
        "verified_files": len(expected),
        "restored": restore,
        "original_root": manifest["original_root"],
        "final_contents_inspected": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create", "verify", "restore"])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--images", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--checkout", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.command == "create":
        if args.out is None:
            parser.error("create requires --out")
        result = create(args.out.resolve(), args.images)
    else:
        if args.archive is None:
            parser.error("verify/restore require --archive")
        result = verify(args.archive, args.checkout.resolve(), args.command == "restore")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
