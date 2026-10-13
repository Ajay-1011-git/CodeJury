"""Collect and validate execution-filtered Critic training records."""

import json
from pathlib import Path

from ...codec import errors, sha256_text
from .config import config_hash
from .episodes import load_set
from .prompt import SYSTEM, PromptLeak, build_prompt, guard_prompt
from .situations import SITUATION_MODE, classify
from .targets import invalid_variants, no_objection, validate_draft

RECORD_SCHEMA = "stage2-critic-record.v1"
MANIFEST_SCHEMA = "stage2-critic-data-manifest.v1"
OUT_RECORDS = "records.jsonl"
OUT_MANIFEST = "manifest.json"


def _record(episode, situation, mode, kind, draft, prompt, mode_runtime, extra=None):
    completion = json.dumps(draft, sort_keys=True, separators=(",", ":"))
    return {
        "schema": RECORD_SCHEMA,
        "record_id": f"{episode.bundle['run_id']}:{situation}:{kind}",
        "run_id": episode.bundle["run_id"],
        "base_problem_id": episode.base_problem_id,
        "family_id": episode.family_id,
        "provenance": episode.provenance,
        "runtime_mode": mode_runtime,
        "situation": situation,
        "mode": mode,
        "kind": kind,
        "system": SYSTEM,
        "prompt": prompt,
        "completion": completion,
        "prompt_hash": sha256_text(prompt),
        "completion_hash": sha256_text(completion),
        "label_source": episode.label["source_kind"] if episode.label else None,
        **(extra or {}),
    }


def _mode_for(situation: str, bundle: dict, priority: list[str]) -> str:
    if situation in SITUATION_MODE:
        return SITUATION_MODE[situation]
    present = {g["interpretation"] for g in bundle["audit_gaps"]}
    if present:
        return "audit_gap"
    return next(
        m for m in priority if m in ("validate_revision", "challenge_agreement", "discriminate")
    )


def collect(
    config: dict, split_manifest: dict, episode_root, sandbox, out_dir, *, runtime_mode: str
) -> dict:
    data = config["data"]
    episodes = load_set(
        episode_root, split_manifest, split=data["split"], runtime_mode=runtime_mode
    )
    records, rejected = [], [{"stage": "intake", **r} for r in episodes.rejected]
    for ep in episodes.episodes:
        label = ep.label
        if label is None:
            rejected.append({"stage": "label", "run_id": ep.bundle["run_id"], "reason": "no label"})
            continue
        if label["source_kind"] == "teacher_filtered" and sandbox is None:
            rejected.append(
                {
                    "stage": "execution",
                    "run_id": ep.bundle["run_id"],
                    "reason": "teacher draft needs execution filtering, no sandbox",
                }
            )
            continue
        situations = classify(ep.bundle, label["candidate_truth"])
        if not situations:
            rejected.append(
                {
                    "stage": "situation",
                    "run_id": ep.bundle["run_id"],
                    "reason": "no candidate has a label",
                }
            )
            continue
        situation = situations[0]
        mode = _mode_for(situation, ep.bundle, data["mode_priority"])
        prompt = build_prompt(ep.bundle, mode)
        try:
            guard_prompt(
                prompt,
                ep.bundle,
                [label["reference_source"], *(d["rationale"] for d in label["drafts"])],
            )
        except PromptLeak as exc:
            rejected.append({"stage": "guard", "run_id": ep.bundle["run_id"], "reason": str(exc)})
            continue
        if situation == "correct_candidate":
            draft = no_objection(ep.bundle, mode)
            ok, why, kind = (
                not errors(draft, "CriticDraft"),
                "invalid no-objection draft",
                "no_objection",
            )
            if ok:
                records.append(_record(ep, situation, mode, kind, draft, prompt, runtime_mode))
            else:
                rejected.append({"stage": "schema", "run_id": ep.bundle["run_id"], "reason": why})
            continue
        accepted = None
        for draft in label["drafts"]:
            if draft["mode"] != mode:
                continue
            ok, why, stats = (
                validate_draft(sandbox, ep.bundle, draft, label["reference_source"])
                if sandbox
                else (False, "no sandbox: execution filter pending", {})
            )
            if ok:
                accepted = (draft, stats)
                break
            rejected.append({"stage": "execution", "run_id": ep.bundle["run_id"], "reason": why})
        if accepted is None:
            continue
        draft, stats = accepted
        records.append(
            _record(
                ep,
                situation,
                mode,
                "counterexample",
                draft,
                prompt,
                runtime_mode,
                {"validation": stats},
            )
        )
        for pending in invalid_variants(ep.bundle, draft)[: data["invalid_variants_per_episode"]]:
            p2 = build_prompt(ep.bundle, mode, [pending])
            records.append(
                _record(
                    ep,
                    situation,
                    mode,
                    f"invalid_proposal:{pending['kind']}",
                    draft,
                    p2,
                    runtime_mode,
                    {"provenance": "synthetic_invalid", "gate_reason": pending["gate_reason"]},
                )
            )
    return _finish(config, episodes, records, rejected, out_dir, runtime_mode)


def counts(records: list[dict]) -> dict:
    total = len(records)
    by = lambda f: sum(1 for r in records if f(r))  # noqa: E731
    correct = by(lambda r: r["kind"] == "no_objection")
    invalid = by(lambda r: r["kind"].startswith("invalid_proposal"))
    return {
        "records": total,
        "counterexample": by(lambda r: r["kind"] == "counterexample"),
        "no_objection_correct_candidate": correct,
        "invalid_proposal": invalid,
        "by_mode": {
            m: by(lambda r, m=m: r["mode"] == m) for m in sorted({r["mode"] for r in records})
        },
        "by_provenance": {
            p: by(lambda r, p=p: r["provenance"] == p)
            for p in sorted({r["provenance"] for r in records})
        },
        "correct_fraction": round(correct / total, 4) if total else 0.0,
        "invalid_fraction": round(invalid / total, 4) if total else 0.0,
    }


def _finish(config, episodes, records, rejected, out_dir, runtime_mode) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)
    (out / OUT_RECORDS).write_text(body)
    mix = config["data"]["mix_targets"]
    c = counts(records)
    c["mix"] = {
        "correct_candidate_target": mix["correct_candidate_min"],
        "invalid_proposal_target": mix["invalid_proposal_min"],
        "correct_shortfall": c["correct_fraction"] < mix["correct_candidate_min"],
        "invalid_shortfall": c["invalid_fraction"] < mix["invalid_proposal_min"],
        "note": "Targets, not available counts; shortfalls are reported, never padded.",
    }
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "runtime_mode": runtime_mode,
        "fixture": runtime_mode == "fixture",
        "split": config["data"]["split"],
        "episode_set_hash": episodes.set_hash,
        "config_hash": config_hash(config),
        "records_sha256": sha256_text(body),
        "counts": c,
        "intake_episodes": len(episodes.episodes),
        "rejected": rejected,
        "base_problem_ids": sorted({r["base_problem_id"] for r in records}),
    }
    (out / OUT_MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def validate(out_dir, split_manifest: dict, *, runtime_mode: str) -> list[str]:
    """Independent re-check of an emitted data set. Returns problems; empty means valid."""
    out, problems = Path(out_dir), []
    manifest = json.loads((out / OUT_MANIFEST).read_text())
    body = (out / OUT_RECORDS).read_text()
    if manifest["schema"] != MANIFEST_SCHEMA:
        problems.append("unknown manifest schema")
    if manifest["runtime_mode"] != runtime_mode:
        problems.append("runtime_mode mismatch: fixture and real data must not be mixed")
    if sha256_text(body) != manifest["records_sha256"]:
        problems.append("records hash mismatch")
    allowed = set(split_manifest["splits"][manifest["split"]]["base_problem_ids"])
    seen = set()
    for line in body.splitlines():
        r = json.loads(line)
        if r["runtime_mode"] != runtime_mode:
            problems.append(f"{r['record_id']}: mixed runtime_mode")
        if runtime_mode == "real" and r["base_problem_id"] not in allowed:
            problems.append(f"{r['record_id']}: base problem outside {manifest['split']}")
        if r["record_id"] in seen:
            problems.append(f"{r['record_id']}: duplicate")
        seen.add(r["record_id"])
        if (
            sha256_text(r["prompt"]) != r["prompt_hash"]
            or sha256_text(r["completion"]) != r["completion_hash"]
        ):
            problems.append(f"{r['record_id']}: hash mismatch")
        bad = errors(json.loads(r["completion"]), "CriticDraft")
        if bad:
            problems.append(f"{r['record_id']}: completion not a CriticDraft ({bad[0]})")
        for key in ("reference", "hidden", "truth", "label", "gold"):
            if f'"{key}' in r["prompt"]:
                problems.append(f"{r['record_id']}: label-side key {key} in prompt")
    if counts([json.loads(x) for x in body.splitlines()]) != {
        k: v for k, v in manifest["counts"].items() if k != "mix"
    }:
        problems.append("manifest counts do not match records")
    return problems
