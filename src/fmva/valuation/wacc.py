"""Cost of capital calculations."""

from __future__ import annotations

from fmva.valuation.models import ValuationAssumptions


def cost_of_equity(assumptions: ValuationAssumptions) -> float:
    """CAPM cost of equity."""

    return assumptions.risk_free_rate + assumptions.beta * assumptions.equity_risk_premium


def calculate_wacc(assumptions: ValuationAssumptions, tax_rate: float) -> float:
    """Calculate after-tax weighted average cost of capital."""

    assumptions.validate()
    if not 0 <= tax_rate <= 1:
        raise ValueError("WACC tax rate must be between 0 and 1.")
    return (
        assumptions.target_equity_weight * cost_of_equity(assumptions)
        + assumptions.target_debt_weight * assumptions.pre_tax_cost_of_debt * (1.0 - tax_rate)
    )
