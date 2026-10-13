"""Execute remote proposals only inside the existing no-network Docker sandbox."""

import ast
import json
import random
from collections import Counter

from codejury.contracts.intake import inspect_source, validate_json
from codejury.models.worker import file_hash
from codejury.properties import equal
from codejury.runner import DockerRunner

from ..contracts import canonical_json, checked, json_hash
from ..data import learning_example, runtime_example, write_report
from ..leases import ComputeLease
from ..registry import MODEL_SYSTEM, Registry, local_path
from .collect import remote_prompt, source

SAFE_CALLS = {
    "abs",
    "all",
    "any",
    "bool",
    "enumerate",
    "int",
    "len",
    "list",
    "max",
    "min",
    "range",
    "reversed",
    "round",
    "set",
    "sorted",
    "sum",
    "tuple",
    "zip",
}
SAFE_METHODS = {
    "append",
    "count",
    "extend",
    "index",
    "insert",
    "pop",
    "remove",
    "reverse",
    "sort",
    "copy",
}


def structural(row, draft):
    if row["split"] != "train":
        raise ValueError("not_train")
    checked(draft, "RepairDraft")
    target = ast.parse(row["buggy_source"]).body[0]
    inspect_source(draft["source"], "solve", len(row["domain"]))
    tree = ast.parse(draft["source"])
    function = tree.body[0]
    if ast.dump(function.args) != ast.dump(target.args):
        raise ValueError("signature")
    problem, _ = runtime_example(row)
    ids = [r["requirement_id"] for r in problem["requirements"]]
    if sorted(draft["requirement_ids"]) != sorted(ids) or draft["assumptions"]:
        raise ValueError("requirements_or_unreviewed_assumptions")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Dict, ast.DictComp)):
            raise ValueError("lookup_table_needs_review")
        if isinstance(node, ast.Attribute) and node.attr not in SAFE_METHODS:
            raise ValueError("attribute_scope")
        if isinstance(node, ast.Call) and not (
            isinstance(node.func, ast.Name)
            and node.func.id in SAFE_CALLS
            or isinstance(node.func, ast.Attribute)
            and node.func.attr in SAFE_METHODS
        ):
            raise ValueError("call_scope")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            # This pilot's reviewed contracts all have integer/list inputs and outputs.
            # No docstrings/test IDs or string-dependent shortcuts are needed.
            raise ValueError("string_literal_needs_review")
    return ast.dump(tree, include_attributes=False)


def edge_inputs(row):
    rng = random.Random(17)
    batches = []
    for index in range(16):
        args = []
        for domain in row["domain"]:
            lo, hi = domain["min"], domain["max"]
            values = [lo, hi, min(hi, max(lo, 0)), min(hi, max(lo, -1)), min(hi, max(lo, 1))]
            if domain["kind"] == "integer":
                args.append(values[index] if index < len(values) else rng.randint(lo, hi))
            else:
                low, high = domain["min_length"], domain["max_length"]
                length = low if index == 0 else high if index < 5 else rng.randint(low, high)
                args.append(
                    [values[index % len(values)]] * length
                    if index < 5
                    else [rng.randint(lo, hi) for _ in range(length)]
                )
        if args not in batches:
            batches.append(args)
    return batches


def execute(runner, source_text, inputs):
    result = []
    for start in range(0, len(inputs), 8):
        result.extend(runner.execute_many(source_text, "solve", inputs[start : start + 8]))
    return result


def clean_result(result):
    if result.exception_type or result.input_mutated:
        return False
    try:
        validate_json(result.actual_output)
    except ValueError:
        return False
    return True


def verify(row, draft, runner):
    normalized = structural(row, draft)
    tests = row["visible_tests"] + row["assessment_tests"]
    inputs = [test["args"] for test in tests]
    references = execute(runner, row["correct_source"], inputs)
    if not all(
        clean_result(r) and equal(r.actual_output, t["expected"])
        for r, t in zip(references, tests, strict=True)
    ):
        raise ValueError("reference_failed_trusted_training_tests")
    actual = execute(runner, draft["source"], inputs)
    if not all(
        clean_result(r) and equal(r.actual_output, t["expected"])
        for r, t in zip(actual, tests, strict=True)
    ):
        raise ValueError("supplied_or_trusted_training_test_failure")
    edges = edge_inputs(row)
    expected = execute(runner, row["correct_source"], edges)
    actual_edges = execute(runner, draft["source"], edges)
    if not all(
        clean_result(r) and clean_result(a) and equal(r.actual_output, a.actual_output)
        for r, a in zip(expected, actual_edges, strict=True)
    ):
        raise ValueError("training_reference_edge_failure")
    return {
        "normalized_source_hash": json_hash(normalized),
        "function_executions": 2 * (len(inputs) + len(edges)),
        "trusted_tests": len(tests),
        "additional_edges": len(edges),
        "assessment_scope": "TRAIN only",
        "purity": "observed_no_input_mutation",
    }


def chat(row, draft):
    return {
        "messages": [
            {"role": "system", "content": MODEL_SYSTEM},
            {"role": "user", "content": learning_example(row)["a_prompt"]},
            {"role": "assistant", "content": canonical_json(draft).decode()},
        ]
    }


def token_check(record, tokenizer, dataset_class):
    dataset = dataset_class([record], tokenizer, mask_prompt=True)
    tokens, offset = dataset.process(dataset[0])
    prefix = tokenizer.apply_chat_template(
        record["messages"][:-1], tokenize=True, add_generation_prompt=True, return_dict=False
    )
    if (
        tokens[:offset] != prefix
        or len(prefix) != offset
        or not 0 < offset < len(tokens)
        or len(tokens) > 4096
        or offset + 1024 > 4096
        or len(tokens) - offset > 1024
    ):
        raise ValueError("learner_context_or_completion_mask")
    return {
        "prompt_tokens": offset,
        "completion_tokens": len(tokens) - offset,
        "total_tokens": len(tokens),
        "runtime_prefix_matches": True,
    }


def validate_all(cfg):
    _, rows, manifest_hash = source(cfg)
    lookup = {r["record_id"]: r for r in rows if r["split"] == "train"}
    root = local_path(cfg["artifact_root"])
    output = root / "validated-v1"
    output.mkdir(parents=True, exist_ok=True)
    runner = DockerRunner()
    runner_info = runner.ready()
    import yaml

    runtime = yaml.safe_load(local_path("config/stage2_core/runtime.yaml").read_text())
    registry = Registry(local_path(runtime["model_manifest"]))
    with ComputeLease(owner="ajay", job_id="teacher-token-validation", kind="teacher"):
        from mlx_lm.tuner.datasets import ChatDataset
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            str(registry.model_dir), local_files_only=True, trust_remote_code=False
        )
        results = []
        seen = set()
        for path in sorted((root / "proposals-v1").glob("*.json")):
            if path.name == "plan.json":
                continue
            proposal = json.loads(path.read_text())
            lineage = proposal["lineage"]
            row = lookup.get(lineage["record_id"])
            if (
                row is None
                or lineage["split"] != "train"
                or lineage["source_manifest_hash"] != manifest_hash
                or lineage["record_hash"] != json_hash(row)
                or proposal["prompt_hash"] != json_hash(remote_prompt(row))
            ):
                raise ValueError("Proposal training lineage mismatch")
            result_path = output / path.name
            if result_path.exists():
                result = json.loads(result_path.read_text())
                if result["proposal_hash"] != file_hash(path):
                    raise ValueError("Validated proposal changed")
                if result["status"] == "accepted":
                    seen.add(
                        (row["base_problem_id"], result["verification"]["normalized_source_hash"])
                    )
                results.append(result)
                continue
            draft = proposal["response"]["draft"]
            result = {
                "lineage": lineage,
                "proposal_hash": file_hash(path),
                "proposal_path": str(path),
                "status": "rejected",
            }
            try:
                tokens = token_check(chat(row, draft), tokenizer, ChatDataset)
                proof = verify(row, draft, runner)
                identity = (row["base_problem_id"], proof["normalized_source_hash"])
                if identity in seen:
                    raise ValueError("duplicate_solution_same_base")
                seen.add(identity)
                result.update(status="accepted", verification=proof, tokens=tokens, draft=draft)
            except (ValueError, SyntaxError) as error:
                # Only bounded local validation reason, never remote response/HTTP exception text.
                result["reason"] = str(error)[:120]
            write_report(result_path, result)
            results.append(result)
            print(
                json.dumps(
                    {
                        "validated": len(results),
                        "status": result["status"],
                        "reason": result.get("reason"),
                    }
                ),
                flush=True,
            )
    summary = {
        "proposals": len(results),
        "accepted": sum(r["status"] == "accepted" for r in results),
        "accepted_bases": len(
            {r["lineage"]["base_problem_id"] for r in results if r["status"] == "accepted"}
        ),
        "rejections": dict(Counter(r["reason"] for r in results if r["status"] != "accepted")),
        "runner": runner_info,
        "final_contents_opened": False,
        "results_hash": json_hash(results),
    }
    # A smoke validation can precede the complete pilot; immutable summary per results set.
    summary_path = output / ("summary-" + json_hash(summary) + ".json")
    if not summary_path.exists():
        write_report(summary_path, summary)
    return summary
