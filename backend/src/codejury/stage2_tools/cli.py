"""ToolPort self-test: contract conformance (CPU) plus a live call (native, else pending)."""

import argparse
import ast
import json
import subprocess
import sys
import threading
from pathlib import Path

from . import contract_cli, factory
from .runner import InfrastructureError


def _factory_is_clean() -> bool:
    tree = ast.parse(Path(factory.__file__).read_text())
    names = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    return not any(token in name for name in names for token in ("test", "fixture", "mock", "fake"))


def self_test(config: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "config": str(config),
        "contract": contract_cli.check(contract_cli.REPO_ROOT / "contracts"),
        "live_factory_imports_no_fakes": _factory_is_clean(),
    }
    fixtures = contract_cli.REPO_ROOT / "contracts/stage2-fixtures"
    try:
        port = factory.make_tool_port(config)
        request = json.loads((fixtures / "tool-evaluate-request.json").read_text())
        result = port.call(request, threading.Event())
        report["native_evaluate"] = {
            "status": result["status"],
            "executions": len(result["executions"]),
        }
        report["overall"] = "passed" if result["status"] == "ok" else "failed"
    except (InfrastructureError, OSError, subprocess.SubprocessError) as exc:
        report["native_evaluate"] = "pending_native"
        report["reason"] = f"{type(exc).__name__}: {exc}"
        report["overall"] = "pending_native"
    (out / "tool-port-self-test.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="stage2_tools.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("self-test")
    st.add_argument("--config", required=True, type=Path)
    st.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    report = self_test(args.config, args.out)
    print(
        json.dumps(
            {k: report[k] for k in ("overall", "native_evaluate", "live_factory_imports_no_fakes")},
            indent=2,
        )
    )
    return {"passed": 0, "pending_native": 3}.get(report["overall"], 1)


if __name__ == "__main__":
    sys.exit(main())
