"""Actual selected-A train-only generations; candidate code runs in Docker only."""

import ast
import json
from dataclasses import asdict
from pathlib import Path
from threading import Event
from uuid import uuid4

import yaml
from jsonschema import ValidationError

from codejury.models.worker import file_hash
from codejury.properties import equal
from codejury.runner import DockerRunner

from ...budgets import CAPS
from ...candidates import parse_draft
from ...contracts import json_hash
from ...data import config as a_config
from ...data import (
    final_pool_metadata,
    learning_example,
    load_stage1,
    runtime_example,
    write_report,
)
from ...model_worker import NativeModelPort
from ...registry import Registry, local_path
from ..fixer_a.refresh import recipe
from . import ALPHAS, SEEDS, failure_fractions


def settings(path):
    value = yaml.safe_load(Path(path).read_text())
    fields = {
        "version",
        "a_config",
        "selected_a_manifest",
        "seeds",
        "alpha_trials",
        "broad_fraction",
        "sample_count",
        "training_enabled",
        "refresh",
    }
    if (
        type(value) is not dict
        or set(value) != fields
        or value["version"] != "stage2.fixer-b-training.v1"
        or value["seeds"] != list(SEEDS)
        or value["alpha_trials"] != list(ALPHAS)
        or type(value["training_enabled"]) is not bool
        or type(value["broad_fraction"]) not in (int, float)
        or not 0.25 <= value["broad_fraction"] <= 0.5
        or type(value["sample_count"]) is not int
        or value["sample_count"] < 4
    ):
        raise ValueError("Invalid frozen B training configuration")
    recipe({"seed": 17, "refresh": value["refresh"]})
    return value


def selected_a(cfg):
    selection = json.loads(local_path(cfg["selected_a_manifest"]).read_text())
    registry = Registry(Path(selection["registry_path"]))
    if (
        selection["status"] != "selected_limited_validation"
        or selection["adapter_hash"] != registry.identity("fixer_a")["adapter_hash"]
        or registry.record["adapters"]["fixer_a"]["card"]["status"] != "completed"
    ):
        raise ValueError("B mining requires actually selected/frozen A")
    return registry


def assess(record, problem, tests, response, directory, runner):
    """Freeze visible acceptance before offline learning assessment; no feedback revision."""
    repair, error = None, None
    if response["status"] != "ok":
        raise RuntimeError("Native transport failure; not a semantic failure")
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
    except (ValueError, SyntaxError, ValidationError) as exc:
        repair, error = None, type(exc).__name__
    visible, offline = [], []
    if repair is not None:
        try:
            visible = runner.execute_many(repair["source"], "solve", [t["inputs"] for t in tests])
        except ValueError as exc:
            repair, error = None, type(exc).__name__
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
    write_report(directory / "answer.json", answer)
    if accepted:
        offline = runner.execute_many(
            repair["source"], "solve", [t["args"] for t in record["assessment_tests"]]
        )
    solved = (
        accepted
        and bool(offline)
        and all(
            not r.exception_type and not r.input_mutated and equal(r.actual_output, t["expected"])
            for r, t in zip(offline, record["assessment_tests"], strict=True)
        )
    )
    result = {
        "solved": bool(solved),
        "accepted": accepted,
        "incorrect_accepted": accepted and not solved,
        "malformed": repair is None,
        "format_error": error,
        "answer_hash": json_hash(answer),
        "function_executions": len(visible) + len(offline),
        "offline_validation": [asdict(r) for r in offline],
    }
    write_report(directory / "assessment.json", result)
    return result


def mine(config_path, out):
    cfg = settings(config_path)
    a_path = local_path(cfg["a_config"])
    learning = a_config(a_path)
    final_seal = final_pool_metadata(a_path)
    manifest, records = load_stage1(local_path(learning["source_manifest"]))
    bases = {}
    for row in sorted(records, key=lambda r: r["record_id"]):
        if row["split"] == "train":
            bases.setdefault(row["base_problem_id"], row)
    registry = selected_a(cfg)
    runtime = yaml.safe_load(local_path(learning["runtime_config"]).read_text())
    directory = Path(out).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    runner = DockerRunner()
    runner_info = runner.ready()
    frozen = {
        "runtime_mode": "live",
        "split": "train",
        "registry_path": str(registry.path),
        "registry_hash": registry.manifest_hash,
        "identity": registry.identity("fixer_a"),
        "source_manifest_hash": json_hash(manifest),
        "selection_hash": file_hash(local_path(cfg["selected_a_manifest"])),
        "final_seal": final_seal,
        "seeds": list(SEEDS),
        "runner": runner_info,
        "view_rule": "First sorted variant per training base; same A runtime view for all seeds.",
        "sampler": "greedy; fixed seeds are repeated deterministic trials, not independent draws",
    }
    write_report(directory / "frozen.json", frozen)
    samples, counts, rows = [], 0, []
    with NativeModelPort(registry, runtime) as port:
        for base, record in sorted(bases.items()):
            problem, tests = runtime_example(record)
            prompt = learning_example(record)["a_prompt"]
            for seed in SEEDS:
                trial = directory / (record["record_id"] + "-" + str(seed))
                trial.mkdir()
                request = {
                    "schema_version": "stage2.v1",
                    "request_id": "mine-" + uuid4().hex,
                    "run_id": "b-train-only-mining",
                    "role": "fixer_a",
                    "purpose": "repair",
                    "prompt": prompt,
                    "seed": seed,
                    "max_new_tokens": learning["max_new_tokens"],
                    "remaining_budget": CAPS,
                }
                response = port.generate(request, Event())
                write_report(
                    trial / "generation.json",
                    {
                        "request": request,
                        "response": response,
                        "record_id": record["record_id"],
                        "prompt_hash": json_hash(prompt),
                    },
                )
                try:
                    outcome = assess(record, problem, tests, response, trial, runner)
                except Exception as exc:
                    write_report(
                        directory / "interrupted.json",
                        {
                            "status": "infrastructure_error",
                            "base_problem_id": base,
                            "seed": seed,
                            "exception_type": type(exc).__name__,
                            "completed_samples": len(samples),
                            "note": "No failure fractions; explicit fresh replay required.",
                        },
                    )
                    raise
                sample = {
                    "runtime_mode": "live",
                    "split": "train",
                    "base_problem_id": base,
                    "seed": seed,
                    "response": response,
                    "solved": outcome["solved"],
                    "infrastructure_error": False,
                    "answer_hash": outcome["answer_hash"],
                }
                samples.append(sample)
                rows.append(
                    {
                        "record_id": record["record_id"],
                        "base_problem_id": base,
                        "seed": seed,
                        **outcome,
                        "usage": response["usage"],
                    }
                )
                counts += outcome["function_executions"]
                with (directory / "samples.jsonl").open("a") as stream:
                    stream.write(json.dumps(sample) + "\n")
                print(
                    json.dumps(
                        {
                            "base": base,
                            "seed": seed,
                            "solved": outcome["solved"],
                            "completed": len(samples),
                        }
                    ),
                    flush=True,
                )
    measured = failure_fractions(
        samples, **{k: frozen["identity"][k] for k in ("adapter_hash", "model_config_hash")}
    )
    if set(measured["fractions"]) != set(bases) or measured["retry_base_ids"]:
        raise RuntimeError("Incomplete train-only failure measurements")
    report = {
        "status": "completed_native_mining",
        "frozen": frozen,
        "measured": measured,
        "samples_hash": json_hash(samples),
        "rows": rows,
        "base_problems": len(bases),
        "samples": len(samples),
        "solved": sum(r["solved"] for r in rows),
        "malformed": sum(r["malformed"] for r in rows),
        "incorrect_accepted": sum(r["incorrect_accepted"] for r in rows),
        "function_executions": counts,
        "training_started": False,
        "canonical_episodes": False,
    }
    write_report(directory / "report.json", report)
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "status",
                    "base_problems",
                    "samples",
                    "solved",
                    "malformed",
                    "function_executions",
                )
            }
        ),
        flush=True,
    )
    return report
