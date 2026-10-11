import pytest

from codejury.properties import check, equal, expected, outcome


@pytest.mark.parametrize(
    "left,right", [(True, 1), ([True], [1]), ({"v": True}, {"v": 1}), (1, 1.0)]
)
def test_equality_is_recursive_and_type_sensitive(left, right):
    assert not equal(left, right)


def test_properties_keep_order_multiplicity_and_types():
    assert expected("unique_preserve_order_ints", [3, 1, 3, 2]) == [3, 1, 2]
    assert check("sort_ascending_ints", [[2, 1, 2]], [1, 2, 2])
    assert not check("sort_ascending_ints", [[2, 1, 2]], [1, 2])
    assert not check("sum_ints", [[1]], True)
    assert check("sum_ints", [[]], 0)


@pytest.mark.parametrize("status", ["proposed", "observation_only", "rejected"])
def test_proposed_expectation_cannot_reject_candidate(status):
    test = {
        "oracle_status": status,
        "oracle_kind": "literal",
        "oracle_source": "model",
        "expected": 999,
    }
    assert outcome(test, 1) == "observed"
    assert outcome(test, 1, input_mutated=True) == "observed"


def test_authoritative_mutation_rejects():
    test = {
        "oracle_status": "authoritative",
        "oracle_kind": "literal",
        "oracle_source": "user",
        "expected": 1,
    }
    assert outcome(test, 1, input_mutated=True) == "fail"
