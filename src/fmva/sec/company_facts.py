"""Company Facts parsing and annual observation selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from fmva.exceptions import SecDataError


class FactKind(StrEnum):
    """XBRL fact time behavior."""

    INSTANT = "instant"
    DURATION = "duration"


class FiscalPeriodType(StrEnum):
    """Normalized fiscal-period classification."""

    FY = "FY"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    YTD = "YTD"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class FactObservation:
    """One normalized SEC Company Facts observation."""

    taxonomy: str
    tag: str
    label: str | None
    value: Decimal
    unit: str
    start_date: date | None
    end_date: date
    filed_date: date
    accession_number: str
    form: str
    fiscal_year: int | None
    sec_fiscal_year: int | None
    fiscal_period: FiscalPeriodType
    frame: str | None
    fact_kind: FactKind
    is_amendment: bool

    @property
    def duration_days(self) -> int | None:
        """Return inclusive duration length where applicable."""

        if self.start_date is None:
            return None
        return (self.end_date - self.start_date).days + 1


@dataclass(frozen=True, slots=True)
class CompanyFacts:
    """Normalized facts for one SEC registrant."""

    cik: str
    entity_name: str
    observations: tuple[FactObservation, ...]

    @classmethod
    def from_sec_payload(cls, payload: dict[str, Any]) -> CompanyFacts:
        """Parse all numeric facts without prematurely discarding duplicates."""

        try:
            cik = f"{int(payload['cik']):010d}"
            entity_name = str(payload["entityName"])
            taxonomies = payload["facts"]
        except (KeyError, TypeError, ValueError) as exc:
            raise SecDataError("Malformed SEC Company Facts root payload.") from exc
        if not isinstance(taxonomies, dict):
            raise SecDataError("SEC Company Facts 'facts' must be an object.")
        parsed: list[FactObservation] = []
        for taxonomy, concepts in taxonomies.items():
            if not isinstance(concepts, dict):
                continue
            for tag, concept in concepts.items():
                if not isinstance(concept, dict):
                    continue
                label = _optional_string(concept.get("label"))
                units = concept.get("units")
                if not isinstance(units, dict):
                    continue
                for unit, observations in units.items():
                    if not isinstance(observations, list):
                        continue
                    for raw in observations:
                        if not isinstance(raw, dict):
                            continue
                        try:
                            parsed.append(_parse_observation(str(taxonomy), str(tag), label, str(unit), raw))
                        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                            raise SecDataError(
                                f"Malformed fact observation: {taxonomy}:{tag} ({unit})."
                            ) from exc
        return cls(cik=cik, entity_name=entity_name, observations=tuple(parsed))

    def for_concept(self, tag: str, *, taxonomy: str = "us-gaap") -> tuple[FactObservation, ...]:
        """Return all observations for an exact taxonomy and concept."""

        return tuple(o for o in self.observations if o.taxonomy == taxonomy and o.tag == tag)

    def annual_observations(
        self,
        tag: str,
        *,
        taxonomy: str = "us-gaap",
        years: int | None = None,
    ) -> tuple[FactObservation, ...]:
        """Select one annual 10-K observation per fiscal year, preferring restatements.

        Duration facts must span approximately one fiscal year. Instant facts rely on FY
        classification and 10-K presentation. Later filed facts win for the same fiscal year,
        which captures comparative restatements while retaining the selected accession.
        """

        candidates = []
        for observation in self.for_concept(tag, taxonomy=taxonomy):
            if observation.form not in {"10-K", "10-K/A"}:
                continue
            if observation.fiscal_period is not FiscalPeriodType.FY:
                continue
            if observation.fiscal_year is None:
                continue
            days = observation.duration_days
            if days is not None and not 330 <= days <= 371:
                continue
            candidates.append(observation)
        selected: dict[date, FactObservation] = {}
        for candidate in candidates:
            current = selected.get(candidate.end_date)
            if current is None or _selection_key(candidate) > _selection_key(current):
                selected[candidate.end_date] = candidate
        result = tuple(selected[end_date] for end_date in sorted(selected))
        return result[-years:] if years is not None else result


def classify_fiscal_period(raw: dict[str, Any], start: date | None, end: date) -> FiscalPeriodType:
    """Classify a fact without treating YTD duration facts as standalone quarters."""

    fp = str(raw.get("fp") or "").upper()
    form = str(raw.get("form") or "").upper()
    if fp == "FY" and form in {"10-K", "10-K/A"}:
        return FiscalPeriodType.FY
    if start is None:
        return FiscalPeriodType(fp) if fp in {"Q1", "Q2", "Q3", "Q4"} else FiscalPeriodType.OTHER
    days = (end - start).days + 1
    if fp in {"Q1", "Q2", "Q3", "Q4"}:
        if 70 <= days <= 110:
            return FiscalPeriodType(fp)
        if days > 110:
            return FiscalPeriodType.YTD
    return FiscalPeriodType.OTHER


def _parse_observation(
    taxonomy: str,
    tag: str,
    label: str | None,
    unit: str,
    raw: dict[str, Any],
) -> FactObservation:
    start = _optional_date(raw.get("start"))
    end = date.fromisoformat(str(raw["end"]))
    filed = date.fromisoformat(str(raw["filed"]))
    form = str(raw["form"])
    sec_fiscal_year = int(raw["fy"]) if raw.get("fy") is not None else None
    fiscal_period = classify_fiscal_period(raw, start, end)
    fiscal_year = end.year if fiscal_period is FiscalPeriodType.FY else sec_fiscal_year
    return FactObservation(
        taxonomy=taxonomy,
        tag=tag,
        label=label,
        value=Decimal(str(raw["val"])),
        unit=unit,
        start_date=start,
        end_date=end,
        filed_date=filed,
        accession_number=str(raw["accn"]),
        form=form,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        sec_fiscal_year=sec_fiscal_year,
        frame=_optional_string(raw.get("frame")),
        fact_kind=FactKind.INSTANT if start is None else FactKind.DURATION,
        is_amendment=form.endswith("/A"),
    )


def _selection_key(observation: FactObservation) -> tuple[date, int, str]:
    return (observation.filed_date, int(observation.is_amendment), observation.accession_number)


def _optional_date(value: Any) -> date | None:
    return None if value in (None, "") else date.fromisoformat(str(value))


def _optional_string(value: Any) -> str | None:
    return None if value in (None, "") else str(value)
