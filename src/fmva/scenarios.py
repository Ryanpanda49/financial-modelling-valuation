"""Typed scenario-set configuration for repeatable multi-case model runs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from fmva.exceptions import ConfigurationError


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    """One named forecast and valuation assumption combination."""

    name: str
    slug: str
    forecast_assumptions_path: Path
    valuation_assumptions_path: Path
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ScenarioSet:
    """Ordered, validated collection of model cases."""

    name: str
    scenarios: tuple[ScenarioDefinition, ...]

    @classmethod
    def from_yaml(cls, path: str | Path) -> ScenarioSet:
        """Load scenario paths relative to the scenario-set YAML file."""

        config_path = Path(path)
        try:
            payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("root must be a mapping")
            raw_scenarios = payload["scenarios"]
            if not isinstance(raw_scenarios, list) or not raw_scenarios:
                raise TypeError("scenarios must be a non-empty list")
            scenarios = tuple(
                _scenario_from_mapping(item, config_path.parent)
                for item in raw_scenarios
            )
            name = str(payload.get("name") or config_path.stem)
        except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
            raise ConfigurationError(f"Invalid scenario set: {config_path}") from exc
        slugs = [item.slug for item in scenarios]
        if len(set(slugs)) != len(slugs):
            raise ConfigurationError("Scenario names must produce unique slugs.")
        return cls(name=name, scenarios=scenarios)


def _scenario_from_mapping(value: object, base: Path) -> ScenarioDefinition:
    if not isinstance(value, dict):
        raise TypeError("scenario must be a mapping")
    name = str(value["name"]).strip()
    if not name:
        raise ValueError("scenario name is required")
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not slug:
        raise ValueError("scenario name must contain a letter or number")
    forecast = _resolve_path(base, value["forecast_assumptions"])
    valuation = _resolve_path(base, value["valuation_assumptions"])
    for assumption_path in (forecast, valuation):
        if not assumption_path.is_file():
            raise ValueError(f"scenario assumption file does not exist: {assumption_path}")
    description = value.get("description")
    return ScenarioDefinition(
        name=name,
        slug=slug,
        forecast_assumptions_path=forecast,
        valuation_assumptions_path=valuation,
        description=None if description in (None, "") else str(description),
    )


def _resolve_path(base: Path, value: object) -> Path:
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else (base / path).resolve()
