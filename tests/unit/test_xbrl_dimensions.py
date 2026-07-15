from pathlib import Path

import pytest

from fmva.exceptions import SecDataError
from fmva.sec.xbrl_dimensions import (
    BusinessKpiMapping,
    dimensional_facts_to_business_kpis,
    filing_directory_url,
    parse_dimensional_facts,
    select_instance_document,
)


def test_filing_directory_and_instance_selection_are_deterministic() -> None:
    payload = {
        "directory": {
            "item": [
                {"name": "msft-20250630.htm"},
                {"name": "msft-20250630.xml"},
                {"name": "msft-20250630_cal.xml"},
                {"name": "msft-20250630_lab.xml"},
                {"name": "FilingSummary.xml"},
            ]
        }
    }

    assert filing_directory_url("0000789019", "0000950170-25-100235").endswith(
        "/789019/000095017025100235/index.json"
    )
    assert select_instance_document(payload, "msft-20250630.htm") == "msft-20250630.xml"


def test_instance_selection_rejects_ambiguous_xml() -> None:
    payload = {"directory": {"item": [{"name": "a.xml"}, {"name": "b.xml"}]}}
    with pytest.raises(SecDataError, match="unique"):
        select_instance_document(payload)


def test_dimensional_parser_maps_msft_segment_facts_to_auditable_kpis() -> None:
    facts = parse_dimensional_facts(Path("tests/fixtures/msft_segment_instance_sample.xml"))
    mapping = BusinessKpiMapping.from_yaml("config/business_kpi_mapping.msft.yaml")
    history = dimensional_facts_to_business_kpis(facts, mapping)
    frame = history.to_frame()

    assert len(facts) == 18
    assert len(frame) == 18
    assert history.metric_frame("segment_revenue").loc["intelligent_cloud", 2025] == pytest.approx(
        106265.0
    )
    assert history.metric_frame("segment_cogs").loc[
        "productivity_and_business_processes", 2024
    ] == pytest.approx(19611.0)
    assert frame.loc[frame["fiscal_year"] == 2024, "is_restated"].all()
    assert not frame.loc[frame["fiscal_year"] == 2025, "is_restated"].any()
    assert frame["notes"].str.contains("context FY").all()
