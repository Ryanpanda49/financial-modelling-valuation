"""Historical statement reconciliation and completeness checks."""

from __future__ import annotations

import math

import pandas as pd

from fmva.checks.models import CheckResult, CheckSeverity, CheckStatus
from fmva.data.statement_builder import HistoricalStatements


class HistoricalCheckSuite:
    """Run checks that are meaningful before forecasting begins."""

    def __init__(self, *, absolute_tolerance: float = 1e-6, relative_tolerance: float = 1e-6) -> None:
        self.absolute_tolerance = absolute_tolerance
        self.relative_tolerance = relative_tolerance

    def run(self, history: HistoricalStatements) -> tuple[CheckResult, ...]:
        """Run completeness, balance-sheet, and cash roll-forward checks."""

        results: list[CheckResult] = []
        results.extend(self._required_account_checks(history))
        results.extend(self._balance_sheet_checks(history.statements.get("balance_sheet")))
        results.extend(
            self._cash_rollforward_checks(
                history.statements.get("balance_sheet"),
                history.statements.get("cash_flow_statement"),
            )
        )
        return tuple(results)

    def _required_account_checks(self, history: HistoricalStatements) -> list[CheckResult]:
        failures = [issue for issue in history.quality_issues if issue.code == "REQUIRED_ACCOUNT_MISSING"]
        return [
            CheckResult(
                check="required_account_completeness",
                actual=0.0 if failures else 1.0,
                expected=1.0,
                difference=-1.0 if failures else 0.0,
                tolerance=0.0,
                status=CheckStatus.FAIL if failures else CheckStatus.PASS,
                severity=CheckSeverity.ERROR,
                message=(
                    f"{len(failures)} required account-period values are missing."
                    if failures
                    else None
                ),
                context={"missing_count": len(failures)},
            )
        ]

    def _balance_sheet_checks(self, balance_sheet: pd.DataFrame | None) -> list[CheckResult]:
        required = {"total_assets", "total_liabilities", "total_equity"}
        if balance_sheet is None or not required.issubset(balance_sheet.index):
            return [self._not_applicable("balance_sheet", "Required total rows are unavailable.")]
        return [
            self._numeric_check(
                "balance_sheet",
                float(balance_sheet.loc["total_assets", year]),
                float(balance_sheet.loc["total_liabilities", year])
                + float(balance_sheet.loc["total_equity", year]),
                year,
            )
            for year in balance_sheet.columns
        ]

    def _cash_rollforward_checks(
        self,
        balance_sheet: pd.DataFrame | None,
        cash_flow: pd.DataFrame | None,
    ) -> list[CheckResult]:
        if (
            balance_sheet is None
            or cash_flow is None
            or "cash_and_equivalents" not in balance_sheet.index
            or "net_change_in_cash" not in cash_flow.index
        ):
            return [self._not_applicable("historical_cash_rollforward", "Cash rows are unavailable.")]
        common_years = sorted(set(balance_sheet.columns) & set(cash_flow.columns))
        results = []
        for previous, current in zip(common_years, common_years[1:], strict=False):
            actual = float(balance_sheet.loc["cash_and_equivalents", current])
            expected = float(balance_sheet.loc["cash_and_equivalents", previous]) + float(
                cash_flow.loc["net_change_in_cash", current]
            )
            results.append(self._numeric_check("historical_cash_rollforward", actual, expected, current))
        return results or [
            self._not_applicable("historical_cash_rollforward", "At least two common years are required.")
        ]

    def _numeric_check(self, name: str, actual: float, expected: float, year: int) -> CheckResult:
        if math.isnan(actual) or math.isnan(expected):
            return CheckResult(
                check=name,
                actual=None,
                expected=None,
                difference=None,
                tolerance=self.absolute_tolerance,
                status=CheckStatus.NOT_APPLICABLE,
                severity=CheckSeverity.WARNING,
                message="One or more required values are missing.",
                context={"fiscal_year": year},
            )
        difference = actual - expected
        tolerance = max(self.absolute_tolerance, self.relative_tolerance * max(abs(actual), abs(expected), 1.0))
        passed = abs(difference) <= tolerance
        return CheckResult(
            check=name,
            actual=actual,
            expected=expected,
            difference=difference,
            tolerance=tolerance,
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            severity=CheckSeverity.ERROR,
            message=None if passed else f"{name} does not reconcile for FY{year}.",
            context={"fiscal_year": year},
        )

    def _not_applicable(self, name: str, message: str) -> CheckResult:
        return CheckResult(
            check=name,
            actual=None,
            expected=None,
            difference=None,
            tolerance=self.absolute_tolerance,
            status=CheckStatus.NOT_APPLICABLE,
            severity=CheckSeverity.WARNING,
            message=message,
        )
