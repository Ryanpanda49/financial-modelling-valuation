from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from fmva import ValuationModel
from fmva.data.statement_builder import HistoricalStatements
from fmva.sec.company_registry import CompanyIdentity


def _standardized_wmt_shape_history() -> HistoricalStatements:
    years = [2020, 2021, 2022, 2023, 2024]
    income = pd.DataFrame(
        {
            year: {
                "revenue": 800.0 + (year - 2020) * 50.0,
                "net_income": 70.0 + (year - 2020) * 7.5,
                "diluted_shares": 104.0 - (year - 2020),
            }
            for year in years
        }
    )
    balance_data = {}
    for year in years:
        step = year - 2020
        cash = 80.0 + step * 5.0
        receivables = 80.0 + step * 5.0
        inventory = 70.0 + step * 2.5
        other_current_assets = 16.0 + step
        ppe = 260.0 + step * 10.0
        other_assets = 354.0 + step * 11.5
        payables = 60.0 + step * 2.5
        accrued = 25.0 + step * 1.25
        short_debt = 50.0
        long_debt = 150.0
        other_liabilities = 185.0 + step * 3.75
        retained = 210.0 + step * 10.0
        total_assets = cash + receivables + inventory + other_current_assets + ppe + other_assets
        total_liabilities = payables + accrued + short_debt + long_debt + other_liabilities
        contributed = total_assets - total_liabilities - retained
        balance_data[year] = {
            "cash_and_equivalents": cash,
            "accounts_receivable": receivables,
            "inventory": inventory,
            "other_current_assets": other_current_assets,
            "property_plant_equipment": ppe,
            "total_assets": total_assets,
            "accounts_payable": payables,
            "accrued_liabilities": accrued,
            "short_term_debt": short_debt,
            "long_term_debt": long_debt,
            "total_liabilities": total_liabilities,
            "retained_earnings": retained,
            "total_equity": retained + contributed,
        }
    balance = pd.DataFrame(balance_data)
    cash_flow = pd.DataFrame(
        {year: {"net_change_in_cash": 5.0 if year > 2020 else 0.0} for year in years}
    )
    return HistoricalStatements(
        statements={
            "income_statement": income,
            "balance_sheet": balance,
            "cash_flow_statement": cash_flow,
        },
        observations=(),
        quality_issues=(),
    )


def test_offline_history_runs_complete_public_api_and_outputs(tmp_path: Path) -> None:
    company = CompanyIdentity(
        ticker="WMT",
        cik="0000104169",
        name="Walmart Inc. (synthetic standardized fixture)",
        fiscal_year_end="0131",
        sic="5331",
        sic_description="Retail-Variety Stores",
        entity_type="operating",
        filings_url="https://www.sec.gov/edgar/browse/?CIK=0000104169",
    )
    model = ValuationModel.from_history(
        company=company,
        history=_standardized_wmt_shape_history(),
        forecast_assumptions_path="config/forecast_assumptions.example.yaml",
        valuation_assumptions_path="config/valuation_assumptions.example.yaml",
    )
    result = model.run()

    assert result.historical is not None
    assert result.historical_ratios is not None
    assert "revenue_growth" in result.historical_ratios.table.index
    assert result.forecast.income_statement.loc["revenue", 2025] == pytest.approx(1050.0)
    assert result.dcf.equity_bridge["less_debt"] == pytest.approx(-200.0)
    assert result.dcf.equity_bridge["add_cash"] == pytest.approx(100.0)
    assert result.dcf.implied_share_price == pytest.approx(result.dcf.equity_value / 100.0)
    assert all(check.status.value == "PASS" for check in result.forecast.checks)

    report = result.export_markdown(tmp_path / "wmt_report.md")
    workbook_path = result.export_excel(tmp_path / "wmt_model.xlsx")
    content = report.read_text(encoding="utf-8")
    workbook = load_workbook(workbook_path, data_only=False)
    assert "### Income Statement" in content
    assert "## Historical Data Quality" in content
    assert workbook["Historical"]["A4"].value == "Income Statement"
    assert workbook["Ratios"]["A4"].value == "Historical Ratios"
    assert workbook["Sources_Audit"]["B5"].value == "Standardized SEC history"
    assert "Other assets are derived" in workbook["Sources_Audit"]["B13"].value
