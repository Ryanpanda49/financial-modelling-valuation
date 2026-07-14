"""Forecast financial ratio library with safe denominator handling."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fmva.data.statement_builder import HistoricalStatements
from fmva.forecasting.three_statement import ForecastResult, InitialFinancialState


@dataclass(frozen=True, slots=True)
class RatioResult:
    """Calculated ratio table and non-fatal applicability/data warnings."""

    table: pd.DataFrame
    warnings: tuple[str, ...]


def calculate_historical_ratios(history: HistoricalStatements) -> RatioResult:
    """Calculate requested ratios from standardized annual historical statements."""

    income = history.statements.get("income_statement")
    balance = history.statements.get("balance_sheet")
    cash_flow = history.statements.get("cash_flow_statement")
    if income is None or balance is None or cash_flow is None:
        raise ValueError("Historical income, balance sheet, and cash flow statements are required.")
    years = sorted(set(income.columns) & set(balance.columns) & set(cash_flow.columns))
    if not years:
        raise ValueError("Historical statements do not share common fiscal years.")
    warnings: list[str] = []

    def row(frame: pd.DataFrame, account: str) -> pd.Series:
        if account not in frame.index:
            warnings.append(f"Historical ratio input '{account}' is missing; returned null where used.")
            return pd.Series(np.nan, index=years, dtype=float)
        return frame.loc[account, years].astype(float)

    revenue = row(income, "revenue")
    cogs = row(income, "cogs")
    gross_profit = row(income, "gross_profit")
    operating_income = row(income, "operating_income")
    depreciation = row(income, "depreciation_and_amortization")
    ebitda = operating_income + depreciation
    net_income = row(income, "net_income")
    parent_income = row(income, "net_income_attributable_to_parent")
    diluted_shares = row(income, "diluted_shares")
    income_tax = row(income, "income_tax")
    pre_tax_income = row(income, "income_before_tax")
    interest_expense = row(income, "interest_expense")

    cash = row(balance, "cash_and_equivalents")
    short_investments = row(balance, "short_term_investments").fillna(0.0)
    receivables = row(balance, "accounts_receivable")
    inventory = row(balance, "inventory")
    current_assets = row(balance, "total_current_assets")
    payables = row(balance, "accounts_payable")
    current_liabilities = row(balance, "total_current_liabilities")
    short_debt = row(balance, "short_term_debt").fillna(0.0)
    long_debt = row(balance, "long_term_debt").fillna(0.0)
    total_assets = row(balance, "total_assets")
    total_equity = row(balance, "total_equity")
    debt = short_debt + long_debt

    cfo = row(cash_flow, "cash_from_operations")
    capex = row(cash_flow, "capital_expenditures")
    fcf = cfo - capex
    average_assets = (total_assets + total_assets.shift(1)) / 2.0
    average_equity = (total_equity + total_equity.shift(1)) / 2.0
    average_inventory = (inventory + inventory.shift(1)) / 2.0
    average_receivables = (receivables + receivables.shift(1)) / 2.0
    average_payables = (payables + payables.shift(1)) / 2.0
    invested_capital = debt + total_equity - cash
    average_invested = (invested_capital + invested_capital.shift(1)) / 2.0
    effective_tax = _safe_divide(
        income_tax, pre_tax_income, "historical_effective_tax_rate", warnings
    ).clip(0, 1)
    nopat = operating_income * (1.0 - effective_tax)

    rows: dict[str, pd.Series] = {
        "revenue_growth": revenue.pct_change(fill_method=None),
        "ebitda_growth": ebitda.pct_change(fill_method=None),
        "net_income_growth": net_income.pct_change(fill_method=None),
        "eps_growth": _safe_divide(parent_income, diluted_shares, "historical_eps", warnings).pct_change(fill_method=None),
        "fcf_growth": fcf.pct_change(fill_method=None),
        "gross_margin": _safe_divide(gross_profit, revenue, "historical_gross_margin", warnings),
        "ebitda_margin": _safe_divide(ebitda, revenue, "historical_ebitda_margin", warnings),
        "operating_margin": _safe_divide(operating_income, revenue, "historical_operating_margin", warnings),
        "net_margin": _safe_divide(net_income, revenue, "historical_net_margin", warnings),
        "roa": _safe_divide(net_income, average_assets, "historical_roa", warnings),
        "roe": _safe_divide(parent_income, average_equity, "historical_roe", warnings),
        "roic": _safe_divide(nopat, average_invested, "historical_roic", warnings),
        "current_ratio": _safe_divide(current_assets, current_liabilities, "historical_current_ratio", warnings),
        "quick_ratio": _safe_divide(cash + short_investments + receivables, current_liabilities, "historical_quick_ratio", warnings),
        "cash_ratio": _safe_divide(cash + short_investments, current_liabilities, "historical_cash_ratio", warnings),
        "debt_to_equity": _safe_divide(debt, total_equity, "historical_debt_to_equity", warnings),
        "debt_to_ebitda": _safe_divide(debt, ebitda, "historical_debt_to_ebitda", warnings),
        "net_debt_to_ebitda": _safe_divide(debt - cash, ebitda, "historical_net_debt_to_ebitda", warnings),
        "interest_coverage": _safe_divide(operating_income, interest_expense, "historical_interest_coverage", warnings),
        "asset_turnover": _safe_divide(revenue, average_assets, "historical_asset_turnover", warnings),
        "inventory_turnover": _safe_divide(cogs, average_inventory, "historical_inventory_turnover", warnings),
        "receivables_turnover": _safe_divide(revenue, average_receivables, "historical_receivables_turnover", warnings),
        "payables_turnover": _safe_divide(cogs, average_payables, "historical_payables_turnover", warnings),
        "cfo_to_net_income": _safe_divide(cfo, net_income, "historical_cfo_to_net_income", warnings),
        "fcf_margin": _safe_divide(fcf, revenue, "historical_fcf_margin", warnings),
        "capex_to_revenue": _safe_divide(capex, revenue, "historical_capex_to_revenue", warnings),
        "cash_conversion_ratio": _safe_divide(cfo, ebitda, "historical_cash_conversion_ratio", warnings),
    }
    rows["dso"] = 365.0 / rows["receivables_turnover"]
    rows["dio"] = 365.0 / rows["inventory_turnover"]
    rows["dpo"] = 365.0 / rows["payables_turnover"]
    rows["cash_conversion_cycle"] = rows["dso"] + rows["dio"] - rows["dpo"]
    table = pd.DataFrame(rows).T.reindex(columns=years)
    table.index.name = "ratio"
    table.columns.name = "fiscal_year"
    if np.isinf(table.to_numpy(dtype=float)).any():
        raise AssertionError("Historical ratio table must never contain infinity.")
    return RatioResult(table=table, warnings=tuple(dict.fromkeys(warnings)))


def calculate_financial_ratios(
    forecast: ForecastResult,
    initial: InitialFinancialState,
) -> RatioResult:
    """Calculate growth, profitability, liquidity, leverage, efficiency, and cash ratios."""

    years = list(forecast.income_statement.columns)
    income = forecast.income_statement
    balance = forecast.balance_sheet
    cash_flow = forecast.cash_flow_statement
    working = forecast.working_capital
    rows: dict[str, pd.Series] = {}
    warnings: list[str] = []

    rows["revenue_growth"] = _growth(income.loc["revenue"], initial.revenue)
    rows["ebitda_growth"] = income.loc["ebitda"].pct_change(fill_method=None)
    rows["net_income_growth"] = _growth(income.loc["net_income"], initial.net_income)
    if initial.diluted_shares and initial.diluted_shares > 0:
        eps = income.loc["net_income_attributable_to_parent"] / initial.diluted_shares
        rows["eps_growth"] = _growth(
            eps,
            (initial.net_income / initial.diluted_shares) if initial.net_income is not None else None,
        )
    else:
        rows["eps_growth"] = pd.Series(np.nan, index=years)
        warnings.append("EPS growth is not applicable because diluted shares are missing or zero.")
    fcf = cash_flow.loc["cash_from_operations"] + cash_flow.loc["capital_expenditures"]
    rows["fcf_growth"] = fcf.pct_change(fill_method=None)

    rows["gross_margin"] = _safe_divide(income.loc["gross_profit"], income.loc["revenue"], "gross_margin", warnings)
    rows["ebitda_margin"] = _safe_divide(income.loc["ebitda"], income.loc["revenue"], "ebitda_margin", warnings)
    rows["operating_margin"] = _safe_divide(income.loc["operating_income"], income.loc["revenue"], "operating_margin", warnings)
    rows["net_margin"] = _safe_divide(income.loc["net_income"], income.loc["revenue"], "net_margin", warnings)

    average_assets = _average_balance(balance.loc["total_assets"], initial.total_assets)
    initial_equity = initial.contributed_equity + initial.retained_earnings
    average_equity = _average_balance(balance.loc["total_equity"], initial_equity)
    debt = balance.loc["short_term_debt"] + balance.loc["long_term_debt"]
    initial_debt = initial.short_term_debt + initial.long_term_debt
    invested_capital = debt + balance.loc["total_equity"] - balance.loc["cash_and_equivalents"]
    initial_invested = initial_debt + initial_equity - initial.cash_and_equivalents
    average_invested = _average_balance(invested_capital, initial_invested)
    effective_tax = _safe_divide(income.loc["income_tax"], income.loc["income_before_tax"], "effective_tax_rate", warnings).clip(0, 1)
    nopat = income.loc["operating_income"] * (1.0 - effective_tax)
    rows["roa"] = _safe_divide(income.loc["net_income"], average_assets, "roa", warnings)
    rows["roe"] = _safe_divide(income.loc["net_income_attributable_to_parent"], average_equity, "roe", warnings)
    rows["roic"] = _safe_divide(nopat, average_invested, "roic", warnings)

    rows["current_ratio"] = _safe_divide(balance.loc["total_current_assets"], balance.loc["total_current_liabilities"], "current_ratio", warnings)
    quick_assets = balance.loc["cash_and_equivalents"] + balance.loc["accounts_receivable"]
    rows["quick_ratio"] = _safe_divide(quick_assets, balance.loc["total_current_liabilities"], "quick_ratio", warnings)
    rows["cash_ratio"] = _safe_divide(balance.loc["cash_and_equivalents"], balance.loc["total_current_liabilities"], "cash_ratio", warnings)

    rows["debt_to_equity"] = _safe_divide(debt, balance.loc["total_equity"], "debt_to_equity", warnings)
    rows["debt_to_ebitda"] = _safe_divide(debt, income.loc["ebitda"], "debt_to_ebitda", warnings)
    rows["net_debt_to_ebitda"] = _safe_divide(debt - balance.loc["cash_and_equivalents"], income.loc["ebitda"], "net_debt_to_ebitda", warnings)
    rows["interest_coverage"] = _safe_divide(income.loc["operating_income"], income.loc["interest_expense"], "interest_coverage", warnings)

    average_inventory = _average_balance(balance.loc["inventory"], initial.inventory)
    average_receivables = _average_balance(balance.loc["accounts_receivable"], initial.accounts_receivable)
    average_payables = _average_balance(balance.loc["accounts_payable"], initial.accounts_payable)
    rows["asset_turnover"] = _safe_divide(income.loc["revenue"], average_assets, "asset_turnover", warnings)
    rows["inventory_turnover"] = _safe_divide(income.loc["cogs"], average_inventory, "inventory_turnover", warnings)
    rows["receivables_turnover"] = _safe_divide(income.loc["revenue"], average_receivables, "receivables_turnover", warnings)
    rows["payables_turnover"] = _safe_divide(income.loc["cogs"], average_payables, "payables_turnover", warnings)
    rows["dso"] = working.loc["dso"]
    rows["dio"] = working.loc["dio"]
    rows["dpo"] = working.loc["dpo"]
    rows["cash_conversion_cycle"] = working.loc["cash_conversion_cycle"]

    rows["cfo_to_net_income"] = _safe_divide(cash_flow.loc["cash_from_operations"], income.loc["net_income"], "cfo_to_net_income", warnings)
    rows["fcf_margin"] = _safe_divide(fcf, income.loc["revenue"], "fcf_margin", warnings)
    rows["capex_to_revenue"] = _safe_divide(-cash_flow.loc["capital_expenditures"], income.loc["revenue"], "capex_to_revenue", warnings)
    rows["cash_conversion_ratio"] = _safe_divide(cash_flow.loc["cash_from_operations"], income.loc["ebitda"], "cash_conversion_ratio", warnings)

    table = pd.DataFrame(rows).T.reindex(columns=years)
    table.index.name = "ratio"
    table.columns.name = "fiscal_year"
    if np.isinf(table.to_numpy(dtype=float)).any():
        raise AssertionError("Ratio table must never contain infinity.")
    return RatioResult(table=table, warnings=tuple(dict.fromkeys(warnings)))


def _growth(values: pd.Series, initial_value: float | None) -> pd.Series:
    result = values.pct_change(fill_method=None)
    if initial_value is not None and initial_value != 0:
        result.iloc[0] = values.iloc[0] / initial_value - 1.0
    return result


def _average_balance(values: pd.Series, initial_value: float) -> pd.Series:
    prior = values.shift(1)
    prior.iloc[0] = initial_value
    return (values + prior) / 2.0


def _safe_divide(
    numerator: pd.Series,
    denominator: pd.Series,
    name: str,
    warnings: list[str],
) -> pd.Series:
    invalid = denominator.isna() | (denominator.abs() <= 1e-12)
    if invalid.any():
        years = ", ".join(str(year) for year in denominator.index[invalid])
        warnings.append(f"{name}: missing or zero denominator for {years}; returned null.")
    return numerator.divide(denominator.mask(invalid)).replace([np.inf, -np.inf], np.nan)
