"""Offline, train-only composed logic corruptions; every target is execution-filtered.

Uses the inherited split identities. No teacher, model, assessment or development
benchmark examples are inputs. Candidate and reference execution stays in Docker.
"""

import ast
import copy
import hashlib
import itertools
import json
import random
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from codejury.stage2_tools.codec import typed_equal
from codejury.training.data import assert_disjoint

from ..contracts import canonical_json
from ..data import learning_example, load_stage1, validate_records, write_report
from ..registry import MODEL_SYSTEM, local_path


def procedural_sources():
    """Equivalent implementations of existing train identities, authored locally."""
    bodies = {
        "total": "result = 0\nfor x in values:\n    result += x\nreturn result",
        "square_total": "result = 0\nfor x in values:\n    result += x * x\nreturn result",
        "alternating_total": (
            "result = 0\n"
            "for i, x in enumerate(values):\n"
            "    if i % 2 == 0:\n"
            "        result += x\n"
            "    else:\n"
            "        result -= x\n"
            "return result"
        ),
        "nonzero_count": """result = 0
for x in values:
    if x != 0:
        result += 1
return result""",
        "range_width": (
            "if not values:\n"
            "    return 0\n"
            "low = values[0]\n"
            "high = values[0]\n"
            "for x in values[1:]:\n"
            "    if x < low:\n"
            "        low = x\n"
            "    if x > high:\n"
            "        high = x\n"
            "return high - low"
        ),
        "prefix_sums": (
            "result = []\n"
            "current = 0\n"
            "for x in values:\n"
            "    current += x\n"
            "    result.append(current)\n"
            "return result"
        ),
        "running_max": (
            "result = []\n"
            "for x in values:\n"
            "    if result and result[-1] > x:\n"
            "        result.append(result[-1])\n"
            "    else:\n"
            "        result.append(x)\n"
            "return result"
        ),
        "prefix_positive_counts": (
            "result = []\n"
            "count = 0\n"
            "for x in values:\n"
            "    if x > 0:\n"
            "        count += 1\n"
            "    result.append(count)\n"
            "return result"
        ),
        "adjacent_differences": (
            "result = []\n"
            "for i in range(1, len(values)):\n"
            "    result.append(values[i] - values[i - 1])\n"
            "return result"
        ),
        "prefix_alternating": (
            "result = []\n"
            "current = 0\n"
            "for i, x in enumerate(values):\n"
            "    if i % 2 == 0:\n"
            "        current += x\n"
            "    else:\n"
            "        current -= x\n"
            "    result.append(current)\n"
            "return result"
        ),
        "first_index": """for i, x in enumerate(values):
    if x == target:
        return i
return -1""",
        "last_index": (
            "result = -1\n"
            "for i, x in enumerate(values):\n"
            "    if x == target:\n"
            "        result = i\n"
            "return result"
        ),
        "contains": "for x in values:\n    if x == target:\n        return True\nreturn False",
        "occurrence_count": """count = 0
for x in values:
    if x == target:
        count += 1
return count""",
        "first_positive_index": """for i, x in enumerate(values):
    if x > 0:
        return i
return -1""",
        "strictly_increasing": (
            "for i in range(1, len(values)):\n"
            "    if values[i - 1] >= values[i]:\n"
            "        return False\n"
            "return True"
        ),
        "nondecreasing": (
            "for i in range(1, len(values)):\n"
            "    if values[i - 1] > values[i]:\n"
            "        return False\n"
            "return True"
        ),
        "palindrome_sequence": (
            "for i in range(len(values) // 2):\n"
            "    if values[i] != values[len(values) - 1 - i]:\n"
            "        return False\n"
            "return True"
        ),
        "all_equal": """for x in values[1:]:
    if x != values[0]:
        return False
return True""",
        "one_positive": """count = 0
for x in values:
    if x > 0:
        count += 1
return count == 1""",
        "reverse_sequence": (
            "result = []\n"
            "for i in range(len(values) - 1, -1, -1):\n"
            "    result.append(values[i])\n"
            "return result"
        ),
        "remove_endpoints": (
            "result = []\n"
            "for i in range(1, len(values) - 1):\n"
            "    result.append(values[i])\n"
            "return result"
        ),
    }
    for name, expression in {
        "positive_values": "x > 0",
        "even_values": "x % 2 == 0",
        "above_threshold": "x > threshold",
        "without_zero": "x != 0",
        "negative_positions": "x < 0",
    }.items():
        loop = "i, x in enumerate(values)" if name == "negative_positions" else "x in values"
        output = "i" if name == "negative_positions" else "x"
        bodies[name] = (
            f"result = []\nfor {loop}:\n    if {expression}:\n"
            f"        result.append({output})\nreturn result"
        )
    for name, expression in {
        "increment_each": "x + 1",
        "negate_each": "-x",
        "absolute_each": "abs(x)",
    }.items():
        bodies[name] = (
            f"result = []\nfor x in values:\n    result.append({expression})\nreturn result"
        )
    return bodies


def mutation_sites(source):
    sites = []
    for index, node in enumerate(ast.walk(ast.parse(source))):
        replacement, kind = None, None
        if isinstance(node, ast.Constant) and type(node.value) is int:
            replacement, kind = ast.Constant(node.value + 1), "boundary_constant"
        elif isinstance(node, ast.Compare) and len(node.ops) == 1:
            swaps = {
                ast.Gt: ast.GtE,
                ast.GtE: ast.Gt,
                ast.Lt: ast.LtE,
                ast.LtE: ast.Lt,
                ast.Eq: ast.NotEq,
                ast.NotEq: ast.Eq,
            }
            if type(node.ops[0]) in swaps:
                replacement = copy.deepcopy(node)
                replacement.ops = [swaps[type(node.ops[0])]()]
                kind = "comparison_swap"
        elif isinstance(node, (ast.BinOp, ast.AugAssign)):
            swaps = {
                ast.Add: ast.Sub,
                ast.Sub: ast.Add,
                ast.Mult: ast.Add,
                ast.FloorDiv: ast.Mod,
                ast.Mod: ast.FloorDiv,
            }
            if type(node.op) in swaps:
                replacement = copy.deepcopy(node)
                replacement.op = swaps[type(node.op)]()
                kind = "operator_swap"
        elif isinstance(node, ast.For):
            replacement = copy.deepcopy(node)
            # A realistic missed last iteration; list() also supports range/enumerate.
            replacement.iter = ast.Subscript(
                ast.Call(ast.Name("list", ast.Load()), [copy.deepcopy(node.iter)], []),
                ast.Slice(None, ast.UnaryOp(ast.USub(), ast.Constant(1)), None),
                ast.Load(),
            )
            kind = "missed_last_iteration"
        if replacement is not None:
            sites.append(
                {"node": index, "kind": kind, "replacement": replacement, "line": node.lineno}
            )
    return sites


def mutate(source, sites):
    """Replace disjoint AST nodes; overlapping mutations are rejected explicitly."""
    if not 1 <= len(sites) <= 3 or len({s["node"] for s in sites}) != len(sites):
        raise ValueError("Declare 1–3 distinct mutation sites")
    tree = ast.parse(source)
    nodes = list(ast.walk(tree))
    chosen = {s["node"] for s in sites}
    for index in chosen:
        descendants = {id(n) for n in ast.walk(nodes[index]) if n is not nodes[index]}
        if any(id(nodes[other]) in descendants for other in chosen):
            raise ValueError("Overlapping mutation sites")
    replacements = {id(nodes[s["node"]]): s["replacement"] for s in sites}

    class Replace(ast.NodeTransformer):
        def generic_visit(self, node):
            if id(node) in replacements:
                return ast.copy_location(copy.deepcopy(replacements[id(node)]), node)
            return super().generic_visit(node)

    return ast.unparse(ast.fix_missing_locations(Replace().visit(tree))) + "\n"


def sample_args(domains, rng):
    values = []
    for d in domains:
        if d["kind"] == "integer":
            values.append(rng.randint(d["min"], d["max"]))
        elif d["kind"] == "list_integer":
            values.append(
                [
                    rng.randint(d["min"], d["max"])
                    for _ in range(rng.randint(d["min_length"], d["max_length"]))
                ]
            )
        else:
            raise ValueError("Only inherited integer/list train domains are allowed")
    return values


def correct(result, expected):
    return (
        not result.exception_type
        and not result.input_mutated
        and typed_equal(result.actual_output, expected)
    )


def execute(runner, source, args):
    # The inherited sandbox caps each batch at eight calls.
    results = []
    name = ast.parse(source).body[0].name
    for start in range(0, len(args), 8):
        results.extend(runner.execute_many(source, name, args[start : start + 8]))
    return results


def build(out, runner, *, variants_per_base=2, seed=17):
    """Create an auditable, immutable SFT export, or fail without admitting targets."""
    directory = Path(out).resolve()
    if local_path("artifacts") not in directory.parents:
        raise ValueError("Private training exports must stay in ignored artifacts")
    if variants_per_base != 2 or seed != 17:
        raise ValueError("v1 freezes two variants per base and seed 17")
    manifest, original = load_stage1(local_path("data/manifests/stage1.json"))
    bases = {r["base_problem_id"]: r for r in original if r["split"] == "train"}
    bodies = procedural_sources()
    if not bodies.keys() <= bases.keys():
        raise ValueError("New base identity is not in the inherited train split")
    directory.mkdir(parents=True, exist_ok=False)
    generator = Path(__file__).read_bytes()
    (directory / "generator.py").write_bytes(generator)
    runner.ready()
    records, decisions, executions = [], [], 0
    rng = random.Random(seed)
    for base, body in bodies.items():
        parent = bases[base]
        params = [a.arg for a in ast.parse(parent["correct_source"]).body[0].args.args]
        source = f"def {base}({', '.join(params)}):\n" + "".join(
            "    " + line + "\n" for line in body.splitlines()
        )
        authored = parent["visible_tests"] + parent["assessment_tests"]
        extra = [sample_args(parent["domain"], rng) for _ in range(12)]
        args = [t["args"] for t in authored] + extra
        inherited = execute(runner, parent["correct_source"], args)
        references = execute(runner, source, args)
        executions += 2 * len(args)
        if not all(
            correct(r, t["expected"])
            for r, t in zip(references[: len(authored)], authored, strict=True)
        ) or not all(
            not old.exception_type and correct(new, old.actual_output)
            for old, new in zip(inherited, references, strict=True)
        ):
            raise ValueError(f"Procedural reference failed independent/differential checks: {base}")
        tests = authored + [
            {"test_id": f"sample-{i}", "args": a, "expected": r.actual_output}
            for i, (a, r) in enumerate(zip(extra, references[len(authored) :], strict=True))
        ]
        sites = mutation_sites(source)
        # Composed mutations first. Singles are allowed when no useful pair survives.
        plans = list(itertools.combinations(sites, 2)) + [(s,) for s in sites]
        count, sources = 0, set()
        for plan in plans:
            identity = [{k: s[k] for k in ("node", "kind", "line")} for s in plan]
            entry = {"base_problem_id": base, "mutations": identity}
            try:
                buggy = mutate(source, plan)
            except ValueError:
                decisions.append({**entry, "accepted": False, "reason": "overlapping_sites"})
                continue
            if buggy in sources:
                decisions.append({**entry, "accepted": False, "reason": "duplicate_variant"})
                continue
            sources.add(buggy)
            actual = execute(runner, buggy, args)
            executions += len(args)
            failing = [
                t["test_id"]
                for r, t in zip(actual, tests, strict=True)
                if not correct(r, t["expected"])
            ]
            if not set(failing) & {t["test_id"] for t in tests[2:]}:
                decisions.append({**entry, "accepted": False, "reason": "hidden_suite_survived"})
                continue
            row = copy.deepcopy(parent)
            row.update(
                record_id=f"{base}-logic-{count}",
                buggy_source=buggy,
                correct_source=source,
                assessment_tests=tests[2:],
                failure_evidence=[
                    {"test_id": t["test_id"], "args": t["args"], "result": asdict(r)}
                    for r, t in zip(actual[:2], tests[:2], strict=True)
                    if not correct(r, t["expected"])
                ],
            )
            kinds = ", ".join(s["kind"].replace("_", " ") for s in plan)
            diagnosis = (
                f"The {kinds} corruption violates the contract. Restore the correct "
                "boundaries and state updates while preserving the interface."
            )
            row["response_target"] = {"source": source, "diagnosis": diagnosis, "assumptions": []}
            row["provenance"] = {
                **parent["provenance"],
                "mutation": "composed_logic",
                "mutations": identity,
                "teacher": "none",
            }
            records.append(row)
            decisions.append(
                {**entry, "accepted": True, "record_id": row["record_id"], "failing_tests": failing}
            )
            count += 1
            if count == variants_per_base:
                break
        if not count:
            decisions.append(
                {
                    "base_problem_id": base,
                    "accepted": False,
                    "reason": "no_execution_killed_variant",
                }
            )
        print(json.dumps({"base": base, "accepted_variants": count}), flush=True)
    # Existing validation remains unchanged and separate; never optimize on its loss.
    validation = [r for r in original if r["split"] == "validation"]
    for row in validation:
        tests = row["visible_tests"] + row["assessment_tests"]
        results = execute(runner, row["correct_source"], [t["args"] for t in tests])
        executions += len(tests)
        if not all(correct(r, t["expected"]) for r, t in zip(results, tests, strict=True)):
            raise ValueError("Validation reference failed")
    # The inherited Stage 1 admission check deliberately requires `solve`.
    # Preserve that check unchanged; validate a canonical interface-name copy,
    # then retain the actual named sources that were already executed in Docker.
    canonical = copy.deepcopy(records)
    for row in canonical:
        for field in ("buggy_source", "correct_source"):
            tree = ast.parse(row[field])
            tree.body[0].name = "solve"
            row[field] = ast.unparse(tree) + "\n"
        row["response_target"]["source"] = row["correct_source"]
    validate_records(canonical + validation)
    assert_disjoint(records + validation, identity_only=True)
    if len(records) < 40:
        raise ValueError("Too few execution-filtered logic examples")
    for name, rows in (("train.jsonl", records), ("valid.jsonl", validation)):
        chats = []
        for row in rows:
            example = learning_example(row)
            chats.append(
                {
                    "messages": [
                        {"role": "system", "content": MODEL_SYSTEM},
                        {"role": "user", "content": example["a_prompt"]},
                        {
                            "role": "assistant",
                            "content": canonical_json(example["target"]).decode(),
                        },
                    ]
                }
            )
        (directory / name).write_bytes(b"".join(canonical_json(row) + b"\n" for row in chats))
    (directory / "records.jsonl").write_bytes(
        b"".join(canonical_json(row) + b"\n" for row in records)
    )
    write_report(directory / "decisions.json", decisions)
    proof = {
        "version": "stage2.logic-corpus.v1",
        "role": "fixer_a",
        "runtime_mode": "live",
        "contains_final_assessment": False,
        "source_manifest_hash": hashlib.sha256(
            local_path("data/manifests/stage1.json").read_bytes()
        ).hexdigest(),
        "generator_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "files": {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in ("train.jsonl", "valid.jsonl", "records.jsonl", "decisions.json")
        },
        "splits": {
            "train": {
                "records": len(records),
                "base_problems": len({r["base_problem_id"] for r in records}),
            },
            "validation": {
                "records": len(validation),
                "base_problems": len({r["base_problem_id"] for r in validation}),
            },
        },
        "function_executions": executions,
        "rejection_counts": dict(Counter(d["reason"] for d in decisions if not d["accepted"])),
        "composed_records": sum(len(r["provenance"]["mutations"]) > 1 for r in records),
        "seed": seed,
        "scope": (
            "Bounded v1 topology experiment, not the full v2 rank/LR sweep. No "
            "cloud teacher or dev/final records."
        ),
    }
    write_report(directory / "manifest.json", proof)
    return proof
