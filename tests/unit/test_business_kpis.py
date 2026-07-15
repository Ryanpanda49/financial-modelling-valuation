from pathlib import Path

import pytest

from fmva.data.business_kpis import BusinessKpiHistory
from fmva.exceptions import HistoricalDataError

FIXTURE = Path("data/sample/msft_business_kpis_fy2023_2025.csv")


def test_business_kpi_import_retains_sources_and_pivots_metrics() -> None:
    history = BusinessKpiHistory.from_tabular(FIXTURE)
    revenue = history.metric_frame("segment_revenue")

    assert len(history.records) == 18
    assert revenue.loc["intelligent_cloud", 2025] == 106265
    assert history.records[0].source_url.startswith("https://www.sec.gov/")
    assert set(history.to_frame()["confidence"]) == {"HIGH"}


def test_business_kpi_import_rejects_duplicate_metric_dimension_year(tmp_path: Path) -> None:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text("\n".join([*lines, lines[1]]), encoding="utf-8")

    with pytest.raises(HistoricalDataError, match="Duplicate business KPI key"):
        BusinessKpiHistory.from_tabular(duplicate)
