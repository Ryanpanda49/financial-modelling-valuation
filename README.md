# Financial Modelling & Valuation Framework

[![CI](https://github.com/Ryanpanda49/financial-modelling-valuation/actions/workflows/ci.yml/badge.svg)](https://github.com/Ryanpanda49/financial-modelling-valuation/actions/workflows/ci.yml)

An open-source, modular and explainable financial modelling and valuation framework for
U.S. public companies. The project retrieves standardized financial data from SEC EDGAR,
builds linked financial forecasts, performs financial analysis and DCF valuation, and
exports reproducible model outputs.

The framework is research-oriented and semi-automated. Data retrieval and calculations are
automated; forecast assumptions and company-specific operating judgments remain explicit
researcher inputs.

> This project is for educational and research purposes only and does not constitute
> investment advice.

## Current status

The repository foundation, SEC data layer, standardized history foundation, linked forecast
engine, financial ratios, DCF, sensitivity analysis, Excel workbooks, Markdown reports,
structured CSV tables, and static charts are implemented. Live WMT SEC mapping and a complete
FY2022–FY2026 historical-to-FY2031 forecast run have been validated, including historical
ratios and historical-to-forecast trend charts. A sanitized public WMT history snapshot and
an AAPL technology-company snapshot and a COST membership-retail snapshot provide deterministic
offline regression coverage. Valuation inputs support dated field-level source metadata;
committed examples remain explicitly illustrative.

Implemented:

- Typed configuration with SEC User-Agent validation.
- Ticker/CIK company lookup from the SEC ticker registry.
- SEC JSON client with local cache, conservative rate limiting, timeout, and retry/backoff.
- Company Facts parsing and annual 10-K fact selection.
- Explicit fiscal-period classification and restatement preference.
- Complete MVP canonical account dictionary with deterministic XBRL fallback priorities.
- USD-million/share-million normalization and documented sign conventions.
- Standardized historical statement tables with field-level provenance and quality issues.
- Auditable historical-to-opening-state adapter with explicit residuals and missing-account warnings.
- Historical balance-sheet and cash roll-forward checks.
- Five-year linked income statement, balance sheet, and cash flow forecast.
- Working-capital, PP&E, debt/cash/interest, and retained-earnings schedules.
- Growth, profitability, liquidity, leverage, efficiency, and cash-flow ratios.
- UFCF, WACC, both terminal-value methods, equity bridge, implied price, and sensitivity.
- Unified `ModelResult` with Markdown, CSV-table, and six static PNG chart exporters.
- Fourteen-sheet, blue-themed Excel workbook with formula-driven sensitivity and model checks.
- Public `ValuationModel.from_sec(...)` orchestration API and `python -m fmva.run` command.
- Live WMT mapping validation with all historical, forecast, and DCF checks passing.
- Live AAPL compatibility validation with all historical, forecast, and DCF checks passing.
- Live COST compatibility validation with all historical, forecast, and DCF checks passing.
- Historical and forecast ratios displayed together with continuous blue trend charts.
- Offline unit and integration tests.
- Versioned public WMT history fixture with no request headers or personal contact data.
- Versioned public AAPL fixture proving the mapping is not retailer-specific.
- Versioned public COST fixture covering a non-calendar fiscal year and membership retailer.
- Python 3.11/3.12 GitHub Actions regression workflow and public-release privacy audit.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Configure SEC access

Copy the example configuration and replace the placeholder with a real name and monitored
email address before making live SEC requests:

```bash
cp config/model_config.example.yaml config/model_config.yaml
```

SEC requests deliberately fail fast while the placeholder User-Agent remains configured.

## Reproduce the WMT example offline

The complete WMT workflow can run without SEC access or private configuration by using the
pinned public filing snapshot:

```bash
python -m fmva.run \
  --history-json data/sample/wmt_fy2022_2026_history.json \
  --forecast-assumptions examples/wmt/forecast_assumptions.yaml \
  --valuation-assumptions examples/wmt/valuation_assumptions.yaml \
  --output outputs/wmt_offline
```

This path is intended for reproducibility and CI. Refresh SEC data before current research.

The parallel AAPL compatibility run is documented in
[the AAPL example](examples/aapl/README.md) and
[validation note](docs/aapl_compatibility_validation.md).
The third COST regression case is documented in
[the COST example](examples/cost/README.md) and
[validation note](docs/cost_compatibility_validation.md).

## CLI data-layer example

```bash
python -m fmva.cli company WMT --config config/model_config.yaml
python -m fmva.cli facts WMT --concept Revenues --config config/model_config.yaml
python -m fmva.cli history WMT --years 5 --config config/model_config.yaml
```

The linked forecast engine can be audited without network access:

```bash
python -m fmva.cli forecast \
  --initial config/initial_state.example.yaml \
  --assumptions config/forecast_assumptions.example.yaml \
  --valuation config/valuation_assumptions.example.yaml \
  --output outputs/example \
  --company-name "Example Company" \
  --ticker EXM \
  --as-of 2024-12-31
```

This writes `model.xlsx`, `report.md`, nine audit-friendly CSV tables, and six non-interactive
PNG charts. The workbook contract is documented in [Excel export design](docs/excel_export_design.md)
and the common palette in [Output style guide](docs/output_style_guide.md). The public exporter
uses `openpyxl` and does not require desktop Excel, internal spreadsheet tooling, or a paid component.

The final target API remains:

```python
from fmva import ValuationModel

model = ValuationModel.from_sec(
    ticker="WMT",
    config_path="config/model_config.yaml",
)
result = model.run()
result.export_excel("outputs/wmt_model.xlsx")
result.export_markdown("outputs/wmt_report.md")
```

The same workflow is available from the command line:

```bash
python -m fmva.run \
  --ticker WMT \
  --config config/model_config.yaml \
  --forecast-assumptions config/forecast_assumptions.example.yaml \
  --valuation-assumptions config/valuation_assumptions.example.yaml \
  --output outputs/wmt
```

Forecast years must begin immediately after the latest standardized historical fiscal year.
Copy and update the example assumption files before a live run; the example years are not
automatically shifted because assumptions must remain explicit research inputs.

## Tests

```bash
pytest
```

Tests use synthetic fixtures plus sanitized public WMT, AAPL, and COST snapshots; they do not
require network access or contact details. Live SEC refresh remains an explicit researcher-run
validation.

## Documentation

- [Reference model analysis](docs/reference_model_analysis.md)
- [Architecture](docs/architecture.md)
- [Data model](docs/data_model.md)
- [MVP scope](docs/mvp_scope.md)
- [Excel export design](docs/excel_export_design.md)
- [Output style guide](docs/output_style_guide.md)
- [WMT live SEC validation](docs/wmt_live_validation.md)
- [AAPL compatibility validation](docs/aapl_compatibility_validation.md)
- [COST compatibility validation](docs/cost_compatibility_validation.md)

## Data and privacy

The internal reference Excel and textbook PDF are excluded from Git. Runtime SEC caches,
private model configurations, and generated company outputs are also ignored by default.
Run `python scripts/public_release_check.py` before publishing or opening a pull request.
