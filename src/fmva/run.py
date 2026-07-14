"""End-to-end command for live SEC or pinned history, valuation, and exports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fmva.logging import configure_logging
from fmva.model import ValuationModel
from fmva.output import ModelResult
from fmva.scenarios import ScenarioSet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ticker", help="Ticker for a live SEC workflow.")
    source.add_argument("--history-json", help="Versioned history snapshot for offline use.")
    source.add_argument(
        "--history-table",
        help="Canonical manual history in CSV, XLSX, or XLSM format.",
    )
    parser.add_argument("--config", help="Private SEC config; required with --ticker.")
    parser.add_argument(
        "--forecast-assumptions",
        default="config/forecast_assumptions.example.yaml",
    )
    parser.add_argument(
        "--valuation-assumptions",
        default="config/valuation_assumptions.example.yaml",
    )
    parser.add_argument("--mapping", default="config/account_mapping.yaml")
    parser.add_argument(
        "--scenario-set",
        help="YAML file containing one or more named forecast/valuation cases.",
    )
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the full live workflow and export the public result bundle."""

    configure_logging()
    args = build_parser().parse_args(argv)
    if args.scenario_set:
        scenario_set = ScenarioSet.from_yaml(args.scenario_set)
        first = scenario_set.scenarios[0]
        base_model = _build_model(
            args,
            first.forecast_assumptions_path,
            first.valuation_assumptions_path,
        )
        payloads: dict[str, object] = {}
        for position, scenario in enumerate(scenario_set.scenarios):
            model = (
                base_model
                if position == 0
                else ValuationModel.from_history(
                    company=base_model.company,
                    history=base_model.history,
                    forecast_assumptions_path=scenario.forecast_assumptions_path,
                    valuation_assumptions_path=scenario.valuation_assumptions_path,
                )
            )
            payloads[scenario.slug] = _export_result(
                model.run(),
                Path(args.output) / scenario.slug,
            )
        print(json.dumps({"scenario_set": scenario_set.name, "scenarios": payloads}, indent=2))
        return 0

    model = _build_model(args, args.forecast_assumptions, args.valuation_assumptions)
    payload = _export_result(model.run(), Path(args.output))
    print(json.dumps(payload, indent=2))
    return 0


def _build_model(
    args: argparse.Namespace,
    forecast_assumptions_path: str | Path,
    valuation_assumptions_path: str | Path,
) -> ValuationModel:
    if args.history_json:
        model = ValuationModel.from_history_json(
            args.history_json,
            forecast_assumptions_path=forecast_assumptions_path,
            valuation_assumptions_path=valuation_assumptions_path,
        )
    elif args.history_table:
        model = ValuationModel.from_tabular_history(
            args.history_table,
            forecast_assumptions_path=forecast_assumptions_path,
            valuation_assumptions_path=valuation_assumptions_path,
            account_mapping_path=args.mapping,
        )
    else:
        if not args.config:
            raise SystemExit("--config is required when --ticker is used.")
        model = ValuationModel.from_sec(
            ticker=args.ticker,
            config_path=args.config,
            forecast_assumptions_path=forecast_assumptions_path,
            valuation_assumptions_path=valuation_assumptions_path,
            account_mapping_path=args.mapping,
        )
    return model


def _export_result(result: ModelResult, output: Path) -> dict[str, object]:
    workbook = result.export_excel(output / f"{result.ticker.lower()}_model.xlsx")
    report = result.export_markdown(output / f"{result.ticker.lower()}_report.md")
    tables = result.export_tables(output / "tables")
    charts = result.export_charts(output / "charts")
    return {
        "ticker": result.ticker,
        "company": result.company_name,
        "excel": str(workbook),
        "markdown": str(report),
        "tables": {name: str(path) for name, path in tables.items()},
        "charts": {name: str(path) for name, path in charts.items()},
    }


if __name__ == "__main__":
    raise SystemExit(main())
