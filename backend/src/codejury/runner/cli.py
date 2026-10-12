import argparse
import json
from dataclasses import asdict

from ..properties import equal
from . import DockerRunner, InfrastructureError


def main():
    parser = argparse.ArgumentParser(description="Real isolated runner checks; no host fallback")
    parser.add_argument("command", choices=["self-test"])
    parser.add_argument("--profile", choices=["stage1-demo"], required=True)
    parser.parse_args()
    runner = DockerRunner()
    try:
        print(json.dumps(runner.ready(), indent=2))
        cases = [
            ("success", "def total(values):\n    return sum(values)\n", [[1, 2]], 3, None),
            (
                "input_mutation",
                "def total(values):\n    values.append(9)\n    return sum(values)\n",
                [[1]],
                10,
                None,
            ),
            (
                "timeout",
                "def total(values):\n    while True:\n        pass\n",
                [[]],
                None,
                "TimeoutError",
            ),
            (
                "oversized_output",
                "def total(values):\n    return [0] * 10000\n",
                [[]],
                None,
                "ValueError",
            ),
        ]
        for name, source, args, expected, error in cases:
            result = runner.execute(source, "total", args)
            assert equal(result.actual_output, expected) and result.exception_type == error
            if name == "input_mutation":
                assert result.input_mutated
            print(json.dumps({"check": name, "result": asdict(result)}, separators=(",", ":")))
        mismatch = runner.execute("def total(values):\n    return 0\n", "total", [[1]])
        assert not equal(mismatch.actual_output, 1)
        print("PASS independent assertion mismatch detection; 5 real checks")
    except (InfrastructureError, AssertionError) as exc:
        print(f"FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
