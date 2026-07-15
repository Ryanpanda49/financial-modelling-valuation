"""Discover and retrieve filing-level XBRL instance documents from SEC Archives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from fmva.exceptions import SecDataError
from fmva.sec.client import SecClient
from fmva.sec.xbrl_dimensions import select_instance_document


@dataclass(frozen=True, slots=True)
class FilingMetadata:
    """Minimum SEC submission metadata required to locate one filing directory."""

    accession_number: str
    filing_date: date
    report_date: date | None
    form: str
    primary_document: str
    is_amendment: bool


@dataclass(frozen=True, slots=True)
class FilingInstance:
    """Retrieved XBRL instance and its complete SEC source identity."""

    cik: str
    filing: FilingMetadata
    document_name: str
    document_url: str
    content: str


def select_annual_filing(
    submissions: Mapping[str, Any],
    *,
    accession_number: str | None = None,
    include_amendments: bool = False,
) -> FilingMetadata:
    """Select the latest recent 10-K, or one explicitly requested accession."""

    records = _recent_filing_records(submissions)
    normalized_accession = accession_number.replace("-", "") if accession_number else None
    candidates = [record for record in records if record.form in {"10-K", "10-K/A"}]
    if normalized_accession:
        candidates = [
            record
            for record in candidates
            if record.accession_number.replace("-", "") == normalized_accession
        ]
    elif not include_amendments:
        candidates = [record for record in candidates if not record.is_amendment]
    if not candidates:
        target = f" accession {accession_number}" if accession_number else ""
        raise SecDataError(f"No eligible recent annual filing found{target}.")
    return max(
        candidates,
        key=lambda record: (record.report_date or record.filing_date, record.filing_date),
    )


def filing_document_url(cik: str | int, accession_number: str, document_name: str) -> str:
    """Build the canonical SEC Archives URL for one filing document."""

    accession = accession_number.replace("-", "").strip()
    if not accession.isdigit() or not document_name or "/" in document_name:
        raise ValueError("Invalid accession number or filing document name.")
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{accession}/{document_name}"
    )


class FilingInstanceService:
    """Resolve a filing directory, select its instance, and retrieve it through SecClient."""

    def __init__(self, client: SecClient) -> None:
        self.client = client

    def fetch_latest_10k(
        self,
        cik: str,
        submissions: Mapping[str, Any],
        *,
        accession_number: str | None = None,
    ) -> FilingInstance:
        filing = select_annual_filing(submissions, accession_number=accession_number)
        directory = self.client.filing_directory(cik, filing.accession_number)
        document_name = select_instance_document(directory, filing.primary_document)
        document_url = filing_document_url(cik, filing.accession_number, document_name)
        return FilingInstance(
            cik=f"{int(cik):010d}",
            filing=filing,
            document_name=document_name,
            document_url=document_url,
            content=self.client.get_text(document_url),
        )


def _recent_filing_records(submissions: Mapping[str, Any]) -> tuple[FilingMetadata, ...]:
    try:
        recent = submissions["filings"]["recent"]
        accessions = recent["accessionNumber"]
        filing_dates = recent["filingDate"]
        report_dates = recent["reportDate"]
        forms = recent["form"]
        primary_documents = recent["primaryDocument"]
    except (KeyError, TypeError) as exc:
        raise SecDataError("SEC submissions payload lacks recent filing arrays.") from exc
    lengths = {
        len(accessions),
        len(filing_dates),
        len(report_dates),
        len(forms),
        len(primary_documents),
    }
    if len(lengths) != 1:
        raise SecDataError("SEC recent filing arrays have inconsistent lengths.")
    records: list[FilingMetadata] = []
    try:
        for index, accession in enumerate(accessions):
            form = str(forms[index]).upper()
            records.append(
                FilingMetadata(
                    accession_number=str(accession),
                    filing_date=date.fromisoformat(str(filing_dates[index])),
                    report_date=(
                        date.fromisoformat(str(report_dates[index]))
                        if report_dates[index]
                        else None
                    ),
                    form=form,
                    primary_document=str(primary_documents[index]),
                    is_amendment=form.endswith("/A"),
                )
            )
    except (TypeError, ValueError) as exc:
        raise SecDataError("SEC recent filing metadata contains invalid values.") from exc
    return tuple(records)
