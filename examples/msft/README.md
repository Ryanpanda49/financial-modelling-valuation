# MSFT example

```bash
python -m fmva.run \
  --history-json data/sample/msft_fy2021_2025_history.json \
  --forecast-assumptions examples/msft/forecast_assumptions.yaml \
  --valuation-assumptions examples/msft/valuation_assumptions.yaml \
  --output outputs/msft_offline
```

The fixture contains public SEC Company Facts. Forecast and valuation inputs are illustrative
compatibility assumptions, not company guidance, a target price, or investment advice. The output
bundle uses the project's common blue Excel and chart theme.

## Source-aware segment model

```bash
python -m fmva.run \
  --history-json data/sample/msft_fy2021_2025_history.json \
  --forecast-assumptions examples/msft/forecast_assumptions.yaml \
  --valuation-assumptions examples/msft/valuation_assumptions.yaml \
  --business-drivers examples/msft/business_drivers.yaml \
  --business-kpi-history data/sample/msft_business_kpis_fy2023_2025.csv \
  --output outputs/msft_segment
```

The historical KPI table preserves FY2025 10-K source URLs and restatement metadata for FY2023–
FY2025 segment revenue and cost of revenue. The segment forecast assumptions are illustrative.
