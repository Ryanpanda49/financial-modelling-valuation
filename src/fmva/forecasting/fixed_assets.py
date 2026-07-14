"""Aggregate CapEx and depreciation schedule."""

from __future__ import annotations

from dataclasses import dataclass

from fmva.forecasting.assumptions import ForecastAssumptions


@dataclass(frozen=True, slots=True)
class FixedAssetSchedule:
    """One-period PP&E roll-forward."""

    beginning_ppe: float
    capital_expenditures: float
    depreciation: float
    asset_disposals: float
    ending_ppe: float


def calculate_fixed_assets(
    beginning_ppe: float,
    revenue: float,
    year: int,
    assumptions: ForecastAssumptions,
) -> FixedAssetSchedule:
    """Calculate ending PP&E without an unexplained asset plug."""

    capital_expenditures = revenue * assumptions.capex_as_pct_revenue[year]
    depreciation = beginning_ppe * assumptions.depreciation_as_pct_beginning_ppe[year]
    disposals = assumptions.asset_disposals[year]
    ending_ppe = beginning_ppe + capital_expenditures - depreciation - disposals
    if ending_ppe < 0:
        raise ValueError(f"PP&E becomes negative in FY{year}.")
    return FixedAssetSchedule(
        beginning_ppe=beginning_ppe,
        capital_expenditures=capital_expenditures,
        depreciation=depreciation,
        asset_disposals=disposals,
        ending_ppe=ending_ppe,
    )
