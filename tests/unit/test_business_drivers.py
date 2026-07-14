from pathlib import Path

import pytest

from fmva.exceptions import ConfigurationError
from fmva.forecasting.assumptions import ForecastAssumptions
from fmva.forecasting.business_drivers import CostMembershipRetailModel

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
