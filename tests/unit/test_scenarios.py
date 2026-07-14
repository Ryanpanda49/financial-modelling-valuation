from pathlib import Path

import pytest

from fmva import ValuationModel
from fmva.exceptions import ConfigurationError
from fmva.scenarios import ScenarioSet


def test_loads_three_cost_scenarios_with_relative_paths() -> None:
    result = ScenarioSet.from_yaml("examples/cost/scenario_set.yaml")

    assert result.name == "Illustrative COST operating cases"
    assert [item.slug for item in result.scenarios] == ["base", "upside", "downside"]
    assert all(item.forecast_assumptions_path.is_file() for item in result.scenarios)


def test_duplicate_scenario_slugs_fail(tmp_path: Path) -> None:
    forecast = Path("examples/cost/forecast_assumptions.yaml").resolve()
    valuation = Path("examples/cost/valuation_assumptions.yaml").resolve()
    path = tmp_path / "scenarios.yaml"
    path.write_text(
        "scenarios:\n"
        f"  - {{name: Base Case, forecast_assumptions: '{forecast}', valuation_assumptions: '{valuation}'}}\n"
        f"  - {{name: Base-Case, forecast_assumptions: '{forecast}', valuation_assumptions: '{valuation}'}}\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="unique slugs"):
        ScenarioSet.from_yaml(path)


def test_cost_scenario_values_are_directionally_ordered() -> None:
    scenarios = ScenarioSet.from_yaml("examples/cost/scenario_set.yaml")
    base = ValuationModel.from_history_json(
        "data/sample/cost_fy2021_2025_history.json",
        forecast_assumptions_path="examples/cost/forecast_assumptions.yaml",
        valuation_assumptions_path="examples/cost/valuation_assumptions.yaml",
    )
    values = {
        scenario.slug: ValuationModel.from_history(
            company=base.company,
            history=base.history,
            forecast_assumptions_path=scenario.forecast_assumptions_path,
            valuation_assumptions_path=scenario.valuation_assumptions_path,
        ).run().dcf.implied_share_price
        for scenario in scenarios.scenarios
    }

    assert values["upside"] > values["base"] > values["downside"]
