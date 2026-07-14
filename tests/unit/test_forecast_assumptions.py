import pytest

from fmva.exceptions import ConfigurationError
from fmva.forecasting.assumptions import ForecastAssumptions


def test_loads_centralized_forecast_assumptions() -> None:
    assumptions = ForecastAssumptions.from_yaml("config/forecast_assumptions.example.yaml")
    assert assumptions.years == (2025, 2026, 2027, 2028, 2029)
    assert assumptions.revenue_growth[2029] == 0.03
    assert set(assumptions.tax_rate) == set(assumptions.years)


def test_rejects_invalid_tax_rate() -> None:
    assumptions = ForecastAssumptions.from_yaml("config/forecast_assumptions.example.yaml")
    object.__setattr__(assumptions, "tax_rate", {year: 1.2 for year in assumptions.years})
    with pytest.raises(ConfigurationError, match="tax_rate"):
        assumptions.validate()
