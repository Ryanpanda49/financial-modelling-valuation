"""Ticker/CIK resolution and company identity enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fmva.exceptions import CompanyNotFoundError, SecDataError
from fmva.sec.client import SecClient


@dataclass(frozen=True, slots=True)
class CompanyIdentity:
    """Minimum company identity required by the modelling workflow."""

    ticker: str
    cik: str
    name: str
    fiscal_year_end: str | None
    sic: str | None
    sic_description: str | None
    entity_type: str | None
    filings_url: str


class CompanyRegistry:
    """Resolve tickers/CIKs using SEC public registries."""

    def __init__(self, client: SecClient) -> None:
        self.client = client

    def get_company(self, identifier: str | int) -> CompanyIdentity:
        """Resolve a ticker or numeric CIK and enrich it from submissions metadata."""

        normalized = str(identifier).strip()
        if not normalized:
            raise CompanyNotFoundError("Company identifier cannot be empty.")
        ticker_hint: str | None = None
        if normalized.isdigit():
            cik = f"{int(normalized):010d}"
        else:
            ticker_hint = normalized.upper()
            cik = self._lookup_ticker(ticker_hint)
        submissions = self.client.submissions(cik)
        try:
            tickers = submissions.get("tickers") or []
            ticker = ticker_hint or str(tickers[0]).upper()
            name = str(submissions["name"])
        except (KeyError, IndexError, TypeError) as exc:
            raise SecDataError(f"SEC submissions payload lacks identity fields for CIK {cik}.") from exc
        return CompanyIdentity(
            ticker=ticker,
            cik=cik,
            name=name,
            fiscal_year_end=_optional_string(submissions.get("fiscalYearEnd")),
            sic=_optional_string(submissions.get("sic")),
            sic_description=_optional_string(submissions.get("sicDescription")),
            entity_type=_optional_string(submissions.get("entityType")),
            filings_url=f"{SecClient.WWW_BASE}/edgar/browse/?CIK={cik}",
        )

    def _lookup_ticker(self, ticker: str) -> str:
        registry = self.client.company_tickers()
        for record in registry.values():
            if not isinstance(record, dict):
                continue
            if str(record.get("ticker", "")).upper() == ticker:
                try:
                    return f"{int(record['cik_str']):010d}"
                except (KeyError, TypeError, ValueError) as exc:
                    raise SecDataError(f"Invalid CIK record for ticker {ticker}.") from exc
        raise CompanyNotFoundError(f"Ticker not found in SEC registry: {ticker}")


def _optional_string(value: Any) -> str | None:
    return None if value in (None, "") else str(value)
