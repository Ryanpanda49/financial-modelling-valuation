from pathlib import Path

import pytest

from fmva.exceptions import ConfigurationError
from fmva.forecasting.assumptions import ForecastAssumptions
from fmva.forecasting.business_drivers import (
    CostMembershipRetailModel,
    SegmentRevenueModel,
    SubscriberArpuModel,
)

DRIVERS = Path("examples/cost/business_drivers.yaml")
FORECAST = Path("examples/cost/forecast_assumptions.yaml")


def test_cost_driver_model_builds_store_and_membership_revenue_bridge() -> None:
    model = CostMembershipRetailModel.from_yaml(DRIVERS)
    assumptions = ForecastAssumptions.from_yaml(FORECAST)

    result = model.forecast(275235.0, 2026, assumptions)
    drivers = model.driver_table()

    assert result.revenue == pytest.approx(
        drivers.loc["merchandise_revenue", 2026]
        + drivers.loc["membership_fee_revenue", 2026]
    )
    assert result.cogs == pytest.approx(drivers.loc["merchandise_cogs", 2026])
    assert drivers.loc["ending_warehouses", 2026] == 944
    assert drivers.loc["beginning_warehouses", 2027] == 944


def test_cost_driver_model_rejects_unreconciled_opening_revenue() -> None:
    model = CostMembershipRetailModel.from_yaml(DRIVERS)
    assumptions = ForecastAssumptions.from_yaml(FORECAST)

    with pytest.raises(ConfigurationError, match="does not reconcile"):
        model.forecast(200000.0, 2026, assumptions)


def test_segment_model_rolls_each_business_and_consolidates_cogs() -> None:
    model = SegmentRevenueModel.from_yaml("examples/msft/business_drivers.yaml")
    assumptions = ForecastAssumptions.from_yaml("examples/msft/forecast_assumptions.yaml")

    result = model.forecast(281724.0, 2026, assumptions)
    drivers = model.driver_table()
    segment_revenue_rows = [
        row
        for row in drivers.index
        if row.endswith("_revenue")
        and not row.endswith("_pct_revenue")
        and row != "total_revenue"
    ]
    segment_cogs_rows = [
        row for row in drivers.index if row.endswith("_cogs") and row != "total_segment_cogs"
    ]

    assert result.revenue == pytest.approx(drivers.loc[segment_revenue_rows, 2026].sum())
    assert result.cogs == pytest.approx(drivers.loc[segment_cogs_rows, 2026].sum())
    assert drivers.loc["intelligent_cloud_revenue_growth", 2026] == pytest.approx(0.21)


def test_subscriber_arpu_model_reconciles_subscription_and_residual_revenue() -> None:
    model = SubscriberArpuModel.from_yaml("examples/msft/subscriber_business_drivers.yaml")
    assumptions = ForecastAssumptions.from_yaml("examples/msft/forecast_assumptions.yaml")

    result = model.forecast(281724.0, 2026, assumptions)
    drivers = model.driver_table()

    assert drivers.loc["microsoft_365_consumer_subscribers_millions", 2026] == pytest.approx(
        96.12
    )
    assert drivers.loc["microsoft_365_consumer_annual_arpu_usd", 2026] == pytest.approx(
        105.0
    )
    assert result.revenue == pytest.approx(
        drivers.loc["microsoft_365_consumer_revenue", 2026]
        + drivers.loc["all_other_revenue_revenue", 2026]
    )
    assert result.cogs == pytest.approx(drivers.loc["total_business_cogs", 2026])
