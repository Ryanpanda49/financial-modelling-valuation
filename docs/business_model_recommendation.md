# Business Model Recommendation and Draft Initialization

## Control principle

The framework may rank model archetypes and prepare assumption drafts, but it does not select or
activate a company model automatically. The output policy is always
`researcher_confirmation_required`. A researcher must explicitly choose `--model-type`, review the
sources and gaps, edit assumptions, and decide whether the model is suitable for valuation.

## Candidate models

The recommender evaluates Top-down, Segment Revenue, Store/Membership, and Subscriber/ARPU. Each
candidate returns a bounded data-readiness score, readiness (`BASELINE`, `READY`, `PARTIAL`, or
`INSUFFICIENT`), supporting evidence, data gaps, and a mandatory confirmation flag. Scores measure
data readiness, not expected investment returns or forecast accuracy.

```bash
python -m fmva.cli recommend-business-model \
  --history-json data/sample/msft_fy2021_2025_history.json \
  --business-kpi-history data/sample/msft_business_kpis_fy2023_2025.csv \
  --output outputs/msft_model_candidates.csv
```

For the committed MSFT dataset, the segment model is `READY` with a score of 1.0 because three
segments, three historical years, segment COGS, and an exact consolidated revenue reconciliation
are available. Top-down remains the 0.7 baseline. Subscriber/ARPU is not recommended from this KPI
file because it contains no subscriber or attributable product-revenue history.

## Draft generation

After explicit model selection, the initializer can generate a loadable YAML draft:

```bash
python -m fmva.cli draft-business-model \
  --history-json data/sample/msft_fy2021_2025_history.json \
  --business-kpi-history data/sample/msft_business_kpis_fy2023_2025.csv \
  --model-type segment_revenue \
  --forecast-years 2026 2027 2028 2029 2030 \
  --output outputs/msft_segment_draft.yaml
```

Every draft includes `RESEARCHER_REVIEW_REQUIRED` status, the opening fiscal year, historical
run-rate basis, explicit fallback warnings, reconciled opening values where applicable, and
centralized forecast-year assumptions accepted by existing model loaders.

### Segment draft

Opening revenue uses latest reported segments. Growth uses historical segment CAGR. Cost ratios use
latest segment COGS; missing segment cost falls back to the consolidated ratio with a warning.

### Subscriber/ARPU draft

Opening users come from KPI history. ARPU is direct or derived from attributable subscription
revenue divided by users. Unattributed revenue is disclosed as `all_other_revenue`. Product cost
falls back to consolidated COGS ratio with a warning until better data is supplied.

### Store/membership draft

Opening stores, members, and fee economics come from KPI history. New stores use historical average
net additions. Missing comparable sales, renewal, mix, or productivity creates explicit warnings
and review placeholders.

## Limitations

- A high readiness score is not a prediction-accuracy score.
- Historical CAGR is a neutral starting point, not company guidance.
- KPI definitions and restatements require review.
- Top-down uses the central forecast-assumptions file and has no separate Business Driver draft.
- Drafts require research rationale before use in a published valuation.
