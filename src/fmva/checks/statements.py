"""Forecast statement and supporting-schedule checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fmva.checks.models import CheckResult, CheckSeverity, CheckStatus

if TYPE_CHECKING:
    from fmva.forecasting.three_statement import ForecastResult, InitialFinancialState


class ForecastCheckSuite:
    """Verify all first-version three-statement identities."""

    def __init__(self, tolerance: float = 1e-6) -> None:
        self.tolerance = tolerance

    def run(
        self,
        result: ForecastResult,
        initial: InitialFinancialState,
    ) -> tuple[CheckResult, ...]:
        checks: list[CheckResult] = []
        prior_cash = initial.cash_and_equivalents
        prior_retained = initial.retained_earnings
        prior_contributed = initial.contributed_equity
        prior_ppe = initial.property_plant_equipment
        prior_short = initial.short_term_debt
        prior_long = initial.long_term_debt
        for year in result.balance_sheet.columns:
            bs = result.balance_sheet[year]
            cfs = result.cash_flow_statement[year]
            income = result.income_statement[year]
            fixed = result.fixed_assets[year]
            debt = result.debt_schedule[year]
            checks.extend(
                [
                    self._check("balance_sheet", bs["total_assets"], bs["total_liabilities_and_equity"], year),
                    self._check("cash_cfs_to_bs", cfs["ending_cash"], bs["cash_and_equivalents"], year),
                    self._check("cash_rollforward", prior_cash + cfs["net_change_in_cash"], bs["cash_and_equivalents"], year),
                    self._check(
                        "retained_earnings",
                        prior_retained + income["net_income_attributable_to_parent"] + cfs["dividends_paid"],
                        bs["retained_earnings"],
                        year,
                    ),
                    self._check(
                        "contributed_equity",
                        prior_contributed + cfs["share_issuance"] + cfs["share_repurchases"],
                        bs["contributed_equity"],
                        year,
                    ),
                    self._check(
                        "ppe_rollforward",
                        prior_ppe + fixed["capital_expenditures"] - fixed["depreciation"] - fixed["asset_disposals"],
                        fixed["ending_ppe"],
                        year,
                    ),
                    self._check(
                        "debt_rollforward",
                        prior_short + prior_long + debt["new_borrowing"] - debt["debt_repayment"],
                        debt["ending_short_term_debt"] + debt["ending_long_term_debt"],
                        year,
                    ),
                ]
            )
            converged = bool(debt["solver_converged"])
            checks.append(
                CheckResult(
                    check="debt_interest_solver",
                    actual=float(debt["solver_delta"]),
                    expected=0.0,
                    difference=float(debt["solver_delta"]),
                    tolerance=self.tolerance,
                    status=CheckStatus.PASS if converged else CheckStatus.FAIL,
                    severity=CheckSeverity.ERROR,
                    message=None if converged else f"Debt/interest solver did not converge in FY{year}.",
                    context={"fiscal_year": year, "iterations": int(debt["solver_iterations"])},
                )
            )
            prior_cash = bs["cash_and_equivalents"]
            prior_retained = bs["retained_earnings"]
            prior_contributed = bs["contributed_equity"]
            prior_ppe = fixed["ending_ppe"]
            prior_short = debt["ending_short_term_debt"]
            prior_long = debt["ending_long_term_debt"]
        return tuple(checks)

    def _check(self, name: str, actual: float, expected: float, year: int) -> CheckResult:
        difference = float(actual - expected)
        tolerance = max(self.tolerance, self.tolerance * max(abs(actual), abs(expected), 1.0))
        passed = abs(difference) <= tolerance
        return CheckResult(
            check=name,
            actual=float(actual),
            expected=float(expected),
            difference=difference,
            tolerance=tolerance,
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            severity=CheckSeverity.ERROR,
            message=None if passed else f"{name} failed for FY{year}.",
            context={"fiscal_year": year},
        )
