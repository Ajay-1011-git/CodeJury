"""Actual validation diagnostic; never selects a checkpoint from training loss."""

import ast
import json
from dataclasses import asdict
from pathlib import Path
from threading import Event
from uuid import uuid4

from jsonschema import ValidationError

from codejury.properties import equal
from codejury.runner import DockerRunner

from ...budgets import CAPS
from ...candidates import parse_draft
from ...contracts import canonical_json, json_hash
from ...data import (
    config,
    final_pool_metadata,
    learning_example,
    load_stage1,
    runtime_example,
    write_report,
)
from ...factory import make_model_port
from ...leases import ComputeLease
from ...registry import MODEL_SYSTEM, local_path


def mask_audit(rows, registry):
    # Inspect/use the installed upstream processor, with native imports behind the lease.
    with ComputeLease(
        owner="ajay", job_id="sft-mask-" + uuid4().hex, kind="training", cancel=Event()
    ):
        from mlx_lm.tuner.datasets import ChatDataset
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            str(registry.model_dir), local_files_only=True, trust_remote_code=False
        )
        result = []
        for row in rows:
            example = learning_example(row)
            messages = [
                {"role": "system", "content": MODEL_SYSTEM},
                {"role": "user", "content": example["a_prompt"]},
                {"role": "assistant", "content": canonical_json(example["target"]).decode()},
            ]
            dataset = ChatDataset([{"messages": messages}], tokenizer, mask_prompt=True)
            tokens, offset = dataset.process(dataset[0])
            runtime = tokenizer.apply_chat_template(
                messages[:-1], tokenize=True, add_generation_prompt=True, return_dict=False
            )
            if (
                tokens[:offset] != runtime
                or offset != len(runtime)
                or not 0 < offset < len(tokens) <= 4096
            ):
                raise ValueError("Chat masking/context alignment failed")
            result.append(
                {
                    "record_id": row["record_id"],
                    "prompt_tokens": offset,
                    "completion_tokens": len(tokens) - offset,
                    "total_tokens": len(tokens),
                }
            )
    return {
        "processor": "mlx_lm.tuner.datasets.ChatDataset.process",
        "mask_prompt": True,
        "runtime_prefix_matches": True,
        "rows": result,
        "max_tokens": max(r["total_tokens"] for r in result),
        "would_truncate_at_stage1_768": sum(r["total_tokens"] > 768 for r in result),
        "within_stage2_context": True,
    }


def evaluate(
    config_path, out=None, *, registry_path=None, all_variants=False, roles=("raw", "fixer_a")
):
    settings = config(config_path)
    manifest, records = load_stage1(local_path(settings["source_manifest"]))
    learning_records = records
    if tuple(roles) not in (("raw", "fixer_a"), ("fixer_a",)):
        raise ValueError("Validation compares raw/A or an A checkpoint only")
    selected = {}
    for row in records:
        if row["split"] == "validation":
            selected.setdefault(row["record_id"] if all_variants else row["base_problem_id"], row)
    records = list(selected.values())
    directory = Path(out) if out else local_path(settings["report_directory"]) / "native"
    directory.mkdir(parents=True, exist_ok=False)
    rows, executions = [], 0
    runner = DockerRunner()
    runner_info = runner.ready()
    runtime_config = local_path(settings["runtime_config"])
    if registry_path is not None:
        import yaml

        from ...model_worker import NativeModelPort
        from ...registry import Registry

        model_port = NativeModelPort(
            Registry(Path(registry_path)), yaml.safe_load(runtime_config.read_text())
        )
    else:
        model_port = make_model_port(runtime_config)
    with model_port as port:
        masks = mask_audit(learning_records, port.registry)
        write_report(directory / "mask-audit.json", masks)
        model_manifest_hash = port.registry.manifest_hash
        registry_used = str(port.registry.path)
        base_revision_hash = port.registry.base["base_revision_hash"]
        for record in records:
            example = learning_example(record)
            problem, tests = runtime_example(record)
            for role in roles:
                request = {
                    "schema_version": "stage2.v1",
                    "request_id": "val-" + uuid4().hex,
                    "run_id": "a-validation",
                    "role": role,
                    "purpose": "repair",
                    "prompt": example["a_prompt"],
                    "seed": settings["seed"],
                    "max_new_tokens": settings["max_new_tokens"],
                    "remaining_budget": CAPS,
                }
                response = port.generate(request, Event())
                record_path = directory / (record["record_id"] + "-" + role)
                record_path.mkdir()
                # Freeze generation before any candidate/offline assessment call.
                write_report(
                    record_path / "generation.json",
                    {
                        "request": request,
                        "response": response,
                        "prompt_hash": json_hash(example["a_prompt"]),
                        "inspection": port.inspect(),
                    },
                )
                repair, format_error = None, None
                if response["status"] == "ok":
                    try:
                        repair = parse_draft(response["text"])
                        target = ast.parse(problem["source"]).body[0]
                        bundle = ast.parse(repair["source"]).body
                        if (
                            len(bundle) != 1
                            or not isinstance(bundle[0], ast.FunctionDef)
                            or bundle[0].name != target.name
                            or ast.dump(bundle[0].args) != ast.dump(target.args)
                            or len(set(repair["requirement_ids"])) != len(repair["requirement_ids"])
                            or not set(repair["requirement_ids"])
                            <= {r["requirement_id"] for r in problem["requirements"]}
                        ):
                            raise ValueError("Signature/requirement mismatch")
                    except (ValueError, SyntaxError, ValidationError) as error:
                        repair, format_error = None, type(error).__name__
                else:
                    format_error = response["status"]
                visible, offline = [], []
                if repair is not None:
                    try:
                        visible = runner.execute_many(
                            repair["source"], "solve", [t["inputs"] for t in tests]
                        )
                        executions += len(visible)
                    except ValueError as error:
                        repair, format_error = None, type(error).__name__
                accepted = (
                    bool(visible)
                    and repair is not None
                    and all(
                        not r.exception_type
                        and not r.input_mutated
                        and equal(r.actual_output, t["oracle_spec"]["expected"])
                        for r, t in zip(visible, tests, strict=True)
                    )
                )
                answer = {
                    "source": repair["source"] if repair else None,
                    "accepted": accepted,
                    "visible_executions": [asdict(r) for r in visible],
                }
                write_report(record_path / "answer.json", answer)
                if accepted:
                    offline = runner.execute_many(
                        repair["source"], "solve", [t["args"] for t in record["assessment_tests"]]
                    )
                    executions += len(offline)
                solved = (
                    accepted
                    and bool(offline)
                    and all(
                        not r.exception_type
                        and not r.input_mutated
                        and equal(r.actual_output, t["expected"])
                        for r, t in zip(offline, record["assessment_tests"], strict=True)
                    )
                )
                row = {
                    "record_id": record["record_id"],
                    "base_problem_id": record["base_problem_id"],
                    "role": role,
                    "solved": bool(solved),
                    "accepted": accepted,
                    "incorrect_accepted": accepted and not solved,
                    "malformed": repair is None,
                    "format_error": format_error,
                    "usage": response["usage"],
                    "response_status": response["status"],
                    "adapter_hash": response["adapter_hash"],
                    "model_config_hash": response["model_config_hash"],
                    "offline_validation": [asdict(r) for r in offline],
                }
                write_report(record_path / "assessment.json", row)
                rows.append(row)
                print(
                    json.dumps({k: row[k] for k in ("record_id", "role", "solved", "malformed")}),
                    flush=True,
                )
                if response["status"] != "ok":
                    write_report(
                        directory / "interrupted.json",
                        {
                            "rows": rows,
                            "reason": "Native infrastructure/budget failure; no quality conclusion",
                        },
                    )
                    raise RuntimeError("Validation interrupted; partial evidence retained")
    aggregates = {}
    for role in roles:
        subset = [r for r in rows if r["role"] == role]
        aggregates[role] = {
            "total": len(subset),
            **{
                key: sum(r[key] for r in subset)
                for key in ("solved", "accepted", "incorrect_accepted", "malformed")
            },
            "input_tokens": sum(r["usage"]["input_tokens"] for r in subset),
            "output_tokens": sum(r["usage"]["output_tokens"] for r in subset),
            "generation_elapsed_ms": sum(r["usage"]["elapsed_ms"] for r in subset),
            "peak_memory_mb": max(r["usage"]["peak_memory_mb"] or 0 for r in subset),
        }
    report = {
        "status": "completed_diagnostic",
        "aggregates": aggregates,
        "rows": rows,
        "function_executions": executions,
        "model_manifest_hash": model_manifest_hash,
        "registry_path": registry_used,
        "base_revision_hash": base_revision_hash,
        "all_variants": all_variants,
        "seed": settings["seed"],
        "max_new_tokens": settings["max_new_tokens"],
        "source_manifest_hash": json_hash(manifest),
        "runner": runner_info,
        "training_started": False,
        "selected_adapter": None,
        "scope": (
            "All 20 authorized validation variants; one seed."
            if all_variants
            else "One fixed corruption per each of 10 Stage 1 validation bases; one seed."
        ),
        "limitations": [
            "Earlier A checkpoints not compared in Stage 2 yet.",
            "Not a final benchmark; limited imported synthetic corpus.",
            "No expanded Stage 2 corpus.",
            "Checkpoint selection/non-regression remains pending.",
        ],
    }
    write_report(directory / "report.json", report)
    print(json.dumps({"status": report["status"], "aggregates": aggregates}), flush=True)
    return report


def training_preconditions(config_path):
    settings = config(config_path)
    reasons = []
    seal = None
    try:
        seal = final_pool_metadata(config_path)
    except (ValueError, KeyError, OSError) as error:
        reasons.append(str(error))
    if not settings["training_enabled"]:
        reasons.append("Training disabled by configuration")
    else:
        from .refresh import recipe

        try:
            recipe(settings)
        except ValueError as error:
            reasons.append(str(error))
    return {
        "status": "blocked" if reasons else "ready_for_pilot",
        "training_started": False,
        "reasons": reasons,
        "selected_adapter": None,
        "final_pool": seal,
    }
