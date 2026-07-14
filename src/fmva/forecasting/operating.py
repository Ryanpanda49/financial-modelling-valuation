"""Operating forecast interfaces and top-down implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fmva.forecasting.assumptions import ForecastAssumptions


@dataclass(frozen=True, slots=True)
class OperatingForecast:
    """Core operating outputs before financing and tax."""

    revenue: float
    cogs: float
    gross_profit: float
    selling_general_admin: float
    research_and_development: float
    other_operating_income: float
    ebitda: float


class OperatingModel(Protocol):
    """Extension point for top-down or company-specific bottom-up drivers."""

    def forecast(self, prior_revenue: float, year: int, assumptions: ForecastAssumptions) -> OperatingForecast:
        """Forecast one period's operating results."""


class TopDownOperatingModel:
    """Revenue growth and margin-driven operating model."""

    def forecast(self, prior_revenue: float, year: int, assumptions: ForecastAssumptions) -> OperatingForecast:
        revenue = prior_revenue * (1.0 + assumptions.revenue_growth[year])
        cogs = revenue * assumptions.cogs_as_pct_revenue[year]
        sga = revenue * assumptions.sga_as_pct_revenue[year]
        research_and_development = revenue * assumptions.rd_as_pct_revenue[year]
        other_operating_income = (
            revenue * assumptions.other_operating_income_as_pct_revenue[year]
        )
        gross_profit = revenue - cogs
        ebitda = gross_profit - sga - research_and_development + other_operating_income
        return OperatingForecast(
            revenue=revenue,
            cogs=cogs,
            gross_profit=gross_profit,
            selling_general_admin=sga,
            research_and_development=research_and_development,
            other_operating_income=other_operating_income,
            ebitda=ebitda,
        )
