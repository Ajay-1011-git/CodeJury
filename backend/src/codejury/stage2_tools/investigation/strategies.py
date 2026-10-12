"""Public-Hypothesis strategies for ValueDomains, one per registered generator family.

Only documented APIs are used (strategies, given, settings, seed, find). A family that cannot be
expressed for an argument domain returns None; callers reject or quarantine, they never guess.
"""

from hypothesis import strategies as st

FAMILIES = (
    "general",
    "empty",
    "singleton",
    "duplicates",
    "ascending",
    "descending",
    "boundary",
    "negative",
    "unicode",
    "missing_key",
    "audit_site",
)


def _text(domain: dict, lo=None, hi=None):
    alphabet = st.sampled_from(sorted(domain["alphabet"]))
    return st.text(
        alphabet=alphabet,
        min_size=lo if lo is not None else domain["min_length"],
        max_size=hi if hi is not None else domain["max_length"],
    )


def general(domain: dict):
    kind = domain["kind"]
    if kind == "null":
        return st.none()
    if kind == "boolean":
        return st.booleans()
    if kind == "integer":
        return st.integers(domain["min"], domain["max"])
    if kind == "string":
        return _text(domain)
    if kind == "list":
        return st.lists(
            general(domain["item_domain"]),
            min_size=domain["min_length"],
            max_size=domain["max_length"],
        )
    if kind == "union":
        return st.one_of(*[general(o) for o in domain["options"]])
    if kind == "dict":
        required = {k: general(domain["value_domain"]) for k in domain["required_keys"]}
        extra = st.dictionaries(
            _text(domain["key_domain"]),
            general(domain["value_domain"]),
            max_size=domain["max_size"],
        )

        def build(parts):
            merged = {**parts[1], **parts[0]}
            return merged

        return (
            st.tuples(st.fixed_dictionaries(required), extra)
            .map(build)
            .filter(lambda d: domain["min_size"] <= len(d) <= domain["max_size"])
        )
    raise ValueError(f"unknown domain {kind}")


def _bounds(domain: dict):
    return st.sampled_from(
        sorted(
            {
                domain["min"],
                domain["max"],
                min(domain["max"], domain["min"] + 1),
                max(domain["min"], domain["max"] - 1),
            }
        )
    )


def for_family(domain: dict, family: str, *, constants: tuple[int, ...] = ()):
    """Strategy of in-domain values for an argument under the family, or None if unsupported."""
    kind = domain["kind"]
    if family == "general":
        return general(domain)
    if kind == "union":
        parts = [
            s
            for o in domain["options"]
            if (s := for_family(o, family, constants=constants)) is not None
        ]
        return st.one_of(*parts) if parts else None
    if family == "empty":
        if kind == "list" and domain["min_length"] == 0:
            return st.just([])
        if kind == "string" and domain["min_length"] == 0:
            return st.just("")
        if kind == "dict" and domain["min_size"] == 0 and not domain["required_keys"]:
            return st.just({})
        return None
    if family == "singleton":
        if kind == "list" and domain["min_length"] <= 1 <= domain["max_length"]:
            return st.lists(general(domain["item_domain"]), min_size=1, max_size=1)
        if kind == "string" and domain["min_length"] <= 1 <= domain["max_length"]:
            return _text(domain, 1, 1)
        if (
            kind == "dict"
            and domain["min_size"] <= max(1, len(domain["required_keys"])) <= domain["max_size"]
        ):
            return general(
                {
                    **domain,
                    "min_size": max(1, len(domain["required_keys"])),
                    "max_size": max(1, len(domain["required_keys"])),
                }
            )
        return None
    if family == "duplicates":
        if kind == "list" and domain["max_length"] >= 2:
            lo = max(2, domain["min_length"])
            return st.tuples(
                general(domain["item_domain"]), st.integers(lo, domain["max_length"])
            ).map(lambda t: [t[0]] * t[1])
        if kind == "string" and domain["max_length"] >= 2:
            lo = max(2, domain["min_length"])
            return st.tuples(_text(domain, 1, 1), st.integers(lo, domain["max_length"])).map(
                lambda t: t[0] * t[1]
            )
        return None
    if family in {"ascending", "descending"}:
        item = domain.get("item_domain") if kind == "list" else None
        if item and item["kind"] in {"integer", "string"}:
            rev = family == "descending"
            return general(domain).map(lambda xs: sorted(xs, reverse=rev))
        return None
    if family == "boundary":
        if kind == "integer":
            return _bounds(domain)
        if kind == "string":
            return st.sampled_from([domain["min_length"], domain["max_length"]]).flatmap(
                lambda n: _text(domain, n, n)
            )
        if kind == "list":
            inner = for_family(domain["item_domain"], "boundary")
            if inner is None:
                return None
            return st.sampled_from([domain["min_length"], domain["max_length"]]).flatmap(
                lambda n: st.lists(inner, min_size=n, max_size=n)
            )
        return None
    if family == "negative":
        if kind == "integer" and domain["min"] < 0:
            return st.integers(domain["min"], min(-1, domain["max"]))
        if kind == "list":
            inner = for_family(domain["item_domain"], "negative")
            if inner is None:
                return None
            return (
                st.lists(
                    inner, min_size=max(1, domain["min_length"]), max_size=domain["max_length"]
                )
                if domain["max_length"] >= 1
                else None
            )
        return None
    if family == "unicode":
        if (
            kind == "string"
            and any(ord(c) > 127 for c in domain["alphabet"])
            and (domain["max_length"] >= 1)
        ):
            return _text(domain, max(1, domain["min_length"]), domain["max_length"]).filter(
                lambda text: any(ord(c) > 127 for c in text)
            )
        if kind == "list" and domain["max_length"] >= 1:
            inner = for_family(domain["item_domain"], "unicode")
            if inner is None:
                return None
            return st.lists(
                inner, min_size=max(1, domain["min_length"]), max_size=domain["max_length"]
            )
        return None
    if family == "audit_site":
        values = sorted({v for c in constants for v in (c - 1, c, c + 1)})
        if kind == "integer":
            pool = [v for v in values if domain["min"] <= v <= domain["max"]] or [
                domain["min"],
                domain["max"],
            ]
            return st.sampled_from(pool)
        if kind == "list":
            inner = for_family(domain["item_domain"], "audit_site", constants=constants)
            if inner is None:
                return None
            return st.lists(inner, min_size=domain["min_length"], max_size=domain["max_length"])
        return None
    return None


def invalid_missing_key(domain: dict):
    """Dicts that omit a required key: domain-INVALID by construction (never executed)."""
    if domain["kind"] != "dict" or not domain["required_keys"]:
        return None
    key = domain["required_keys"][0]
    base = general(
        {**domain, "required_keys": [k for k in domain["required_keys"] if k != key], "min_size": 0}
    )
    return base.map(lambda d: {k: v for k, v in d.items() if k != key})
