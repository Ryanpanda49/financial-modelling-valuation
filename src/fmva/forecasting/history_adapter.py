"""Convert standardized annual history into an auditable forecast opening state."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from fmva.data.statement_builder import HistoricalStatements
from fmva.exceptions import HistoricalDataError
from fmva.forecasting.three_statement import InitialFinancialState


@dataclass(frozen=True, slots=True)
class OpeningStateResult:
    """Opening state plus explicit derivations and missing-account warnings."""

    state: InitialFinancialState
    fiscal_year: int
    source_values: dict[str, float]
    warnings: tuple[str, ...]


def historical_to_initial_state(
    history: HistoricalStatements,
    *,
    fiscal_year: int | None = None,
    tolerance: float = 1e-6,
) -> OpeningStateResult:
    """Build a balanced opening state from the latest usable annual statements.

    Total assets, liabilities, and equity are mandatory. Optional detailed accounts may
    default to zero only with a visible warning. Residual asset and liability buckets are
    derived from reported totals rather than independently forecast or plugged.
    """

    try:
        income = history.statements["income_statement"]
        balance = history.statements["balance_sheet"]
    except KeyError as exc:
        raise HistoricalDataError("Income statement and balance sheet history are required.") from exc
    common_years = sorted(set(income.columns).intersection(balance.columns))
    if not common_years:
        raise HistoricalDataError("Historical statements do not share a common fiscal year.")
    year = fiscal_year if fiscal_year is not None else int(common_years[-1])
    if year not in common_years:
        raise HistoricalDataError(f"Fiscal year {year} is not present in both historical statements.")

    warnings: list[str] = []
    values: dict[str, float] = {}

    def required(frame: pd.DataFrame, account: str) -> float:
        value = _read(frame, account, year)
        if value is None:
            raise HistoricalDataError(
                f"Required opening-state account '{account}' is missing for fiscal year {year}."
            )
        values[account] = value
        return value

    def optional(frame: pd.DataFrame, account: str, default: float = 0.0) -> float:
        value = _read(frame, account, year)
        if value is None:
            warnings.append(
                f"{account} is missing for FY{year}; used explicit default {default:.1f}."
            )
            value = default
        values[account] = value
        return value

    revenue = required(income, "revenue")
    cash = required(balance, "cash_and_equivalents")
    receivables = optional(balance, "accounts_receivable")
    inventory = optional(balance, "inventory")
    other_current_assets = optional(balance, "other_current_assets")
    ppe = required(balance, "property_plant_equipment")
    total_assets = required(balance, "total_assets")
    payables = optional(balance, "accounts_payable")
    accrued = optional(balance, "accrued_liabilities")
    short_debt = optional(balance, "short_term_debt")
    long_debt = optional(balance, "long_term_debt")
    total_liabilities = required(balance, "total_liabilities")
    total_equity = required(balance, "total_equity")
    retained_earnings = optional(balance, "retained_earnings")
    net_income = optional(income, "net_income", default=math.nan)
    diluted_shares = optional(income, "diluted_shares", default=math.nan)

    other_assets = total_assets - cash - receivables - inventory - other_current_assets - ppe
    other_liabilities = total_liabilities - payables - accrued - short_debt - long_debt
    if other_assets < -tolerance:
        raise HistoricalDataError(
            f"Derived other assets are negative ({other_assets:.6f}) for FY{year}; "
            "review canonical account overlap and units."
        )
    if other_liabilities < -tolerance:
        raise HistoricalDataError(
            f"Derived other liabilities are negative ({other_liabilities:.6f}) for FY{year}; "
            "review debt/current-liability overlap and units."
        )
    other_assets = max(0.0, other_assets)
    other_liabilities = max(0.0, other_liabilities)
    contributed_equity = total_equity - retained_earnings
    values.update(
        {
            "other_assets_residual": other_assets,
            "other_liabilities_residual": other_liabilities,
            "contributed_equity_residual": contributed_equity,
        }
    )
    warnings.extend(
        (
            "Other assets are derived as total assets less explicitly modelled asset accounts.",
            "Other liabilities are derived as total liabilities less explicitly modelled liability accounts.",
            "Contributed equity is derived as total equity less retained earnings.",
        )
    )
    state = InitialFinancialState(
        fiscal_year=year,
        revenue=revenue,
        cash_and_equivalents=cash,
        accounts_receivable=receivables,
        inventory=inventory,
        other_current_assets=other_current_assets,
        property_plant_equipment=ppe,
        other_assets=other_assets,
        accounts_payable=payables,
        accrued_liabilities=accrued,
        short_term_debt=short_debt,
        long_term_debt=long_debt,
        other_liabilities=other_liabilities,
        contributed_equity=contributed_equity,
        retained_earnings=retained_earnings,
        net_income=None if math.isnan(net_income) else net_income,
        diluted_shares=None if math.isnan(diluted_shares) else diluted_shares,
    )
    state.validate(tolerance=max(tolerance, 1e-6))
    return OpeningStateResult(
        state=state,
        fiscal_year=year,
        source_values=values,
        warnings=tuple(warnings),
    )


def _read(frame: pd.DataFrame, account: str, year: int) -> float | None:
    if account not in frame.index or year not in frame.columns:
        return None
    value = frame.loc[account, year]
    if pd.isna(value):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    return numeric
