"""Controller identities and AST-only intake; semantic support belongs to ToolPort."""

import ast
from uuid import uuid4

from codejury.stage2_core.contracts import CheckedToolPort, checked, source_hash


def interfaces(source, target):
    tree = ast.parse(source)
    functions = {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if not isinstance(node, ast.FunctionDef) or node.decorator_list:
            raise ValueError("Only plain functions and approved imports are supported")
        args = node.args
        if (
            args.vararg
            or args.kwarg
            or args.kwonlyargs
            or args.defaults
            or args.kw_defaults
            or node.returns
            or any(a.annotation for a in args.posonlyargs + args.args)
        ):
            raise ValueError("Fixed unannotated positional interfaces required")
        if not 1 <= len(args.posonlyargs + args.args) <= 6:
            raise ValueError("Interface requires 1–6 positional parameters")
        if node.name in functions:
            raise ValueError("Duplicate function name")
        if any(
            isinstance(n, (ast.AsyncFunctionDef, ast.Yield, ast.YieldFrom, ast.ClassDef))
            for n in ast.walk(node)
        ):
            raise ValueError("Async, generators and classes are unsupported")
        functions[node.name] = node
    if target not in functions or len(functions) > 4:
        raise ValueError("One target and at most three helpers required")
    return functions


def signature(node):
    # Never unparse a default, annotation or body into an independent view.
    names = [a.arg for a in node.args.posonlyargs]
    if names:
        names.append("/")
    names.extend(a.arg for a in node.args.args)
    return f"{node.name}({', '.join(names)})"


def prepare(create, *, problem_id=None):
    create = checked(create, "RunCreate")
    nodes = interfaces(create["source"], create["function_name"])
    target = nodes[create["function_name"]]
    names = [a.arg for a in target.args.posonlyargs + target.args.args]
    if names != [d["name"] for d in create["domain_schema"]]:
        raise ValueError("Domains must match positional parameter names and order")
    helpers = {h["name"]: h for h in create["helper_interfaces"]}
    if len(helpers) != len(create["helper_interfaces"]) or helpers.keys() != (
        nodes.keys() - {create["function_name"]}
    ):
        raise ValueError("Every helper requires exactly one reviewed interface")
    if any(
        h["signature"] != signature(nodes[name]) or not h["contract_text"].strip()
        for name, h in helpers.items()
    ):
        raise ValueError("Helper interface mismatch or missing behavior")
    requirements = {r["requirement_id"]: r for r in create["requirements"]}
    if len(requirements) != len(create["requirements"]):
        raise ValueError("Duplicate requirement identity")
    tests = []
    for supplied in create["supplied_tests"]:
        ids = supplied["requirement_ids"]
        if (
            not ids
            or len(set(ids)) != len(ids)
            or any(
                r not in requirements or requirements[r]["approval_status"] != "approved"
                for r in ids
            )
        ):
            raise ValueError("Supplied tests require approved requirement references")
        tests.append(
            checked(
                {
                    "schema_version": "stage2.v1",
                    "test_id": "t-" + uuid4().hex,
                    "input_codec_version": "json.v1",
                    "inputs": supplied["inputs"],
                    "related_inputs": None,
                    "oracle_spec": {"kind": "literal", "expected": supplied["expected"]},
                    "oracle_status": "authoritative",
                    "oracle_source": "user",
                    # Tentative until the ToolPort receipt confirms domain/oracle support.
                    "domain_valid": True,
                    "requirement_ids": ids,
                    "provenance": "supplied",
                },
                "TestCase",
            )
        )
    problem = {
        k: create[k]
        for k in (
            "source",
            "function_name",
            "contract_text",
            "domain_schema",
            "helper_interfaces",
            "requirements",
            "allowed_dependencies",
            "resource_profile",
        )
    }
    problem.update(
        schema_version="stage2.v1",
        problem_id=problem_id or "p-" + uuid4().hex,
        source_hash=source_hash(create["source"]),
        signature=signature(target),
        supplied_test_ids=[t["test_id"] for t in tests],
        input_codec_version="json.v1",
    )
    return checked(problem, "Problem"), tests


def validate_source(ledger, run_id, tool_port, source, tests, cancel):
    problem = ledger.snapshot(run_id)["problem"]
    identifier = "validate-" + uuid4().hex
    request = checked(
        {
            "schema_version": "stage2.v1",
            "request_id": identifier,
            "id_prefix": identifier,
            "run_id": run_id,
            "problem": problem,
            "parameters": {"operation": "validate", "source": source, "tests": tests},
            "remaining_budget": ledger.accounts[run_id].remaining(),
        },
        "ToolRequest",
    )
    ledger.dispatch_tool(request)
    result = CheckedToolPort(tool_port).call(request, cancel)
    ledger.settle_tool(result)
    receipt = result["validation"]
    return (
        not cancel.is_set()
        and result["status"] == "ok"
        and receipt is not None
        and receipt["valid"]
        and receipt["error"] is None
        and receipt["signature"] == problem["signature"]
    )


def admit(create, *, ledger, run_id, tool_port, cancel, profile, model_configs, mode="live"):
    problem, tests = prepare(create)
    ledger.create_run(run_id, problem, mode=mode, profile=profile, model_configs=model_configs)
    for test in tests:
        ledger.add_test(run_id, test)
    valid = validate_source(ledger, run_id, tool_port, problem["source"], tests, cancel)
    if not valid:
        ledger.append_event(run_id, "action_refused", "Intake lacks valid semantic receipt")
    return {"problem": problem, "tests": tests, "valid": valid}
