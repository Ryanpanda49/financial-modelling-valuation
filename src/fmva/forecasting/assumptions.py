"""Centralized, typed forecast assumptions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from fmva.exceptions import ConfigurationError


@dataclass(frozen=True, slots=True)
class ForecastAssumptions:
    """All first-version operating and financing drivers by forecast year."""

    years: tuple[int, ...]
    revenue_growth: dict[int, float]
    cogs_as_pct_revenue: dict[int, float]
    sga_as_pct_revenue: dict[int, float]
    rd_as_pct_revenue: dict[int, float]
    other_operating_income_as_pct_revenue: dict[int, float]
    tax_rate: dict[int, float]
    dividend_payout_ratio: dict[int, float]
    days_sales_outstanding: dict[int, float]
    days_inventory_outstanding: dict[int, float]
    days_payables_outstanding: dict[int, float]
    other_current_assets_as_pct_revenue: dict[int, float]
    accrued_liabilities_as_pct_revenue: dict[int, float]
    capex_as_pct_revenue: dict[int, float]
    depreciation_as_pct_beginning_ppe: dict[int, float]
    useful_life: dict[int, float]
    residual_value_rate: dict[int, float]
    asset_disposals: dict[int, float]
    short_term_interest_rate: dict[int, float]
    long_term_interest_rate: dict[int, float]
    minimum_cash_as_pct_revenue: dict[int, float]
    new_borrowing: dict[int, float]
    debt_repayment: dict[int, float]
    share_issuance: dict[int, float]
    share_repurchases: dict[int, float]
    max_solver_iterations: int = 50
    solver_tolerance: float = 1e-8

    @classmethod
    def from_yaml(cls, path: str | Path) -> ForecastAssumptions:
        """Load a forecast assumption set; no calculation assumptions live in code."""

        config_path = Path(path)
        try:
            payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            years = tuple(int(year) for year in payload["forecast_years"])
            operating = payload["operating"]
            working_capital = payload["working_capital"]
            fixed_assets = payload["fixed_assets"]
            debt = payload["debt"]
            solver = payload.get("solver", {})
        except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
            raise ConfigurationError(f"Invalid forecast assumptions: {config_path}") from exc
        result = cls(
            years=years,
            revenue_growth=_series(operating, "revenue_growth", years),
            cogs_as_pct_revenue=_series(operating, "cogs_as_pct_revenue", years),
            sga_as_pct_revenue=_series(operating, "sga_as_pct_revenue", years),
            rd_as_pct_revenue=_series(operating, "rd_as_pct_revenue", years),
            other_operating_income_as_pct_revenue=_series(
                operating, "other_operating_income_as_pct_revenue", years
            ),
            tax_rate=_series(operating, "tax_rate", years),
            dividend_payout_ratio=_series(operating, "dividend_payout_ratio", years),
            days_sales_outstanding=_series(working_capital, "days_sales_outstanding", years),
            days_inventory_outstanding=_series(working_capital, "days_inventory_outstanding", years),
            days_payables_outstanding=_series(working_capital, "days_payables_outstanding", years),
            other_current_assets_as_pct_revenue=_series(
                working_capital, "other_current_assets_as_pct_revenue", years
            ),
            accrued_liabilities_as_pct_revenue=_series(
                working_capital, "accrued_liabilities_as_pct_revenue", years
            ),
            capex_as_pct_revenue=_series(fixed_assets, "capex_as_pct_revenue", years),
            depreciation_as_pct_beginning_ppe=_series(
                fixed_assets, "depreciation_as_pct_beginning_ppe", years
            ),
            useful_life=_series(fixed_assets, "useful_life", years),
            residual_value_rate=_series(fixed_assets, "residual_value_rate", years),
            asset_disposals=_series(fixed_assets, "asset_disposals", years),
            short_term_interest_rate=_series(debt, "short_term_interest_rate", years),
            long_term_interest_rate=_series(debt, "long_term_interest_rate", years),
            minimum_cash_as_pct_revenue=_series(debt, "minimum_cash_as_pct_revenue", years),
            new_borrowing=_series(debt, "new_borrowing", years),
            debt_repayment=_series(debt, "debt_repayment", years),
            share_issuance=_series(debt, "share_issuance", years),
            share_repurchases=_series(debt, "share_repurchases", years),
            max_solver_iterations=int(solver.get("max_iterations", 50)),
            solver_tolerance=float(solver.get("tolerance", 1e-8)),
        )
        result.validate()
        return result

    def validate(self) -> None:
        """Validate period coverage and economically meaningful bounds."""

        if not self.years or tuple(sorted(set(self.years))) != self.years:
            raise ConfigurationError("forecast_years must be unique and increasing.")
        percentage_fields = (
            self.cogs_as_pct_revenue,
            self.sga_as_pct_revenue,
            self.rd_as_pct_revenue,
            self.other_operating_income_as_pct_revenue,
            self.tax_rate,
            self.dividend_payout_ratio,
            self.other_current_assets_as_pct_revenue,
            self.accrued_liabilities_as_pct_revenue,
            self.capex_as_pct_revenue,
            self.depreciation_as_pct_beginning_ppe,
            self.residual_value_rate,
            self.short_term_interest_rate,
            self.long_term_interest_rate,
            self.minimum_cash_as_pct_revenue,
        )
        for values in percentage_fields:
            if set(values) != set(self.years):
                raise ConfigurationError("Every forecast assumption must cover every forecast year.")
            if any(value < 0 for value in values.values()):
                raise ConfigurationError("Percentage assumptions cannot be negative in the MVP.")
        for values in (
            self.days_sales_outstanding,
            self.days_inventory_outstanding,
            self.days_payables_outstanding,
            self.useful_life,
            self.asset_disposals,
            self.new_borrowing,
            self.debt_repayment,
            self.share_issuance,
            self.share_repurchases,
        ):
            if any(value < 0 for value in values.values()):
                raise ConfigurationError("Days and schedule cash-flow assumptions cannot be negative.")
        if any(not 0 <= value <= 1 for value in self.tax_rate.values()):
            raise ConfigurationError("tax_rate must be between 0 and 1.")
        if any(not 0 <= value <= 1 for value in self.dividend_payout_ratio.values()):
            raise ConfigurationError("dividend_payout_ratio must be between 0 and 1.")
        if any(not 0 <= value <= 1 for value in self.residual_value_rate.values()):
            raise ConfigurationError("residual_value_rate must be between 0 and 1.")
        if any(value <= -1 for value in self.revenue_growth.values()):
            raise ConfigurationError("revenue_growth must be greater than -100%.")
        if any(value <= 0 for value in self.useful_life.values()):
            raise ConfigurationError("useful_life must be positive.")
        if self.max_solver_iterations < 1 or self.solver_tolerance <= 0:
            raise ConfigurationError("Solver iteration count and tolerance must be positive.")


def _series(section: dict[str, Any], key: str, years: tuple[int, ...]) -> dict[int, float]:
    try:
        raw = section[key]
    except (KeyError, TypeError) as exc:
        raise ConfigurationError(f"Missing forecast assumption: {key}") from exc
    if isinstance(raw, (int, float)):
        return {year: float(raw) for year in years}
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Forecast assumption '{key}' must be a scalar or year mapping.")
    try:
        result = {int(year): float(value) for year, value in raw.items()}
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid values for forecast assumption: {key}") from exc
    if set(result) != set(years):
        raise ConfigurationError(f"Forecast assumption '{key}' must cover exactly {years}.")
    return result
