"""Five bounded AST edit families shared by repair search and the mutation auditor.

Everything here is host-side parsing/unparsing only; whether an edit compiles and behaves is
decided by the sandbox. Heuristics (scope/type) only order proposals, they never accept them.
"""

import ast
import copy
import hashlib
from dataclasses import dataclass, field

from ..codec.json_v1 import MAX_SAFE_INTEGER
from ..domains import SourceError, check_bundle, normalized_hash

FAMILIES = (
    "comparison",
    "boundary_constant",
    "boolean_negation",
    "arithmetic",
    "variable_reference",
)
_CMP = {
    ast.Lt: [ast.LtE, ast.Gt, ast.GtE],
    ast.LtE: [ast.Lt, ast.GtE, ast.Gt],
    ast.Gt: [ast.GtE, ast.Lt, ast.LtE],
    ast.GtE: [ast.Gt, ast.LtE, ast.Lt],
    ast.Eq: [ast.NotEq],
    ast.NotEq: [ast.Eq],
}
# Division (/) and exponentiation (**) are excluded: they can produce floats.
_ARITH = {
    ast.Add: [ast.Sub, ast.Mult],
    ast.Sub: [ast.Add, ast.Mult],
    ast.Mult: [ast.Add, ast.Sub],
    ast.FloorDiv: [ast.Mult, ast.Mod],
    ast.Mod: [ast.FloorDiv],
}


@dataclass
class EditProposal:
    family: str
    location: dict
    before: str
    after: str
    source: str
    parent_source_hash: str
    result_source_hash: str
    node_index: int = 0
    extra: dict = field(default_factory=dict)

    def edit(self) -> dict:
        return {
            "location": self.location,
            "operator_family": self.family,
            "before": self.before,
            "after": self.after,
            "parent_source_hash": self.parent_source_hash,
            "result_source_hash": self.result_source_hash,
        }


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def location_of(node: ast.AST) -> dict:
    return {
        "lineno": node.lineno,
        "col_offset": node.col_offset,
        "end_lineno": node.end_lineno,
        "end_col_offset": node.end_col_offset,
    }


def overlaps(a: dict, b: dict) -> bool:
    return (a["lineno"], a["col_offset"]) <= (b["end_lineno"], b["end_col_offset"]) and (
        b["lineno"],
        b["col_offset"],
    ) <= (a["end_lineno"], a["end_col_offset"])


def _function_scopes(tree: ast.Module) -> dict[int, set[str]]:
    """Map id(Name node) -> names bound in the enclosing function (params + assigned names)."""
    scope = {}
    for function in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
        bound = {a.arg for a in function.args.args}
        for node in ast.walk(function):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                bound.add(node.id)
        for node in ast.walk(function):
            if isinstance(node, ast.Name):
                scope[id(node)] = bound
    return scope


def _negation_targets(node: ast.AST):
    if isinstance(node, (ast.If, ast.While, ast.IfExp)):
        yield node.test
    if isinstance(node, ast.comprehension):
        yield from node.ifs


def _variants(tree: ast.Module, family: str) -> list[tuple[int, ast.AST, str, object]]:
    """(node_index, node, label, payload) for every replacement of the family."""
    scopes = _function_scopes(tree) if family == "variable_reference" else {}
    nodes = list(ast.walk(tree))
    index = {id(n): i for i, n in enumerate(nodes)}
    out = []
    for node in nodes:
        if family == "comparison" and isinstance(node, ast.Compare):
            for k, op in enumerate(node.ops):
                for new in _CMP.get(type(op), []):
                    out.append((index[id(node)], node, "op", (k, new)))
        elif family == "boundary_constant":
            if (
                isinstance(node, ast.Constant)
                and type(node.value) is int
                and abs(node.value) <= MAX_SAFE_INTEGER
            ):
                for delta in (1, -1):
                    if abs(node.value + delta) <= MAX_SAFE_INTEGER:
                        out.append((index[id(node)], node, "const", node.value + delta))
        elif family == "boolean_negation":
            for test in _negation_targets(node):
                out.append((index[id(test)], test, "neg", None))
        elif family == "arithmetic":
            if isinstance(node, (ast.BinOp, ast.AugAssign)):
                for new in _ARITH.get(type(node.op), []):
                    out.append((index[id(node)], node, "arith", new))
        elif family == "variable_reference":
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and id(node) in scopes:
                for name in sorted(scopes[id(node)] - {node.id}):
                    out.append((index[id(node)], node, "name", name))
    return out


def _apply(tree: ast.Module, node_index: int, label: str, payload) -> ast.Module:
    copy_tree = copy.deepcopy(tree)  # every edit starts from a fresh copy of its parent
    node = list(ast.walk(copy_tree))[node_index]
    if label == "op":
        position, new = payload
        node.ops[position] = new()
    elif label == "const":
        node.value = payload
    elif label == "arith":
        node.op = payload()
    elif label == "name":
        node.id = payload
    elif label == "neg":
        _replace_with_negation(copy_tree, node)
    return copy_tree


def _replace_with_negation(tree: ast.Module, target: ast.AST) -> None:
    for parent in ast.walk(tree):
        for name, value in ast.iter_fields(parent):
            if value is target:
                setattr(parent, name, _negate(target))
                return
            if isinstance(value, list) and any(item is target for item in value):
                value[:] = [_negate(item) if item is target else item for item in value]
                return


def _negate(test: ast.AST) -> ast.AST:
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return test.operand
    wrapped = ast.UnaryOp(op=ast.Not(), operand=test)
    return ast.copy_location(wrapped, test)


def enumerate_edits(
    source: str,
    families=FAMILIES,
    *,
    limit: int | None = None,
) -> list[EditProposal]:
    """All single-edit proposals of the requested families, each a fresh copy of the parent.

    Proposals are returned in a stable, family-then-position order; the caller ranks them.
    """
    tree = ast.parse(source)
    parent_hash = sha(source)
    proposals: list[EditProposal] = []
    for family in families:
        for node_index, node, label, payload in _variants(tree, family):
            if limit is not None and len(proposals) >= limit:
                return proposals
            # AST offsets are UTF-8 byte offsets. Preserve comments, spelling and all
            # source outside the reported edit so the core can replay the exact chain.
            lines = source.encode().splitlines(keepends=True)
            start = sum(map(len, lines[: node.lineno - 1])) + node.col_offset
            stop = sum(map(len, lines[: node.end_lineno - 1])) + node.end_col_offset
            before = source.encode()[start:stop].decode()
            changed = _apply(tree, node_index, label, payload)
            new_node = list(ast.walk(changed))[node_index] if label != "neg" else None
            after = ast.unparse(new_node) if new_node is not None else _after_negation(node)

            def splice(replacement):
                return (
                    source.encode()[:start] + replacement.encode() + source.encode()[stop:]
                ).decode()

            text = splice(after)
            expected = ast.dump(ast.parse(ast.unparse(changed)), include_attributes=False)
            try:
                same = ast.dump(ast.parse(text), include_attributes=False) == expected
            except SyntaxError:
                same = False
            # Add grouping only when the parent needs it to preserve the intended AST.
            if not same and isinstance(node, ast.expr):
                after = "(" + after + ")"
                text = splice(after)
            if ast.dump(ast.parse(text), include_attributes=False) != expected:
                continue
            proposals.append(
                EditProposal(
                    family,
                    location_of(node),
                    before,
                    after,
                    text,
                    parent_hash,
                    sha(text),
                    node_index,
                )
            )
    return proposals


def _after_negation(test: ast.AST) -> str:
    return ast.unparse(_negate(copy.deepcopy(test)))


def check_edit_result(proposal: EditProposal, parent_source: str, problem: dict) -> str | None:
    """Reason an edit result is unacceptable (changed signature/dependencies/names), else None."""
    try:
        parent = check_bundle(parent_source, problem)
        child = check_bundle(proposal.source, problem)
    except SourceError as exc:
        return str(exc)
    if child.signature != parent.signature or child.helpers != parent.helpers:
        return "signature changed"
    if child.imports != parent.imports:
        return "dependencies changed"
    if proposal.result_source_hash == sha(parent_source) or normalized_hash(
        proposal.source
    ) == normalized_hash(parent_source):
        return "no-op edit"
    return None
