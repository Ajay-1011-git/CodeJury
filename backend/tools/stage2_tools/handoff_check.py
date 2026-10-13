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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts", type=Path, default=ROOT / "contracts")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    rows = collect(args.contracts, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(rows))
    print(json.dumps(rows, indent=2))
    return 2 if args.strict and any(r["status"] != PASSED for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
