"""YAML configuration loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fmva.config.models import AppConfig, ModelConfig, SecConfig
from fmva.exceptions import ConfigurationError


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration section '{name}' must be a mapping.")
    return value


def load_config(path: str | Path, *, live_sec: bool = False) -> AppConfig:
    """Load and validate an application YAML file."""

    config_path = Path(path)
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"Cannot read configuration: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML configuration: {config_path}") from exc
    root = _mapping(payload, "root")
    sec_raw = _mapping(root.get("sec"), "sec")
    model_raw = _mapping(root.get("model"), "model")
    try:
        sec = SecConfig(
            user_agent=str(sec_raw["user_agent"]),
            timeout_seconds=float(sec_raw.get("timeout_seconds", 30)),
            max_retries=int(sec_raw.get("max_retries", 3)),
            requests_per_second=float(sec_raw.get("requests_per_second", 5)),
            cache_enabled=bool(sec_raw.get("cache_enabled", True)),
            cache_directory=Path(sec_raw.get("cache_directory", "data/cache/sec")),
            cache_ttl_seconds=int(sec_raw.get("cache_ttl_seconds", 86_400)),
        )
        model = ModelConfig(
            currency=str(model_raw.get("currency", "USD")),
            scale=str(model_raw.get("scale", "millions")),
            historical_years=int(model_raw.get("historical_years", 5)),
            forecast_years=int(model_raw.get("forecast_years", 5)),
            absolute_tolerance=float(model_raw.get("absolute_tolerance", 1e-6)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid configuration value in {config_path}") from exc
    result = AppConfig(sec=sec, model=model)
    result.validate(live_sec=live_sec)
    return result
