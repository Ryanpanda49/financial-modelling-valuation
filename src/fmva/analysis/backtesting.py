"""Out-of-sample forecast accuracy metrics for business-driver model evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from fmva.exceptions import HistoricalDataError

REQUIRED_BACKTEST_COLUMNS = (
    "model",
    "metric",
    "origin_year",
    "target_year",
    "actual",
    "predicted",
)
OPTIONAL_BACKTEST_COLUMNS = ("baseline_predicted", "prior_actual")


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """Validated observation-level errors and grouped accuracy statistics."""

    observations: pd.DataFrame
    errors: pd.DataFrame
    summary: pd.DataFrame

    @classmethod
    def from_csv(cls, path: str | Path) -> BacktestReport:
        source = Path(path)
        try:
            frame = pd.read_csv(source)
        except (OSError, pd.errors.ParserError) as exc:
            raise HistoricalDataError(f"Unable to read backtest input: {source}") from exc
        return cls.from_frame(frame)

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> BacktestReport:
        """Validate frozen forecasts and calculate model/horizon accuracy metrics."""

        observations = _validate_observations(frame)
        errors = _calculate_errors(observations)
        grouped = errors.groupby(["model", "metric", "horizon_years"], sort=True)
        summary = grouped.apply(_summarize_group).reset_index()
        return cls(observations=observations, errors=errors, summary=summary)

    def overall_summary(self) -> pd.DataFrame:
        """Aggregate across horizons while retaining model and metric identity."""

        grouped = self.errors.groupby(["model", "metric"], sort=True)
        return grouped.apply(_summarize_group).reset_index()


def _validate_observations(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_BACKTEST_COLUMNS if column not in frame.columns]
    if missing:
        raise HistoricalDataError(f"Backtest input is missing columns: {missing}")
    columns = [*REQUIRED_BACKTEST_COLUMNS]
    columns.extend(column for column in OPTIONAL_BACKTEST_COLUMNS if column in frame.columns)
    selected = frame.loc[:, columns].copy()
    for column in OPTIONAL_BACKTEST_COLUMNS:
        if column not in frame.columns:
            selected[column] = math.nan
    selected["model"] = selected["model"].astype(str).str.strip()
    selected["metric"] = selected["metric"].astype(str).str.strip()
    if selected["model"].eq("").any() or selected["metric"].eq("").any():
        raise HistoricalDataError("Backtest model and metric names cannot be empty.")
    for column in ("origin_year", "target_year"):
        selected[column] = pd.to_numeric(selected[column], errors="raise").astype(int)
    for column in ("actual", "predicted", *OPTIONAL_BACKTEST_COLUMNS):
        selected[column] = pd.to_numeric(selected[column], errors="coerce")
    if selected[["actual", "predicted"]].isna().any(axis=None):
        raise HistoricalDataError("Backtest actual and predicted values must be numeric and present.")
    finite = selected[["actual", "predicted"]].apply(
        lambda column: column.map(math.isfinite)
    )
    if not finite.all(axis=None):
        raise HistoricalDataError("Backtest actual and predicted values must be finite.")
    if (selected["target_year"] <= selected["origin_year"]).any():
        raise HistoricalDataError("Backtest target_year must be later than origin_year.")
    keys = ["model", "metric", "origin_year", "target_year"]
    if selected.duplicated(keys).any():
        raise HistoricalDataError("Backtest input contains duplicate model-metric-origin-target keys.")
    return selected.sort_values(keys).reset_index(drop=True)


def _calculate_errors(observations: pd.DataFrame) -> pd.DataFrame:
    errors = observations.copy()
    errors["horizon_years"] = errors["target_year"] - errors["origin_year"]
    errors["error"] = errors["predicted"] - errors["actual"]
    errors["absolute_error"] = errors["error"].abs()
    actual_abs = errors["actual"].abs()
    errors["absolute_percentage_error"] = errors["absolute_error"].div(
        actual_abs.where(actual_abs.ne(0))
    )
    smape_denominator = errors["predicted"].abs() + actual_abs
    errors["symmetric_absolute_percentage_error"] = (
        2.0 * errors["absolute_error"] / smape_denominator.where(smape_denominator.ne(0))
    )
    errors["baseline_absolute_error"] = (
        errors["baseline_predicted"] - errors["actual"]
    ).abs()
    errors["beats_baseline"] = errors["absolute_error"] < errors["baseline_absolute_error"]
    actual_direction = (errors["actual"] - errors["prior_actual"]).apply(_direction)
    predicted_direction = (errors["predicted"] - errors["prior_actual"]).apply(_direction)
    errors["direction_correct"] = actual_direction.eq(predicted_direction).where(
        errors["prior_actual"].notna()
    )
    return errors


def _summarize_group(group: pd.DataFrame) -> pd.Series:
    actual_abs_sum = float(group["actual"].abs().sum())
    absolute_error_sum = float(group["absolute_error"].sum())
    baseline_available = group["baseline_predicted"].notna()
    baseline_group = group.loc[baseline_available]
    baseline_denominator = float(baseline_group["actual"].abs().sum())
    baseline_wape = (
        float(baseline_group["baseline_absolute_error"].sum()) / baseline_denominator
        if baseline_denominator
        else math.nan
    )
    wape = absolute_error_sum / actual_abs_sum if actual_abs_sum else math.nan
    relative_improvement = (
        (baseline_wape - wape) / baseline_wape
        if math.isfinite(baseline_wape) and baseline_wape != 0 and math.isfinite(wape)
        else math.nan
    )
    direction = group["direction_correct"].dropna()
    return pd.Series(
        {
            "observations": int(len(group)),
            "mae": float(group["absolute_error"].mean()),
            "rmse": math.sqrt(float((group["error"] ** 2).mean())),
            "mape": float(group["absolute_percentage_error"].mean()),
            "smape": float(group["symmetric_absolute_percentage_error"].mean()),
            "wape": wape,
            "normalized_bias": (
                float(group["error"].sum()) / actual_abs_sum if actual_abs_sum else math.nan
            ),
            "direction_accuracy": float(direction.mean()) if not direction.empty else math.nan,
            "baseline_wape": baseline_wape,
            "relative_wape_improvement": relative_improvement,
            "baseline_win_rate": (
                float(group.loc[baseline_available, "beats_baseline"].mean())
                if baseline_available.any()
                else math.nan
            ),
        }
    )


def _direction(value: float) -> int | None:
    if pd.isna(value):
        return None
    return 1 if value > 0 else -1 if value < 0 else 0
