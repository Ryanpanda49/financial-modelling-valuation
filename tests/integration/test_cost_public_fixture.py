import json
from pathlib import Path

import pytest

from fmva import ValuationModel
from fmva.data.models import SelectionMethod
from fmva.data.statement_builder import HistoricalStatements

FIXTURE = Path("data/sample/cost_fy2021_2025_history.json")


def test_public_cost_fixture_runs_complete_offline_model() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    history = HistoricalStatements.from_dict(payload)
    parent_income = next(
        item
        for item in history.observations
        if item.account == "net_income_attributable_to_parent"
        and item.fiscal_year == 2025
    )
    model = ValuationModel.from_history_json(
        FIXTURE,
        forecast_assumptions_path="examples/cost/forecast_assumptions.yaml",
        valuation_assumptions_path="examples/cost/valuation_assumptions.yaml",
    )
    result = model.run()

    assert payload["metadata"]["fiscal_years"] == [2021, 2022, 2023, 2024, 2025]
    assert len(history.observations) == 330
    assert not history.quality_issues
    assert parent_income.provenance.selection_method is SelectionMethod.DERIVED
    assert any("minority_interest" in warning for warning in parent_income.provenance.warnings)
    assert list(result.forecast.income_statement.columns) == [2026, 2027, 2028, 2029, 2030]
    assert all(check.status.value == "PASS" for check in result.historical_checks)
    assert all(check.status.value == "PASS" for check in result.forecast.checks)
    assert all(check.status.value == "PASS" for check in result.dcf.checks)
    assert result.dcf.implied_share_price == pytest.approx(302.27, abs=0.02)
