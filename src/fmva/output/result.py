"""Unified model result and exporter facade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from fmva.analysis.ratios import RatioResult
from fmva.checks.models import CheckResult
from fmva.data.statement_builder import HistoricalStatements
from fmva.forecasting.three_statement import ForecastResult
from fmva.output.charts import build_charts
from fmva.output.excel import export_excel
from fmva.output.markdown import export_markdown
from fmva.output.result_types import ModelResultData
from fmva.valuation.dcf import DcfResult


@dataclass(frozen=True, slots=True)
class ModelResult:
    """Public result bundle consumed by every output format."""

    company_name: str
    ticker: str
    as_of: str
    forecast: ForecastResult
    ratios: RatioResult
    dcf: DcfResult
    sensitivity: pd.DataFrame
    assumption_summary: list[dict[str, object]]
    limitations: tuple[str, ...] = ()
    historical: HistoricalStatements | None = None
    historical_ratios: RatioResult | None = None
    historical_checks: tuple[CheckResult, ...] = ()
    opening_state_warnings: tuple[str, ...] = ()

    def _data(self) -> ModelResultData:
        return ModelResultData(
            company_name=self.company_name,
            ticker=self.ticker,
            as_of=self.as_of,
            forecast=self.forecast,
            ratios=self.ratios,
            dcf=self.dcf,
            sensitivity=self.sensitivity,
            assumption_summary=self.assumption_summary,
            limitations=self.limitations,
            historical=self.historical,
            historical_ratios=self.historical_ratios,
            historical_checks=self.historical_checks,
            opening_state_warnings=self.opening_state_warnings,
        )

    def export_markdown(self, path: str | Path) -> Path:
        """Export a complete Markdown report."""

        return export_markdown(self._data(), path)

    def export_excel(self, path: str | Path) -> Path:
        """Export the complete analyst-style Excel workbook."""

        return export_excel(self._data(), path)

    def export_charts(self, directory: str | Path) -> dict[str, Path]:
        """Export the six required static charts."""

        return build_charts(
            self.forecast,
            self.ratios,
            self.sensitivity,
            directory,
            historical=self.historical,
            historical_ratios=self.historical_ratios,
        )

    def export_tables(self, directory: str | Path) -> dict[str, Path]:
        """Export structured CSV tables without presentation formatting."""

        output = Path(directory)
        output.mkdir(parents=True, exist_ok=True)
        tables = {
            "income_statement": self.forecast.income_statement,
            "balance_sheet": self.forecast.balance_sheet,
            "cash_flow_statement": self.forecast.cash_flow_statement,
            "working_capital": self.forecast.working_capital,
            "fixed_assets": self.forecast.fixed_assets,
            "debt_schedule": self.forecast.debt_schedule,
            "financial_ratios": self.ratios.table,
            "dcf_forecast": self.dcf.forecast,
            "sensitivity": self.sensitivity,
        }
        if self.historical is not None:
            tables.update(
                {
                    f"historical_{name}": table
                    for name, table in self.historical.statements.items()
                }
            )
            tables["historical_provenance"] = self.historical.provenance_frame()
            tables["historical_data_quality"] = self.historical.quality_frame()
            if self.historical_ratios is not None:
                tables["historical_financial_ratios"] = self.historical_ratios.table
        paths = {}
        for name, table in tables.items():
            path = output / f"{name}.csv"
            table.to_csv(path)
            paths[name] = path
        return paths
