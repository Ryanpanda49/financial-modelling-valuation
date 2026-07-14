import json
from pathlib import Path

import pytest

from fmva import ValuationModel
from fmva.data.statement_builder import HistoricalStatements

FIXTURE = Path("data/sample/wmt_fy2022_2026_history.json")


def test_public_wmt_fixture_is_sanitized_and_complete() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    history = HistoricalStatements.from_dict(payload)
    content = FIXTURE.read_text(encoding="utf-8").lower()

    assert payload["metadata"]["ticker"] == "WMT"
    assert payload["metadata"]["fiscal_years"] == [2022, 2023, 2024, 2025, 2026]
    assert len(history.observations) == 330
    assert not history.quality_issues
    assert "user_agent" not in content
    assert "request_headers" not in content
    assert "cache_directory" not in content


def test_public_wmt_fixture_runs_full_offline_model() -> None:
    model = ValuationModel.from_history_json(
        FIXTURE,
        forecast_assumptions_path="examples/wmt/forecast_assumptions.yaml",
        valuation_assumptions_path="examples/wmt/valuation_assumptions.yaml",
    )
    result = model.run()

    assert result.ticker == "WMT"
    assert list(result.forecast.income_statement.columns) == [2027, 2028, 2029, 2030, 2031]
    assert all(check.status.value == "PASS" for check in result.historical_checks)
    assert all(check.status.value == "PASS" for check in result.forecast.checks)
    assert all(check.status.value == "PASS" for check in result.dcf.checks)
    assert result.dcf.implied_share_price == pytest.approx(51.02, abs=0.02)
