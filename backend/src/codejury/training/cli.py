import argparse
from pathlib import Path

from .data import collect, export_sft, validate_data


def main():
    parser = argparse.ArgumentParser(description="Offline CodeJury data and training tools")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("collect-data", "validate-data", "export-sft"):
        sub = commands.add_parser(command)
        sub.add_argument("--manifest", type=Path, required=True)
        if command == "export-sft":
            sub.add_argument("--out", type=Path, required=True)
    for command in ("pilot", "train", "select"):
        sub = commands.add_parser(command)
        sub.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "collect-data":
        collect(args.manifest)
    elif args.command == "validate-data":
        validate_data(args.manifest)
    elif args.command == "export-sft":
        export_sft(args.manifest, args.out)
    elif args.command == "select":
        from .select import select

        select(args.config)
    else:
        from .launch import launch

        launch(args.config, pilot=args.command == "pilot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
