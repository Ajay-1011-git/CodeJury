"""Critic data/training entrypoint. train/evaluate/export need native MLX and are pending here."""

import argparse
import json
import sys
from pathlib import Path

from .critic_training.data import config as cconfig
from .critic_training.data import pipeline

BACKEND = Path(__file__).resolve().parents[3]


def _paths(args):
    config_path = Path(args.config).resolve()
    config = cconfig.load(config_path)
    manifest = json.loads((BACKEND / config["split_manifest"]).read_text())
    return config_path, config, manifest


def _collect(args) -> int:
    config_path, config, manifest = _paths(args)
    mode = "fixture" if args.fixture else "real"
    sandbox = None
    if not args.fixture:
        from .factory import make_tool_port  # noqa: F401  (raises without a built runner image)
        from .runner.docker import DockerSandbox

        sandbox = DockerSandbox(config_path.with_name(config["runner_config"]))
    else:
        print(
            "fixture mode: episodes are synthetic; no execution sandbox, so execution-filtered "
            "targets stay pending",
            file=sys.stderr,
        )
    root = args.episodes or BACKEND / config["data"]["episodes_root"]
    out = args.out or BACKEND / config["data"]["out_dir"]
    result = pipeline.collect(config, manifest, root, sandbox, out, runtime_mode=mode)
    print(json.dumps({k: result[k] for k in ("runtime_mode", "split", "counts")}, indent=2))
    return 0


def _validate(args) -> int:
    _, config, manifest = _paths(args)
    out = args.out or BACKEND / config["data"]["out_dir"]
    problems = pipeline.validate(out, manifest, runtime_mode="fixture" if args.fixture else "real")
    print(json.dumps({"valid": not problems, "problems": problems}, indent=2))
    return 1 if problems else 0


def _pending(name: str):
    def run(args) -> int:
        print(
            json.dumps(
                {
                    "status": "pending",
                    "command": name,
                    "reason": "needs native MLX hardware and real data; nothing was run",
                }
            )
        )
        return 3

    return run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="critic_cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn in (("collect", _collect), ("validate", _validate)):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True)
        p.add_argument("--fixture", action="store_true")
        p.add_argument("--episodes")
        p.add_argument("--out")
        p.set_defaults(fn=fn)
    for name in ("train", "evaluate", "export"):
        p = sub.add_parser(name)
        p.add_argument("--config")
        p.add_argument("--out")
        p.set_defaults(fn=_pending(name))
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
