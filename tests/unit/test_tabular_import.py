from pathlib import Path

import pandas as pd
import pytest

from fmva import ValuationModel
from fmva.data.models import SelectionMethod
from fmva.data.tabular_import import import_canonical_history
from fmva.exceptions import HistoricalDataError

WORKBOOK = Path("data/sample/cost_manual_history_input.xlsx")


def test_manual_excel_history_runs_complete_model() -> None:
    imported = import_canonical_history(WORKBOOK)
    model = ValuationModel.from_tabular_history(
        WORKBOOK,
        forecast_assumptions_path="examples/cost/forecast_assumptions.yaml",
        valuation_assumptions_path="examples/cost/valuation_assumptions.yaml",
    )
    result = model.run()

    assert imported.company.ticker == "COST"
    assert len(imported.history.observations) == 330
    assert not imported.history.quality_issues
    assert all(
        item.provenance.selection_method
        in {SelectionMethod.MANUAL, SelectionMethod.MISSING}
        for item in imported.history.observations
    )
    assert all(check.status.value == "PASS" for check in result.historical_checks)
    assert result.dcf.implied_share_price == pytest.approx(302.27, abs=0.02)


def test_manual_csv_uses_repeated_company_metadata(tmp_path: Path) -> None:
    sheets = pd.read_excel(WORKBOOK, sheet_name=None)
    company = dict(sheets["Company"].itertuples(index=False, name=None))
    frame = sheets["Historical Financials"]
    for field in ("ticker", "cik", "company_name", "filings_url"):
        frame[field] = company[field]
    path = tmp_path / "history.csv"
    frame.to_csv(path, index=False)

    imported = import_canonical_history(path)

    assert imported.company.cik == "0000909832"
    assert imported.history.statements["income_statement"].loc["revenue", 2025] == 275235.0


def test_manual_history_rejects_duplicate_account_period(tmp_path: Path) -> None:
    sheets = pd.read_excel(WORKBOOK, sheet_name=None)
    company = dict(sheets["Company"].itertuples(index=False, name=None))
    frame = sheets["Historical Financials"]
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    for field in ("ticker", "cik", "company_name", "filings_url"):
        frame[field] = company[field]
    path = tmp_path / "duplicate.csv"
    frame.to_csv(path, index=False)

    with pytest.raises(HistoricalDataError, match="Duplicate manual history row"):
        import_canonical_history(path)
