"""Reject-only overlap filtering for the local training corpus."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codejury.stage2_core.registry import local_path
from codejury.stage2_core.training.split_guard import filter_logic_split

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = filter_logic_split(args.source, args.out, local_path("data/dev_bench"))
    print(json.dumps(result, indent=2))
