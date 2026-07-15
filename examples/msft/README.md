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

The same canonical KPI table can be regenerated from the minimal dimensional-XBRL regression
fixture:

```bash
python -m fmva.cli business-kpis \
  --instance tests/fixtures/msft_segment_instance_sample.xml \
  --mapping config/business_kpi_mapping.msft.yaml \
  --output outputs/msft_segment_kpis.csv
```

## Subscriber/ARPU archetype

```bash
python -m fmva.run \
  --history-json data/sample/msft_fy2021_2025_history.json \
  --forecast-assumptions examples/msft/forecast_assumptions.yaml \
  --valuation-assumptions examples/msft/valuation_assumptions.yaml \
  --business-drivers examples/msft/subscriber_business_drivers.yaml \
  --output outputs/msft_subscriber
```

This deliberately hybrid example uses a disclosed subscriber KPI but researcher-authored opening
ARPU. All revenue not supported by that KPI is shown as `all_other_revenue`; it is not silently
forced into the subscription formula.
