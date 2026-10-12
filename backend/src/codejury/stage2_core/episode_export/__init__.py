"""Train-only canonical exchange. Export frozen pre-action states, never later evidence."""

import hashlib
import json
from pathlib import Path

from ..contracts import canonical_json, checked, json_hash
from ..controller import records
from ..controller.inputs import training_input
from ..data import load_stage1
from ..registry import local_path


def export(ledger, run_ids, out, *, base_revision_hash, split="train"):
    if split != "train" or not run_ids or len(run_ids) != len(set(run_ids)):
        raise ValueError("Unique training runs are required; assessment exports are forbidden")
    episodes, bases, provenance, selected = [], set(), [], []
    manifest, train = None, None
    for run_id in run_ids:
        snapshot = ledger.snapshot(run_id)
        metadata = records(ledger, run_id, "metadata")
        if (
            snapshot["runtime_mode"] != "live"
            or snapshot["status"]
            in {"running", "queued", "infrastructure_error", "cancelled", "invalid_input"}
            or len(metadata) != 1
            or metadata[0]["mode"] != "live"
            or type(metadata[0].get("profile")) is not dict
            or json_hash(metadata[0]["profile"]) != snapshot["profile_hash"]
            or metadata[0]["model_manifest_hash"] != snapshot["model_manifest_hash"]
        ):
            raise ValueError("Only terminal actual native/sandbox learning runs can be exported")
        source = metadata[0]["provenance"]
        if (
            type(source) is not dict
            or set(source)
            != {
                "split",
                "base_problem_id",
                "record_id",
                "source_manifest_hash",
                "runtime_input_hash",
            }
            or source["split"] != "train"
            or source["runtime_input_hash"] != json_hash(snapshot["problem"])
        ):
            raise ValueError("Episode lacks frozen training source provenance")
        if train is None:
            manifest, rows = load_stage1(local_path("data/manifests/stage1.json"))
            train = {r["record_id"]: r for r in rows if r["split"] == "train"}
        row = train.get(source["record_id"])
        if (
            row is None
            or source["base_problem_id"] != row["base_problem_id"]
            or source["source_manifest_hash"] != json_hash(manifest)
            or training_input(row)[0] != snapshot["problem"]
            or metadata[0]["model_identities"]["fixer_a"]["model_revision_hash"]
            != base_revision_hash
        ):
            raise ValueError("Training provenance or frozen base identity could not be rejoined")
        frozen = records(ledger, run_id, "episode")
        if not frozen:
            raise ValueError("No frozen pre-action EpisodeBundles collected")
        for episode in frozen:
            episode = checked(episode, "EpisodeBundle")
            if episode["run_id"] != run_id or episode["problem"] != snapshot["problem"]:
                raise ValueError("Frozen episode identity differs from runtime input")
            for row in episode["executions"]:
                if row["trace_ref"]:
                    ledger.read_object(row["trace_ref"])
            episodes.append(episode)
        bases.add(source["base_problem_id"])
        provenance.append({"run_id": run_id, **source})
        selected.append(
            {
                "run_id": run_id,
                "status": snapshot["status"],
                "decision": snapshot["decision"],
                "resource_usage": snapshot["resource_usage"],
            }
        )
    out = Path(out)
    if out.exists():
        raise FileExistsError("Exchange outputs are immutable; choose a new directory")
    # Everything has been checked before publishing the exchange directory.
    out.mkdir(parents=True)
    (out / "episodes.jsonl").write_bytes(b"".join(canonical_json(e) + b"\n" for e in episodes))
    for name, body in (("provenance.json", provenance), ("outcomes.json", selected)):
        (out / name).write_bytes(canonical_json(body) + b"\n")
    transports = []
    with ledger.connection() as db:
        for run_id in run_ids:
            for row in db.execute(
                "SELECT definition,body,status,response,usage FROM requests "
                "WHERE run_id=? ORDER BY rowid",
                (run_id,),
            ):
                transports.append(
                    {
                        "run_id": run_id,
                        "definition": row["definition"],
                        "request": json.loads(row["body"]),
                        "status": row["status"],
                        "response": json.loads(row["response"]) if row["response"] else None,
                        "usage": json.loads(row["usage"]) if row["usage"] else None,
                    }
                )
    (out / "transports.jsonl").write_bytes(b"".join(canonical_json(t) + b"\n" for t in transports))
    hashes = {r["trace_ref"] for e in episodes for r in e["executions"] if r["trace_ref"]}
    (out / "objects").mkdir()
    for digest in sorted(hashes):
        (out / "objects" / digest).write_bytes(ledger.read_object(digest))
    files = []
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        content = path.read_bytes()
        files.append(
            {
                "relative_path": path.relative_to(out).as_posix(),
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
        )
    manifest = checked(
        {
            "schema_version": "stage2.v1",
            "exchange_id": out.name,
            "owner": "ajay",
            "kind": "episodes",
            "base_revision_hash": base_revision_hash,
            "split": "train",
            "files": files,
            "record_count": len(episodes),
            "base_problem_count": len(bases),
            "contains_hidden_assessment": False,
            "note": "Actual native A/B and Docker tools; frozen fixed-v1 pre-action states. "
            "Raw bootstrap Critic is identified in audit.jsonl. "
            "No reference solutions or offline labels. "
            "Multiple states from one run share its base problem and must stay in one split.",
        },
        "ArtifactManifest",
    )
    audit = []
    for run_id in run_ids:
        audit.append(
            {
                "run_id": run_id,
                "metadata": records(ledger, run_id, "metadata"),
                "critic_modes": records(ledger, run_id, "critic_mode"),
                "actions": records(ledger, run_id, "action"),
                "outcomes": records(ledger, run_id, "outcome"),
                "events": ledger.events(run_id),
            }
        )
    (out / "audit.jsonl").write_bytes(b"".join(canonical_json(a) + b"\n" for a in audit))
    content = (out / "audit.jsonl").read_bytes()
    manifest["files"].append(
        {
            "relative_path": "audit.jsonl",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
    )
    (out / "manifest.json").write_text(
        json.dumps(checked(manifest, "ArtifactManifest"), indent=2) + "\n"
    )
    return manifest
