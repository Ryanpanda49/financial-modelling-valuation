# COST example

Run the deterministic Costco example without SEC identity lookup, network access, or private
configuration:

```bash
python -m fmva.run \
  --history-json data/sample/cost_fy2021_2025_history.json \
  --forecast-assumptions examples/cost/forecast_assumptions.yaml \
  --valuation-assumptions examples/cost/valuation_assumptions.yaml \
  --output outputs/cost_offline
```

The pinned history contains public SEC Company Facts through FY2025. The command exports the
blue Excel workbook, Markdown report, CSV tables, and static blue charts. Forecast and valuation
inputs are illustrative compatibility assumptions, not company guidance or investment advice.

Refresh the SEC history and replace every market assumption with dated research support before
using the framework for current analysis.

## Manual Excel fallback

```bash
python -m fmva.run \
  --history-table data/sample/cost_manual_history_input.xlsx \
  --forecast-assumptions examples/cost/forecast_assumptions.yaml \
  --valuation-assumptions examples/cost/valuation_assumptions.yaml \
  --output outputs/cost_manual
```

## Base, upside, and downside cases

```bash
python -m fmva.run \
  --history-json data/sample/cost_fy2021_2025_history.json \
  --scenario-set examples/cost/scenario_set.yaml \
  --output outputs/cost_scenarios
```
