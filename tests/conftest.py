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


@pytest.fixture
def mock_openai_key(monkeypatch):
    """Provide a mock OpenAI API key for tests that need it."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-mock-key-for-testing-only")
    return "sk-test-mock-key-for-testing-only"
