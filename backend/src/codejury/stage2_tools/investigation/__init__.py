"""Oracle-gated investigation, shrinking and replay."""

from .engine import InvestigationError, InvestigationOutcome, Investigator
from .strategies import FAMILIES

__all__ = ["FAMILIES", "InvestigationError", "InvestigationOutcome", "Investigator"]
