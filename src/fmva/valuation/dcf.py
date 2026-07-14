"""DCF forecast table, terminal value, and equity bridge."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from fmva.checks.models import CheckResult
from fmva.forecasting.three_statement import ForecastResult
from fmva.valuation.checks import ValuationCheckSuite
from fmva.valuation.free_cash_flow import calculate_unlevered_fcf
from fmva.valuation.models import ValuationAssumptions
from fmva.valuation.terminal_value import (
    exit_multiple_terminal_value,
    perpetuity_growth_terminal_value,
)
from fmva.valuation.wacc import calculate_wacc, cost_of_equity


class TerminalMethod(StrEnum):
    """Supported terminal value methods."""

    PERPETUITY_GROWTH = "perpetuity_growth"
    EXIT_MULTIPLE = "exit_multiple"


@dataclass(frozen=True, slots=True)
class DcfResult:
    """Complete DCF calculation and equity bridge."""

    forecast: pd.DataFrame
    terminal_method: TerminalMethod
    cost_of_equity: float
    wacc: float
    terminal_value: float
    pv_terminal_value: float
    pv_forecast_fcf: float
    enterprise_value: float
    equity_bridge: pd.Series
    equity_value: float
    implied_share_price: float
    checks: tuple[CheckResult, ...]


def value_dcf(
    forecast: ForecastResult,
    assumptions: ValuationAssumptions,
    *,
    terminal_method: TerminalMethod | str = TerminalMethod.PERPETUITY_GROWTH,
    wacc_override: float | None = None,
) -> DcfResult:
    """Value a forecast using end-of-year discounting."""

    assumptions.validate()
    method = TerminalMethod(terminal_method)
    years = list(forecast.income_statement.columns)
    if not years:
        raise ValueError("DCF requires at least one forecast period.")
    tax_rates = forecast.income_statement.loc["income_tax"] / forecast.income_statement.loc[
        "income_before_tax"
    ].replace(0.0, float("nan"))
    tax_rates = tax_rates.fillna(0.0).clip(lower=0.0, upper=1.0)
    ufcf = calculate_unlevered_fcf(
        forecast.income_statement.loc["operating_income"],
        tax_rates,
        forecast.income_statement.loc["depreciation_and_amortization"],
        forecast.fixed_assets.loc["capital_expenditures"],
        forecast.working_capital.loc["change_in_net_working_capital"],
    )
    normalized_tax_rate = float(tax_rates.iloc[-1])
    wacc = calculate_wacc(assumptions, normalized_tax_rate) if wacc_override is None else wacc_override
    if wacc <= 0:
        raise ValueError("WACC must be positive.")
    periods = pd.Series(range(1, len(years) + 1), index=years, dtype=float)
    discount_factor = 1.0 / (1.0 + wacc) ** periods
    pv_fcf = ufcf * discount_factor
    if method is TerminalMethod.PERPETUITY_GROWTH:
        terminal_value = perpetuity_growth_terminal_value(
            float(ufcf.iloc[-1]), wacc, assumptions.terminal_growth_rate
        )
    else:
        terminal_value = exit_multiple_terminal_value(
            float(forecast.income_statement.loc["ebitda"].iloc[-1]),
            assumptions.exit_multiple,
        )
    pv_terminal_value = terminal_value * float(discount_factor.iloc[-1])
    pv_forecast_fcf = float(pv_fcf.sum())
    enterprise_value = pv_forecast_fcf + pv_terminal_value
    bridge = pd.Series(
        {
            "enterprise_value": enterprise_value,
            "less_debt": -assumptions.debt,
            "less_preferred_stock": -assumptions.preferred_stock,
            "less_minority_interest": -assumptions.minority_interest,
            "add_cash": assumptions.cash,
            "add_non_operating_investments": assumptions.non_operating_investments,
        },
        name="equity_bridge",
    )
    equity_value = float(bridge.sum())
    implied_share_price = equity_value / assumptions.diluted_shares
    table = pd.DataFrame(
        {
            "ebit": forecast.income_statement.loc["operating_income"],
            "tax_rate": tax_rates,
            "nopat": forecast.income_statement.loc["operating_income"] * (1.0 - tax_rates),
            "depreciation_and_amortization": forecast.income_statement.loc[
                "depreciation_and_amortization"
            ],
            "capital_expenditures": forecast.fixed_assets.loc["capital_expenditures"],
            "change_in_net_working_capital": forecast.working_capital.loc[
                "change_in_net_working_capital"
            ],
            "unlevered_fcf": ufcf,
            "discount_period": periods,
            "discount_factor": discount_factor,
            "pv_fcf": pv_fcf,
        }
    )
    table.index.name = "fiscal_year"
    result = DcfResult(
        forecast=table,
        terminal_method=method,
        cost_of_equity=cost_of_equity(assumptions),
        wacc=wacc,
        terminal_value=terminal_value,
        pv_terminal_value=pv_terminal_value,
        pv_forecast_fcf=pv_forecast_fcf,
        enterprise_value=enterprise_value,
        equity_bridge=bridge,
        equity_value=equity_value,
        implied_share_price=implied_share_price,
        checks=(),
    )
    return DcfResult(
        forecast=result.forecast,
        terminal_method=result.terminal_method,
        cost_of_equity=result.cost_of_equity,
        wacc=result.wacc,
        terminal_value=result.terminal_value,
        pv_terminal_value=result.pv_terminal_value,
        pv_forecast_fcf=result.pv_forecast_fcf,
        enterprise_value=result.enterprise_value,
        equity_bridge=result.equity_bridge,
        equity_value=result.equity_value,
        implied_share_price=result.implied_share_price,
        checks=ValuationCheckSuite().run(result, assumptions),
    )
