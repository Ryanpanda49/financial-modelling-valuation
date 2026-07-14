"""Static, non-commercial financial charts."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from fmva.analysis.ratios import RatioResult
from fmva.data.statement_builder import HistoricalStatements
from fmva.forecasting.three_statement import ForecastResult


def build_charts(
    forecast: ForecastResult,
    ratios: RatioResult,
    sensitivity: pd.DataFrame,
    output_directory: str | Path,
    historical: HistoricalStatements | None = None,
    historical_ratios: RatioResult | None = None,
) -> dict[str, Path]:
    """Create the six required PNG charts and return stable names to paths."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(output / ".mplconfig"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.style.use("seaborn-v0_8-whitegrid")
    colors = {"primary": "#17365D", "secondary": "#5B9BD5", "accent": "#2F75B5"}
    paths: dict[str, Path] = {}

    def save(name: str) -> Path:
        path = output / f"{name}.png"
        plt.tight_layout()
        plt.savefig(path, dpi=160, bbox_inches="tight")
        plt.close()
        paths[name] = path
        return path

    years = forecast.income_statement.columns
    historical_years = (
        historical.statements["income_statement"].columns
        if historical is not None and "income_statement" in historical.statements
        else []
    )

    def add_forecast_region() -> None:
        if len(historical_years) > 0:
            boundary = (float(historical_years[-1]) + float(years[0])) / 2.0
            plt.axvline(boundary, color=colors["secondary"], linestyle="--", linewidth=1)
            plt.axvspan(boundary, float(years[-1]) + 0.5, color="#EAF3F8", alpha=0.45)
    plt.figure(figsize=(8, 4.5))
    revenue = _historical_forecast_series(
        historical.statements["income_statement"].loc["revenue"] if historical is not None else None,
        forecast.income_statement.loc["revenue"],
    )
    plt.plot(revenue.index, revenue, marker="o", color=colors["primary"])
    add_forecast_region()
    plt.title("Revenue Trend — Historical and Forecast (USD millions)")
    plt.xlabel("Fiscal year")
    plt.ylabel("USD millions")
    save("revenue_trend")

    plt.figure(figsize=(8, 4.5))
    gross_margin = _historical_forecast_series(
        historical_ratios.table.loc["gross_margin"] if historical_ratios is not None else None,
        ratios.table.loc["gross_margin"],
    )
    operating_margin = _historical_forecast_series(
        historical_ratios.table.loc["operating_margin"] if historical_ratios is not None else None,
        ratios.table.loc["operating_margin"],
    )
    plt.plot(
        gross_margin.index, gross_margin * 100, marker="o",
        label="Gross margin", color=colors["secondary"],
    )
    plt.plot(
        operating_margin.index, operating_margin * 100, marker="o",
        label="Operating margin", color=colors["primary"],
    )
    add_forecast_region()
    plt.title("Gross and Operating Margin — Historical and Forecast")
    plt.xlabel("Fiscal year")
    plt.ylabel("Percent")
    plt.legend()
    save("margin_trend")

    plt.figure(figsize=(8, 4.5))
    net_income = _historical_forecast_series(
        historical.statements["income_statement"].loc["net_income"] if historical is not None else None,
        forecast.income_statement.loc["net_income"],
    )
    plt.bar(net_income.index, net_income, color=colors["secondary"])
    add_forecast_region()
    plt.title("Net Income — Historical and Forecast (USD millions)")
    plt.xlabel("Fiscal year")
    plt.ylabel("USD millions")
    save("net_income")

    cfo = forecast.cash_flow_statement.loc["cash_from_operations"]
    fcf = cfo + forecast.cash_flow_statement.loc["capital_expenditures"]
    if historical is not None:
        historical_cash_flow = historical.statements["cash_flow_statement"]
        cfo = _historical_forecast_series(
            historical_cash_flow.loc["cash_from_operations"], cfo
        )
        fcf = _historical_forecast_series(
            historical_cash_flow.loc["cash_from_operations"]
            - historical_cash_flow.loc["capital_expenditures"],
            fcf,
        )
    plt.figure(figsize=(8, 4.5))
    plt.plot(cfo.index, cfo, marker="o", label="CFO", color=colors["primary"])
    plt.plot(fcf.index, fcf, marker="o", label="FCF", color=colors["accent"])
    add_forecast_region()
    plt.title("CFO and FCF — Historical and Forecast (USD millions)")
    plt.xlabel("Fiscal year")
    plt.ylabel("USD millions")
    plt.legend()
    save("cfo_and_fcf")

    debt = forecast.balance_sheet.loc["short_term_debt"] + forecast.balance_sheet.loc["long_term_debt"]
    cash = forecast.balance_sheet.loc["cash_and_equivalents"]
    if historical is not None:
        historical_balance = historical.statements["balance_sheet"]
        cash = _historical_forecast_series(
            historical_balance.loc["cash_and_equivalents"], cash
        )
        debt = _historical_forecast_series(
            historical_balance.loc["short_term_debt"].fillna(0.0)
            + historical_balance.loc["long_term_debt"].fillna(0.0),
            debt,
        )
    plt.figure(figsize=(8, 4.5))
    plt.plot(
        cash.index, cash, marker="o",
        label="Cash", color=colors["secondary"],
    )
    plt.plot(debt.index, debt, marker="o", label="Debt", color=colors["primary"])
    add_forecast_region()
    plt.title("Cash and Debt — Historical and Forecast (USD millions)")
    plt.xlabel("Fiscal year")
    plt.ylabel("USD millions")
    plt.legend()
    save("cash_and_debt")

    plt.figure(figsize=(8, 5))
    image = plt.imshow(sensitivity.to_numpy(dtype=float), aspect="auto", cmap="Blues")
    plt.colorbar(image, label="Implied share price")
    plt.xticks(range(len(sensitivity.columns)), [f"{value:.1%}" for value in sensitivity.columns])
    plt.yticks(range(len(sensitivity.index)), [f"{value:.1%}" for value in sensitivity.index])
    plt.xlabel("Terminal growth rate")
    plt.ylabel("WACC")
    plt.title("DCF Sensitivity")
    save("dcf_sensitivity")

    return paths


def _historical_forecast_series(
    historical: pd.Series | None,
    forecast: pd.Series,
) -> pd.Series:
    if historical is None:
        return forecast.astype(float)
    return pd.concat([historical.astype(float), forecast.astype(float)])
