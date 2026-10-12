"""Reviewed property templates and metamorphic relations.

Implementations are pure host-side reference functions; candidate outputs stay untrusted. Each
template's version hash covers its identity and reviewed source text, so changing a template
changes every dependent oracle version.
"""

import hashlib
import inspect
import random
from dataclasses import dataclass
from typing import Callable

from ..codec import typed_equal


def _sorted(values):
    return sorted(values)


def _unique(values):
    seen, out = set(), []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _sum(values):
    return sum(values)


def _reverse(text):
    return text[::-1]  # Unicode codepoint order, never grapheme clusters.


def _count(values, target):
    return sum(1 for value in values if value == target)


def _is_int_list(arg):
    domain = arg["domain"]
    return domain["kind"] == "list" and domain["item_domain"]["kind"] == "integer"


@dataclass(frozen=True)
class Template:
    template_id: str
    compatible: Callable[[list], bool]
    reference: Callable
    version: str


def _make(template_id, compatible, reference) -> Template:
    text = f"{template_id}\n{inspect.getsource(reference)}"
    return Template(template_id, compatible, reference, hashlib.sha256(text.encode()).hexdigest())


TEMPLATES: dict[str, Template] = {
    t.template_id: t
    for t in (
        _make("sort_ascending_ints", lambda d: len(d) == 1 and _is_int_list(d[0]), _sorted),
        _make("unique_preserve_order_ints", lambda d: len(d) == 1 and _is_int_list(d[0]), _unique),
        _make("sum_ints", lambda d: len(d) == 1 and _is_int_list(d[0]), _sum),
        _make(
            "reverse_string", lambda d: len(d) == 1 and d[0]["domain"]["kind"] == "string", _reverse
        ),
        _make(
            "count_occurrences_ints",
            lambda d: len(d) == 2 and _is_int_list(d[0]) and d[1]["domain"]["kind"] == "integer",
            _count,
        ),
    )
}


def template_compatible(template_id: str, domain_schema: list[dict]) -> bool:
    template = TEMPLATES.get(template_id)
    return bool(template and template.compatible(domain_schema))


def expected_output(template_id: str, inputs: list):
    """The reviewed expected value for an input vector (inputs are not mutated)."""
    return TEMPLATES[template_id].reference(*[_copy(v) for v in inputs])


def _copy(value):
    return list(value) if type(value) is list else value


@dataclass(frozen=True)
class Relation:
    relation_id: str
    templates: frozenset  # property templates whose approved contract admits this relation
    version: str


def _perm_followup(inputs: list, seed: int = 0) -> list:
    follow = [_copy(v) for v in inputs]
    items = follow[0]
    rng = random.Random(seed)
    if len(items) > 1:
        shuffled = items[:]
        for _ in range(8):  # ensure a genuinely different order when one exists
            rng.shuffle(shuffled)
            if shuffled != items or len(set(map(repr, items))) == 1:
                break
        follow[0] = shuffled
    return follow


def _idem_followup(inputs: list, seed: int = 0) -> list:
    follow = [_copy(v) for v in inputs]
    follow[0] = sorted(follow[0])
    return follow


def _perm_valid(base, follow) -> bool:
    return (
        len(base) == len(follow)
        and type(follow[0]) is list
        and sorted(base[0]) == sorted(follow[0])
        and all(typed_equal(a, b) for a, b in zip(base[1:], follow[1:]))
    )


def _idem_valid(base, follow) -> bool:
    return len(base) == 1 and type(follow[0]) is list and follow == [sorted(base[0])]


def _rel(relation_id, templates, fn):
    text = f"{relation_id}\n{inspect.getsource(fn)}"
    return Relation(relation_id, frozenset(templates), hashlib.sha256(text.encode()).hexdigest())


METAMORPHIC: dict[str, Relation] = {
    "permutation_invariant": _rel(
        "permutation_invariant", {"sum_ints", "sort_ascending_ints"}, _perm_valid
    ),
    "idempotent": _rel("idempotent", {"sort_ascending_ints"}, _idem_valid),
}
_FOLLOWUP = {"permutation_invariant": _perm_followup, "idempotent": _idem_followup}
_VALID = {"permutation_invariant": _perm_valid, "idempotent": _idem_valid}


def relation_followup(relation_id: str, inputs: list, seed: int = 0) -> list:
    return _FOLLOWUP[relation_id](inputs, seed)


def relation_inputs_valid(relation_id: str, base: list, follow: list) -> bool:
    return _VALID[relation_id](base, follow)


def registry_hash() -> str:
    parts = sorted(f"{k}:{v.version}" for k, v in TEMPLATES.items())
    parts += sorted(f"{k}:{v.version}" for k, v in METAMORPHIC.items())
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()
