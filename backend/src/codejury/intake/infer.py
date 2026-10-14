"""AST-only interface/use-site inference. No candidate execution or cloud transport."""

import ast

from codejury.stage2_core.intake import interfaces, signature
from codejury.stage2_tools.domains import validate_domain
from codejury.stage2_tools.domains.source import analyze_source

ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ()[]{}.,:;!?+-*/_=|"
KINDS = (
    "integer",
    "boolean",
    "string",
    "integer_list",
    "string_list",
    "integer_matrix",
    "integer_dict",
    "null",
)


def domain_for(kind):
    integer = {"kind": "integer", "min": -1000, "max": 1000}
    string = {"kind": "string", "alphabet": ALPHABET, "min_length": 0, "max_length": 64}

    def sequence(item):
        return {"kind": "list", "item_domain": item, "min_length": 0, "max_length": 32}

    if kind == "integer":
        domain = integer
    elif kind == "boolean":
        domain = {"kind": "boolean"}
    elif kind == "null":
        domain = {"kind": "null"}
    elif kind == "string":
        domain = string
    elif kind == "integer_list":
        domain = sequence(integer)
    elif kind == "string_list":
        domain = sequence(string)
    elif kind == "integer_matrix":
        domain = sequence(sequence(integer))
    elif kind == "integer_dict":
        domain = {
            "kind": "dict",
            "key_domain": string,
            "value_domain": integer,
            "required_keys": [],
            "min_size": 0,
            "max_size": 20,
        }
    else:
        raise ValueError("Unsupported inferred domain kind")
    validate_domain(domain)
    return domain


def infer(source, function_name):
    analyze_source(source, function_name, [], [])
    target = interfaces(source, function_name)[function_name]
    names = [a.arg for a in target.args.args]
    uses = {name: set() for name in names}
    string_methods = {
        "split",
        "strip",
        "lower",
        "upper",
        "replace",
        "startswith",
        "endswith",
        "join",
        "find",
        "rfind",
        "isdigit",
        "isalpha",
        "swapcase",
        "rjust",
        "ljust",
        "rsplit",
    }
    for node in ast.walk(target):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Name) and node.iter.id in uses:
            uses[node.iter.id].add("iterated")
        if (
            isinstance(node, ast.comprehension)
            and isinstance(node.iter, ast.Name)
            and node.iter.id in uses
        ):
            uses[node.iter.id].add("iterated")
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id in uses
        ):
            uses[node.value.id].add("indexed")
        if isinstance(node, ast.Compare):
            for part in [node.left, *node.comparators]:
                if isinstance(part, ast.Name) and part.id in uses:
                    uses[part.id].add("compared")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "len",
                "sum",
                "sorted",
                "range",
                "abs",
            }:
                for arg in node.args:
                    if isinstance(arg, ast.Name) and arg.id in uses:
                        uses[arg.id].add(
                            {
                                "len": "length_used",
                                "sum": "numeric_reduction",
                                "sorted": "ordered",
                                "range": "integer_iteration_bound",
                                "abs": "numeric",
                            }[node.func.id]
                        )
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in uses
            ):
                method = node.func.attr
                if method in {"items", "keys", "values", "get"}:
                    uses[node.func.value.id].add("dictionary_use")
                elif method in string_methods:
                    uses[node.func.value.id].add("string_use")
    domains = []
    for name in names:
        facts = uses[name]
        kind = (
            "integer_dict"
            if "dictionary_use" in facts
            else "string"
            if "string_use" in facts
            else "integer"
            if facts & {"integer_iteration_bound", "numeric"}
            else "integer_list"
            if facts & {"iterated", "indexed", "length_used", "numeric_reduction", "ordered"}
            else "integer"
        )
        domains.append(
            {
                "param": name,
                "domain": domain_for(kind),
                "source": "local_ast",
                "confidence": "tentative",
                "uses": sorted(facts),
            }
        )
    # Strings from the body never cross the cloud boundary. Numeric literal facts are
    # bounded scalars only, with no expressions, variable names or source snippets.
    literals = sorted(
        {
            node.value
            for node in ast.walk(target)
            if isinstance(node, ast.Constant)
            and type(node.value) is int
            and abs(node.value) <= 1000000
        }
    )[:16]
    return {
        "function": {"name": function_name, "signature": signature(target)},
        "arg_domains": domains,
        "ast_facts": {
            "parameters": [
                {"name": d["param"], "uses": d["uses"], "tentative_kind": d["domain"]["kind"]}
                for d in domains
            ],
            "numeric_literals": literals,
        },
    }
