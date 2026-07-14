import pandas as pd
import pytest

from fmva.data.statement_builder import HistoricalStatements
from fmva.exceptions import HistoricalDataError
from fmva.forecasting.history_adapter import historical_to_initial_state


def _history() -> HistoricalStatements:
    income = pd.DataFrame(
        {
            2023: {"revenue": 900.0, "net_income": 90.0, "diluted_shares": 102.0},
            2024: {"revenue": 1000.0, "net_income": 100.0, "diluted_shares": 100.0},
        }
    )
    balance = pd.DataFrame(
        {
            2023: {
                "cash_and_equivalents": 90.0,
                "accounts_receivable": 90.0,
                "inventory": 75.0,
                "other_current_assets": 15.0,
                "property_plant_equipment": 280.0,
                "total_assets": 950.0,
                "accounts_payable": 65.0,
                "accrued_liabilities": 25.0,
                "short_term_debt": 50.0,
                "long_term_debt": 150.0,
                "total_liabilities": 480.0,
                "retained_earnings": 220.0,
                "total_equity": 470.0,
            },
            2024: {
                "cash_and_equivalents": 100.0,
                "accounts_receivable": 100.0,
                "inventory": 80.0,
                "other_current_assets": 20.0,
                "property_plant_equipment": 300.0,
                "total_assets": 1000.0,
                "accounts_payable": 70.0,
                "accrued_liabilities": 30.0,
                "short_term_debt": 50.0,
                "long_term_debt": 150.0,
                "total_liabilities": 500.0,
                "retained_earnings": 250.0,
                "total_equity": 500.0,
            },
        }
    )
    return HistoricalStatements(
        statements={"income_statement": income, "balance_sheet": balance},
        observations=(),
        quality_issues=(),
    )


def test_latest_history_builds_balanced_opening_state_with_disclosed_residuals() -> None:
    result = historical_to_initial_state(_history())

    assert result.fiscal_year == 2024
    assert result.state.other_assets == pytest.approx(400.0)
    assert result.state.other_liabilities == pytest.approx(200.0)
    assert result.state.contributed_equity == pytest.approx(250.0)
    assert result.state.total_assets == pytest.approx(
        result.state.total_liabilities_and_equity
    )
    assert len(result.warnings) == 3


def test_optional_missing_account_is_explicitly_defaulted_and_warned() -> None:
    history = _history()
    history.statements["balance_sheet"].loc["inventory", 2024] = float("nan")
    result = historical_to_initial_state(history)

    assert result.state.inventory == 0.0
    assert any("inventory is missing" in warning for warning in result.warnings)


def test_required_total_missing_fails_instead_of_plugging() -> None:
    history = _history()
    history.statements["balance_sheet"].loc["total_assets", 2024] = float("nan")

    with pytest.raises(HistoricalDataError, match="total_assets"):
        historical_to_initial_state(history)


def test_overlapping_accounts_that_create_negative_residual_fail() -> None:
    history = _history()
    history.statements["balance_sheet"].loc["property_plant_equipment", 2024] = 900.0

    with pytest.raises(HistoricalDataError, match="other assets are negative"):
        historical_to_initial_state(history)
