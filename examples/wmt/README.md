# WMT example

For the deterministic offline example, no SEC identity or network access is needed:

```bash
python -m fmva.run \
  --history-json data/sample/wmt_fy2022_2026_history.json \
  --forecast-assumptions examples/wmt/forecast_assumptions.yaml \
  --valuation-assumptions examples/wmt/valuation_assumptions.yaml \
  --output outputs/wmt_offline
```

The pinned history contains public SEC data through FY2026. Refresh it before using the model
for current research.

## Live SEC refresh

Copy the configuration to a private file and replace the SEC User-Agent placeholder before
live use. Confirm that forecast assumption years begin immediately after the latest WMT fiscal
year returned by SEC Company Facts, then run:

```bash
python -m fmva.run \
  --ticker WMT \
  --config examples/wmt/model_config.yaml \
  --forecast-assumptions examples/wmt/forecast_assumptions.yaml \
  --valuation-assumptions examples/wmt/valuation_assumptions.yaml \
  --output outputs/wmt
```

The command builds standardized historical statements with provenance, applies the opening-
state quality gate, runs the linked forecast and DCF, and exports the blue Excel workbook,
Markdown report, CSV tables, and PNG charts. The committed configuration retains a placeholder
on purpose and therefore cannot contact SEC until copied and edited privately.
