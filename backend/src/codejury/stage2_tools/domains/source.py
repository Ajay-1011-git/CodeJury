"""Static, host-side source analysis. Parsing only; submitted source is never imported here.

Static rejection supplements, and never replaces, the VM sandbox.
"""

import ast
import hashlib
import re
from dataclasses import dataclass, field

# Reviewed import allowlist. Each symbol was checked as a pure, deterministic standard-library
# callable (see backend/docs/stage2_tools/audit.md) before being enabled.
ALLOWLIST = {
    "math.gcd",
    "math.isqrt",
    "bisect.bisect_left",
    "bisect.bisect_right",
    "collections.Counter",
    "collections.deque",
}
BUILTIN_CALLS = {
    "len",
    "range",
    "sum",
    "min",
    "max",
    "abs",
    "sorted",
    "reversed",
    "enumerate",
    "zip",
    "all",
    "any",
    "int",
    "bool",
    "str",
    "list",
    "dict",
    "set",
    "tuple",
}
EXCEPTION_NAMES = {
    "Exception",
    "ValueError",
    "TypeError",
    "IndexError",
    "KeyError",
    "ZeroDivisionError",
    "AssertionError",
}
MAX_SOURCE_BYTES = 48_000
MAX_NODES = 5000
MAX_HELPERS = 3
_FORBIDDEN = (
    ast.ClassDef,
    ast.AsyncFunctionDef,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.Await,
    ast.Global,
    ast.Nonlocal,
    ast.Lambda,
    ast.Yield,
    ast.YieldFrom,
    ast.With,
    ast.Match,
)
_SIGNATURE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(([^()]*)\)\s*$")


class SourceError(ValueError):
    pass


@dataclass
class SourceInfo:
    function_name: str
    signature: str
    helpers: dict[str, str] = field(default_factory=dict)
    imports: dict[str, str] = field(default_factory=dict)  # local alias -> module or module.attr
    tree: ast.Module | None = None


def signature_of(function: ast.FunctionDef) -> str:
    return f"{function.name}({', '.join(a.arg for a in function.args.args)})"


def parse_signature(text: str) -> tuple[str, list[str]]:
    match = _SIGNATURE.match(text)
    if not match:
        raise SourceError(f"Malformed signature {text!r}")
    params = [p.strip() for p in match.group(2).split(",")] if match.group(2).strip() else []
    if any(not p.isidentifier() for p in params):
        raise SourceError(f"Malformed signature {text!r}")
    return match.group(1), params


def _check_function(function: ast.FunctionDef) -> None:
    args = function.args
    if function.decorator_list or function.returns:
        raise SourceError(f"{function.name}: decorators and return annotations are unsupported")
    if (
        args.posonlyargs
        or args.vararg
        or args.kwarg
        or args.kwonlyargs
        or args.defaults
        or args.kw_defaults
        or any(a.annotation for a in args.args)
        or not 1 <= len(args.args) <= 6
    ):
        raise SourceError(f"{function.name}: need 1-6 plain positional parameters, no defaults")
    if len({a.arg for a in args.args}) != len(args.args):
        raise SourceError(f"{function.name}: duplicate parameter names")


def _collect_imports(tree: ast.Module, allowed: set[str]) -> dict[str, str]:
    imports: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.level or node.module is None:
                raise SourceError("Relative imports are unsupported")
            for alias in node.names:
                dotted = f"{node.module}.{alias.name}"
                if alias.name == "*" or dotted not in allowed:
                    raise SourceError(f"Import {dotted} is not an allowed dependency")
                imports[alias.asname or alias.name] = dotted
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "." in alias.name or not any(a.startswith(alias.name + ".") for a in allowed):
                    raise SourceError(f"Module {alias.name} is not an allowed dependency")
                imports[alias.asname or alias.name] = alias.name
    return imports


def analyze_source(
    source: str,
    function_name: str,
    helper_interfaces: list[dict],
    allowed_dependencies: list[str],
    *,
    require_helpers: bool = True,
) -> SourceInfo:
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise SourceError("Source exceeds 48,000 bytes")
    allowed = set(allowed_dependencies)
    if not allowed <= ALLOWLIST:
        raise SourceError(
            f"Dependencies outside the reviewed allowlist: {sorted(allowed - ALLOWLIST)}"
        )
    if not function_name.isidentifier():
        raise SourceError("Invalid function name")
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise SourceError("Source is not valid Python syntax") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise SourceError("Source AST exceeds the node limit")
    imports = _collect_imports(tree, allowed)
    functions = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if not isinstance(node, ast.FunctionDef):
            raise SourceError("Only imports and function definitions are allowed at module level")
        functions.append(node)
    names = [f.name for f in functions]
    if len(set(names)) != len(names):
        raise SourceError("Duplicate function definitions")
    if function_name not in names:
        raise SourceError(f"Target function {function_name} is not defined")
    helper_defs = [f for f in functions if f.name != function_name]
    if len(helper_defs) > MAX_HELPERS:
        raise SourceError("At most 3 helper functions are supported")
    declared = {}
    for iface in helper_interfaces:
        name, params = parse_signature(iface["signature"])
        if name != iface["name"]:
            raise SourceError(f"Helper interface {iface['name']} signature names {name}")
        declared[name] = params
    if function_name in declared:
        raise SourceError("Target cannot also be a helper")
    for helper in helper_defs:
        if helper.name not in declared:
            raise SourceError(f"Helper {helper.name} has no reviewed interface")
    if require_helpers:
        missing = set(declared) - {h.name for h in helper_defs}
        if missing:
            raise SourceError(f"Missing helpers: {sorted(missing)}")
    for function in functions:
        _check_function(function)
        if (
            function.name in declared
            and [a.arg for a in function.args.args] != declared[function.name]
        ):
            raise SourceError(f"Helper {function.name} changed its reviewed signature")
    for node in nodes:
        if isinstance(node, _FORBIDDEN):
            raise SourceError(f"Unsupported construct {type(node).__name__}")
        if isinstance(node, ast.FunctionDef) and not any(node is f for f in functions):
            raise SourceError("Nested function definitions are unsupported")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise SourceError("Dunder names are unsupported")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise SourceError("Private/dunder attribute access is unsupported")
    module_names = set(names) | set(imports)
    for function in functions:
        bound = {a.arg for a in function.args.args}
        for node in ast.walk(function):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                bound.add(node.id)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                bound.add(node.name)
        for node in ast.walk(function):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in bound | module_names | BUILTIN_CALLS | EXCEPTION_NAMES:
                    raise SourceError(f"Unknown or disallowed name {node.id!r}")
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                target = imports.get(node.value.id)
                if target and "." not in target and f"{target}.{node.attr}" not in allowed:
                    raise SourceError(f"{target}.{node.attr} is not an allowed dependency")
                if target and "." in target:
                    raise SourceError("Attributes of imported callables are unsupported")
    target = next(f for f in functions if f.name == function_name)
    return SourceInfo(
        function_name,
        signature_of(target),
        {h.name: signature_of(h) for h in helper_defs},
        imports,
        tree,
    )


def check_bundle(source: str, problem: dict) -> SourceInfo:
    """A candidate bundle must preserve the target signature, helper interfaces and imports."""
    info = analyze_source(
        source,
        problem["function_name"],
        problem["helper_interfaces"],
        problem["allowed_dependencies"],
    )
    if info.signature != problem["signature"]:
        raise SourceError("Target signature changed")
    return info


def normalized_hash(source: str) -> str:
    """Hash of the formatting-independent AST, for deduplicating alternatives."""
    tree = ast.parse(source)
    # Python 3.12 adds empty type_params to function/class ASTs. Normalize that
    # metadata structurally so the same supported source clusters on 3.11/3.12.
    # Never edit the rendered dump: that could also alter literal string values.
    for node in ast.walk(tree):
        if getattr(node, "type_params", None) == []:
            node._fields = tuple(field for field in node._fields if field != "type_params")
    return hashlib.sha256(ast.dump(tree, annotate_fields=True).encode()).hexdigest()
