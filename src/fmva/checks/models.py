"""Common structured check result."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CheckStatus(StrEnum):
    """Machine-readable check status."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CheckSeverity(StrEnum):
    """Consequence when a check does not pass."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One auditable assertion with actual, expected, and tolerance."""

    check: str
    actual: float | None
    expected: float | None
    difference: float | None
    tolerance: float
    status: CheckStatus
    severity: CheckSeverity
    message: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
