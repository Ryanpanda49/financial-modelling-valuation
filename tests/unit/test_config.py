from pathlib import Path

import pytest

from fmva.config.loader import load_config
from fmva.config.models import SecConfig
from fmva.exceptions import ConfigurationError


def test_placeholder_user_agent_is_rejected_for_live_requests() -> None:
    with pytest.raises(ConfigurationError, match="real name"):
        SecConfig(user_agent="Your Name your.email@example.com").validate_for_live_requests()


def test_example_config_is_valid_offline() -> None:
    config = load_config(Path("config/model_config.example.yaml"), live_sec=False)
    assert config.model.historical_years == 5
