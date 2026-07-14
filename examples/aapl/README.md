# AAPL compatibility example

This second-company example tests the generic SEC mapping against a technology company with
material R&D, short-term investments, debt, and share repurchases. It is a framework regression,
not Apple investment research.

```bash
python -m fmva.run \
  --history-json data/sample/aapl_fy2021_2025_history.json \
  --forecast-assumptions examples/aapl/forecast_assumptions.yaml \
  --valuation-assumptions examples/aapl/valuation_assumptions.yaml \
  --output outputs/aapl_offline
```

The D&A normalization is explicit: the top-down model uses a cash SG&A proxy so forecast D&A
from the fixed-asset schedule is subtracted exactly once. All assumptions and valuation inputs
are illustrative and researcher-editable.
