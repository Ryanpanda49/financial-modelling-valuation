from pathlib import Path

import pytest

from fmva.exceptions import SecDataError
from fmva.sec.filing_instance import (
    FilingInstanceService,
    filing_document_url,
    select_annual_filing,
)


def submissions() -> dict:
    return {
        "filings": {
            "recent": {
                "accessionNumber": [
                    "0000950170-25-100235",
                    "0000950170-24-087843",
                    "0000950170-24-090000",
                ],
                "filingDate": ["2025-07-30", "2024-07-30", "2024-08-10"],
                "reportDate": ["2025-06-30", "2024-06-30", "2024-06-30"],
                "form": ["10-K", "10-K", "10-K/A"],
                "primaryDocument": [
                    "msft-20250630.htm",
                    "msft-20240630.htm",
                    "msft-20240630a.htm",
                ],
            }
        }
    }


def test_select_latest_annual_filing_excludes_amendments_by_default() -> None:
    filing = select_annual_filing(submissions())

    assert filing.accession_number == "0000950170-25-100235"
    assert filing.primary_document == "msft-20250630.htm"
    assert not filing.is_amendment


def test_select_explicit_accession_and_reject_missing() -> None:
    filing = select_annual_filing(
        submissions(), accession_number="000095017024087843"
    )
    assert filing.report_date is not None and filing.report_date.year == 2024

    with pytest.raises(SecDataError, match="No eligible"):
        select_annual_filing(submissions(), accession_number="0000000000-00-000000")


def test_filing_instance_service_builds_url_and_retrieves_cached_client_text() -> None:
    class StubClient:
        def filing_directory(self, cik: str, accession: str) -> dict:
            assert cik == "0000789019"
            assert accession == "0000950170-25-100235"
            return {
                "directory": {
                    "item": [
                        {"name": "msft-20250630.xml"},
                        {"name": "msft-20250630_cal.xml"},
                    ]
                }
            }

        def get_text(self, url: str) -> str:
            assert url.endswith("/789019/000095017025100235/msft-20250630.xml")
            return Path("tests/fixtures/msft_segment_instance_sample.xml").read_text()

    instance = FilingInstanceService(StubClient()).fetch_latest_10k(  # type: ignore[arg-type]
        "0000789019", submissions()
    )

    assert instance.document_name == "msft-20250630.xml"
    assert instance.content.startswith("<?xml")
    assert filing_document_url(
        "0000789019", "0000950170-25-100235", "msft-20250630.xml"
    ) == instance.document_url
