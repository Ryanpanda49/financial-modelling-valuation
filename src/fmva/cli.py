"""Command-line entry points for the implemented data layer."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from fmva.analysis.backtesting import BacktestReport
from fmva.analysis.ratios import calculate_financial_ratios
from fmva.checks.historical import HistoricalCheckSuite
from fmva.config.loader import load_config
from fmva.data.account_mapping import AccountMap, AccountMapper
from fmva.data.business_kpis import BusinessKpiHistory
from fmva.data.statement_builder import StatementBuilder
from fmva.forecasting.assumptions import ForecastAssumptions
from fmva.forecasting.business_drivers import load_business_driver_model
from fmva.forecasting.three_statement import InitialFinancialState, ThreeStatementModel
from fmva.logging import configure_logging
from fmva.output import ModelResult
from fmva.output.assumptions import summarize_assumptions
from fmva.sec.client import SecClient
from fmva.sec.company_facts import CompanyFacts
from fmva.sec.company_registry import CompanyRegistry
from fmva.sec.filing_instance import FilingInstanceService
from fmva.sec.xbrl_dimensions import (
    BusinessKpiMapping,
    dimensional_facts_to_business_kpis,
    parse_dimensional_facts,
)
from fmva.valuation.dcf import value_dcf
from fmva.valuation.models import ValuationAssumptions
from fmva.valuation.sensitivity import wacc_terminal_growth_sensitivity


def _json_default(value: Any) -> Any:
    if isinstance(value, (Decimal, Path)):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Not JSON serializable: {type(value)!r}")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(prog="fmva", description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    company = subcommands.add_parser("company", help="Resolve ticker/CIK and company metadata.")
    company.add_argument("identifier")
    company.add_argument("--config", required=True)
    facts = subcommands.add_parser("facts", help="Show annual Company Facts observations.")
    facts.add_argument("identifier")
    facts.add_argument("--concept", required=True)
    facts.add_argument("--taxonomy", default="us-gaap")
    facts.add_argument("--years", type=int, default=5)
    facts.add_argument("--config", required=True)
    history = subcommands.add_parser("history", help="Build standardized annual historical statements.")
    history.add_argument("identifier")
    history.add_argument("--years", type=int, default=None)
    history.add_argument("--mapping", default="config/account_mapping.yaml")
    history.add_argument("--config", required=True)
    business_kpis = subcommands.add_parser(
        "business-kpis",
        help="Convert a filing-level XBRL instance into canonical dimensional KPIs.",
    )
    business_kpi_source = business_kpis.add_mutually_exclusive_group(required=True)
    business_kpi_source.add_argument("--instance", help="Local XBRL instance XML.")
    business_kpi_source.add_argument(
        "--identifier", help="Ticker or CIK for automatic latest 10-K discovery."
    )
    business_kpis.add_argument("--mapping", required=True)
    business_kpis.add_argument("--config", help="Private SEC config; required with --identifier.")
    business_kpis.add_argument("--accession", help="Optional explicit 10-K accession number.")
    business_kpis.add_argument("--output", help="Optional canonical CSV output path.")
    business_kpis.add_argument("--quality-output", help="Optional JSON quality-summary path.")
    backtest = subcommands.add_parser(
        "backtest",
        help="Measure frozen business-driver forecasts against later actual results.",
    )
    backtest.add_argument("--input", required=True, help="Canonical backtest observation CSV.")
    backtest.add_argument("--summary-output", help="Optional grouped accuracy CSV.")
    backtest.add_argument("--errors-output", help="Optional observation-level error CSV.")
    forecast = subcommands.add_parser("forecast", help="Run the linked synthetic/manual forecast engine.")
    forecast.add_argument("--initial", required=True)
    forecast.add_argument("--assumptions", required=True)
    forecast.add_argument("--valuation")
    forecast.add_argument("--business-drivers")
    forecast.add_argument("--business-kpi-history")
    forecast.add_argument("--output", help="Export Markdown, CSV tables, and PNG charts.")
    forecast.add_argument("--company-name", default="Manual Model")
    forecast.add_argument("--ticker", default="MANUAL")
    forecast.add_argument("--as-of")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the data-layer CLI."""

    configure_logging()
    args = build_parser().parse_args(argv)
    if args.command == "backtest":
        backtest_report = BacktestReport.from_csv(args.input)
        if args.summary_output:
            summary_path = Path(args.summary_output)
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            backtest_report.summary.to_csv(summary_path, index=False)
        if args.errors_output:
            errors_path = Path(args.errors_output)
            errors_path.parent.mkdir(parents=True, exist_ok=True)
            backtest_report.errors.to_csv(errors_path, index=False)
        summary_records = backtest_report.summary.astype(object).where(
            backtest_report.summary.notna(), None
        ).to_dict(orient="records")
        print(json.dumps({"summary": summary_records}, indent=2, allow_nan=False))
        return 0
    if args.command == "business-kpis":
        mapping = BusinessKpiMapping.from_yaml(args.mapping)
        source_identity: dict[str, object]
        if args.identifier:
            if not args.config:
                raise SystemExit("--config is required when --identifier is used.")
            config = load_config(args.config, live_sec=True)
            client = SecClient(config.sec)
            company = CompanyRegistry(client).get_company(args.identifier)
            submissions = client.submissions(company.cik)
            instance = FilingInstanceService(client).fetch_latest_10k(
                company.cik,
                submissions,
                accession_number=args.accession,
            )
            mapping = mapping.with_filing_source(
                source_url=instance.document_url,
                source_document=(
                    f"{company.name} {instance.filing.form} XBRL instance "
                    f"{instance.filing.accession_number}"
                ),
                filing_date=instance.filing.filing_date,
            )
            xml_source: str | Path = instance.content
            source_identity = {
                "ticker": company.ticker,
                "cik": company.cik,
                "accession_number": instance.filing.accession_number,
                "instance_url": instance.document_url,
            }
        else:
            xml_source = Path(args.instance)
            source_identity = {"instance_path": str(xml_source)}
        kpi_history = dimensional_facts_to_business_kpis(
            parse_dimensional_facts(xml_source), mapping
        )
        frame = kpi_history.to_frame()
        quality = kpi_history.quality_summary()
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(output_path, index=False)
        if args.quality_output:
            quality_path = Path(args.quality_output)
            quality_path.parent.mkdir(parents=True, exist_ok=True)
            quality_path.write_text(
                json.dumps(quality, indent=2, default=_json_default), encoding="utf-8"
            )
        print(
            json.dumps(
                {
                    "source": source_identity,
                    "quality": quality,
                    "records": frame.to_dict(orient="records"),
                },
                indent=2,
                default=_json_default,
            )
        )
        return 0
    if args.command == "forecast":
        initial_payload = yaml.safe_load(Path(args.initial).read_text(encoding="utf-8"))
        initial = InitialFinancialState(**initial_payload)
        forecast_assumptions = ForecastAssumptions.from_yaml(args.assumptions)
        operating_model = (
            load_business_driver_model(args.business_drivers) if args.business_drivers else None
        )
        forecast_result = ThreeStatementModel(operating_model).run(initial, forecast_assumptions)
        business_kpi_history = (
            BusinessKpiHistory.from_tabular(args.business_kpi_history).to_frame()
            if args.business_kpi_history
            else None
        )
        output = {
            "income_statement": forecast_result.income_statement.to_dict(),
            "balance_sheet": forecast_result.balance_sheet.to_dict(),
            "cash_flow_statement": forecast_result.cash_flow_statement.to_dict(),
            "working_capital": forecast_result.working_capital.to_dict(),
            "fixed_assets": forecast_result.fixed_assets.to_dict(),
            "debt_schedule": forecast_result.debt_schedule.to_dict(),
            "checks": [asdict(item) for item in forecast_result.checks],
        }
        if forecast_result.business_drivers is not None:
            output["business_drivers"] = forecast_result.business_drivers.to_dict()
        if business_kpi_history is not None:
            output["business_kpi_history"] = business_kpi_history.to_dict(orient="records")
        ratios = calculate_financial_ratios(forecast_result, initial)
        output["financial_ratios"] = ratios.table.astype(object).where(
            ratios.table.notna(), None
        ).to_dict()
        output["ratio_warnings"] = ratios.warnings
        if args.valuation:
            valuation_assumptions = ValuationAssumptions.from_yaml(args.valuation)
            dcf = value_dcf(forecast_result, valuation_assumptions)
            wacc_values = [dcf.wacc + offset for offset in (-0.02, -0.01, 0.0, 0.01, 0.02)]
            growth = valuation_assumptions.terminal_growth_rate
            growth_values = [growth + offset for offset in (-0.01, -0.005, 0.0, 0.005, 0.01)]
            sensitivity = wacc_terminal_growth_sensitivity(
                forecast_result, valuation_assumptions, wacc_values, growth_values
            )
            output["dcf"] = {
                "forecast": dcf.forecast.to_dict(orient="index"),
                "terminal_method": dcf.terminal_method,
                "cost_of_equity": dcf.cost_of_equity,
                "wacc": dcf.wacc,
                "terminal_value": dcf.terminal_value,
                "pv_terminal_value": dcf.pv_terminal_value,
                "pv_forecast_fcf": dcf.pv_forecast_fcf,
                "enterprise_value": dcf.enterprise_value,
                "equity_bridge": dcf.equity_bridge.to_dict(),
                "equity_value": dcf.equity_value,
                "implied_share_price": dcf.implied_share_price,
                "checks": [asdict(item) for item in dcf.checks],
            }
            output["sensitivity"] = sensitivity.astype(object).where(
                sensitivity.notna(), None
            ).to_dict()
            if args.output:
                export_directory = Path(args.output)
                result = ModelResult(
                    company_name=args.company_name,
                    ticker=args.ticker.upper(),
                    as_of=args.as_of or f"FY{initial.fiscal_year}",
                    forecast=forecast_result,
                    ratios=ratios,
                    dcf=dcf,
                    sensitivity=sensitivity,
                    assumption_summary=summarize_assumptions(forecast_assumptions),
                    limitations=(
                        "Forecast begins from a manually supplied opening state; SEC historical "
                        "provenance is not included in this report.",
                    ),
                    business_kpi_history=business_kpi_history,
                )
                report = result.export_markdown(export_directory / "report.md")
                workbook = result.export_excel(export_directory / "model.xlsx")
                tables = result.export_tables(export_directory / "tables")
                charts = result.export_charts(export_directory / "charts")
                output["exports"] = {
                    "markdown": str(report),
                    "excel": str(workbook),
                    "tables": {name: str(path) for name, path in tables.items()},
                    "charts": {name: str(path) for name, path in charts.items()},
                }
        elif args.output:
            raise ValueError("--output requires --valuation so the report includes DCF results.")
        print(json.dumps(output, indent=2, default=_json_default, allow_nan=False))
        return 0
    config = load_config(args.config, live_sec=True)
    client = SecClient(config.sec)
    registry = CompanyRegistry(client)
    company = registry.get_company(args.identifier)
    if args.command == "company":
        print(json.dumps(asdict(company), indent=2, default=_json_default))
        return 0
    payload = client.company_facts(company.cik)
    company_facts = CompanyFacts.from_sec_payload(payload)
    if args.command == "facts":
        observations = company_facts.annual_observations(
            args.concept,
            taxonomy=args.taxonomy,
            years=args.years,
        )
        print(json.dumps([asdict(item) for item in observations], indent=2, default=_json_default))
        return 0
    years = args.years or config.model.historical_years
    history = StatementBuilder(
        AccountMapper(AccountMap.from_yaml(args.mapping))
    ).build(company_facts, years=years)
    checks = HistoricalCheckSuite(
        absolute_tolerance=config.model.absolute_tolerance
    ).run(history)
    provenance = history.provenance_frame()
    output = {
        "company": asdict(company),
        "statements": {
            name: frame.astype(object).where(frame.notna(), None).to_dict()
            for name, frame in history.statements.items()
        },
        "provenance": provenance.astype(object).where(
            provenance.notna(), None
        ).to_dict(orient="records"),
        "quality_issues": history.quality_frame().to_dict(orient="records"),
        "checks": [asdict(item) for item in checks],
    }
    print(json.dumps(output, indent=2, default=_json_default, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
