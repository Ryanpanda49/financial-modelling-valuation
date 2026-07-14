"""Presentation helpers for centralized forecast assumptions."""

from __future__ import annotations

from fmva.forecasting.assumptions import ForecastAssumptions
from fmva.valuation.models import ValuationAssumptions


def summarize_assumptions(assumptions: ForecastAssumptions) -> list[dict[str, object]]:
    """Build a compact, auditable output table from typed assumptions."""

    fields = (
        "revenue_growth",
        "cogs_as_pct_revenue",
        "sga_as_pct_revenue",
        "rd_as_pct_revenue",
        "other_operating_income_as_pct_revenue",
        "tax_rate",
        "dividend_payout_ratio",
        "days_sales_outstanding",
        "days_inventory_outstanding",
        "days_payables_outstanding",
        "capex_as_pct_revenue",
        "depreciation_as_pct_beginning_ppe",
        "short_term_interest_rate",
        "long_term_interest_rate",
        "minimum_cash_as_pct_revenue",
        "share_issuance",
        "share_repurchases",
    )
    return [
        {
            "Assumption": field,
            **{str(year): getattr(assumptions, field)[year] for year in assumptions.years},
            "Source": "User configuration",
        }
        for field in fields
    ]


def summarize_valuation_assumptions(
    assumptions: ValuationAssumptions,
    *,
    historical_bridge: bool = False,
) -> list[dict[str, object]]:
    """Build visible market and equity-bridge assumption records."""

    percentage_fields = {
        "risk_free_rate",
        "equity_risk_premium",
        "pre_tax_cost_of_debt",
        "target_debt_weight",
        "target_equity_weight",
        "terminal_growth_rate",
    }
    multiple_fields = {"beta", "exit_multiple"}
    records = []
    for name in assumptions.NUMERIC_FIELDS:
        value = getattr(assumptions, name)
        if name in percentage_fields:
            unit = "Percent"
        elif name in multiple_fields:
            unit = "Multiple"
        elif name == "diluted_shares":
            unit = "Millions of shares"
        else:
            unit = "USD millions"
        historical_value = historical_bridge and name in {"debt", "cash", "diluted_shares"}
        source_record = assumptions.metadata.sources.get(name)
        if historical_value:
            source = "Standardized SEC history"
            source_url = ""
            as_of = assumptions.metadata.valuation_date or "Historical fiscal year end"
            accessed = ""
            rationale = "Runtime equity-bridge value from standardized history."
            status = "HISTORICAL"
        elif source_record is not None:
            source = source_record.source_name
            source_url = source_record.source_url or ""
            as_of = source_record.as_of_date
            accessed = source_record.accessed_date
            rationale = source_record.rationale
            status = "ILLUSTRATIVE" if assumptions.metadata.is_illustrative else "SOURCED"
        else:
            source = "User valuation configuration"
            source_url = ""
            as_of = assumptions.metadata.valuation_date or "Not supplied"
            accessed = ""
            rationale = "No field-level source metadata supplied."
            status = "ILLUSTRATIVE" if assumptions.metadata.is_illustrative else "UNSOURCED"
        records.append(
            {
                "Assumption": f"valuation_{name}",
                "Value": value,
                "Unit": unit,
                "Source": source,
                "As of": as_of,
                "Accessed": accessed,
                "Source URL": source_url,
                "Rationale": rationale,
                "Status": status,
            }
        )
    return records
