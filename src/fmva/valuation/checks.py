"""Structured DCF reconciliation checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fmva.checks.models import CheckResult, CheckSeverity, CheckStatus

if TYPE_CHECKING:
    from fmva.valuation.dcf import DcfResult
    from fmva.valuation.models import ValuationAssumptions


class ValuationCheckSuite:
    """Verify DCF tables, terminal value discounting, and equity bridge."""

    def __init__(self, tolerance: float = 1e-6) -> None:
        self.tolerance = tolerance

    def run(
        self,
        result: DcfResult,
        assumptions: ValuationAssumptions,
    ) -> tuple[CheckResult, ...]:
        last_discount_factor = float(result.forecast["discount_factor"].iloc[-1])
        monotonic = bool(result.forecast["discount_factor"].is_monotonic_decreasing)
        return (
            self._check("dcf_pv_forecast_fcf", result.pv_forecast_fcf, float(result.forecast["pv_fcf"].sum())),
            self._check("dcf_pv_terminal_value", result.pv_terminal_value, result.terminal_value * last_discount_factor),
            self._check("dcf_enterprise_value", result.enterprise_value, result.pv_forecast_fcf + result.pv_terminal_value),
            self._check("dcf_equity_bridge", result.equity_value, float(result.equity_bridge.sum())),
            self._check("dcf_implied_share_price", result.implied_share_price, result.equity_value / assumptions.diluted_shares),
            CheckResult(
                check="dcf_discount_factor_monotonic",
                actual=1.0 if monotonic else 0.0,
                expected=1.0,
                difference=0.0 if monotonic else -1.0,
                tolerance=0.0,
                status=CheckStatus.PASS if monotonic else CheckStatus.FAIL,
                severity=CheckSeverity.ERROR,
                message=None if monotonic else "DCF discount factors are not monotonically decreasing.",
            ),
        )

    def _check(self, name: str, actual: float, expected: float) -> CheckResult:
        difference = actual - expected
        tolerance = max(self.tolerance, self.tolerance * max(abs(actual), abs(expected), 1.0))
        passed = abs(difference) <= tolerance
        return CheckResult(
            check=name,
            actual=actual,
            expected=expected,
            difference=difference,
            tolerance=tolerance,
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            severity=CheckSeverity.ERROR,
            message=None if passed else f"{name} does not reconcile.",
        )
