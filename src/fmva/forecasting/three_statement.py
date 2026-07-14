"""Orchestrate a linked, no-plug three-statement forecast."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from fmva.checks.models import CheckResult
from fmva.checks.statements import ForecastCheckSuite
from fmva.forecasting.assumptions import ForecastAssumptions
from fmva.forecasting.debt_cash import solve_debt_and_interest
from fmva.forecasting.fixed_assets import calculate_fixed_assets
from fmva.forecasting.operating import OperatingModel, TopDownOperatingModel
from fmva.forecasting.working_capital import calculate_working_capital


@dataclass(frozen=True, slots=True)
class InitialFinancialState:
    """Last historical period required to start the linked forecast."""

    fiscal_year: int
    revenue: float
    cash_and_equivalents: float
    accounts_receivable: float
    inventory: float
    other_current_assets: float
    property_plant_equipment: float
    other_assets: float
    accounts_payable: float
    accrued_liabilities: float
    short_term_debt: float
    long_term_debt: float
    other_liabilities: float
    contributed_equity: float
    retained_earnings: float
    net_income: float | None = None
    diluted_shares: float | None = None

    @property
    def net_working_capital(self) -> float:
        return (
            self.accounts_receivable
            + self.inventory
            + self.other_current_assets
            - self.accounts_payable
            - self.accrued_liabilities
        )

    @property
    def total_assets(self) -> float:
        return (
            self.cash_and_equivalents
            + self.accounts_receivable
            + self.inventory
            + self.other_current_assets
            + self.property_plant_equipment
            + self.other_assets
        )

    @property
    def total_liabilities_and_equity(self) -> float:
        return (
            self.accounts_payable
            + self.accrued_liabilities
            + self.short_term_debt
            + self.long_term_debt
            + self.other_liabilities
            + self.contributed_equity
            + self.retained_earnings
        )

    def validate(self, tolerance: float = 1e-6) -> None:
        """Require a balanced opening state; never manufacture a forecast plug."""

        difference = self.total_assets - self.total_liabilities_and_equity
        if abs(difference) > tolerance:
            raise ValueError(f"Opening balance sheet is out of balance by {difference:.6f}.")


@dataclass(frozen=True, slots=True)
class ForecastResult:
    """Linked statements, supporting schedules, and structured checks."""

    income_statement: pd.DataFrame
    balance_sheet: pd.DataFrame
    cash_flow_statement: pd.DataFrame
    working_capital: pd.DataFrame
    fixed_assets: pd.DataFrame
    debt_schedule: pd.DataFrame
    checks: tuple[CheckResult, ...]


class ThreeStatementModel:
    """Forecast linked statements in dependency order."""

    def __init__(self, operating_model: OperatingModel | None = None) -> None:
        self.operating_model = operating_model or TopDownOperatingModel()

    def run(
        self,
        initial: InitialFinancialState,
        assumptions: ForecastAssumptions,
    ) -> ForecastResult:
        """Run all forecast years and return auditable schedules and checks."""

        initial.validate()
        if assumptions.years[0] != initial.fiscal_year + 1:
            raise ValueError("The first forecast year must immediately follow the initial fiscal year.")
        income: dict[int, dict[str, float]] = {}
        balance: dict[int, dict[str, float]] = {}
        cash_flow: dict[int, dict[str, float]] = {}
        working_capital: dict[int, dict[str, float]] = {}
        fixed_assets: dict[int, dict[str, float]] = {}
        debt_schedule: dict[int, dict[str, float | bool]] = {}

        prior_revenue = initial.revenue
        prior_cash = initial.cash_and_equivalents
        prior_nwc = initial.net_working_capital
        prior_ppe = initial.property_plant_equipment
        prior_short_debt = initial.short_term_debt
        prior_long_debt = initial.long_term_debt
        prior_retained_earnings = initial.retained_earnings
        prior_contributed_equity = initial.contributed_equity

        for year in assumptions.years:
            operating = self.operating_model.forecast(prior_revenue, year, assumptions)
            wc = calculate_working_capital(
                operating.revenue, operating.cogs, prior_nwc, year, assumptions
            )
            assets = calculate_fixed_assets(prior_ppe, operating.revenue, year, assumptions)
            ebit = operating.ebitda - assets.depreciation
            tax_rate = assumptions.tax_rate[year]
            payout_ratio = assumptions.dividend_payout_ratio[year]
            share_issuance = assumptions.share_issuance[year]
            share_repurchases = assumptions.share_repurchases[year]
            zero_interest_ebt = ebit
            zero_interest_tax = max(0.0, zero_interest_ebt * tax_rate)
            zero_interest_net_income = zero_interest_ebt - zero_interest_tax
            zero_interest_dividends = max(0.0, zero_interest_net_income * payout_ratio)
            cash_before_financing_and_interest = (
                zero_interest_net_income
                + assets.depreciation
                - wc.change_in_net_working_capital
                - assets.capital_expenditures
                + assets.asset_disposals
                - zero_interest_dividends
                + share_issuance
                - share_repurchases
            )
            interest_cash_effect_factor = (1.0 - tax_rate) * (1.0 - payout_ratio)
            debt = solve_debt_and_interest(
                year=year,
                revenue=operating.revenue,
                beginning_cash=prior_cash,
                beginning_short_term_debt=prior_short_debt,
                beginning_long_term_debt=prior_long_debt,
                cash_before_financing_and_interest=cash_before_financing_and_interest,
                interest_cash_effect_factor=interest_cash_effect_factor,
                assumptions=assumptions,
            )
            ebt = ebit - debt.interest_expense
            income_tax = max(0.0, ebt * tax_rate)
            net_income = ebt - income_tax
            dividends = max(0.0, net_income * payout_ratio)
            cash_from_operations = net_income + assets.depreciation - wc.change_in_net_working_capital
            cash_from_investing = -assets.capital_expenditures + assets.asset_disposals
            cash_from_financing = (
                debt.new_borrowing
                - debt.debt_repayment
                + share_issuance
                - share_repurchases
                - dividends
            )
            net_change_in_cash = cash_from_operations + cash_from_investing + cash_from_financing
            ending_cash = prior_cash + net_change_in_cash
            ending_retained_earnings = prior_retained_earnings + net_income - dividends
            ending_contributed_equity = (
                prior_contributed_equity + share_issuance - share_repurchases
            )

            total_current_assets = (
                ending_cash + wc.accounts_receivable + wc.inventory + wc.other_current_assets
            )
            total_assets = total_current_assets + assets.ending_ppe + initial.other_assets
            total_current_liabilities = (
                wc.accounts_payable + wc.accrued_liabilities + debt.ending_short_term_debt
            )
            total_liabilities = (
                total_current_liabilities + debt.ending_long_term_debt + initial.other_liabilities
            )
            total_equity = ending_contributed_equity + ending_retained_earnings

            income[year] = {
                "revenue": operating.revenue,
                "cogs": operating.cogs,
                "gross_profit": operating.gross_profit,
                "selling_general_admin": operating.selling_general_admin,
                "research_and_development": operating.research_and_development,
                "other_operating_income": operating.other_operating_income,
                "ebitda": operating.ebitda,
                "depreciation_and_amortization": assets.depreciation,
                "operating_income": ebit,
                "interest_expense": debt.interest_expense,
                "income_before_tax": ebt,
                "income_tax": income_tax,
                "net_income": net_income,
                "minority_interest": 0.0,
                "net_income_attributable_to_parent": net_income,
            }
            balance[year] = {
                "cash_and_equivalents": ending_cash,
                "accounts_receivable": wc.accounts_receivable,
                "inventory": wc.inventory,
                "other_current_assets": wc.other_current_assets,
                "total_current_assets": total_current_assets,
                "property_plant_equipment": assets.ending_ppe,
                "other_noncurrent_assets": initial.other_assets,
                "total_assets": total_assets,
                "accounts_payable": wc.accounts_payable,
                "accrued_liabilities": wc.accrued_liabilities,
                "short_term_debt": debt.ending_short_term_debt,
                "total_current_liabilities": total_current_liabilities,
                "long_term_debt": debt.ending_long_term_debt,
                "other_noncurrent_liabilities": initial.other_liabilities,
                "total_liabilities": total_liabilities,
                "contributed_equity": ending_contributed_equity,
                "retained_earnings": ending_retained_earnings,
                "total_equity": total_equity,
                "total_liabilities_and_equity": total_liabilities + total_equity,
            }
            cash_flow[year] = {
                "net_income": net_income,
                "depreciation_and_amortization": assets.depreciation,
                "change_in_net_working_capital": -wc.change_in_net_working_capital,
                "cash_from_operations": cash_from_operations,
                "capital_expenditures": -assets.capital_expenditures,
                "asset_disposals": assets.asset_disposals,
                "cash_from_investing": cash_from_investing,
                "debt_issuance": debt.new_borrowing,
                "debt_repayment": -debt.debt_repayment,
                "share_issuance": share_issuance,
                "share_repurchases": -share_repurchases,
                "dividends_paid": -dividends,
                "cash_from_financing": cash_from_financing,
                "net_change_in_cash": net_change_in_cash,
                "ending_cash": ending_cash,
            }
            working_capital[year] = asdict(wc)
            fixed_assets[year] = asdict(assets)
            debt_schedule[year] = asdict(debt)

            prior_revenue = operating.revenue
            prior_cash = ending_cash
            prior_nwc = wc.net_working_capital
            prior_ppe = assets.ending_ppe
            prior_short_debt = debt.ending_short_term_debt
            prior_long_debt = debt.ending_long_term_debt
            prior_retained_earnings = ending_retained_earnings
            prior_contributed_equity = ending_contributed_equity

        result_without_checks = ForecastResult(
            income_statement=_frame(income),
            balance_sheet=_frame(balance),
            cash_flow_statement=_frame(cash_flow),
            working_capital=_frame(working_capital),
            fixed_assets=_frame(fixed_assets),
            debt_schedule=_frame(debt_schedule),
            checks=(),
        )
        checks = ForecastCheckSuite().run(result_without_checks, initial)
        return ForecastResult(
            income_statement=result_without_checks.income_statement,
            balance_sheet=result_without_checks.balance_sheet,
            cash_flow_statement=result_without_checks.cash_flow_statement,
            working_capital=result_without_checks.working_capital,
            fixed_assets=result_without_checks.fixed_assets,
            debt_schedule=result_without_checks.debt_schedule,
            checks=checks,
        )


def _frame(data: dict[int, dict[str, float | bool]]) -> pd.DataFrame:
    frame = pd.DataFrame(data)
    frame.columns.name = "fiscal_year"
    frame.index.name = "account"
    return frame
