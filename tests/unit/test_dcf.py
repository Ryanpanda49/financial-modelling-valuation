import pandas as pd
import pytest

from fmva.checks.models import CheckStatus
from fmva.exceptions import ConfigurationError
from fmva.forecasting.assumptions import ForecastAssumptions
from fmva.forecasting.three_statement import InitialFinancialState, ThreeStatementModel
from fmva.valuation.dcf import TerminalMethod, value_dcf
from fmva.valuation.free_cash_flow import calculate_unlevered_fcf
from fmva.valuation.models import ValuationAssumptions, ValuationMetadata
from fmva.valuation.sensitivity import wacc_terminal_growth_sensitivity
from fmva.valuation.terminal_value import perpetuity_growth_terminal_value


def forecast():
    state = InitialFinancialState(
        fiscal_year=2024,
        revenue=1000.0,
        cash_and_equivalents=100.0,
        accounts_receivable=100.0,
        inventory=80.0,
        other_current_assets=20.0,
        property_plant_equipment=300.0,
        other_assets=400.0,
        accounts_payable=70.0,
        accrued_liabilities=30.0,
        short_term_debt=50.0,
        long_term_debt=150.0,
        other_liabilities=200.0,
        contributed_equity=250.0,
        retained_earnings=250.0,
    )
    return ThreeStatementModel().run(
        state,
        ForecastAssumptions.from_yaml("config/forecast_assumptions.example.yaml"),
    )


def test_unlevered_fcf_formula() -> None:
    index = [2025, 2026]
    result = calculate_unlevered_fcf(
        pd.Series([100.0, 110.0], index=index),
        pd.Series([0.25, 0.25], index=index),
        pd.Series([10.0, 11.0], index=index),
        pd.Series([20.0, 21.0], index=index),
        pd.Series([5.0, 6.0], index=index),
    )
    assert result.tolist() == [60.0, 66.5]


def test_dcf_contains_complete_bridge_and_discount_table() -> None:
    assumptions = ValuationAssumptions.from_yaml("config/valuation_assumptions.example.yaml")
    assert assumptions.metadata.is_illustrative
    assert assumptions.metadata.valuation_date == "2025-01-01"
    assert assumptions.metadata.sources["risk_free_rate"].as_of_date == "2025-01-01"
    result = value_dcf(forecast(), assumptions)
    assert list(result.forecast.columns) == [
        "ebit",
        "tax_rate",
        "nopat",
        "depreciation_and_amortization",
        "capital_expenditures",
        "change_in_net_working_capital",
        "unlevered_fcf",
        "discount_period",
        "discount_factor",
        "pv_fcf",
    ]
    assert result.enterprise_value == pytest.approx(result.pv_forecast_fcf + result.pv_terminal_value)
    assert result.equity_value == pytest.approx(result.equity_bridge.sum())
    assert result.implied_share_price == pytest.approx(result.equity_value / assumptions.diluted_shares)
    assert result.wacc > assumptions.terminal_growth_rate
    assert result.checks
    assert all(check.status is CheckStatus.PASS for check in result.checks)


def test_exit_multiple_method_is_supported() -> None:
    assumptions = ValuationAssumptions.from_yaml("config/valuation_assumptions.example.yaml")
    result = value_dcf(forecast(), assumptions, terminal_method=TerminalMethod.EXIT_MULTIPLE)
    assert result.terminal_method is TerminalMethod.EXIT_MULTIPLE
    assert result.terminal_value > 0


def test_invalid_wacc_terminal_growth_is_rejected() -> None:
    with pytest.raises(ValueError, match="greater than"):
        perpetuity_growth_terminal_value(100.0, 0.02, 0.02)


def test_sensitivity_recalculates_and_has_expected_direction() -> None:
    assumptions = ValuationAssumptions.from_yaml("config/valuation_assumptions.example.yaml")
    table = wacc_terminal_growth_sensitivity(
        forecast(), assumptions, [0.07, 0.08, 0.09], [0.01, 0.02, 0.03]
    )
    assert table.loc[0.07, 0.02] > table.loc[0.08, 0.02] > table.loc[0.09, 0.02]
    assert table.loc[0.08, 0.01] < table.loc[0.08, 0.02] < table.loc[0.08, 0.03]


def test_non_illustrative_valuation_requires_dated_core_sources() -> None:
    with pytest.raises(ConfigurationError, match="lacks sources"):
        ValuationMetadata.from_mapping(
            {
                "valuation_date": "2026-07-14",
                "scenario_name": "Research case",
                "is_illustrative": False,
                "sources": {},
            }
        )
