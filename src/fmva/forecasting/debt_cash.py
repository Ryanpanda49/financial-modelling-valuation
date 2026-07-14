"""Debt balances, financing policy, and interest calculations."""

from __future__ import annotations

from dataclasses import dataclass

from fmva.forecasting.assumptions import ForecastAssumptions


@dataclass(frozen=True, slots=True)
class DebtSchedule:
    """One-period debt roll-forward and interest expense."""

    beginning_short_term_debt: float
    beginning_long_term_debt: float
    new_borrowing: float
    debt_repayment: float
    ending_short_term_debt: float
    ending_long_term_debt: float
    average_debt: float
    interest_expense: float
    minimum_cash: float
    solver_iterations: int
    solver_delta: float
    solver_converged: bool


def solve_debt_and_interest(
    *,
    year: int,
    revenue: float,
    beginning_cash: float,
    beginning_short_term_debt: float,
    beginning_long_term_debt: float,
    cash_before_financing_and_interest: float,
    interest_cash_effect_factor: float,
    assumptions: ForecastAssumptions,
) -> DebtSchedule:
    """Solve minimum-cash borrowing and average-debt interest explicitly.

    `cash_before_financing_and_interest` includes operating/investing cash before interest,
    debt issuance/repayment, and dividends. Planned borrowing is treated as short-term in the
    MVP. Planned repayment first reduces short-term debt, then long-term debt.
    """

    planned_borrowing = assumptions.new_borrowing[year]
    planned_repayment = assumptions.debt_repayment[year]
    minimum_cash = revenue * assumptions.minimum_cash_as_pct_revenue[year]
    interest = 0.0
    last_interest = float("inf")
    ending_short = beginning_short_term_debt
    ending_long = beginning_long_term_debt
    total_borrowing = planned_borrowing
    actual_repayment = 0.0
    for iteration in range(1, assumptions.max_solver_iterations + 1):
        repay_short = min(planned_repayment, beginning_short_term_debt + total_borrowing)
        remaining_repayment = max(0.0, planned_repayment - repay_short)
        repay_long = min(remaining_repayment, beginning_long_term_debt)
        actual_repayment = repay_short + repay_long
        ending_short = beginning_short_term_debt + total_borrowing - repay_short
        ending_long = beginning_long_term_debt - repay_long
        average_short = (beginning_short_term_debt + ending_short) / 2.0
        average_long = (beginning_long_term_debt + ending_long) / 2.0
        interest = (
            average_short * assumptions.short_term_interest_rate[year]
            + average_long * assumptions.long_term_interest_rate[year]
        )
        cash_after_planned_financing = (
            beginning_cash
            + cash_before_financing_and_interest
            - interest * interest_cash_effect_factor
            + total_borrowing
            - actual_repayment
        )
        additional_borrowing = max(0.0, minimum_cash - cash_after_planned_financing)
        # Add only the remaining shortfall to the current draw. Interest on the
        # incremental borrowing can create a smaller shortfall on the next pass.
        new_total_borrowing = total_borrowing + additional_borrowing
        delta = max(abs(new_total_borrowing - total_borrowing), abs(interest - last_interest))
        if delta <= assumptions.solver_tolerance:
            return DebtSchedule(
                beginning_short_term_debt=beginning_short_term_debt,
                beginning_long_term_debt=beginning_long_term_debt,
                new_borrowing=new_total_borrowing,
                debt_repayment=actual_repayment,
                ending_short_term_debt=ending_short,
                ending_long_term_debt=ending_long,
                average_debt=average_short + average_long,
                interest_expense=interest,
                minimum_cash=minimum_cash,
                solver_iterations=iteration,
                solver_delta=delta,
                solver_converged=True,
            )
        total_borrowing = new_total_borrowing
        last_interest = interest
    return DebtSchedule(
        beginning_short_term_debt=beginning_short_term_debt,
        beginning_long_term_debt=beginning_long_term_debt,
        new_borrowing=total_borrowing,
        debt_repayment=actual_repayment,
        ending_short_term_debt=ending_short,
        ending_long_term_debt=ending_long,
        average_debt=(beginning_short_term_debt + ending_short + beginning_long_term_debt + ending_long) / 2.0,
        interest_expense=interest,
        minimum_cash=minimum_cash,
        solver_iterations=assumptions.max_solver_iterations,
        solver_delta=delta,
        solver_converged=False,
    )
