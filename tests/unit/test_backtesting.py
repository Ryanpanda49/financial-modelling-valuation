import pandas as pd
import pytest

from fmva.analysis.backtesting import BacktestReport
from fmva.exceptions import HistoricalDataError


def observations() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "model": "segment_revenue",
                "metric": "revenue",
                "origin_year": 2021,
                "target_year": 2022,
                "actual": 110.0,
                "predicted": 108.0,
                "baseline_predicted": 100.0,
                "prior_actual": 100.0,
            },
            {
                "model": "segment_revenue",
                "metric": "revenue",
                "origin_year": 2022,
                "target_year": 2023,
                "actual": 120.0,
                "predicted": 126.0,
                "baseline_predicted": 100.0,
                "prior_actual": 110.0,
            },
        ]
    )


def test_backtest_calculates_wape_direction_and_baseline_improvement() -> None:
    report = BacktestReport.from_frame(observations())
    summary = report.summary.iloc[0]

    assert summary["observations"] == 2
    assert summary["mae"] == pytest.approx(4.0)
    assert summary["wape"] == pytest.approx(8.0 / 230.0)
    assert summary["baseline_wape"] == pytest.approx(30.0 / 230.0)
    assert summary["relative_wape_improvement"] == pytest.approx(1.0 - 8.0 / 30.0)
    assert summary["baseline_win_rate"] == pytest.approx(1.0)
    assert summary["direction_accuracy"] == pytest.approx(1.0)


def test_backtest_rejects_duplicates_and_non_out_of_sample_periods() -> None:
    duplicate = pd.concat([observations(), observations().iloc[[0]]], ignore_index=True)
    with pytest.raises(HistoricalDataError, match="duplicate"):
        BacktestReport.from_frame(duplicate)

    invalid = observations()
    invalid.loc[0, "target_year"] = invalid.loc[0, "origin_year"]
    with pytest.raises(HistoricalDataError, match="later"):
        BacktestReport.from_frame(invalid)
