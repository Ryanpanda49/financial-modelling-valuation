import pytest

from fmva.checks.models import CheckStatus
from fmva.forecasting.assumptions import ForecastAssumptions
from fmva.forecasting.three_statement import InitialFinancialState, ThreeStatementModel


def initial_state() -> InitialFinancialState:
    return InitialFinancialState(
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


def test_five_year_forecast_links_and_all_checks_pass() -> None:
    assumptions = ForecastAssumptions.from_yaml("config/forecast_assumptions.example.yaml")
    result = ThreeStatementModel().run(initial_state(), assumptions)
    assert list(result.income_statement.columns) == [2025, 2026, 2027, 2028, 2029]
    assert result.income_statement.loc["revenue", 2025] == pytest.approx(1050.0)
    assert result.working_capital.loc["cash_conversion_cycle", 2025] == pytest.approx(42.29)
    assert result.fixed_assets.loc["ending_ppe", 2025] == pytest.approx(354.0)
    assert result.balance_sheet.loc["cash_and_equivalents", 2025] == pytest.approx(
        result.cash_flow_statement.loc["ending_cash", 2025]
    )
    assert result.checks
    assert all(check.status is CheckStatus.PASS for check in result.checks)


def test_opening_balance_sheet_must_balance() -> None:
    assumptions = ForecastAssumptions.from_yaml("config/forecast_assumptions.example.yaml")
    state = initial_state()
    object.__setattr__(state, "cash_and_equivalents", 101.0)
    with pytest.raises(ValueError, match="out of balance"):
        ThreeStatementModel().run(state, assumptions)


def test_minimum_cash_policy_can_trigger_borrowing() -> None:
    assumptions = ForecastAssumptions.from_yaml("config/forecast_assumptions.example.yaml")
    object.__setattr__(
        assumptions,
        "minimum_cash_as_pct_revenue",
        {year: 0.40 for year in assumptions.years},
    )
    result = ThreeStatementModel().run(initial_state(), assumptions)
    assert result.debt_schedule.loc["new_borrowing", 2025] > 0
    assert result.balance_sheet.loc["cash_and_equivalents", 2025] == pytest.approx(
        result.debt_schedule.loc["minimum_cash", 2025], abs=1e-6
    )
    assert all(check.status is CheckStatus.PASS for check in result.checks)


def test_share_repurchases_flow_through_cash_and_contributed_equity() -> None:
    assumptions = ForecastAssumptions.from_yaml("config/forecast_assumptions.example.yaml")
    object.__setattr__(
        assumptions,
        "share_repurchases",
        {year: 10.0 for year in assumptions.years},
    )
    result = ThreeStatementModel().run(initial_state(), assumptions)

    assert result.cash_flow_statement.loc["share_repurchases", 2025] == pytest.approx(-10.0)
    assert result.balance_sheet.loc["contributed_equity", 2025] == pytest.approx(240.0)
    assert any(check.check == "contributed_equity" for check in result.checks)
    assert all(check.status is CheckStatus.PASS for check in result.checks)
