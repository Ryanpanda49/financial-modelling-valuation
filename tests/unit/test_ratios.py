import numpy as np
import pytest

from fmva.analysis.ratios import calculate_financial_ratios
from fmva.forecasting.assumptions import ForecastAssumptions
from fmva.forecasting.three_statement import InitialFinancialState, ThreeStatementModel


def state() -> InitialFinancialState:
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
        net_income=140.0,
        diluted_shares=100.0,
    )


def test_ratio_library_outputs_requested_categories_without_infinity() -> None:
    initial = state()
    forecast = ThreeStatementModel().run(
        initial,
        ForecastAssumptions.from_yaml("config/forecast_assumptions.example.yaml"),
    )
    result = calculate_financial_ratios(forecast, initial)
    expected = {
        "revenue_growth", "ebitda_growth", "net_income_growth", "eps_growth", "fcf_growth",
        "gross_margin", "ebitda_margin", "operating_margin", "net_margin", "roa", "roe", "roic",
        "current_ratio", "quick_ratio", "cash_ratio", "debt_to_equity", "debt_to_ebitda",
        "net_debt_to_ebitda", "interest_coverage", "asset_turnover", "inventory_turnover",
        "receivables_turnover", "payables_turnover", "dso", "dio", "dpo",
        "cash_conversion_cycle", "cfo_to_net_income", "fcf_margin", "capex_to_revenue",
        "cash_conversion_ratio",
    }
    assert expected <= set(result.table.index)
    assert result.table.loc["revenue_growth", 2025] == pytest.approx(0.05)
    assert result.table.loc["gross_margin", 2025] == pytest.approx(0.40)
    assert not np.isinf(result.table.to_numpy(dtype=float)).any()


def test_missing_share_count_returns_warning_not_infinity() -> None:
    initial = state()
    object.__setattr__(initial, "diluted_shares", None)
    forecast = ThreeStatementModel().run(
        initial,
        ForecastAssumptions.from_yaml("config/forecast_assumptions.example.yaml"),
    )
    result = calculate_financial_ratios(forecast, initial)
    assert result.table.loc["eps_growth"].isna().all()
    assert any("diluted shares" in warning for warning in result.warnings)
