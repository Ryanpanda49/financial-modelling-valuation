"""Valuation sensitivity tables that rerun full DCF mechanics."""

from __future__ import annotations

import pandas as pd

from fmva.forecasting.three_statement import ForecastResult
from fmva.valuation.dcf import TerminalMethod, value_dcf
from fmva.valuation.models import ValuationAssumptions


def wacc_terminal_growth_sensitivity(
    forecast: ForecastResult,
    assumptions: ValuationAssumptions,
    wacc_values: list[float],
    terminal_growth_values: list[float],
) -> pd.DataFrame:
    """Recalculate implied share price for every valid WACC/g pair."""

    table = pd.DataFrame(index=wacc_values, columns=terminal_growth_values, dtype=float)
    table.index.name = "wacc"
    table.columns.name = "terminal_growth_rate"
    for wacc in wacc_values:
        for growth in terminal_growth_values:
            if wacc <= growth:
                table.loc[wacc, growth] = float("nan")
                continue
            scenario = assumptions.with_rates(terminal_growth_rate=growth)
            table.loc[wacc, growth] = value_dcf(
                forecast,
                scenario,
                terminal_method=TerminalMethod.PERPETUITY_GROWTH,
                wacc_override=wacc,
            ).implied_share_price
    return table
