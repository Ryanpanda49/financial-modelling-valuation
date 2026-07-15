"""Markdown research report exporter."""

from __future__ import annotations

from pathlib import Path

from fmva.output.result_types import ModelResultData


def export_markdown(data: ModelResultData, path: str | Path) -> Path:
    """Write a transparent Markdown report with required sections."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    check_rows = [
        {
            "Check": item.check,
            "Period": item.context.get("fiscal_year", "—"),
            "Difference": item.difference,
            "Tolerance": item.tolerance,
            "Status": item.status.value,
            "Message": item.message or "",
        }
        for item in (*data.historical_checks, *data.forecast.checks, *data.dcf.checks)
    ]
    checks_table = _records_to_markdown(check_rows)
    assumptions_table = _records_to_markdown(data.assumption_summary)
    sensitivity = data.sensitivity.copy()
    sensitivity.index = [f"{value:.1%}" for value in sensitivity.index]
    sensitivity.columns = [f"{value:.1%}" for value in sensitivity.columns]
    limitations = "\n".join(f"- {item}" for item in data.limitations) or "- None recorded."
    content = f"""# {data.company_name} Financial Model and Valuation

> This report is for educational and research purposes only and does not constitute investment advice.

## Company Overview

| Field | Value |
|---|---|
| Company | {data.company_name} |
| Ticker | {data.ticker} |
| As of | {data.as_of} |
| Currency | USD millions, except per-share values |
| Forecast periods | {', '.join(str(year) for year in data.forecast.income_statement.columns)} |

## Historical Financial Performance

{_historical_markdown(data)}

### Historical Financial Ratios

{_historical_ratio_markdown(data)}

## Historical Data Quality

{_historical_quality_markdown(data)}

{_business_history_markdown(data)}

## Forecast Assumptions

{assumptions_table}

{_business_driver_markdown(data)}

## Projected Financials

### Income Statement

{data.forecast.income_statement.to_markdown(floatfmt=',.2f')}

### Balance Sheet

{data.forecast.balance_sheet.to_markdown(floatfmt=',.2f')}

### Cash Flow Statement

{data.forecast.cash_flow_statement.to_markdown(floatfmt=',.2f')}

## Profitability

{_selected_ratios(data, ['gross_margin', 'ebitda_margin', 'operating_margin', 'net_margin', 'roa', 'roe', 'roic'])}

## Liquidity

{_selected_ratios(data, ['current_ratio', 'quick_ratio', 'cash_ratio'])}

## Leverage

{_selected_ratios(data, ['debt_to_equity', 'debt_to_ebitda', 'net_debt_to_ebitda', 'interest_coverage'])}

## Cash Flow

{_selected_ratios(data, ['cfo_to_net_income', 'fcf_margin', 'capex_to_revenue', 'cash_conversion_ratio'])}

## DCF Valuation

| Metric | Value |
|---|---:|
| Cost of equity | {data.dcf.cost_of_equity:.2%} |
| WACC | {data.dcf.wacc:.2%} |
| PV of forecast FCF | {data.dcf.pv_forecast_fcf:,.2f} |
| Terminal value | {data.dcf.terminal_value:,.2f} |
| PV of terminal value | {data.dcf.pv_terminal_value:,.2f} |
| Enterprise value | {data.dcf.enterprise_value:,.2f} |
| Equity value | {data.dcf.equity_value:,.2f} |
| Implied share price | {data.dcf.implied_share_price:,.2f} |

### Forecast FCF

{data.dcf.forecast.to_markdown(floatfmt=',.4f')}

### Equity Bridge

{data.dcf.equity_bridge.to_frame('Value').to_markdown(floatfmt=',.2f')}

## Sensitivity Analysis

{sensitivity.to_markdown(floatfmt=',.2f')}

## Model Checks

{checks_table}

## Ratio Warnings

{chr(10).join(f'- {warning}' for warning in data.ratios.warnings) or '- None.'}

## Limitations

{limitations}

## Opening-State Adapter Warnings

{chr(10).join(f'- {warning}' for warning in data.opening_state_warnings) or '- None.'}
"""
    target.write_text(content, encoding="utf-8")
    return target


def _selected_ratios(data: ModelResultData, names: list[str]) -> str:
    table = data.ratios.table.loc[names].copy()
    percentage = {
        "gross_margin", "ebitda_margin", "operating_margin", "net_margin", "roa", "roe", "roic",
        "fcf_margin", "capex_to_revenue", "cash_conversion_ratio",
    }
    for name in table.index:
        if name in percentage:
            table.loc[name] = table.loc[name] * 100
    return table.to_markdown(floatfmt=",.2f")


def _records_to_markdown(records: list[dict[str, object]]) -> str:
    if not records:
        return "No records."
    import pandas as pd

    return pd.DataFrame(records).to_markdown(index=False, floatfmt=",.6f")


def _historical_markdown(data: ModelResultData) -> str:
    if data.historical is None:
        return (
            "Historical SEC statements are not included in this synthetic/manual opening-state "
            "run. Missing history is disclosed rather than manufactured."
        )
    sections = []
    for name, table in data.historical.statements.items():
        sections.append(f"### {_display_name(name)}\n\n{table.to_markdown(floatfmt=',.2f')}")
    return "\n\n".join(sections)


def _business_driver_markdown(data: ModelResultData) -> str:
    if data.forecast.business_drivers is None:
        return ""
    return (
        "## Business Driver Model\n\n"
        "> Illustrative researcher inputs; not company guidance.\n\n"
        + data.forecast.business_drivers.to_markdown(floatfmt=",.4f")
    )


def _business_history_markdown(data: ModelResultData) -> str:
    if data.business_kpi_history is None:
        return ""
    return (
        "## Historical Business KPIs\n\n"
        "Reported operating metrics retain source and restatement metadata.\n\n"
        + data.business_kpi_history.to_markdown(index=False, floatfmt=",.2f")
    )


def _historical_quality_markdown(data: ModelResultData) -> str:
    if data.historical is None:
        return "No historical quality records are available for this run."
    quality = data.historical.quality_frame()
    if quality.empty:
        return "No mapping-quality issues were recorded."
    return quality.to_markdown(index=False)


def _historical_ratio_markdown(data: ModelResultData) -> str:
    if data.historical_ratios is None:
        return "No historical ratio table is available for this run."
    return data.historical_ratios.table.to_markdown(floatfmt=",.4f")


def _display_name(value: str) -> str:
    return value.replace("_", " ").title()
