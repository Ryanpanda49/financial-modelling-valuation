"""Audit one live SEC registrant against the canonical mapping without running a forecast."""

from __future__ import annotations

import argparse
import json

from fmva.checks.historical import HistoricalCheckSuite
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
    checks = HistoricalCheckSuite(
        absolute_tolerance=config.model.absolute_tolerance
    ).run(history)
    years = sorted({item.fiscal_year for item in history.observations})
    missing = sorted(
        {
            item.account
            for item in history.observations
            if item.value is None
        }
    )
    payload = {
        "ticker": company.ticker,
        "cik": company.cik,
        "company_name": company.name,
        "fiscal_years": years,
        "observation_count": len(history.observations),
        "quality_issue_count": len(history.quality_issues),
        "quality_issues": [
            {
                "account": item.account,
                "fiscal_year": item.fiscal_year,
                "severity": item.severity,
                "code": item.code,
            }
            for item in history.quality_issues
        ],
        "missing_accounts": missing,
        "checks": [
            {
                "check": item.check,
                "status": item.status.value,
                "difference": item.difference,
                "message": item.message,
            }
            for item in checks
        ],
    }
    print(json.dumps(payload, indent=2))
    return 1 if history.quality_issues or any(item.status.value == "FAIL" for item in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
