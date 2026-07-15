"""Explainable business-model recommendations and researcher-reviewable config drafts."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml

from fmva.data.business_kpis import BusinessKpiHistory
from fmva.data.statement_builder import HistoricalStatements
from fmva.exceptions import ConfigurationError, HistoricalDataError

SEGMENT_REVENUE = ("segment_revenue",)
SEGMENT_COGS = ("segment_cogs",)
STORE_COUNT = ("warehouse_count", "warehouses", "store_count")
PAID_MEMBERS = ("paid_members_millions", "paid_members")
MEMBERSHIP_REVENUE = ("membership_fee_revenue", "membership_revenue")
EFFECTIVE_FEE = ("effective_fee_usd", "annual_membership_fee_usd")
SUBSCRIBERS = ("subscribers_millions", "paid_subscribers_millions", "seats_millions")
ANNUAL_ARPU = ("annual_arpu_usd", "arpu_usd")
SUBSCRIPTION_REVENUE = ("subscription_revenue",)


@dataclass(frozen=True, slots=True)
class BusinessModelCandidate:
    """One ranked model candidate with evidence and unresolved data requirements."""

    model_type: str
    score: float
    readiness: str
    evidence: tuple[str, ...]
    data_gaps: tuple[str, ...]
    requires_researcher_confirmation: bool = True


@dataclass(frozen=True, slots=True)
class BusinessModelRecommendation:
    """Ranked candidates; deliberately does not make an automatic final selection."""

    candidates: tuple[BusinessModelCandidate, ...]
    selection_policy: str = "researcher_confirmation_required"

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    **asdict(candidate),
                    "evidence": "; ".join(candidate.evidence),
                    "data_gaps": "; ".join(candidate.data_gaps),
                }
                for candidate in self.candidates
            ]
        )


@dataclass(frozen=True, slots=True)
class BusinessDriverDraft:
    """Generated YAML payload that remains explicitly subject to researcher review."""

    model_type: str
    payload: dict[str, Any]
    warnings: tuple[str, ...]

    def write_yaml(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(self.payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return target


class BusinessModelRecommender:
    """Score model archetypes from available history without silently selecting one."""

    def recommend(
        self,
        history: HistoricalStatements,
        kpis: BusinessKpiHistory | None = None,
    ) -> BusinessModelRecommendation:
        frame = kpis.to_frame() if kpis is not None else pd.DataFrame()
        metrics = set(frame["metric"].astype(str)) if not frame.empty else set()
        candidates = [
            self._top_down(history),
            self._segment(history, frame, metrics),
            self._store_membership(frame, metrics),
            self._subscriber_arpu(frame, metrics),
        ]
        return BusinessModelRecommendation(
            tuple(sorted(candidates, key=lambda item: (-item.score, item.model_type)))
        )

    def _top_down(self, history: HistoricalStatements) -> BusinessModelCandidate:
        revenue = history.statements["income_statement"].loc["revenue"].dropna()
        score = min(0.7, 0.4 + 0.06 * len(revenue))
        gaps = () if len(revenue) >= 5 else ("At least five annual revenue observations preferred.",)
        return _candidate(
            "top_down",
            score,
            (f"{len(revenue)} annual consolidated revenue observations available.",),
            gaps,
            baseline=True,
        )

    def _segment(
        self,
        history: HistoricalStatements,
        frame: pd.DataFrame,
        metrics: set[str],
    ) -> BusinessModelCandidate:
        score = 0.0
        evidence: list[str] = []
        gaps: list[str] = []
        if _has_any(metrics, SEGMENT_REVENUE):
            revenue = frame.loc[frame["metric"].isin(SEGMENT_REVENUE)]
            dimensions = revenue["dimension"].nunique()
            years = revenue["fiscal_year"].nunique()
            score += 0.45
            evidence.append(f"Segment revenue found for {dimensions} dimensions and {years} years.")
            score += 0.15 if dimensions >= 2 else 0.0
            score += 0.10 if years >= 2 else 0.0
            latest = int(revenue["fiscal_year"].max())
            if latest in history.statements["income_statement"].columns:
                total = float(revenue.loc[revenue["fiscal_year"] == latest, "value"].sum())
                consolidated = _historical_value(history, "revenue", latest)
                difference = abs(total - consolidated)
                if difference <= max(1.0, abs(consolidated) * 0.001):
                    score += 0.15
                    evidence.append("Latest segment revenue reconciles to consolidated revenue.")
                else:
                    gaps.append("Latest segment revenue does not reconcile to consolidated revenue.")
        else:
            gaps.append("No canonical segment_revenue history.")
        if _has_any(metrics, SEGMENT_COGS):
            score += 0.15
            evidence.append("Segment COGS history is available.")
        else:
            gaps.append("Segment COGS is missing; segment margin forecast needs research input.")
        return _candidate("segment_revenue", score, evidence, gaps)

    def _store_membership(
        self,
        frame: pd.DataFrame,
        metrics: set[str],
    ) -> BusinessModelCandidate:
        del frame
        score = 0.0
        evidence: list[str] = []
        gaps: list[str] = []
        score += _metric_score(metrics, STORE_COUNT, 0.30, "Store/warehouse count", evidence, gaps)
        score += _metric_score(metrics, PAID_MEMBERS, 0.25, "Paid members", evidence, gaps)
        score += _metric_score(
            metrics,
            (*MEMBERSHIP_REVENUE, *EFFECTIVE_FEE),
            0.20,
            "Membership revenue or effective fee",
            evidence,
            gaps,
        )
        score += _metric_score(
            metrics,
            ("comparable_sales_growth",),
            0.15,
            "Comparable-sales growth",
            evidence,
            gaps,
        )
        score += _metric_score(
            metrics,
            ("renewal_rate",),
            0.10,
            "Membership renewal rate",
            evidence,
            gaps,
        )
        return _candidate("cost_membership_retail", score, evidence, gaps)

    def _subscriber_arpu(
        self,
        frame: pd.DataFrame,
        metrics: set[str],
    ) -> BusinessModelCandidate:
        score = 0.0
        evidence: list[str] = []
        gaps: list[str] = []
        score += _metric_score(metrics, SUBSCRIBERS, 0.40, "Subscribers or seats", evidence, gaps)
        score += _metric_score(
            metrics,
            (*ANNUAL_ARPU, *SUBSCRIPTION_REVENUE),
            0.30,
            "ARPU or attributable subscription revenue",
            evidence,
            gaps,
        )
        if not frame.empty and _has_any(metrics, SUBSCRIBERS):
            subscriber = frame.loc[frame["metric"].isin(SUBSCRIBERS)]
            if subscriber["fiscal_year"].nunique() >= 2:
                score += 0.15
                evidence.append("At least two subscriber history periods are available.")
            else:
                gaps.append("Subscriber growth history has fewer than two periods.")
            if subscriber["dimension"].nunique() >= 1:
                score += 0.05
        score += _metric_score(
            metrics,
            ("subscriber_churn", "retention_rate"),
            0.10,
            "Churn or retention",
            evidence,
            gaps,
        )
        return _candidate("subscriber_arpu", score, evidence, gaps)


def build_business_driver_draft(
    model_type: str,
    history: HistoricalStatements,
    kpis: BusinessKpiHistory,
    forecast_years: tuple[int, ...],
) -> BusinessDriverDraft:
    """Generate an explicit draft; the caller must choose the model type first."""

    if not forecast_years or tuple(sorted(set(forecast_years))) != forecast_years:
        raise ConfigurationError("Draft forecast years must be unique and increasing.")
    if model_type == "segment_revenue":
        return _segment_draft(history, kpis, forecast_years)
    if model_type == "subscriber_arpu":
        return _subscriber_draft(history, kpis, forecast_years)
    if model_type == "cost_membership_retail":
        return _store_draft(history, kpis, forecast_years)
    raise ConfigurationError(
        "Business-driver drafts support segment_revenue, subscriber_arpu, and "
        "cost_membership_retail; Top-down assumptions use the central forecast YAML."
    )


def _segment_draft(
    history: HistoricalStatements,
    kpis: BusinessKpiHistory,
    years: tuple[int, ...],
) -> BusinessDriverDraft:
    revenue = _metric_alias_frame(kpis, SEGMENT_REVENUE)
    if len(revenue.index) < 2:
        raise HistoricalDataError("Segment draft requires at least two segment dimensions.")
    latest_year = int(max(revenue.columns))
    consolidated = _historical_value(history, "revenue", latest_year)
    opening_total = float(revenue[latest_year].sum())
    _require_reconciliation("segment revenue", opening_total, consolidated)
    cogs = _metric_alias_frame(kpis, SEGMENT_COGS)
    warnings: list[str] = [
        "Historical CAGR and latest cost ratios are held flat across forecast years; review required."
    ]
    opening_segments: dict[str, dict[str, float]] = {}
    growth: dict[str, dict[int, float]] = {}
    cogs_ratios: dict[str, dict[int, float]] = {}
    consolidated_cogs_ratio = _historical_value(history, "cogs", latest_year) / consolidated
    for segment in revenue.index:
        opening = float(revenue.loc[segment, latest_year])
        opening_segments[str(segment)] = {"revenue": opening}
        historical_growth = round(_cagr(revenue.loc[segment].dropna()), 6)
        growth[str(segment)] = {year: historical_growth for year in years}
        if segment in cogs.index and latest_year in cogs.columns:
            ratio = float(cogs.loc[segment, latest_year]) / opening
        else:
            ratio = consolidated_cogs_ratio
            warnings.append(
                f"{segment}: segment COGS missing; draft uses latest consolidated COGS ratio."
            )
        cogs_ratios[str(segment)] = {year: round(ratio, 6) for year in years}
    payload = _draft_header("segment_revenue", latest_year, warnings)
    payload.update(
        {
            "forecast_years": list(years),
            "opening": {"segments": opening_segments},
            "drivers": {
                "segment_revenue_growth": growth,
                "segment_cogs_as_pct_revenue": cogs_ratios,
            },
        }
    )
    return BusinessDriverDraft("segment_revenue", payload, tuple(warnings))


def _subscriber_draft(
    history: HistoricalStatements,
    kpis: BusinessKpiHistory,
    years: tuple[int, ...],
) -> BusinessDriverDraft:
    subscribers = _metric_alias_frame(kpis, SUBSCRIBERS)
    latest_year = int(max(subscribers.columns))
    arpu = _optional_metric_alias_frame(kpis, ANNUAL_ARPU)
    subscription_revenue = _optional_metric_alias_frame(kpis, SUBSCRIPTION_REVENUE)
    warnings: list[str] = [
        "Historical subscriber, ARPU, and residual run rates are held flat; review required."
    ]
    opening_businesses: dict[str, dict[str, float]] = {}
    subscriber_growth: dict[str, dict[int, float]] = {}
    arpu_growth: dict[str, dict[int, float]] = {}
    cogs_ratios: dict[str, dict[int, float]] = {}
    total_subscription_revenue = 0.0
    consolidated = _historical_value(history, "revenue", latest_year)
    consolidated_cogs_ratio = _historical_value(history, "cogs", latest_year) / consolidated
    for business in subscribers.index:
        count = float(subscribers.loc[business, latest_year])
        if arpu is not None and business in arpu.index and latest_year in arpu.columns:
            annual_arpu = float(arpu.loc[business, latest_year])
        elif (
            subscription_revenue is not None
            and business in subscription_revenue.index
            and latest_year in subscription_revenue.columns
        ):
            annual_arpu = float(subscription_revenue.loc[business, latest_year]) / count
            warnings.append(f"{business}: opening ARPU derived from subscription revenue / subscribers.")
        else:
            raise HistoricalDataError(
                f"{business}: subscriber draft requires annual ARPU or attributable revenue."
            )
        revenue = count * annual_arpu
        total_subscription_revenue += revenue
        opening_businesses[str(business)] = {
            "subscribers_millions": count,
            "annual_arpu_usd": annual_arpu,
        }
        subscriber_growth[str(business)] = {
            year: round(_cagr(subscribers.loc[business].dropna()), 6) for year in years
        }
        arpu_growth[str(business)] = {
            year: round(_cagr(arpu.loc[business].dropna()), 6)
            if arpu is not None and business in arpu.index
            else 0.0
            for year in years
        }
        cogs_ratios[str(business)] = {
            year: round(consolidated_cogs_ratio, 6) for year in years
        }
        warnings.append(f"{business}: draft uses consolidated COGS ratio pending product cost data.")
    residual = consolidated - total_subscription_revenue
    if residual < 0:
        raise HistoricalDataError("Attributed subscription revenue exceeds consolidated revenue.")
    consolidated_growth = _cagr(_historical_series(history, "revenue"))
    cogs_ratios["all_other_revenue"] = {
        year: round(consolidated_cogs_ratio, 6) for year in years
    }
    payload = _draft_header("subscriber_arpu", latest_year, warnings)
    payload.update(
        {
            "forecast_years": list(years),
            "opening": {
                "subscriber_businesses": opening_businesses,
                "residual_businesses": {"all_other_revenue": {"revenue": residual}},
            },
            "drivers": {
                "subscriber_growth": subscriber_growth,
                "arpu_growth": arpu_growth,
                "residual_revenue_growth": {
                    "all_other_revenue": {
                        year: round(consolidated_growth, 6) for year in years
                    }
                },
                "business_cogs_as_pct_revenue": cogs_ratios,
            },
        }
    )
    return BusinessDriverDraft("subscriber_arpu", payload, tuple(warnings))


def _store_draft(
    history: HistoricalStatements,
    kpis: BusinessKpiHistory,
    years: tuple[int, ...],
) -> BusinessDriverDraft:
    stores = _metric_alias_frame(kpis, STORE_COUNT)
    members = _metric_alias_frame(kpis, PAID_MEMBERS)
    latest_year = min(int(max(stores.columns)), int(max(members.columns)))
    store_series = stores.sum(axis=0).dropna().sort_index()
    member_series = members.sum(axis=0).dropna().sort_index()
    membership_revenue = _optional_metric_alias_frame(kpis, MEMBERSHIP_REVENUE)
    effective_fee = _optional_metric_alias_frame(kpis, EFFECTIVE_FEE)
    paid_members = float(member_series.loc[latest_year])
    warnings: list[str] = [
        "Historical store/member run rates are held flat across forecast years; review required."
    ]
    if membership_revenue is not None and latest_year in membership_revenue.columns:
        fee_revenue = float(membership_revenue[latest_year].sum())
        fee = fee_revenue / paid_members
    elif effective_fee is not None and latest_year in effective_fee.columns:
        fee = float(effective_fee[latest_year].mean())
        fee_revenue = paid_members * fee
    else:
        raise HistoricalDataError(
            "Store/membership draft requires membership revenue or effective fee history."
        )
    consolidated = _historical_value(history, "revenue", latest_year)
    merchandise_revenue = consolidated - fee_revenue
    if merchandise_revenue <= 0:
        raise HistoricalDataError("Membership revenue must be below consolidated revenue.")
    store_changes = store_series.diff().dropna()
    new_stores = float(store_changes.mean()) if not store_changes.empty else 0.0
    if new_stores < 0:
        warnings.append("Historical average store change is negative; draft sets new stores to zero.")
        new_stores = 0.0
    comparable = _optional_metric_alias_frame(kpis, ("comparable_sales_growth",))
    if comparable is not None and latest_year in comparable.columns:
        comparable_growth = float(comparable[latest_year].mean())
    else:
        comparable_growth = _cagr(_historical_series(history, "revenue"))
        warnings.append("Comparable-sales KPI missing; draft uses consolidated revenue CAGR.")
    renewal = _latest_optional(kpis, ("renewal_rate",), latest_year, 0.90, warnings)
    executive_mix = _latest_optional(
        kpis, ("executive_member_mix",), latest_year, 0.0, warnings
    )
    productivity = _latest_optional(
        kpis, ("new_warehouse_productivity",), latest_year, 0.5, warnings
    )
    consolidated_cogs = _historical_value(history, "cogs", latest_year)
    merchandise_cogs_ratio = min(1.0, consolidated_cogs / merchandise_revenue)
    payload = _draft_header("cost_membership_retail", latest_year, warnings)
    payload.update(
        {
            "forecast_years": list(years),
            "opening": {
                "warehouses": float(store_series.loc[latest_year]),
                "merchandise_revenue": merchandise_revenue,
                "paid_members_millions": paid_members,
                "effective_fee_usd": fee,
            },
            "drivers": {
                "new_warehouses": {year: new_stores for year in years},
                "comparable_sales_growth": {
                    year: round(comparable_growth, 6) for year in years
                },
                "new_warehouse_productivity": {year: productivity for year in years},
                "paid_member_growth": {
                    year: round(_cagr(member_series), 6) for year in years
                },
                "effective_fee_growth": {
                    year: round(_cagr(effective_fee.sum(axis=0).dropna()), 6)
                    if effective_fee is not None
                    else 0.0
                    for year in years
                },
                "executive_member_mix": {year: executive_mix for year in years},
                "renewal_rate": {year: renewal for year in years},
                "merchandise_cogs_as_pct_sales": {
                    year: round(merchandise_cogs_ratio, 6) for year in years
                },
            },
        }
    )
    return BusinessDriverDraft("cost_membership_retail", payload, tuple(warnings))


def _candidate(
    model_type: str,
    score: float,
    evidence: list[str] | tuple[str, ...],
    gaps: list[str] | tuple[str, ...],
    *,
    baseline: bool = False,
) -> BusinessModelCandidate:
    bounded = max(0.0, min(1.0, score))
    readiness = "BASELINE" if baseline else "READY" if bounded >= 0.8 else "PARTIAL" if bounded >= 0.4 else "INSUFFICIENT"
    return BusinessModelCandidate(
        model_type=model_type,
        score=bounded,
        readiness=readiness,
        evidence=tuple(evidence),
        data_gaps=tuple(gaps),
    )


def _metric_score(
    metrics: set[str],
    aliases: tuple[str, ...],
    weight: float,
    label: str,
    evidence: list[str],
    gaps: list[str],
) -> float:
    matched = sorted(metrics & set(aliases))
    if matched:
        evidence.append(f"{label}: {', '.join(matched)}.")
        return weight
    gaps.append(f"{label} KPI is missing.")
    return 0.0


def _has_any(metrics: set[str], aliases: tuple[str, ...]) -> bool:
    return bool(metrics & set(aliases))


def _metric_alias_frame(kpis: BusinessKpiHistory, aliases: tuple[str, ...]) -> pd.DataFrame:
    frame = _optional_metric_alias_frame(kpis, aliases)
    if frame is None:
        raise HistoricalDataError(f"Required business KPI missing; expected one of {aliases}.")
    return frame


def _optional_metric_alias_frame(
    kpis: BusinessKpiHistory,
    aliases: tuple[str, ...],
) -> pd.DataFrame | None:
    long = kpis.to_frame()
    for metric in aliases:
        selected = long.loc[long["metric"] == metric]
        if not selected.empty:
            return selected.pivot(index="dimension", columns="fiscal_year", values="value")
    return None


def _historical_value(history: HistoricalStatements, account: str, year: int) -> float:
    frame = history.statements["income_statement"]
    if account not in frame.index or year not in frame.columns:
        raise HistoricalDataError(f"Historical {account} is unavailable for FY{year}.")
    value = float(cast(Any, frame.loc[account, year]))
    if not math.isfinite(value):
        raise HistoricalDataError(f"Historical {account} is not finite for FY{year}.")
    return value


def _cagr(series: pd.Series) -> float:
    clean = series.dropna().sort_index()
    if len(clean) < 2:
        return 0.0
    first = float(clean.iloc[0])
    last = float(clean.iloc[-1])
    periods = int(clean.index[-1]) - int(clean.index[0])
    if first <= 0 or last < 0 or periods <= 0:
        raise HistoricalDataError("Historical CAGR requires positive opening and valid periods.")
    return float((last / first) ** (1.0 / periods) - 1.0)


def _historical_series(history: HistoricalStatements, account: str) -> pd.Series:
    frame = history.statements["income_statement"]
    if account not in frame.index:
        raise HistoricalDataError(f"Historical {account} is unavailable.")
    return pd.Series(cast(Any, frame.loc[account])).dropna()


def _require_reconciliation(name: str, actual: float, expected: float) -> None:
    tolerance = max(1.0, abs(expected) * 0.001)
    if abs(actual - expected) > tolerance:
        raise HistoricalDataError(
            f"Latest {name} does not reconcile: mapped={actual:.2f}, consolidated={expected:.2f}."
        )


def _draft_header(model_type: str, latest_year: int, warnings: list[str]) -> dict[str, Any]:
    return {
        "model_type": model_type,
        "draft_metadata": {
            "status": "RESEARCHER_REVIEW_REQUIRED",
            "selection_method": "researcher_confirmed_model_type",
            "assumption_basis": "historical_run_rate_not_company_guidance",
            "opening_fiscal_year": latest_year,
            "warnings": warnings,
        },
    }


def _latest_optional(
    kpis: BusinessKpiHistory,
    aliases: tuple[str, ...],
    year: int,
    fallback: float,
    warnings: list[str],
) -> float:
    frame = _optional_metric_alias_frame(kpis, aliases)
    if frame is not None and year in frame.columns:
        return float(frame[year].mean())
    warnings.append(f"{aliases[0]} missing; draft placeholder {fallback:.4f} requires review.")
    return fallback
