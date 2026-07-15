from datetime import date

import pytest

from fmva.data.business_kpis import BusinessKpiHistory, BusinessKpiRecord
from fmva.data.statement_builder import HistoricalStatements
from fmva.forecasting.business_drivers import (
    CostMembershipRetailModel,
    SegmentRevenueModel,
    SubscriberArpuModel,
)
from fmva.forecasting.business_model_selection import (
    BusinessModelRecommender,
    build_business_driver_draft,
)

YEARS = (2026, 2027, 2028, 2029, 2030)


def record(
    metric: str,
    dimension: str,
    fiscal_year: int,
    value: float,
    unit: str,
) -> BusinessKpiRecord:
    return BusinessKpiRecord(
        metric=metric,
        dimension=dimension,
        fiscal_year=fiscal_year,
        value=value,
        unit=unit,
        source_name="Test public filing",
        source_url="https://www.sec.gov/example",
        source_document="Synthetic regression record",
        filing_date=date(2025, 7, 30),
        confidence="HIGH",
        is_direct=True,
        is_restated=False,
        notes="Synthetic test only.",
    )


def test_recommender_ranks_msft_segment_model_without_auto_selecting() -> None:
    history = HistoricalStatements.read_json("data/sample/msft_fy2021_2025_history.json")
    kpis = BusinessKpiHistory.from_tabular(
        "data/sample/msft_business_kpis_fy2023_2025.csv"
    )

    recommendation = BusinessModelRecommender().recommend(history, kpis)

    assert recommendation.selection_policy == "researcher_confirmation_required"
    assert recommendation.candidates[0].model_type == "segment_revenue"
    assert recommendation.candidates[0].score == pytest.approx(1.0)
    assert recommendation.candidates[0].readiness == "READY"
    assert all(candidate.requires_researcher_confirmation for candidate in recommendation.candidates)


def test_segment_draft_is_loadable_and_reconciles_to_history(tmp_path) -> None:
    history = HistoricalStatements.read_json("data/sample/msft_fy2021_2025_history.json")
    kpis = BusinessKpiHistory.from_tabular(
        "data/sample/msft_business_kpis_fy2023_2025.csv"
    )

    draft = build_business_driver_draft("segment_revenue", history, kpis, YEARS)
    path = draft.write_yaml(tmp_path / "segment_draft.yaml")
    model = SegmentRevenueModel.from_yaml(path)

    assert sum(model.inputs.opening_revenue.values()) == pytest.approx(281724.0)
    assert draft.payload["draft_metadata"]["status"] == "RESEARCHER_REVIEW_REQUIRED"


def test_subscriber_draft_derives_arpu_and_discloses_residual(tmp_path) -> None:
    history = HistoricalStatements.read_json("data/sample/msft_fy2021_2025_history.json")
    kpis = BusinessKpiHistory(
        tuple(
            record(metric, "consumer", year, value, unit)
            for metric, year, value, unit in (
                ("subscribers_millions", 2024, 82.5, "millions"),
                ("subscribers_millions", 2025, 89.0, "millions"),
                ("subscription_revenue", 2024, 8000.0, "USD millions"),
                ("subscription_revenue", 2025, 8900.0, "USD millions"),
            )
        )
    )

    recommendation = BusinessModelRecommender().recommend(history, kpis)
    subscriber = next(
        item for item in recommendation.candidates if item.model_type == "subscriber_arpu"
    )
    draft = build_business_driver_draft("subscriber_arpu", history, kpis, YEARS)
    model = SubscriberArpuModel.from_yaml(draft.write_yaml(tmp_path / "subscriber.yaml"))

    assert subscriber.readiness == "READY"
    assert model.inputs.opening_arpu["consumer"] == pytest.approx(100.0)
    assert model.inputs.opening_residual_revenue["all_other_revenue"] == pytest.approx(
        272824.0
    )
    assert any("ARPU derived" in warning for warning in draft.warnings)


def test_store_membership_draft_reconstructs_cost_opening_bridge(tmp_path) -> None:
    history = HistoricalStatements.read_json("data/sample/cost_fy2021_2025_history.json")
    values = (
        ("warehouse_count", 2024, 890.0, "count"),
        ("warehouse_count", 2025, 914.0, "count"),
        ("paid_members_millions", 2024, 76.0, "millions"),
        ("paid_members_millions", 2025, 81.0, "millions"),
        ("membership_fee_revenue", 2024, 4828.0, "USD millions"),
        ("membership_fee_revenue", 2025, 5310.0, "USD millions"),
        ("comparable_sales_growth", 2025, 0.05, "percent"),
        ("renewal_rate", 2025, 0.93, "percent"),
        ("executive_member_mix", 2025, 0.475, "percent"),
        ("new_warehouse_productivity", 2025, 0.55, "percent"),
    )
    kpis = BusinessKpiHistory(
        tuple(record(metric, "consolidated", year, value, unit) for metric, year, value, unit in values)
    )

    draft = build_business_driver_draft("cost_membership_retail", history, kpis, YEARS)
    model = CostMembershipRetailModel.from_yaml(draft.write_yaml(tmp_path / "cost.yaml"))

    opening = (
        model.inputs.starting_merchandise_revenue
        + model.inputs.starting_paid_members * model.inputs.starting_effective_fee
    )
    assert opening == pytest.approx(275235.0)
    assert model.inputs.starting_warehouses == 914.0
