"""CPU integrity audit, optionally with actual isolated reference execution."""

import argparse

from .data import audit, config, export_pools, write_report
from .factory import make_model_port
from .registry import local_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate", "export"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--sandbox", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--verified-report")
    args = parser.parse_args()
    if args.command == "export":
        if not args.out or not args.verified_report:
            parser.error("export requires --out and --verified-report")
        with make_model_port(local_path(config(args.config)["runtime_config"])) as port:
            manifests = export_pools(
                args.config,
                args.out,
                args.verified_report,
                base_revision_hash=port.registry.base["base_revision_hash"],
            )
        print(
            {
                "status": "curated_not_trained",
                "pools": [
                    {k: m[k] for k in ("split", "record_count", "base_problem_count")}
                    for m in manifests
                ],
            }
        )
        return 0
    runner = None
    if args.sandbox:
        from codejury.runner import DockerRunner

        runner = DockerRunner()
    report = audit(args.config, runner=runner)
    destination = args.out or str(
        local_path(config(args.config)["report_directory"])
        / ("data-sandbox.json" if args.sandbox else "data-cpu.json")
    )
    write_report(destination, report)
    print({k: v for k, v in report.items() if k != "notes"})
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
