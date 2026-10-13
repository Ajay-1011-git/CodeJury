"""Stage 2 handoff gate report (S2.12). Reads evidence; never trains, benchmarks or executes
candidates, and never turns a missing artifact into a pass.

Usage (repo root):
  python backend/tools/stage2_tools/handoff_check.py --contracts contracts \
      --out backend/docs/stage2_tools/handoff.md [--seed <commit>] [--strict]
"""

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND / "src"))

from codejury.stage2_tools.codec import errors  # noqa: E402
from codejury.stage2_tools.contract_cli import check as contract_check  # noqa: E402

ART = BACKEND / "artifacts" / "stage2_tools"
OWNED = re.compile(
    r"^(web/.*|backend/(src/codejury|tests|config|data|tools|docs)/.*stage2_tools.*"
    r"|backend/src/codejury/stage2_tools/.*)$"
)
PASSED, PENDING, MISSING, FAILED = "passed", "pending", "missing", "failed"


def git(*argv) -> str | None:
    try:
        done = subprocess.run(
            ["git", "-C", str(ROOT), *argv], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def load(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def gate_contract(contracts: Path) -> tuple[str, str]:
    try:
        r = contract_check(contracts)
    except (ValueError, OSError) as exc:
        return FAILED, str(exc)
    return (
        PASSED,
        f"schema+ports hashes frozen; {r['synthetic_fixtures_validated']} synthetic fixtures valid",
    )


def gate_owner_paths(seed: str | None) -> tuple[str, str]:
    seed = seed or git("merge-base", "HEAD", "origin/main")
    if not seed:
        return MISSING, "no common Stage 2 seed commit could be determined; pass --seed"
    names = git("diff", "--name-only", f"{seed}...HEAD")
    if names is None:
        return MISSING, f"git diff against {seed[:10]} failed"
    outside = [n for n in names.splitlines() if n and not OWNED.match(n)]
    if outside:
        return FAILED, f"files outside owner paths: {', '.join(outside[:5])}"
    return PASSED, f"every changed path since {seed[:10]} is under stage2_tools or web"


def gate_card(role: str) -> tuple[str, str]:
    path = ART / role / "card.json"
    card = load(path)
    if card is None:
        return MISSING, f"artifacts/stage2_tools/{role}/card.json not found (no real training run)"
    problems = errors(card, "AdapterCard")
    if problems:
        return FAILED, problems[0]
    if card["status"] != "completed" or not card["adapter_hash"]:
        return PENDING, f"card status is {card['status']}"
    return PASSED, f"completed, {card['steps']} real steps, adapter {card['adapter_hash'][:12]}"


def gate_critic_data() -> tuple[str, str]:
    m = load(ART / "critic" / "data" / "manifest.json")
    if m is None:
        return MISSING, "no collected Critic data manifest"
    if m.get("fixture"):
        return PENDING, "only fixture data exists; no real TRAINING episodes collected"
    return PASSED, f"{m['counts']['records']} real records"


def gate_benchmark() -> tuple[str, str]:
    report = load(ART / "benchmark-report.json")
    if report is None:
        return MISSING, "no final benchmark report (the sealed final run has not happened)"
    problems = errors(report, "BenchmarkReport")
    if problems:
        return FAILED, problems[0]
    if report["runtime_mode"] != "live":
        return PENDING, f"report is {report['runtime_mode']}, not a live final run"
    return PASSED, f"research_outcome={report.get('research_outcome')}"


def gate_docker() -> tuple[str, str]:
    if not shutil.which("docker"):
        return PENDING, "no docker CLI; runner image never built, sandbox checks not run"
    try:
        ok = subprocess.run(["docker", "info"], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    return (
        (PENDING, "docker present but daemon unreachable")
        if not ok
        else (PENDING, "docker reachable; native self-tests must still be run and recorded")
    )


def gate_mlx() -> tuple[str, str]:
    if importlib.util.find_spec("mlx") is None:
        return PENDING, "mlx is not installed; no native training/reload possible here"
    return PENDING, "mlx importable; training and reload evidence must come from card.json"


def gate_joint() -> tuple[str, str]:
    doc = load(ART / "joint-acceptance.json")
    if doc is None:
        return PENDING, "joint Mac browser/system acceptance with Ajay has not been recorded"
    return (PASSED, "recorded") if doc.get("passed") is True else (FAILED, "recorded as not passed")


def collect(contracts: Path, seed: str | None) -> list[dict]:
    rows = [
        ("Frozen contract and fixtures", gate_contract(contracts)),
        ("Owner-path diff", gate_owner_paths(seed)),
        ("Critic data (real)", gate_critic_data()),
        ("Critic adapter card", gate_card("critic")),
        ("General adapter card", gate_card("general")),
        ("Docker/native sandbox", gate_docker()),
        ("MLX hardware", gate_mlx()),
        ("Final live benchmark report", gate_benchmark()),
        ("Joint Mac browser/system acceptance", gate_joint()),
    ]
    return [{"gate": g, "status": s, "evidence": e} for g, (s, e) in rows]


def render(rows: list[dict]) -> str:
    open_gates = [r for r in rows if r["status"] != PASSED]
    out = [
        "# Stage 2 handoff gate report",
        "",
        "Generated by `backend/tools/stage2_tools/handoff_check.py`. It reads evidence only and",
        "never converts a missing artifact into a pass.",
        "",
        "| Gate | Status | Evidence |",
        "|---|---|---|",
    ]
    out += [f"| {r['gate']} | **{r['status']}** | {r['evidence']} |" for r in rows]
    out += ["", "## Release verdict", ""]
    if open_gates:
        out.append(f"NOT final-releasable: {len(open_gates)} gate(s) are not passed.")
        out += [f"- {r['gate']}: {r['status']}" for r in open_gates]
        out += ["", "A fixed-only or fixture-only release is not the final learned architecture."]
    else:
        out.append(
            "All gates passed. Superiority claims still follow the report's research_outcome only."
        )
    return "\n".join(out) + "\n"


def collect_integrated(contracts: Path, registry_path: Path) -> list[dict]:
    """Read the merged application's byte-verified native evidence, never legacy placeholders."""
    from codejury.models.worker import file_hash
    from codejury.stage2_core.registry import Registry, local_path

    rows = [("Frozen contract and fixtures", gate_contract(contracts))]
    try:
        registry = Registry(registry_path)
    except (OSError, ValueError, KeyError) as exc:
        rows.append(("Integrated native registry", (MISSING, str(exc))))
        registry = None
    if registry:
        for role in ("critic", "judge", "general"):
            try:
                adapter = registry.record["adapters"].get(role)
                if not adapter or adapter["card"]["status"] != "completed":
                    result = (PENDING, "No completed integrated native adapter")
                else:
                    registry.verify_adapter(role)
                    directory = {
                        "critic": "artifacts/stage2_tools/critic-training/selected-v1",
                        "judge": "artifacts/stage2_core/judge-learning/selected-v2",
                        "general": "artifacts/stage2_core/general-learning/selected-v1",
                    }[role]
                    selection = json.loads(local_path(directory + "/selection.json").read_text())
                    report_path = Path(
                        selection.get("training_report_path")
                        or local_path("artifacts/stage2_tools/critic-training/full-v1/report.json")
                    )
                    report = json.loads(report_path.read_text())
                    selected = selection["selected"]
                    if (
                        file_hash(report_path) != selection["training_report_hash"]
                        or report["role"] != role
                        or report["phase"] != "full"
                        or not report["updates_verified"]
                        or not report["reload_verified"]
                        or selected["evaluation"]["adapter_hash"] != adapter["card"]["adapter_hash"]
                        or selected["step"] != adapter["card"]["steps"]
                    ):
                        raise ValueError("Selection/card/full-job proof differs")
                    result = (
                        PASSED,
                        f"Native step {selected['step']}, verified updates/reload "
                        f"and selected hash {adapter['card']['adapter_hash'][:12]}",
                    )
            except (OSError, ValueError, KeyError) as exc:
                result = (FAILED, str(exc))
            rows.append((f"{role.title()} native selection", result))
    try:
        from codejury.stage2_tools.critic_training.data import validate

        validate(local_path("artifacts/stage2_tools/critic-training/corpus-v1"))
        rows.append(("Genuine Critic corpus", (PASSED, "Hash/split/mix validation passed")))
    except (OSError, ValueError, KeyError) as exc:
        rows.append(("Genuine Critic corpus", (MISSING, str(exc))))
    try:
        from codejury.stage2_tools.factory import make_tool_port

        tool = make_tool_port(local_path("../integration/stage2/tools.yaml"))
        tool.sandbox.ready()
        proof = json.loads(
            local_path("artifacts/stage2-integration/runner-v2/runner-self-test.json").read_text()
        )
        if (
            proof["mode"] != "native_sandbox"
            or proof["overall"] != "passed"
            or not all(proof["checks"].values())
            or proof["runtime_hash"] != tool.sandbox.runtime_hash
        ):
            raise ValueError("Isolation proof differs from the current native runner")
        rows.append(
            ("Isolated native runner", (PASSED, "Current ready runner; 12 isolation checks"))
        )
    except Exception as exc:  # runner diagnostics are data, never candidate execution
        rows.append(("Isolated native runner", (PENDING, str(exc))))
    try:
        report = json.loads(
            local_path("docs/stage2_tools/results/benchmark-report.json").read_text()
        )
        meta = json.loads(local_path("artifacts/stage2_tools/final-v1/run-meta.json").read_text())
        if (
            errors(report, "BenchmarkReport")
            or report["runtime_mode"] != "live"
            or report["status"] != "completed"
            or report["dataset_id"] != "final_assessment"
            or not meta["freeze_hash"]
            or not registry
            or meta["registry_hash"] != registry.manifest_hash
            or meta["manifest_hash"] != report["dataset_manifest_hash"]
        ):
            raise ValueError("No matching completed, frozen final benchmark")
        rows.append(("Final frozen benchmark", (PASSED, report["research_outcome"])))
    except (OSError, ValueError, KeyError) as exc:
        rows.append(("Final frozen benchmark", (PENDING, str(exc))))
    acceptance = load(ART / "joint-acceptance.json")
    accepted = bool(
        acceptance
        and registry
        and acceptance.get("passed") is True
        and acceptance.get("runtime_mode") == "live"
        and acceptance.get("registry_hash") == registry.manifest_hash
    )
    rows.append(
        (
            "Live browser/system acceptance",
            (
                PASSED if accepted else PENDING,
                "Matching native browser evidence"
                if accepted
                else "No matching live acceptance evidence",
            ),
        )
    )
    return [{"gate": g, "status": s, "evidence": e} for g, (s, e) in rows]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts", type=Path, default=ROOT / "contracts")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--owner-only",
        action="store_true",
        help="Historical owner-branch gate; default checks the integrated release",
    )
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args(argv)
    if args.owner_only:
        rows = collect(args.contracts, args.seed)
    else:
        import yaml

        from codejury.stage2_core.registry import local_path

        runtime = yaml.safe_load(local_path("config/stage2_core/runtime.yaml").read_text())
        rows = collect_integrated(
            args.contracts, args.registry or local_path(runtime["model_manifest"])
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(rows))
    print(json.dumps(rows, indent=2))
    return 2 if args.strict and any(r["status"] != PASSED for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
