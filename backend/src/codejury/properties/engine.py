"""Hypothesis creates/shrinks values; candidate calls run only in sandbox batches."""

import json
import random

from hypothesis import HealthCheck, Phase, find, given, settings
from hypothesis import strategies as st
from hypothesis.errors import NoSuchExample

from ..contracts.intake import validate_args
from . import expected


class ExplorationLimit(Exception):
    pass


class FoundFailure(Exception):
    pass


def strategy(domains, family="general"):
    values = []
    for domain in domains:
        ints = st.integers(domain["min"], domain["max"])
        if domain["kind"] == "integer":
            values.append(ints)
            continue
        lo, hi = domain["min_length"], domain["max_length"]
        lists = st.lists(ints, min_size=lo, max_size=hi)
        if family == "empty" and lo == 0:
            lists = st.just([])
        elif family == "singleton" and lo <= 1 <= hi:
            lists = st.lists(ints, min_size=1, max_size=1)
        elif family == "duplicates":
            lists = st.tuples(ints, st.integers(lo, hi)).map(lambda x: [x[0]] * x[1])
        elif family == "descending":
            lists = lists.map(lambda x: sorted(x, reverse=True))
        elif family == "boundary":
            lists = st.lists(
                st.sampled_from([domain["min"], domain["max"]]), min_size=lo, max_size=hi
            )
        values.append(lists)
    return st.tuples(*values).map(list)


def explore(request, proposal, evaluate_batch, *, max_inputs=100):
    """evaluate_batch accepts only values, returns trusted evidence rows; no code imported here.

    At most max_inputs distinct exploratory invocations, including shrinking and independent
    replay. A bounded shrink may stop before a globally minimal value; this is disclosed.
    """
    if not 2 <= max_inputs <= 100:
        raise ValueError("Exploration limit must be 2–100")
    seen, failures = {}, []
    prop = request["approved_property"]
    family = proposal["family"]

    def evaluate(inputs):
        fresh = []
        for args in inputs:
            validate_args(args, request["input_domain"])
            key = json.dumps(args, sort_keys=True, separators=(",", ":"))
            if key not in seen and key not in [k for k, _ in fresh]:
                if len(seen) + len(fresh) >= max_inputs - 1:
                    raise ExplorationLimit()
                fresh.append((key, args))
        if fresh:
            rows = evaluate_batch([args for _, args in fresh])
            if len(rows) != len(fresh):
                raise ValueError("Sandbox batch count mismatch")
            for (key, args), row in zip(fresh, rows):
                seen[key] = row
                if prop and row["outcome"] != "pass":
                    failures.append((args, row))
        return [seen[json.dumps(args, sort_keys=True, separators=(",", ":"))] for args in inputs]

    limited = False
    options = dict(
        database=None,
        deadline=None,
        derandomize=True,
        suppress_health_check=[HealthCheck.too_slow],
        max_examples=12,
    )

    @settings(**options, phases=[Phase.generate])
    @given(st.lists(strategy(request["input_domain"], family), min_size=8, max_size=8))
    def batches(inputs):
        evaluate(inputs)
        if failures:
            raise FoundFailure()

    try:
        batches()
    except FoundFailure:
        pass
    except ExplorationLimit:
        limited = True
    minimized = None
    if failures:
        args, _ = failures[0]
        try:
            args = find(
                strategy(request["input_domain"]),
                lambda x: evaluate([x])[0]["outcome"] != "pass",
                settings=settings(
                    database=None,
                    deadline=None,
                    max_examples=100,
                    suppress_health_check=[HealthCheck.too_slow],
                ),
                random=random.Random(17),
            )
        except (ExplorationLimit, NoSuchExample):
            limited = True
            # Smallest failure actually observed, not a claim of global minimality.
            args, _ = min(failures, key=lambda x: (len(json.dumps(x[0])), json.dumps(x[0])))
        row = evaluate_batch([args], force=True)[0]  # Independent replay, charged separately.
        if row["outcome"] != "pass":
            minimized = {
                "args": args,
                "actual_output": row["actual_output"],
                "expected": expected(prop, args[0]),
                "property_id": prop,
                "oracle_status": "authoritative",
            }
    return {
        "inputs": len(seen) + int(bool(failures)),
        "counterexample": minimized,
        "shrink_limited": limited,
        "family": family,
        "authority": "reviewed_contract" if prop else "observation_only",
    }
