"""Build a sanitized public standardized-history fixture from SEC Company Facts."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from fmva.config.loader import load_config
from fmva.data.account_mapping import AccountMap, AccountMapper
from fmva.data.statement_builder import StatementBuilder
from fmva.sec.client import SecClient
from fmva.sec.company_facts import CompanyFacts
from fmva.sec.company_registry import CompanyRegistry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument("--config", default="config/model_config.yaml")
    parser.add_argument("--mapping", default="config/account_mapping.yaml")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config, live_sec=True)
    client = SecClient(config.sec)
    company = CompanyRegistry(client).get_company(args.ticker)
    facts = CompanyFacts.from_sec_payload(client.company_facts(company.cik))
    history = StatementBuilder(
        AccountMapper(AccountMap.from_yaml(args.mapping))
    ).build(facts, years=args.years)
    years = sorted({item.fiscal_year for item in history.observations})
    output = Path(args.output) if args.output else Path(
        f"data/sample/{company.ticker.lower()}_fy{years[0]}_{years[-1]}_history.json"
    )
    latest_filing_date = max(
        item.provenance.filing_date
        for item in history.observations
        if item.provenance.filing_date is not None
    )
    history.write_json(
        output,
        metadata={
            "ticker": company.ticker,
            "cik": company.cik,
            "company_name": company.name,
            "fiscal_year_end": company.fiscal_year_end,
            "sic": company.sic,
            "sic_description": company.sic_description,
            "entity_type": company.entity_type,
            "filings_url": company.filings_url,
            "fiscal_years": years,
            "latest_source_filing_date": latest_filing_date,
            "fixture_generated_on": date.today().isoformat(),
            "source": "SEC EDGAR Company Facts API",
            "source_url": (
                "https://data.sec.gov/api/xbrl/companyfacts/"
                f"CIK{company.cik}.json"
            ),
            "units": "USD millions except per-share data",
            "notice": (
                "Public SEC filing data pinned for deterministic offline tests. "
                "Analyst review remains required."
            ),
        },
    )
    print(output)
    return 1 if history.quality_issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
