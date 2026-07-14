"""Operating working-capital schedule."""

from __future__ import annotations

from dataclasses import dataclass

from fmva.forecasting.assumptions import ForecastAssumptions


@dataclass(frozen=True, slots=True)
class WorkingCapitalSchedule:
    """One-period working-capital balances and cash investment."""

    accounts_receivable: float
    inventory: float
    accounts_payable: float
    other_current_assets: float
    accrued_liabilities: float
    net_working_capital: float
    change_in_net_working_capital: float
    dso: float
    dio: float
    dpo: float
    cash_conversion_cycle: float


def calculate_working_capital(
    revenue: float,
    cogs: float,
    prior_net_working_capital: float,
    year: int,
    assumptions: ForecastAssumptions,
) -> WorkingCapitalSchedule:
    """Calculate operating balances using a 365-day convention."""

    dso = assumptions.days_sales_outstanding[year]
    dio = assumptions.days_inventory_outstanding[year]
    dpo = assumptions.days_payables_outstanding[year]
    accounts_receivable = revenue * dso / 365.0
    inventory = cogs * dio / 365.0
    accounts_payable = cogs * dpo / 365.0
    other_current_assets = revenue * assumptions.other_current_assets_as_pct_revenue[year]
    accrued_liabilities = revenue * assumptions.accrued_liabilities_as_pct_revenue[year]
    net_working_capital = (
        accounts_receivable + inventory + other_current_assets - accounts_payable - accrued_liabilities
    )
    return WorkingCapitalSchedule(
        accounts_receivable=accounts_receivable,
        inventory=inventory,
        accounts_payable=accounts_payable,
        other_current_assets=other_current_assets,
        accrued_liabilities=accrued_liabilities,
        net_working_capital=net_working_capital,
        change_in_net_working_capital=net_working_capital - prior_net_working_capital,
        dso=dso,
        dio=dio,
        dpo=dpo,
        cash_conversion_cycle=dso + dio - dpo,
    )
