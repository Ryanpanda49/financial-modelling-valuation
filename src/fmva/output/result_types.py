"""Internal data contract shared by output modules."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from fmva.analysis.ratios import RatioResult
from fmva.checks.models import CheckResult
from fmva.data.statement_builder import HistoricalStatements
from fmva.forecasting.three_statement import ForecastResult
from fmva.valuation.dcf import DcfResult


@dataclass(frozen=True, slots=True)
class ModelResultData:
    company_name: str
    ticker: str
    as_of: str
    forecast: ForecastResult
    ratios: RatioResult
    dcf: DcfResult
    sensitivity: pd.DataFrame
    assumption_summary: list[dict[str, object]]
    limitations: tuple[str, ...]
    historical: HistoricalStatements | None = None
    historical_ratios: RatioResult | None = None
    historical_checks: tuple[CheckResult, ...] = ()
    opening_state_warnings: tuple[str, ...] = ()
    business_kpi_history: pd.DataFrame | None = None
