"""Typed valuation assumptions and validation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any, ClassVar

import yaml

from fmva.exceptions import ConfigurationError


@dataclass(frozen=True, slots=True)
class ValuationInputSource:
    """Dated source and analyst rationale for one valuation input."""

    source_name: str
    source_url: str | None
    as_of_date: str
    accessed_date: str
    rationale: str

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> ValuationInputSource:
        """Parse and validate one source record."""

        try:
            result = cls(
                source_name=str(payload["source_name"]).strip(),
                source_url=_optional_string(payload.get("source_url")),
                as_of_date=str(payload["as_of_date"]),
                accessed_date=str(payload["accessed_date"]),
                rationale=str(payload["rationale"]).strip(),
            )
            result.validate()
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigurationError("Invalid valuation input source record.") from exc

    def validate(self) -> None:
        """Require explicit labels, valid ISO dates, and research rationale."""

        if not self.source_name or not self.rationale:
            raise ConfigurationError("Valuation source name and rationale cannot be blank.")
        _parse_iso_date(self.as_of_date, "source as_of_date")
        _parse_iso_date(self.accessed_date, "source accessed_date")


@dataclass(frozen=True, slots=True)
class ValuationMetadata:
    """Scenario-level audit metadata kept outside numerical DCF mechanics."""

    valuation_date: str | None = None
    scenario_name: str = "Base case"
    is_illustrative: bool = True
    sources: dict[str, ValuationInputSource] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, payload: object) -> ValuationMetadata:
        """Parse optional metadata while preserving backwards-compatible illustrative use."""

        if payload is None:
            return cls(
                warnings=(
                    "No valuation metadata supplied; inputs are treated as illustrative.",
                )
            )
        if not isinstance(payload, dict):
            raise ConfigurationError("valuation metadata must be a mapping.")
        raw_sources = payload.get("sources", {})
        if not isinstance(raw_sources, dict):
            raise ConfigurationError("valuation metadata sources must be a mapping.")
        sources = {
            str(name): ValuationInputSource.from_mapping(_source_mapping(value, str(name)))
            for name, value in raw_sources.items()
        }
        warnings_raw = payload.get("warnings", [])
        if not isinstance(warnings_raw, list):
            raise ConfigurationError("valuation metadata warnings must be a list.")
        result = cls(
            valuation_date=_optional_string(payload.get("valuation_date")),
            scenario_name=str(payload.get("scenario_name", "Base case")).strip(),
            is_illustrative=bool(payload.get("is_illustrative", True)),
            sources=sources,
            warnings=tuple(str(value) for value in warnings_raw),
        )
        result.validate()
        return result

    def validate(self) -> None:
        """Validate scenario dates and source coverage for non-illustrative research."""

        if not self.scenario_name:
            raise ConfigurationError("Valuation scenario_name cannot be blank.")
        if self.valuation_date is not None:
            _parse_iso_date(self.valuation_date, "valuation_date")
        if self.is_illustrative:
            return
        if self.valuation_date is None:
            raise ConfigurationError("Non-illustrative valuation requires valuation_date.")
        required = {
            "risk_free_rate",
            "equity_risk_premium",
            "beta",
            "pre_tax_cost_of_debt",
        }
        missing = sorted(required - self.sources.keys())
        if missing:
            raise ConfigurationError(
                "Non-illustrative valuation lacks sources for: " + ", ".join(missing)
            )
        missing_urls = sorted(
            name for name in required if self.sources[name].source_url is None
        )
        if missing_urls:
            raise ConfigurationError(
                "Non-illustrative valuation lacks source URLs for: "
                + ", ".join(missing_urls)
            )


@dataclass(frozen=True, slots=True)
class ValuationAssumptions:
    """Market and equity-bridge inputs for DCF."""

    NUMERIC_FIELDS: ClassVar[tuple[str, ...]] = (
        "risk_free_rate",
        "equity_risk_premium",
        "beta",
        "pre_tax_cost_of_debt",
        "target_debt_weight",
        "target_equity_weight",
        "terminal_growth_rate",
        "exit_multiple",
        "debt",
        "preferred_stock",
        "minority_interest",
        "cash",
        "non_operating_investments",
        "diluted_shares",
    )

    risk_free_rate: float
    equity_risk_premium: float
    beta: float
    pre_tax_cost_of_debt: float
    target_debt_weight: float
    target_equity_weight: float
    terminal_growth_rate: float
    exit_multiple: float
    debt: float
    preferred_stock: float
    minority_interest: float
    cash: float
    non_operating_investments: float
    diluted_shares: float
    metadata: ValuationMetadata = field(default_factory=ValuationMetadata)

    @classmethod
    def from_yaml(cls, path: str | Path) -> ValuationAssumptions:
        """Load valuation assumptions from YAML."""

        config_path = Path(path)
        try:
            payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("root must be a mapping")
            values = {name: float(payload[name]) for name in cls.NUMERIC_FIELDS}
            result = cls(
                **values,
                metadata=ValuationMetadata.from_mapping(payload.get("metadata")),
            )
        except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
            raise ConfigurationError(f"Invalid valuation assumptions: {config_path}") from exc
        result.validate()
        return result

    def validate(self) -> None:
        """Validate weights, market inputs, and bridge denominators."""

        if abs(self.target_debt_weight + self.target_equity_weight - 1.0) > 1e-9:
            raise ConfigurationError("Target debt and equity weights must sum to 1.")
        if min(self.target_debt_weight, self.target_equity_weight) < 0:
            raise ConfigurationError("Capital weights cannot be negative.")
        if self.risk_free_rate < 0 or self.equity_risk_premium < 0 or self.beta < 0:
            raise ConfigurationError("CAPM inputs cannot be negative in the MVP.")
        if self.pre_tax_cost_of_debt < 0 or self.exit_multiple <= 0:
            raise ConfigurationError("Debt cost must be nonnegative and exit multiple positive.")
        if self.diluted_shares <= 0:
            raise ConfigurationError("Diluted shares must be greater than zero.")
        if any(
            value < 0
            for value in (
                self.debt,
                self.preferred_stock,
                self.minority_interest,
                self.cash,
                self.non_operating_investments,
            )
        ):
            raise ConfigurationError("Equity-bridge balance inputs cannot be negative.")
        self.metadata.validate()
        unknown_sources = sorted(set(self.metadata.sources) - set(self.NUMERIC_FIELDS))
        if unknown_sources:
            raise ConfigurationError(
                "Valuation metadata contains unknown input sources: "
                + ", ".join(unknown_sources)
            )

    def with_rates(self, *, terminal_growth_rate: float | None = None) -> ValuationAssumptions:
        """Return a copy used by sensitivity analysis."""

        return replace(
            self,
            terminal_growth_rate=(
                self.terminal_growth_rate if terminal_growth_rate is None else terminal_growth_rate
            ),
        )

    def with_bridge(
        self,
        *,
        debt: float,
        cash: float,
        diluted_shares: float | None = None,
    ) -> ValuationAssumptions:
        """Return a copy using standardized historical balance/share bridge inputs."""

        result = replace(
            self,
            debt=float(debt),
            cash=float(cash),
            diluted_shares=(self.diluted_shares if diluted_shares is None else float(diluted_shares)),
        )
        result.validate()
        return result


def _optional_string(value: object) -> str | None:
    return None if value in (None, "") else str(value)


def _parse_iso_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigurationError(f"{label} must use YYYY-MM-DD format.") from exc


def _source_mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"Valuation source '{name}' must be a mapping.")
    return value
