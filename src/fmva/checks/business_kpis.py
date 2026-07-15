"""Checks connecting sourced historical business KPIs to standardized statements."""

from __future__ import annotations

from typing import Any, cast

from fmva.checks.models import CheckResult, CheckSeverity, CheckStatus
from fmva.data.business_kpis import BusinessKpiHistory
from fmva.data.statement_builder import HistoricalStatements


class BusinessKpiCheckSuite:
    """Validate evidence completeness and consolidated KPI tie-outs."""

    def __init__(self, tolerance: float = 1e-6) -> None:
        self.tolerance = tolerance

    def run(
        self,
        kpis: BusinessKpiHistory,
        history: HistoricalStatements,
    ) -> tuple[CheckResult, ...]:
        frame = kpis.to_frame()
        complete = frame[["source_name", "source_url", "source_document", "filing_date"]].apply(
            lambda column: column.astype(str).str.strip().ne("")
        ).all(axis=1)
        checks = [
            self._check(
                "business_kpi_source_completeness",
                float(complete.sum()),
                float(len(frame)),
                None,
            )
        ]
        mappings = {
            "segment_revenue": ("income_statement", "revenue"),
            "segment_cogs": ("income_statement", "cogs"),
        }
        for metric, (statement, account) in mappings.items():
            selected = frame.loc[frame["metric"] == metric]
            if selected.empty or account not in history.statements[statement].index:
                continue
            common_years = set(selected["fiscal_year"]) & set(history.statements[statement].columns)
            if not common_years:
                continue
            year = max(int(value) for value in common_years)
            actual = sum(
                float(cast(Any, value))
                for value in selected.loc[
                    selected["fiscal_year"] == year, "value"
                ].tolist()
            )
            expected = float(cast(Any, history.statements[statement].loc[account, year]))
            checks.append(self._check(f"business_kpi_{metric}_tie", actual, expected, year))
        return tuple(checks)

    def _check(
        self,
        name: str,
        actual: float,
        expected: float,
        year: int | None,
    ) -> CheckResult:
        difference = actual - expected
        tolerance = max(self.tolerance, self.tolerance * max(abs(actual), abs(expected), 1.0))
        passed = abs(difference) <= tolerance
        context = {} if year is None else {"fiscal_year": year}
        return CheckResult(
            check=name,
            actual=actual,
            expected=expected,
            difference=difference,
            tolerance=tolerance,
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            severity=CheckSeverity.ERROR,
            message=None if passed else f"{name} failed; review KPI scope, units, or restatement basis.",
            context=context,
        )
