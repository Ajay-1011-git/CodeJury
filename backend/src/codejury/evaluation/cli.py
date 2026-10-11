import argparse
from pathlib import Path

from .stage1 import export_report, stage1


def main():
    parser = argparse.ArgumentParser(description="Offline, sealed Stage 1 measurement")
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser("stage1")
    evaluate.add_argument("--manifest", type=Path, required=True)
    evaluate.add_argument("--config", type=Path, required=True)
    evaluate.add_argument("--out", type=Path, required=True)
    export = sub.add_parser("export-report")
    export.add_argument("--results", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    pilot = sub.add_parser("export-pilot")
    pilot.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "stage1":
        stage1(args.manifest, args.config, args.out)
    elif args.command == "export-report":
        export_report(args.results, args.out)
    else:
        export_report(None, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
