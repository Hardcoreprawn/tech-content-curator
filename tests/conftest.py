"""Pytest configuration and shared fixtures."""

import pytest

from src.config import _reset_config_cache


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config cache before each test to clear previous state."""
    _reset_config_cache()
    yield
    # Reset again after test to isolate tests
    _reset_config_cache()
