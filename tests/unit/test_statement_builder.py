import json
from pathlib import Path

from fmva.data.account_mapping import AccountMap, AccountMapper
from fmva.data.models import SelectionMethod
from fmva.data.statement_builder import StatementBuilder
from fmva.sec.company_facts import CompanyFacts


def test_builds_scaled_history_with_provenance_and_missingness() -> None:
    payload = json.loads(Path("tests/fixtures/wmt_companyfacts_sample.json").read_text())
    facts = CompanyFacts.from_sec_payload(payload)
    mapper = AccountMapper(AccountMap.from_yaml("config/account_mapping.yaml"))
    result = StatementBuilder(mapper).build(facts, years=5)
    income = result.statements["income_statement"]
    assert income.loc["revenue", 2020] == 524000.0
    assert income.loc["revenue", 2024] == 648100.0
    revenue_2024 = next(
        item for item in result.observations if item.account == "revenue" and item.fiscal_year == 2024
    )
    assert revenue_2024.provenance.source_filing == "0000104169-25-000099"
    assert revenue_2024.provenance.selection_method is SelectionMethod.FALLBACK
    assert any(issue.account == "net_income" for issue in result.quality_issues)
    assert set(result.provenance_frame().columns) >= {
        "source_tag",
        "source_filing",
        "filing_date",
        "confidence",
        "selection_method",
        "is_restated",
    }
    assert list(result.quality_frame().columns) == [
        "account",
        "fiscal_year",
        "severity",
        "code",
        "message",
    ]


def test_derives_gross_profit_when_direct_fact_is_missing() -> None:
    payload = json.loads(Path("tests/fixtures/wmt_companyfacts_sample.json").read_text())
    payload["facts"]["us-gaap"]["CostOfRevenue"] = {
        "label": "Cost of Revenue",
        "units": {
            "USD": [
                {
                    "start": "2023-02-01",
                    "end": "2024-01-31",
                    "val": -500000000000,
                    "accn": "0000104169-24-000001",
                    "fy": 2024,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2024-03-15",
                }
            ]
        },
    }
    facts = CompanyFacts.from_sec_payload(payload)
    result = StatementBuilder(
        AccountMapper(AccountMap.from_yaml("config/account_mapping.yaml"))
    ).build(facts, years=1)
    gross_profit = next(
        item
        for item in result.observations
        if item.account == "gross_profit"
        and item.statement == "income_statement"
        and item.fiscal_year == 2024
    )
    assert gross_profit.value is not None
    assert float(gross_profit.value) == 148100.0
    assert gross_profit.provenance.selection_method is SelectionMethod.DERIVED
    assert gross_profit.provenance.formula == "revenue - cogs"


def test_required_missing_issue_is_removed_when_derivation_succeeds() -> None:
    payload = json.loads(Path("tests/fixtures/wmt_companyfacts_sample.json").read_text())
    payload["facts"]["us-gaap"]["StockholdersEquity"] = {
        "label": "Stockholders Equity",
        "units": {
            "USD": [
                {
                    "end": "2024-01-31",
                    "val": 100000000000,
                    "accn": "0000104169-24-000001",
                    "fy": 2024,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2024-03-15",
                }
            ]
        },
    }
    result = StatementBuilder(
        AccountMapper(AccountMap.from_yaml("config/account_mapping.yaml"))
    ).build(CompanyFacts.from_sec_payload(payload), years=1)

    assert result.statements["balance_sheet"].loc["total_liabilities", 2024] == 152000.0
    assert not any(
        issue.account == "total_liabilities" and issue.code == "REQUIRED_ACCOUNT_MISSING"
        for issue in result.quality_issues
    )


def test_parent_income_derivation_discloses_optional_zero_component() -> None:
    payload = json.loads(Path("tests/fixtures/wmt_companyfacts_sample.json").read_text())
    payload["facts"]["us-gaap"]["NetIncomeLoss"] = {
        "label": "Net Income",
        "units": {
            "USD": [
                {
                    "start": "2023-02-01",
                    "end": "2024-01-31",
                    "val": 15000000000,
                    "accn": "0000104169-24-000001",
                    "fy": 2024,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2024-03-15",
                }
            ]
        },
    }
    result = StatementBuilder(
        AccountMapper(AccountMap.from_yaml("config/account_mapping.yaml"))
    ).build(CompanyFacts.from_sec_payload(payload), years=1)
    parent_income = next(
        item
        for item in result.observations
        if item.account == "net_income_attributable_to_parent"
        and item.statement == "income_statement"
        and item.fiscal_year == 2024
    )

    assert float(parent_income.value) == 15000.0
    assert parent_income.provenance.selection_method is SelectionMethod.DERIVED
    assert any("minority_interest" in warning for warning in parent_income.provenance.warnings)
    assert not any(
        issue.account == "net_income_attributable_to_parent"
        for issue in result.quality_issues
    )
