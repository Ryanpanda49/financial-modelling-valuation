"""Unlevered free cash flow calculation."""

from __future__ import annotations

import pandas as pd


def calculate_unlevered_fcf(
    ebit: pd.Series,
    tax_rate: pd.Series,
    depreciation: pd.Series,
    capex: pd.Series,
    change_in_nwc: pd.Series,
) -> pd.Series:
    """Calculate UFCF = EBIT(1-tax) + D&A - CapEx - change in NWC."""

    aligned = pd.concat(
        [ebit, tax_rate, depreciation, capex, change_in_nwc],
        axis=1,
        keys=["ebit", "tax_rate", "depreciation", "capex", "change_in_nwc"],
    )
    if aligned.isna().any().any():
        missing = aligned.columns[aligned.isna().any()].tolist()
        raise ValueError(f"UFCF inputs contain missing values: {missing}")
    if ((aligned["tax_rate"] < 0) | (aligned["tax_rate"] > 1)).any():
        raise ValueError("UFCF tax rates must be between 0 and 1.")
    result = (
        aligned["ebit"] * (1.0 - aligned["tax_rate"])
        + aligned["depreciation"]
        - aligned["capex"]
        - aligned["change_in_nwc"]
    )
    result.name = "unlevered_fcf"
    return result
