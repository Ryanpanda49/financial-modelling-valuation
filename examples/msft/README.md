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

With a private SEC configuration, the filing directory and instance can be discovered and cached
automatically:

```bash
python -m fmva.cli business-kpis \
  --identifier MSFT \
  --config config/model_config.yaml \
  --accession 0000950170-25-100235 \
  --mapping config/business_kpi_mapping.msft.yaml \
  --output outputs/msft_live_instance/msft_business_kpis.csv \
  --quality-output outputs/msft_live_instance/quality.json
```

The FY2025 live validation produced the same 18 segment revenue/COGS values as the reviewed sample.
See [the validation note](../../docs/msft_live_dimensional_xbrl_validation.md).

## Explainable model recommendation

The segment KPI file ranks `segment_revenue` as `READY`, while Top-down remains the baseline. The
recommender does not activate the model. Generate a draft only after explicitly confirming the
model type:

```bash
python -m fmva.cli recommend-business-model \
  --history-json data/sample/msft_fy2021_2025_history.json \
  --business-kpi-history data/sample/msft_business_kpis_fy2023_2025.csv

python -m fmva.cli draft-business-model \
  --history-json data/sample/msft_fy2021_2025_history.json \
  --business-kpi-history data/sample/msft_business_kpis_fy2023_2025.csv \
  --model-type segment_revenue \
  --forecast-years 2026 2027 2028 2029 2030 \
  --output outputs/msft_segment_draft.yaml
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
