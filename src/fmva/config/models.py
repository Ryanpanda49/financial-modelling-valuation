"""Typed application configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from fmva.exceptions import ConfigurationError

PLACEHOLDER_TOKENS = ("your name", "your.email", "example.com", "changeme")
EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


@dataclass(frozen=True, slots=True)
class SecConfig:
    """SEC request policy and cache settings."""

    user_agent: str
    timeout_seconds: float = 30.0
    max_retries: int = 3
    requests_per_second: float = 5.0
    cache_enabled: bool = True
    cache_directory: Path = Path("data/cache/sec")
    cache_ttl_seconds: int = 86_400

    def validate_for_live_requests(self) -> None:
        """Reject missing or placeholder contact details before contacting SEC."""

        normalized = self.user_agent.strip().lower()
        if not self.user_agent.strip() or any(token in normalized for token in PLACEHOLDER_TOKENS):
            raise ConfigurationError(
                "SEC user_agent must contain a real name and monitored email address; "
                "replace the placeholder in your private model_config.yaml."
            )
        if EMAIL_PATTERN.search(self.user_agent) is None:
            raise ConfigurationError("SEC user_agent must include a valid contact email address.")
        if self.timeout_seconds <= 0:
            raise ConfigurationError("SEC timeout_seconds must be positive.")
        if self.max_retries < 0:
            raise ConfigurationError("SEC max_retries cannot be negative.")
        if not 0 < self.requests_per_second <= 10:
            raise ConfigurationError("SEC requests_per_second must be greater than 0 and at most 10.")
        if self.cache_ttl_seconds < 0:
            raise ConfigurationError("SEC cache_ttl_seconds cannot be negative.")


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Core model conventions."""

    currency: str = "USD"
    scale: str = "millions"
    historical_years: int = 5
    forecast_years: int = 5
    absolute_tolerance: float = 1e-6

    def validate(self) -> None:
        """Validate stable model conventions."""

        if self.currency != "USD" or self.scale != "millions":
            raise ConfigurationError("The MVP requires USD millions.")
        if self.historical_years < 5 or self.forecast_years < 1:
            raise ConfigurationError("At least five historical years and one forecast year are required.")
        if self.absolute_tolerance <= 0:
            raise ConfigurationError("absolute_tolerance must be positive.")


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Complete application configuration."""

    sec: SecConfig
    model: ModelConfig

    def validate(self, *, live_sec: bool = False) -> None:
        """Validate configuration, optionally including live SEC requirements."""

        self.model.validate()
        if live_sec:
            self.sec.validate_for_live_requests()
