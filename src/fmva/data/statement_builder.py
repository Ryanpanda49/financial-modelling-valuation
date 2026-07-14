"""Build annual canonical historical statements with lineage and quality issues."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

from fmva.data.account_mapping import AccountMapper, normalize_sign, normalized_scale
from fmva.data.models import (
    CanonicalObservation,
    Confidence,
    FieldProvenance,
    QualityIssue,
    SelectionMethod,
)
from fmva.exceptions import HistoricalDataError
from fmva.sec.company_facts import CompanyFacts, FactObservation

HISTORICAL_STATEMENTS_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class HistoricalStatements:
    """Canonical annual tables, provenance records, and quality issues."""

    statements: dict[str, pd.DataFrame]
    observations: tuple[CanonicalObservation, ...]
    quality_issues: tuple[QualityIssue, ...]

    def to_dict(self, *, metadata: dict[str, object] | None = None) -> dict[str, object]:
        """Serialize standardized history without SEC request headers or cache details."""

        statements: dict[str, object] = {}
        for name, frame in sorted(self.statements.items()):
            statements[name] = {
                "index": [str(value) for value in frame.index],
                "columns": [int(value) for value in frame.columns],
                "data": [
                    [_json_number(value) for value in row]
                    for row in frame.to_numpy().tolist()
                ],
                "index_name": frame.index.name,
                "columns_name": frame.columns.name,
            }
        observations = [
            {
                "account": item.account,
                "statement": item.statement,
                "fiscal_year": item.fiscal_year,
                "value": str(item.value) if item.value is not None else None,
                "provenance": {
                    "source_tag": item.provenance.source_tag,
                    "source_filing": item.provenance.source_filing,
                    "filing_date": item.provenance.filing_date,
                    "fiscal_period": item.provenance.fiscal_period,
                    "unit": item.provenance.unit,
                    "confidence": item.provenance.confidence.value,
                    "selection_method": item.provenance.selection_method.value,
                    "fallback_rank": item.provenance.fallback_rank,
                    "is_restated": item.provenance.is_restated,
                    "formula": item.provenance.formula,
                    "warnings": list(item.provenance.warnings),
                },
            }
            for item in self.observations
        ]
        issues = [
            {
                "account": item.account,
                "fiscal_year": item.fiscal_year,
                "severity": item.severity,
                "code": item.code,
                "message": item.message,
            }
            for item in self.quality_issues
        ]
        return {
            "schema_version": HISTORICAL_STATEMENTS_SCHEMA_VERSION,
            "metadata": dict(metadata or {}),
            "statements": statements,
            "observations": observations,
            "quality_issues": issues,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> HistoricalStatements:
        """Deserialize a versioned standardized-history payload with strict validation."""

        if payload.get("schema_version") != HISTORICAL_STATEMENTS_SCHEMA_VERSION:
            raise HistoricalDataError(
                "Unsupported historical statements schema_version; expected version 1."
            )
        try:
            raw_statements = _require_mapping(payload["statements"], "statements")
            raw_observations = _require_list(payload["observations"], "observations")
            raw_issues = _require_list(payload["quality_issues"], "quality_issues")
            statements: dict[str, pd.DataFrame] = {}
            for name, raw_frame_value in raw_statements.items():
                raw_frame = _require_mapping(raw_frame_value, f"statements.{name}")
                index = _require_list(raw_frame["index"], f"statements.{name}.index")
                columns = _require_list(raw_frame["columns"], f"statements.{name}.columns")
                data = _require_list(raw_frame["data"], f"statements.{name}.data")
                frame = pd.DataFrame(data, index=index, columns=[int(value) for value in columns])
                frame.index.name = _optional_name(raw_frame.get("index_name"))
                frame.columns.name = _optional_name(raw_frame.get("columns_name"))
                statements[str(name)] = frame.astype(float)

            observations = []
            for position, raw_value in enumerate(raw_observations):
                raw = _require_mapping(raw_value, f"observations[{position}]")
                provenance = _require_mapping(
                    raw["provenance"], f"observations[{position}].provenance"
                )
                raw_warnings = _require_list(
                    provenance.get("warnings", []),
                    f"observations[{position}].provenance.warnings",
                )
                observations.append(
                    CanonicalObservation(
                        account=str(raw["account"]),
                        statement=str(raw["statement"]),
                        fiscal_year=int(raw["fiscal_year"]),
                        value=(
                            None
                            if raw.get("value") is None
                            else Decimal(str(raw["value"]))
                        ),
                        provenance=FieldProvenance(
                            source_tag=_optional_string(provenance.get("source_tag")),
                            source_filing=_optional_string(provenance.get("source_filing")),
                            filing_date=_optional_string(provenance.get("filing_date")),
                            fiscal_period=str(provenance["fiscal_period"]),
                            unit=str(provenance["unit"]),
                            confidence=Confidence(str(provenance["confidence"])),
                            selection_method=SelectionMethod(
                                str(provenance["selection_method"])
                            ),
                            fallback_rank=(
                                None
                                if provenance.get("fallback_rank") is None
                                else int(provenance["fallback_rank"])
                            ),
                            is_restated=bool(provenance["is_restated"]),
                            formula=_optional_string(provenance.get("formula")),
                            warnings=tuple(str(value) for value in raw_warnings),
                        ),
                    )
                )

            issues = []
            for position, raw_value in enumerate(raw_issues):
                raw = _require_mapping(raw_value, f"quality_issues[{position}]")
                issues.append(
                    QualityIssue(
                        account=str(raw["account"]),
                        fiscal_year=int(raw["fiscal_year"]),
                        severity=str(raw["severity"]),
                        code=str(raw["code"]),
                        message=str(raw["message"]),
                    )
                )
        except (
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
        ) as exc:
            raise HistoricalDataError("Malformed historical statements payload.") from exc
        return cls(
            statements=statements,
            observations=tuple(observations),
            quality_issues=tuple(issues),
        )

    def write_json(
        self,
        path: str | Path,
        *,
        metadata: dict[str, object] | None = None,
    ) -> Path:
        """Write a deterministic, human-inspectable public fixture or offline snapshot."""

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.to_dict(metadata=metadata), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return output_path

    @classmethod
    def read_json(cls, path: str | Path) -> HistoricalStatements:
        """Read a standardized-history snapshot from disk."""

        input_path = Path(path)
        try:
            payload = json.loads(input_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HistoricalDataError(f"Cannot read historical statements: {input_path}") from exc
        if not isinstance(payload, dict):
            raise HistoricalDataError("Historical statements JSON root must be an object.")
        return cls.from_dict(payload)

    def provenance_frame(self) -> pd.DataFrame:
        """Return field-level metadata as an exportable flat table."""

        rows = []
        for item in self.observations:
            rows.append(
                {
                    "statement": item.statement,
                    "account": item.account,
                    "fiscal_year": item.fiscal_year,
                    "value": float(item.value) if item.value is not None else None,
                    "source_tag": item.provenance.source_tag,
                    "source_filing": item.provenance.source_filing,
                    "filing_date": item.provenance.filing_date,
                    "fiscal_period": item.provenance.fiscal_period,
                    "unit": item.provenance.unit,
                    "confidence": item.provenance.confidence.value,
                    "selection_method": item.provenance.selection_method.value,
                    "fallback_rank": item.provenance.fallback_rank,
                    "is_restated": item.provenance.is_restated,
                    "formula": item.provenance.formula,
                    "warnings": "; ".join(item.provenance.warnings),
                }
            )
        return pd.DataFrame(rows)

    def quality_frame(self) -> pd.DataFrame:
        """Return quality issues as a stable export table."""

        return pd.DataFrame(
            [
                {
                    "account": item.account,
                    "fiscal_year": item.fiscal_year,
                    "severity": item.severity,
                    "code": item.code,
                    "message": item.message,
                }
                for item in self.quality_issues
            ],
            columns=["account", "fiscal_year", "severity", "code", "message"],
        )


def _json_number(value: object) -> float | int | None:
    """Return a strict-JSON numeric scalar, using null for missing frame cells."""

    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return int(value)
    return float(value)  # type: ignore[arg-type]


def _require_mapping(value: object, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{location} must be an object")
    return value


def _require_list(value: object, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{location} must be an array")
    return value


def _optional_name(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


class StatementBuilder:
    """Map SEC facts into canonical annual statement tables."""

    def __init__(self, mapper: AccountMapper) -> None:
        self.mapper = mapper

    def build(self, facts: CompanyFacts, *, years: int = 5) -> HistoricalStatements:
        """Build a common fiscal-year panel for every configured canonical account."""

        available_years = sorted(
            {
                item.fiscal_year
                for item in facts.observations
                if item.fiscal_year is not None and item.form in {"10-K", "10-K/A"}
            }
        )[-years:]
        observations: list[CanonicalObservation] = []
        issues: list[QualityIssue] = []
        for definition in self.mapper.account_map.accounts.values():
            account = definition.name
            by_year = {}
            selected_candidate = None
            for rank, candidate in enumerate(definition.accepted_tags, start=1):
                annual = facts.annual_observations(
                    candidate.tag,
                    taxonomy=candidate.taxonomy,
                    years=None,
                )
                matching = {
                    item.fiscal_year: item
                    for item in annual
                    if item.fiscal_year in available_years and item.fact_kind is definition.fact_kind
                }
                for fiscal_year, item in matching.items():
                    if fiscal_year not in by_year:
                        by_year[fiscal_year] = (item, rank, candidate.priority)
                if matching and selected_candidate is None:
                    selected_candidate = candidate
            for fiscal_year in available_years:
                selected = by_year.get(fiscal_year)
                if selected is None:
                    observations.extend(
                        _missing(account, statement, fiscal_year)
                        for statement in definition.statements
                    )
                    if definition.required:
                        issues.append(
                            QualityIssue(
                                account=account,
                                fiscal_year=fiscal_year,
                                severity="ERROR",
                                code="REQUIRED_ACCOUNT_MISSING",
                                message=f"No valid annual SEC fact found for required account '{account}'.",
                            )
                        )
                    continue
                fact, rank, configured_priority = selected
                scale = normalized_scale(definition.unit_type, fact.unit)
                value = normalize_sign(fact.value / scale, definition.sign)
                method = SelectionMethod.DIRECT if rank == 1 else SelectionMethod.FALLBACK
                confidence = Confidence.HIGH if rank == 1 else Confidence.MEDIUM
                observations.extend(
                    CanonicalObservation(
                        account=account,
                        statement=statement,
                        fiscal_year=fiscal_year,
                        value=value,
                        provenance=FieldProvenance(
                            source_tag=fact.tag,
                            source_filing=fact.accession_number,
                            filing_date=fact.filed_date.isoformat(),
                            fiscal_period=fact.fiscal_period.value,
                            unit="USD millions" if definition.unit_type == "currency" else definition.unit_type,
                            confidence=confidence,
                            selection_method=method,
                            fallback_rank=configured_priority,
                            is_restated=_is_comparative_restatement(fact),
                        ),
                    )
                    for statement in definition.statements
                )
        observations = _apply_derivations(observations, self.mapper, available_years)
        resolved = {
            (item.account, item.fiscal_year)
            for item in observations
            if item.value is not None
        }
        issues = [
            issue
            for issue in issues
            if issue.code != "REQUIRED_ACCOUNT_MISSING"
            or (issue.account, issue.fiscal_year) not in resolved
        ]
        frames: dict[str, pd.DataFrame] = {}
        statement_names = sorted({item.statement for item in observations})
        for statement in statement_names:
            rows = [item for item in observations if item.statement == statement]
            data = {
                fiscal_year: {
                    item.account: float(item.value) if item.value is not None else float("nan")
                    for item in rows
                    if item.fiscal_year == fiscal_year
                }
                for fiscal_year in available_years
            }
            frames[statement] = pd.DataFrame(data).sort_index()
            frames[statement].columns.name = "fiscal_year"
            frames[statement].index.name = "account"
        return HistoricalStatements(
            statements=frames,
            observations=tuple(observations),
            quality_issues=tuple(issues),
        )


def _missing(account: str, statement: str, fiscal_year: int) -> CanonicalObservation:
    return CanonicalObservation(
        account=account,
        statement=statement,
        fiscal_year=fiscal_year,
        value=None,
        provenance=FieldProvenance(
            source_tag=None,
            source_filing=None,
            filing_date=None,
            fiscal_period="FY",
            unit="unknown",
            confidence=Confidence.MISSING,
            selection_method=SelectionMethod.MISSING,
            fallback_rank=None,
            is_restated=False,
            warnings=("No valid mapped SEC fact.",),
        ),
    )


def _is_comparative_restatement(fact: FactObservation) -> bool:
    fiscal_year = fact.fiscal_year
    filed_date = fact.filed_date
    return fiscal_year is not None and filed_date.year >= fiscal_year + 1


def _apply_derivations(
    observations: list[CanonicalObservation],
    mapper: AccountMapper,
    years: list[int],
) -> list[CanonicalObservation]:
    """Fill configured binary derivations only when all components are present."""

    indexed = {(item.statement, item.account, item.fiscal_year): item for item in observations}
    result = list(observations)
    for definition in mapper.account_map.accounts.values():
        if not definition.derivation:
            continue
        parts = definition.derivation.split()
        if len(parts) != 3 or parts[1] not in {"+", "-"}:
            continue
        left_name, operator, right_name = parts
        for statement in definition.statements:
            for year in years:
                key = (statement, definition.name, year)
                target = indexed.get(key)
                if target is None or target.value is not None:
                    continue
                left = indexed.get((statement, left_name, year))
                right = indexed.get((statement, right_name, year))
                if left is None or right is None:
                    continue
                zero_components = []
                if left.value is None:
                    if left_name not in definition.zero_if_missing:
                        continue
                    left_value = Decimal("0")
                    zero_components.append(left_name)
                else:
                    left_value = left.value
                if right.value is None:
                    if right_name not in definition.zero_if_missing:
                        continue
                    right_value = Decimal("0")
                    zero_components.append(right_name)
                else:
                    right_value = right.value
                value = (
                    left_value + right_value
                    if operator == "+"
                    else left_value - right_value
                )
                warnings = ["Derived from canonical components."]
                if zero_components:
                    warnings.append(
                        "Optional component(s) treated as zero for this derivation: "
                        + ", ".join(zero_components)
                        + ". The source field remains missing and requires analyst review."
                    )
                derived = CanonicalObservation(
                    account=definition.name,
                    statement=statement,
                    fiscal_year=year,
                    value=value,
                    provenance=FieldProvenance(
                        source_tag=None,
                        source_filing=None,
                        filing_date=None,
                        fiscal_period="FY",
                        unit="USD millions",
                        confidence=Confidence.MEDIUM,
                        selection_method=SelectionMethod.DERIVED,
                        fallback_rank=None,
                        is_restated=False,
                        formula=definition.derivation,
                        warnings=tuple(warnings),
                    ),
                )
                result[result.index(target)] = derived
                indexed[key] = derived
    return result
