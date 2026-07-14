# KO example

```bash
python -m fmva.run \
  --history-json data/sample/ko_fy2021_2025_history.json \
  --forecast-assumptions examples/ko/forecast_assumptions.yaml \
  --valuation-assumptions examples/ko/valuation_assumptions.yaml \
  --output outputs/ko_offline
```

The fixture contains public SEC Company Facts. Forecast and valuation inputs are illustrative
compatibility assumptions, not company guidance, a target price, or investment advice. The output
bundle uses the project's common blue Excel and chart theme.
