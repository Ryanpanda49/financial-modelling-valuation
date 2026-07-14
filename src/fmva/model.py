"""High-level research workflow from standardized SEC history to valuation outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fmva.analysis.ratios import calculate_financial_ratios, calculate_historical_ratios
from fmva.checks.historical import HistoricalCheckSuite
from fmva.checks.models import CheckResult
from fmva.config.loader import load_config
from fmva.data.account_mapping import AccountMap, AccountMapper
from fmva.data.statement_builder import HistoricalStatements, StatementBuilder
from fmva.data.tabular_import import import_canonical_history
from fmva.exceptions import HistoricalDataError
from fmva.forecasting.assumptions import ForecastAssumptions
from fmva.forecasting.business_drivers import load_business_driver_model
from fmva.forecasting.history_adapter import OpeningStateResult, historical_to_initial_state
from fmva.forecasting.operating import OperatingModel
from fmva.forecasting.three_statement import ThreeStatementModel
from fmva.output import ModelResult
from fmva.output.assumptions import summarize_assumptions, summarize_valuation_assumptions
from fmva.sec.client import SecClient
from fmva.sec.company_facts import CompanyFacts
from fmva.sec.company_registry import CompanyIdentity, CompanyRegistry
from fmva.valuation.dcf import value_dcf
from fmva.valuation.models import ValuationAssumptions
from fmva.valuation.sensitivity import wacc_terminal_growth_sensitivity


@dataclass(frozen=True, slots=True)
class ValuationModel:
    """Orchestrate history, forecast, analysis, DCF, checks, and public outputs."""

    company: CompanyIdentity
    history: HistoricalStatements
    opening_state: OpeningStateResult
    forecast_assumptions: ForecastAssumptions
    valuation_assumptions: ValuationAssumptions
    historical_checks: tuple[CheckResult, ...]
    operating_model: OperatingModel | None = None

    @classmethod
    def from_sec(
        cls,
        ticker: str,
        config_path: str | Path,
        *,
        forecast_assumptions_path: str | Path = "config/forecast_assumptions.example.yaml",
        valuation_assumptions_path: str | Path = "config/valuation_assumptions.example.yaml",
        account_mapping_path: str | Path = "config/account_mapping.yaml",
        business_driver_path: str | Path | None = None,
    ) -> ValuationModel:
        """Fetch live SEC data and construct a ready-to-run model.

        A real contact-bearing SEC User-Agent is mandatory and validated before any request.
        """

        config = load_config(config_path, live_sec=True)
        client = SecClient(config.sec)
        company = CompanyRegistry(client).get_company(ticker)
        facts = CompanyFacts.from_sec_payload(client.company_facts(company.cik))
        history = StatementBuilder(
            AccountMapper(AccountMap.from_yaml(account_mapping_path))
        ).build(facts, years=config.model.historical_years)
        return cls.from_history(
            company=company,
            history=history,
            forecast_assumptions_path=forecast_assumptions_path,
            valuation_assumptions_path=valuation_assumptions_path,
            tolerance=config.model.absolute_tolerance,
            business_driver_path=business_driver_path,
        )

    @classmethod
    def from_history(
        cls,
        *,
        company: CompanyIdentity,
        history: HistoricalStatements,
        forecast_assumptions_path: str | Path,
        valuation_assumptions_path: str | Path,
        tolerance: float = 1e-6,
        business_driver_path: str | Path | None = None,
    ) -> ValuationModel:
        """Construct the workflow from standardized history for offline/reproducible use."""

        forecast_assumptions = ForecastAssumptions.from_yaml(forecast_assumptions_path)
        valuation_assumptions = ValuationAssumptions.from_yaml(valuation_assumptions_path)
        opening = historical_to_initial_state(history, tolerance=tolerance)
        if forecast_assumptions.years[0] != opening.fiscal_year + 1:
            raise ValueError(
                "Forecast assumptions must start immediately after the latest opening fiscal year."
            )
        checks = HistoricalCheckSuite(absolute_tolerance=tolerance).run(history)
        return cls(
            company=company,
            history=history,
            opening_state=opening,
            forecast_assumptions=forecast_assumptions,
            valuation_assumptions=valuation_assumptions,
            historical_checks=checks,
            operating_model=(
                load_business_driver_model(business_driver_path)
                if business_driver_path is not None
                else None
            ),
        )

    @classmethod
    def from_history_json(
        cls,
        history_path: str | Path,
        *,
        forecast_assumptions_path: str | Path,
        valuation_assumptions_path: str | Path,
        tolerance: float = 1e-6,
        business_driver_path: str | Path | None = None,
    ) -> ValuationModel:
        """Construct an offline workflow from a versioned standardized-history snapshot."""

        input_path = Path(history_path)
        try:
            payload = json.loads(input_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("root must be an object")
            metadata = _metadata_mapping(payload.get("metadata"))
            company = CompanyIdentity(
                ticker=str(metadata["ticker"]).upper(),
                cik=f"{int(metadata['cik']):010d}",
                name=str(metadata["company_name"]),
                fiscal_year_end=_optional_metadata(metadata.get("fiscal_year_end")),
                sic=_optional_metadata(metadata.get("sic")),
                sic_description=_optional_metadata(metadata.get("sic_description")),
                entity_type=_optional_metadata(metadata.get("entity_type")),
                filings_url=str(metadata["filings_url"]),
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise HistoricalDataError(
                f"Historical snapshot lacks valid company metadata: {input_path}"
            ) from exc
        return cls.from_history(
            company=company,
            history=HistoricalStatements.from_dict(payload),
            forecast_assumptions_path=forecast_assumptions_path,
            valuation_assumptions_path=valuation_assumptions_path,
            tolerance=tolerance,
            business_driver_path=business_driver_path,
        )

    @classmethod
    def from_tabular_history(
        cls,
        history_path: str | Path,
        *,
        forecast_assumptions_path: str | Path,
        valuation_assumptions_path: str | Path,
        account_mapping_path: str | Path = "config/account_mapping.yaml",
        tolerance: float = 1e-6,
        business_driver_path: str | Path | None = None,
    ) -> ValuationModel:
        """Construct an offline workflow from canonical CSV or Excel history."""

        imported = import_canonical_history(
            history_path,
            account_mapping_path=account_mapping_path,
        )
        return cls.from_history(
            company=imported.company,
            history=imported.history,
            forecast_assumptions_path=forecast_assumptions_path,
            valuation_assumptions_path=valuation_assumptions_path,
            tolerance=tolerance,
            business_driver_path=business_driver_path,
        )

    def run(self) -> ModelResult:
        """Run linked statements, ratios, DCF, sensitivity, and structured checks."""

        state = self.opening_state.state
        forecast = ThreeStatementModel(self.operating_model).run(state, self.forecast_assumptions)
        historical_ratios = calculate_historical_ratios(self.history)
        ratios = calculate_financial_ratios(forecast, state)
        bridge = self.valuation_assumptions.with_bridge(
            debt=state.short_term_debt + state.long_term_debt,
            cash=state.cash_and_equivalents,
            diluted_shares=state.diluted_shares,
        )
        dcf = value_dcf(forecast, bridge)
        wacc_values = [dcf.wacc + offset for offset in (-0.02, -0.01, 0.0, 0.01, 0.02)]
        growth = bridge.terminal_growth_rate
        growth_values = [growth + offset for offset in (-0.01, -0.005, 0.0, 0.005, 0.01)]
        sensitivity = wacc_terminal_growth_sensitivity(
            forecast,
            bridge,
            wacc_values,
            growth_values,
        )
        limitations: tuple[str, ...] = (
            "Standardized SEC tags may require company-specific overrides and analyst review.",
            "Residual other-assets, other-liabilities, and contributed-equity buckets are disclosed.",
            "Forecast assumptions and market inputs are researcher judgments, not investment advice.",
        )
        if self.operating_model is not None:
            limitations += (
                "Business operating drivers are illustrative researcher inputs and are not company guidance.",
            )
        return ModelResult(
            company_name=self.company.name,
            ticker=self.company.ticker,
            as_of=f"FY{state.fiscal_year}",
            forecast=forecast,
            ratios=ratios,
            dcf=dcf,
            sensitivity=sensitivity,
            assumption_summary=[
                *summarize_assumptions(self.forecast_assumptions),
                *summarize_valuation_assumptions(bridge, historical_bridge=True),
            ],
            limitations=limitations,
            historical=self.history,
            historical_ratios=historical_ratios,
            historical_checks=self.historical_checks,
            opening_state_warnings=self.opening_state.warnings,
        )


def _metadata_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("metadata must be an object")
    return value


def _optional_metadata(value: object) -> str | None:
    return None if value in (None, "") else str(value)
