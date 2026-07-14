import json
from pathlib import Path

import pytest

from fmva import ValuationModel
from fmva.data.statement_builder import HistoricalStatements


@pytest.mark.parametrize(
    ("ticker", "expected_price"),
    (("ko", 67.72), ("msft", 285.43)),
)
def test_public_fixture_runs_complete_offline_model(
    ticker: str,
    expected_price: float,
) -> None:
    fixture = Path(f"data/sample/{ticker}_fy2021_2025_history.json")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    history = HistoricalStatements.from_dict(payload)
    model = ValuationModel.from_history_json(
        fixture,
        forecast_assumptions_path=f"examples/{ticker}/forecast_assumptions.yaml",
        valuation_assumptions_path=f"examples/{ticker}/valuation_assumptions.yaml",
    )
    result = model.run()

    assert payload["metadata"]["fiscal_years"] == [2021, 2022, 2023, 2024, 2025]
    assert len(history.observations) == 330
    assert not history.quality_issues
    assert list(result.forecast.income_statement.columns) == [2026, 2027, 2028, 2029, 2030]
    assert all(check.status.value == "PASS" for check in result.historical_checks)
    assert all(check.status.value == "PASS" for check in result.forecast.checks)
    assert all(check.status.value == "PASS" for check in result.dcf.checks)
    assert result.dcf.implied_share_price == pytest.approx(expected_price, abs=0.02)


def test_ko_debt_and_trade_payables_use_explicit_fallbacks() -> None:
    history = HistoricalStatements.read_json(
        Path("data/sample/ko_fy2021_2025_history.json")
    )
    latest = {
        item.account: item
        for item in history.observations
        if item.fiscal_year == 2025
    }

    assert latest["accounts_payable"].provenance.source_tag == "AccountsPayableTradeCurrent"
    assert latest["short_term_debt"].provenance.source_tag == "NotesAndLoansPayable"
    assert (
        latest["long_term_debt"].provenance.source_tag
        == "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"
    )
