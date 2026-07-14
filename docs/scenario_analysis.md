# Scenario Analysis

Scenario sets combine named forecast and valuation YAML files without embedding assumptions in
code. The historical dataset is loaded once, then reused for every case.

```yaml
name: "Illustrative operating cases"
scenarios:
  - name: "Base"
    forecast_assumptions: forecast_assumptions.yaml
    valuation_assumptions: valuation_assumptions.yaml
  - name: "Downside"
    forecast_assumptions: forecast_assumptions.downside.yaml
    valuation_assumptions: valuation_assumptions.yaml
```

Paths resolve relative to the scenario-set file. Names must produce unique filesystem-safe slugs.
Each scenario receives an independent output directory containing its Excel workbook, Markdown
report, tables, and charts.

```bash
python -m fmva.run \
  --history-json data/sample/cost_fy2021_2025_history.json \
  --scenario-set examples/cost/scenario_set.yaml \
  --output outputs/cost_scenarios
```

The committed COST base/upside/downside cases alter operating assumptions while holding the
illustrative valuation assumption file constant, isolating operating-case effects. They are not
probability-weighted outcomes or investment recommendations.
