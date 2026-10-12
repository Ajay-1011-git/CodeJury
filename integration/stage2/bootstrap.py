"""CPU-only shared bootstrap check; live factories are implemented at E1–E4."""

from codejury.stage2_core.contract_check import REPO_ROOT, check
from codejury.stage2_ports import BaselinePort, ModelPort, RolloutPort, ToolPort

if __name__ == "__main__":
    print(check(REPO_ROOT / "contracts"))
    print("Frozen ports discoverable:", ModelPort, ToolPort, RolloutPort, BaselinePort)
    print("Stage 2 live service pending owner implementations and E1–E4 integration.")
