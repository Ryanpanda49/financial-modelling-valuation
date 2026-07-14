import json
from pathlib import Path

from fmva.sec.company_facts import CompanyFacts, FiscalPeriodType


def load_fixture() -> dict:
    return json.loads(Path("tests/fixtures/wmt_companyfacts_sample.json").read_text())


def test_selects_five_annual_periods_and_latest_restatement() -> None:
    facts = CompanyFacts.from_sec_payload(load_fixture())
    annual = facts.annual_observations("Revenues", years=5)
    assert [item.fiscal_year for item in annual] == [2020, 2021, 2022, 2023, 2024]
    assert annual[-1].accession_number == "0000104169-25-000099"
    assert str(annual[-1].value) == "648100000000"
    assert annual[-1].fiscal_year == 2024
    assert annual[-1].sec_fiscal_year == 2025


def test_ytd_fact_is_not_selected_as_annual() -> None:
    facts = CompanyFacts.from_sec_payload(load_fixture())
    observations = facts.for_concept("Revenues")
    ytd = next(item for item in observations if item.form == "10-Q")
    assert ytd.fiscal_period is FiscalPeriodType.YTD
    assert ytd not in facts.annual_observations("Revenues")


def test_instant_fact_is_classified() -> None:
    facts = CompanyFacts.from_sec_payload(load_fixture())
    assets = facts.annual_observations("Assets")
    assert len(assets) == 1
    assert assets[0].duration_days is None
