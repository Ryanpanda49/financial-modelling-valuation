# Business Driver Backtesting

## Purpose

Passing three-statement and DCF checks proves calculation integrity, not forecast accuracy. The
backtesting layer evaluates forecasts that were frozen at an historical information date and later
compares them with reported actual results. It must not reconstruct old forecasts using information
published after the origin date.

## Observation contract

The `fmva backtest` command accepts a long-form CSV with one row per model, metric, origin, and
target period:

| Field | Requirement |
|---|---|
| `model` / `metric` | Non-empty model and forecast measure identifiers. |
| `origin_year` | Fiscal year whose then-available information was used. |
| `target_year` | Forecast fiscal year; must be later than the origin. |
| `actual` / `predicted` | Finite reported actual and frozen model forecast. |
| `baseline_predicted` | Optional simple Top-down or naive forecast for comparison. |
| `prior_actual` | Optional prior reported value for direction-accuracy measurement. |

Duplicate model-metric-origin-target keys fail. Missing optional values remain unavailable rather
than being silently replaced.

```bash
python -m fmva.cli backtest \
  --input research/frozen_forecasts.csv \
  --summary-output outputs/backtest_summary.csv \
  --errors-output outputs/backtest_errors.csv
```

## Metrics

- MAE and RMSE measure absolute forecast error in the metric's native unit.
- MAPE excludes zero actual denominators.
- sMAPE uses the absolute actual plus absolute forecast denominator.
- WAPE equals total absolute error divided by total absolute actual value.
- Normalized bias reveals systematic over- or under-forecasting.
- Direction accuracy compares actual and predicted direction versus `prior_actual`.
- Baseline WAPE, win rate, and relative WAPE improvement test whether added Bottom-up complexity
  beats a simpler forecast.

Metrics are grouped by model, metric, and forecast horizon. A small sample is not evidence of stable
predictive accuracy; results should disclose observation counts and company coverage.

## Required research protocol

1. Freeze every assumption set with an as-of date and source record.
2. Use only information public at the origin date.
3. Preserve historical segment definitions as known at that date; separately test later recasts.
4. Compare every Bottom-up model with the same Top-down baseline.
5. Report one-, two-, and three-year horizons separately.
6. Do not tune assumptions on the same observations used for final evaluation.

The committed CSV under `tests/fixtures/` is synthetic and only proves metric calculation. It is not
a claim about the accuracy of any company model.
