"""Canonical values and field-level lineage."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Confidence(StrEnum):
    """Confidence assigned to a standardized field."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    MISSING = "MISSING"


class SelectionMethod(StrEnum):
    """How a canonical value was obtained."""

    DIRECT = "DIRECT"
    FALLBACK = "FALLBACK"
    DERIVED = "DERIVED"
    MANUAL = "MANUAL"
    MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class FieldProvenance:
    """Auditable source and selection metadata for one canonical value."""

    source_tag: str | None
    source_filing: str | None
    filing_date: str | None
    fiscal_period: str
    unit: str
    confidence: Confidence
    selection_method: SelectionMethod
    fallback_rank: int | None
    is_restated: bool
    formula: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalObservation:
    """One standardized account value for one fiscal year."""

    account: str
    statement: str
    fiscal_year: int
    value: Decimal | None
    provenance: FieldProvenance


@dataclass(frozen=True, slots=True)
class QualityIssue:
    """One mapping completeness or quality issue."""

    account: str
    fiscal_year: int
    severity: str
    code: str
    message: str
