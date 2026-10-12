"""Benchmark harness, split validation and statistical analysis."""

from .config import load as load_config
from .harness import Harness, HarnessError
from .report import analyze, write_analysis
from .splits import validate_manifest
from .stats import outcome, paired_bootstrap, per_problem

__all__ = [
    "Harness",
    "HarnessError",
    "analyze",
    "load_config",
    "outcome",
    "paired_bootstrap",
    "per_problem",
    "validate_manifest",
    "write_analysis",
]
