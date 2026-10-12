"""Reviewed oracle registry and admission gate."""

from .gate import (
    OracleError,
    admit_test,
    build_supplied_tests,
    check_intake,
    judge,
    oracle_version,
    suite_hash,
)
from .registry import (
    METAMORPHIC,
    TEMPLATES,
    expected_output,
    registry_hash,
    relation_followup,
    template_compatible,
)

__all__ = [
    "METAMORPHIC",
    "TEMPLATES",
    "OracleError",
    "admit_test",
    "build_supplied_tests",
    "check_intake",
    "expected_output",
    "judge",
    "oracle_version",
    "registry_hash",
    "relation_followup",
    "suite_hash",
    "template_compatible",
]
