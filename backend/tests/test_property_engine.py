import copy

from hypothesis import given, settings

from codejury.properties import expected
from codejury.properties.engine import explore, strategy


def domain(min_length=0):
    return [
        {"kind": "list_integer", "min": -3, "max": 3, "min_length": min_length, "max_length": 6}
    ]


def test_domain_valid_families_and_empty_restriction():
    from codejury.contracts.intake import validate_args

    for family in ["general", "empty", "singleton", "duplicates", "descending", "boundary"]:

        @settings(max_examples=15, database=None)
        @given(strategy(domain(2), family))
        def check(args):
            validate_args(args, domain(2))
            assert len(args[0]) >= 2

        check()


def test_bounded_shrink_independent_replay():
    calls = []

    def evaluate(inputs, force=False):
        calls.extend(copy.deepcopy(inputs))
        return [
            {
                "outcome": "pass" if sorted(set(a[0])) == list(dict.fromkeys(a[0])) else "fail",
                "actual_output": sorted(set(a[0])),
            }
            for a in inputs
        ]

    r = {"input_domain": domain(), "approved_property": "unique_preserve_order_ints"}
    result = explore(r, {"family": "descending"}, evaluate)
    assert result["counterexample"]
    assert len(calls) <= 100
    assert calls[-1] == result["counterexample"]["args"]
    assert result["counterexample"]["expected"] == expected(r["approved_property"], calls[-1][0])


def test_observation_cannot_be_counterexample():
    def evaluate(inputs, force=False):
        return [{"outcome": "observed", "actual_output": None} for _ in inputs]

    result = explore(
        {"input_domain": domain(), "approved_property": None}, {"family": "general"}, evaluate
    )
    assert result["counterexample"] is None
    assert result["authority"] == "observation_only"
