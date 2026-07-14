"""Company-specific, researcher-controlled business driver models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fmva.exceptions import ConfigurationError
from fmva.forecasting.assumptions import ForecastAssumptions
from fmva.forecasting.operating import BusinessDriverModel, OperatingForecast


@dataclass(frozen=True, slots=True)
class CostMembershipRetailAssumptions:
    """Store, comparable-sales, and membership drivers for a warehouse retailer."""

    years: tuple[int, ...]
    starting_warehouses: float
    starting_merchandise_revenue: float
    starting_paid_members: float
    starting_effective_fee: float
    new_warehouses: dict[int, float]
    comparable_sales_growth: dict[int, float]
    new_warehouse_productivity: dict[int, float]
    paid_member_growth: dict[int, float]
    effective_fee_growth: dict[int, float]
    executive_member_mix: dict[int, float]
    renewal_rate: dict[int, float]
    merchandise_cogs_as_pct_sales: dict[int, float]

    @classmethod
    def from_yaml(cls, path: str | Path) -> CostMembershipRetailAssumptions:
        """Load and validate an explicit, non-SEC business-driver configuration."""

        source = Path(path)
        try:
            payload = yaml.safe_load(source.read_text(encoding="utf-8"))
            if payload["model_type"] != "cost_membership_retail":
                raise ConfigurationError(
                    f"Unsupported business driver model: {payload['model_type']}"
                )
            years = tuple(int(year) for year in payload["forecast_years"])
            opening = payload["opening"]
            drivers = payload["drivers"]
            result = cls(
                years=years,
                starting_warehouses=float(opening["warehouses"]),
                starting_merchandise_revenue=float(opening["merchandise_revenue"]),
                starting_paid_members=float(opening["paid_members_millions"]),
                starting_effective_fee=float(opening["effective_fee_usd"]),
                new_warehouses=_year_series(drivers, "new_warehouses", years),
                comparable_sales_growth=_year_series(
                    drivers, "comparable_sales_growth", years
                ),
                new_warehouse_productivity=_year_series(
                    drivers, "new_warehouse_productivity", years
                ),
                paid_member_growth=_year_series(drivers, "paid_member_growth", years),
                effective_fee_growth=_year_series(drivers, "effective_fee_growth", years),
                executive_member_mix=_year_series(drivers, "executive_member_mix", years),
                renewal_rate=_year_series(drivers, "renewal_rate", years),
                merchandise_cogs_as_pct_sales=_year_series(
                    drivers, "merchandise_cogs_as_pct_sales", years
                ),
            )
        except ConfigurationError:
            raise
        except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
            raise ConfigurationError(f"Invalid business driver assumptions: {source}") from exc
        result.validate()
        return result

    def validate(self) -> None:
        """Reject incomplete years and economically invalid driver values."""

        if not self.years or tuple(sorted(set(self.years))) != self.years:
            raise ConfigurationError("Business-driver forecast_years must be unique and increasing.")
        if min(
            self.starting_warehouses,
            self.starting_merchandise_revenue,
            self.starting_paid_members,
            self.starting_effective_fee,
        ) <= 0:
            raise ConfigurationError("Opening business-driver values must be positive.")
        for values in (
            self.new_warehouses,
            self.new_warehouse_productivity,
            self.executive_member_mix,
            self.renewal_rate,
            self.merchandise_cogs_as_pct_sales,
        ):
            if set(values) != set(self.years) or any(value < 0 for value in values.values()):
                raise ConfigurationError("Every non-growth driver must cover all years and be non-negative.")
        for values in (self.comparable_sales_growth, self.paid_member_growth, self.effective_fee_growth):
            if set(values) != set(self.years) or any(value <= -1 for value in values.values()):
                raise ConfigurationError("Growth drivers must cover all years and exceed -100%.")
        for values in (
            self.new_warehouse_productivity,
            self.executive_member_mix,
            self.renewal_rate,
            self.merchandise_cogs_as_pct_sales,
        ):
            if any(value > 1 for value in values.values()):
                raise ConfigurationError("Mix, productivity, renewal, and COGS drivers cannot exceed 100%.")


class CostMembershipRetailModel:
    """Bottom-up warehouse retail model that feeds the linked statements directly."""

    def __init__(self, inputs: CostMembershipRetailAssumptions) -> None:
        self.inputs = inputs
        self._forecasts, self._table = self._build()

    @classmethod
    def from_yaml(cls, path: str | Path) -> CostMembershipRetailModel:
        return cls(CostMembershipRetailAssumptions.from_yaml(path))

    def forecast(
        self,
        prior_revenue: float,
        year: int,
        assumptions: ForecastAssumptions,
    ) -> OperatingForecast:
        """Return one precomputed year and enforce history/config reconciliation."""

        if year not in self._forecasts:
            raise ConfigurationError(f"Business driver model does not cover FY{year}.")
        if year == self.inputs.years[0]:
            configured_opening_revenue = (
                self.inputs.starting_merchandise_revenue
                + self.inputs.starting_paid_members * self.inputs.starting_effective_fee
            )
            difference = configured_opening_revenue - prior_revenue
            tolerance = max(1.0, abs(prior_revenue) * 0.001)
            if abs(difference) > tolerance:
                raise ConfigurationError(
                    "Opening business-driver revenue does not reconcile to historical revenue: "
                    f"configured={configured_opening_revenue:.2f}, historical={prior_revenue:.2f}."
                )
        driver = self._forecasts[year]
        revenue = driver["total_revenue"]
        cogs = driver["merchandise_cogs"]
        sga = revenue * assumptions.sga_as_pct_revenue[year]
        research_and_development = revenue * assumptions.rd_as_pct_revenue[year]
        other_operating_income = revenue * assumptions.other_operating_income_as_pct_revenue[year]
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
            drivers=driver,
        )

    def driver_table(self) -> pd.DataFrame:
        """Return a copy so result consumers cannot mutate model state."""

        return self._table.copy()

    def _build(self) -> tuple[dict[int, dict[str, float]], pd.DataFrame]:
        forecasts: dict[int, dict[str, float]] = {}
        prior_warehouses = self.inputs.starting_warehouses
        prior_merchandise_revenue = self.inputs.starting_merchandise_revenue
        prior_paid_members = self.inputs.starting_paid_members
        prior_effective_fee = self.inputs.starting_effective_fee
        prior_sales_per_warehouse = prior_merchandise_revenue / prior_warehouses
        for year in self.inputs.years:
            new_warehouses = self.inputs.new_warehouses[year]
            ending_warehouses = prior_warehouses + new_warehouses
            mature_sales_per_warehouse = prior_sales_per_warehouse * (
                1.0 + self.inputs.comparable_sales_growth[year]
            )
            new_warehouse_sales = (
                new_warehouses
                * 0.5
                * mature_sales_per_warehouse
                * self.inputs.new_warehouse_productivity[year]
            )
            merchandise_revenue = (
                prior_warehouses * mature_sales_per_warehouse + new_warehouse_sales
            )
            paid_members = prior_paid_members * (1.0 + self.inputs.paid_member_growth[year])
            effective_fee = prior_effective_fee * (1.0 + self.inputs.effective_fee_growth[year])
            membership_fee_revenue = paid_members * effective_fee
            total_revenue = merchandise_revenue + membership_fee_revenue
            merchandise_cogs = (
                merchandise_revenue * self.inputs.merchandise_cogs_as_pct_sales[year]
            )
            forecasts[year] = {
                "beginning_warehouses": prior_warehouses,
                "new_warehouses": new_warehouses,
                "ending_warehouses": ending_warehouses,
                "comparable_sales_growth": self.inputs.comparable_sales_growth[year],
                "new_warehouse_productivity": self.inputs.new_warehouse_productivity[year],
                "mature_sales_per_warehouse": mature_sales_per_warehouse,
                "new_warehouse_sales": new_warehouse_sales,
                "merchandise_revenue": merchandise_revenue,
                "paid_members_millions": paid_members,
                "paid_member_growth": self.inputs.paid_member_growth[year],
                "effective_fee_usd": effective_fee,
                "effective_fee_growth": self.inputs.effective_fee_growth[year],
                "executive_member_mix": self.inputs.executive_member_mix[year],
                "renewal_rate": self.inputs.renewal_rate[year],
                "membership_fee_revenue": membership_fee_revenue,
                "total_revenue": total_revenue,
                "merchandise_cogs_as_pct_sales": self.inputs.merchandise_cogs_as_pct_sales[year],
                "merchandise_cogs": merchandise_cogs,
            }
            prior_warehouses = ending_warehouses
            prior_merchandise_revenue = merchandise_revenue
            prior_paid_members = paid_members
            prior_effective_fee = effective_fee
            prior_sales_per_warehouse = merchandise_revenue / ending_warehouses
        table = pd.DataFrame(forecasts)
        table.columns.name = "fiscal_year"
        table.index.name = "business_driver"
        return forecasts, table


def load_business_driver_model(path: str | Path) -> BusinessDriverModel:
    """Factory reserved for additional company and industry model types."""

    try:
        payload: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        model_type = payload["model_type"]
    except (OSError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise ConfigurationError(f"Invalid business driver configuration: {path}") from exc
    if model_type == "cost_membership_retail":
        return CostMembershipRetailModel.from_yaml(path)
    raise ConfigurationError(f"Unsupported business driver model: {model_type}")


def _year_series(section: dict[str, Any], key: str, years: tuple[int, ...]) -> dict[int, float]:
    try:
        raw = section[key]
        if isinstance(raw, (int, float)):
            return {year: float(raw) for year in years}
        result = {int(year): float(value) for year, value in raw.items()}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ConfigurationError(f"Invalid business driver: {key}") from exc
    if set(result) != set(years):
        raise ConfigurationError(f"Business driver '{key}' must cover exactly {years}.")
    return result
