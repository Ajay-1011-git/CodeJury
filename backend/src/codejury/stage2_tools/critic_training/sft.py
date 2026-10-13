"""Export collected Critic records to mlx-lm chat JSONL, split by base problem."""

import hashlib
import json
from pathlib import Path

from .data.pipeline import OUT_MANIFEST, OUT_RECORDS


class SftError(ValueError):
    pass


def _bucket(base_problem_id: str, seed: int) -> float:
    digest = hashlib.sha256(f"{seed}:{base_problem_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def export(data_dir: Path, out_dir: Path, *, validation_fraction: float, seed: int) -> dict:
    manifest = json.loads((Path(data_dir) / OUT_MANIFEST).read_text())
    records = [json.loads(x) for x in (Path(data_dir) / OUT_RECORDS).read_text().splitlines()]
    if not records:
        raise SftError("No records to export")
    if manifest["split"] != "train":
        raise SftError("SFT export reads the train split only")
    bases = sorted({r["base_problem_id"] for r in records})
    if len(bases) < 2 or not 0 < validation_fraction < 1:
        raise SftError("Need at least two base problems and a proper validation fraction")
    valid_bases = {b for b in bases if _bucket(b, seed) < validation_fraction}
    if len(valid_bases) == len(bases):
        valid_bases = set(bases[:1])
    if not valid_bases and len(bases) > 1:
        valid_bases = {min(bases, key=lambda b: _bucket(b, seed))}
    if len(valid_bases) == len(bases):
        raise SftError("Need at least two base problems for a leak-free train/validation split")
    rows = {"train": [], "valid": []}
    for r in records:
        side = "valid" if r["base_problem_id"] in valid_bases else "train"
        rows[side].append(
            {
                "messages": [
                    {"role": "system", "content": r["system"]},
                    {"role": "user", "content": r["prompt"]},
                    {"role": "assistant", "content": r["completion"]},
                ]
            }
        )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for side, items in rows.items():
        body = "".join(json.dumps(x, sort_keys=True) + "\n" for x in items)
        (out / f"{side}.jsonl").write_text(body)
        hashes[side] = hashlib.sha256(body.encode()).hexdigest()
    return {
        "fixture": manifest["fixture"],
        "train_records": len(rows["train"]),
        "valid_records": len(rows["valid"]),
        "train_base_problems": len(bases) - len(valid_bases),
        "valid_base_problems": len(valid_bases),
        "sft_sha256": hashes,
        "data_manifest_sha256": hashlib.sha256(
            (Path(data_dir) / OUT_MANIFEST).read_bytes()
        ).hexdigest(),
    }
