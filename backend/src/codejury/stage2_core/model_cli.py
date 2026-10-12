"""Register retained Stage 1 A and verify real native switching, without executing repairs."""

import argparse
import json
from pathlib import Path
from threading import Event, Timer

from .budgets import CAPS
from .contracts import canonical_json, checked, json_hash
from .factory import make_model_port
from .registry import register_stage1

PUBLIC_PROMPT = (
    "Repair this Python function. Return only JSON with assumptions, diagnosis and source. "
    "Contract: sum all integer values; empty input returns zero; preserve inputs. "
    "Source: def total(values):\n    return 0\n"
    "Visible test: total([2,-4,7]) must equal 5. No hidden tests are provided."
)


def request_for(role, identifier):
    purpose = {
        "raw": "repair",
        "fixer_a": "repair",
        "fixer_b": "reconstruct",
        "critic": "test_proposal",
        "judge": "action_choice",
        "general": "baseline",
    }[role]
    return checked(
        {
            "schema_version": "stage2.v1",
            "request_id": identifier,
            "run_id": "native-public-smoke",
            "role": role,
            "purpose": purpose,
            "prompt": PUBLIC_PROMPT,
            "seed": 17,
            "max_new_tokens": 192,
            "remaining_budget": CAPS,
        },
        "ModelRequest",
    )


def smoke(config: Path, sequence: list[str], out: Path) -> dict:
    if out.exists():
        raise FileExistsError("Smoke evidence refuses overwrite; choose a new output path")
    rows, comparisons = [], []

    def retain_failure(label, result):
        failure = {
            "status": "failed",
            "runtime_mode": "live",
            "sequence": sequence,
            "scope": "Native worker smoke failed; no candidate execution or quality claim",
            "rows": rows,
            "independent_comparisons": comparisons,
            "failure": label,
            "response": result,
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("xb") as stream:
            stream.write(canonical_json(failure) + b"\n")
        raise RuntimeError(label + "; failure evidence retained at " + str(out))

    with make_model_port(config) as port:
        readiness = port.readiness()
        if any(role not in readiness["available_roles"] for role in sequence):
            raise ValueError("Requested smoke contains an unavailable trained role")
        manifest_hash = port.registry.manifest_hash
        for index, role in enumerate(sequence):
            result = port.generate(request_for(role, f"native-switch-{index}"), Event())
            if result["status"] != "ok":
                retain_failure("Native sequence failed", result)
            inspection = port.inspect()
            rows.append(
                {
                    "response": result,
                    "inspection": inspection,
                    "output_hash": json_hash(result["text"]),
                }
            )
        resident_pid = rows[0]["inspection"]["pid"]
        single_base = all(
            row["inspection"]["pid"] == resident_pid
            and row["inspection"]["base_loads"] == 1
            and row["inspection"]["base_object_id"] == rows[0]["inspection"]["base_object_id"]
            for row in rows
        )
        oversized = request_for(sequence[-1], "native-context-limit")
        oversized["prompt"] = "public required contract and source sentinel " * 2000
        context_result = port.generate(oversized, Event())
        if context_result["error"] is None or context_result["error"]["code"] != "context_limit":
            retain_failure("Context overflow was not refused", context_result)
        cancel = Event()
        timer = Timer(0.25, cancel.set)
        timer.start()
        try:
            cancellation_request = request_for(sequence[-1], "native-cancel")
            cancellation_request["prompt"] = (
                "Public cancellation probe. Preserve all supplied content. " * 300
            )
            cancel_result = port.generate(cancellation_request, cancel)
        finally:
            timer.cancel()
        if cancel_result["status"] != "cancelled":
            retain_failure("Native cancellation was not observed", cancel_result)
    # Release the resident worker before loading any independent comparison base.
    for role in dict.fromkeys(sequence):
        with make_model_port(config) as clean:
            result = clean.generate(request_for(role, "clean-" + role), Event())
            if result["status"] != "ok":
                retain_failure("Clean-load native comparison failed", result)
            inspection = clean.inspect()
            same = all(
                row["inspection"]["parameter_hash"] == inspection["parameter_hash"]
                and row["response"]["text"] == result["text"]
                for row in rows
                if row["response"]["role"] == role
            )
            comparisons.append(
                {"role": role, "match": same, "inspection": inspection, "response": result}
            )
    distinct_role_hashes = {
        role: next(
            row["inspection"]["parameter_hash"] for row in rows if row["response"]["role"] == role
        )
        for role in set(sequence)
    }
    distinct_parameters = len(set(distinct_role_hashes.values())) == len(distinct_role_hashes)
    verified = single_base and distinct_parameters and all(row["match"] for row in comparisons)
    report = {
        "status": "passed" if verified else "failed",
        "runtime_mode": "live",
        "scope": "Native generation/switching only; public sum overlaps Stage 1 training family. "
        "No candidate execution, repair-score measurement or final assessment.",
        "manifest_hash": manifest_hash,
        "readiness": readiness,
        "single_resident_base": single_base,
        "distinct_role_parameters": distinct_parameters,
        "sequence": sequence,
        "rows": rows,
        "independent_comparisons": comparisons,
        "switch_verified": verified,
        "native_boundary_probes": {"context_limit": context_result, "cancel": cancel_result},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("xb") as stream:
        stream.write(canonical_json(report) + b"\n")
    if not verified:
        raise RuntimeError(
            "Native switching differs from independent clean loads; evidence retained"
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register-stage1")
    register.add_argument("--model-dir", type=Path, required=True)
    register.add_argument("--adapter-dir", type=Path, required=True)
    register.add_argument("--training-report", type=Path, required=True)
    register.add_argument("--out", type=Path, required=True)
    generate = sub.add_parser("smoke")
    generate.add_argument("--config", type=Path, required=True)
    generate.add_argument("--sequence", default="raw,fixer_a,raw,fixer_a")
    generate.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register-stage1":
        registry = register_stage1(args.model_dir, args.adapter_dir, args.training_report, args.out)
        print(json.dumps(registry.readiness(), indent=2))
    else:
        report = smoke(args.config, args.sequence.split(","), args.out)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "single_resident_base": report["single_resident_base"],
                    "switch_verified": report["switch_verified"],
                    "readiness": report["readiness"],
                    "sequence_usage": [
                        {"role": r["response"]["role"], "usage": r["response"]["usage"]}
                        for r in report["rows"]
                    ],
                    "out": str(args.out),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
