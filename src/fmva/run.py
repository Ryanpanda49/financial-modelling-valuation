"""End-to-end command for live SEC or pinned history, valuation, and exports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fmva.logging import configure_logging
from fmva.model import ValuationModel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ticker", help="Ticker for a live SEC workflow.")
    source.add_argument("--history-json", help="Versioned history snapshot for offline use.")
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
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the full live workflow and export the public result bundle."""

    configure_logging()
    args = build_parser().parse_args(argv)
    if args.history_json:
        model = ValuationModel.from_history_json(
            args.history_json,
            forecast_assumptions_path=args.forecast_assumptions,
            valuation_assumptions_path=args.valuation_assumptions,
        )
    else:
        if not args.config:
            raise SystemExit("--config is required when --ticker is used.")
        model = ValuationModel.from_sec(
            ticker=args.ticker,
            config_path=args.config,
            forecast_assumptions_path=args.forecast_assumptions,
            valuation_assumptions_path=args.valuation_assumptions,
            account_mapping_path=args.mapping,
        )
    result = model.run()
    output = Path(args.output)
    workbook = result.export_excel(output / f"{result.ticker.lower()}_model.xlsx")
    report = result.export_markdown(output / f"{result.ticker.lower()}_report.md")
    tables = result.export_tables(output / "tables")
    charts = result.export_charts(output / "charts")
    payload = {
        "ticker": result.ticker,
        "company": result.company_name,
        "excel": str(workbook),
        "markdown": str(report),
        "tables": {name: str(path) for name, path in tables.items()},
        "charts": {name: str(path) for name, path in charts.items()},
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
