import pandas as pd

from fmva.checks.historical import HistoricalCheckSuite
from fmva.checks.models import CheckStatus
from fmva.data.statement_builder import HistoricalStatements


def history(balance: pd.DataFrame, cash_flow: pd.DataFrame) -> HistoricalStatements:
    return HistoricalStatements(
        statements={"balance_sheet": balance, "cash_flow_statement": cash_flow},
        observations=(),
        quality_issues=(),
    )


def test_balance_and_cash_rollforward_pass() -> None:
    balance = pd.DataFrame(
        {
            2023: {"total_assets": 100.0, "total_liabilities": 60.0, "total_equity": 40.0, "cash_and_equivalents": 10.0},
            2024: {"total_assets": 120.0, "total_liabilities": 70.0, "total_equity": 50.0, "cash_and_equivalents": 13.0},
        }
    )
    cash_flow = pd.DataFrame({2023: {"net_change_in_cash": 2.0}, 2024: {"net_change_in_cash": 3.0}})
    results = HistoricalCheckSuite().run(history(balance, cash_flow))
    relevant = [
        item
        for item in results
        if item.check not in {"required_account_completeness", "valuation_bridge_readiness"}
    ]
    assert relevant
    assert all(item.status is CheckStatus.PASS for item in relevant)


def test_balance_failure_reports_actual_difference() -> None:
    balance = pd.DataFrame(
        {2024: {"total_assets": 121.0, "total_liabilities": 70.0, "total_equity": 50.0, "cash_and_equivalents": 13.0}}
    )
    cash_flow = pd.DataFrame({2024: {"net_change_in_cash": 3.0}})
    result = next(
        item
        for item in HistoricalCheckSuite().run(history(balance, cash_flow))
        if item.check == "balance_sheet"
    )
    assert result.status is CheckStatus.FAIL
    assert result.difference == 1.0
    assert result.actual == 121.0
    assert result.expected == 120.0


def test_interest_without_debt_fails_valuation_diagnostic() -> None:
    balance = pd.DataFrame(
        {2024: {"total_assets": 100.0, "total_liabilities": 60.0, "total_equity": 40.0, "cash_and_equivalents": 10.0}}
    )
    cash_flow = pd.DataFrame({2024: {"net_change_in_cash": 1.0}})
    income = pd.DataFrame({2024: {"diluted_shares": 5.0, "interest_expense": 2.0}})
    source = history(balance, cash_flow)
    source = HistoricalStatements(
        statements={**source.statements, "income_statement": income},
        observations=(),
        quality_issues=(),
    )

    results = HistoricalCheckSuite().run(source)

    debt_check = next(item for item in results if item.check == "debt_interest_consistency")
    bridge_check = next(item for item in results if item.check == "valuation_bridge_readiness")
    assert debt_check.status is CheckStatus.FAIL
    assert bridge_check.status is CheckStatus.FAIL
