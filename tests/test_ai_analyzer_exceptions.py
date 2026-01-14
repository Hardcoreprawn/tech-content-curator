"""Tests for exception handling in src.enrichment.ai_analyzer.

Goal: keep graceful degradation behavior while ensuring we don't silently swallow
unexpected response-shape issues.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.models import CollectedItem, PipelineConfig, RetryConfig, SourceType
from tests.utils.types import http_url


def _config_one_attempt() -> PipelineConfig:
    """Return a PipelineConfig with retries disabled (one attempt only)."""

    return PipelineConfig(
        openai_api_key="test",
        retries=RetryConfig(
            max_attempts=1,
            backoff_multiplier=1.0,
            backoff_min=0.01,
            backoff_max=0.01,
            jitter=0.0,
        ),
    )


def _item() -> CollectedItem:
    """Create a minimal CollectedItem for analyzer tests."""

    return CollectedItem(
        id="id1",
        title="t",
        content="c",
        source=SourceType.REDDIT,
        url=http_url("https://example.com/ok"),
        author="a",
        metadata={},
    )


def _mock_response(content: str) -> object:
    """Create a minimal OpenAI-like response object with message content."""

    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def test_analyze_content_quality_invalid_json_degrades(monkeypatch):
    """Invalid JSON response degrades instead of raising."""

    from src.enrichment.ai_analyzer import analyze_content_quality

    monkeypatch.setattr("src.config.get_config", _config_one_attempt)
    monkeypatch.setattr(
        "src.enrichment.ai_analyzer.chat_completion",
        lambda **_kwargs: _mock_response("not json"),
    )

    score, explanation = analyze_content_quality(_item(), Mock())
    assert score == 0.0
    assert "degraded" in explanation.lower()


def test_extract_topics_invalid_json_returns_empty(monkeypatch):
    """Invalid JSON response returns empty topics list."""

    from src.enrichment.ai_analyzer import extract_topics_and_themes

    monkeypatch.setattr("src.config.get_config", _config_one_attempt)
    monkeypatch.setattr(
        "src.enrichment.ai_analyzer.chat_completion",
        lambda **_kwargs: _mock_response("not json"),
    )

    topics = extract_topics_and_themes(_item(), Mock())
    assert topics == []


def test_extract_topics_wrong_shape_returns_empty(monkeypatch):
    """Non-list JSON (e.g., object) returns empty topics list."""

    from src.enrichment.ai_analyzer import extract_topics_and_themes

    monkeypatch.setattr("src.config.get_config", _config_one_attempt)
    monkeypatch.setattr(
        "src.enrichment.ai_analyzer.chat_completion",
        lambda **_kwargs: _mock_response('{"topic": "python"}'),
    )

    topics = extract_topics_and_themes(_item(), Mock())
    assert topics == []


def test_research_additional_context_openai_failure_degrades(monkeypatch):
    """OpenAI call failures degrade to fallback string."""

    from src.enrichment.ai_analyzer import research_additional_context

    monkeypatch.setattr("src.config.get_config", _config_one_attempt)

    def boom(**_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.enrichment.ai_analyzer.chat_completion", boom)

    text = research_additional_context(_item(), ["python"], Mock())
    assert text == "Research unavailable"


def test_analyze_content_quality_openai_failure_degrades(monkeypatch):
    """OpenAI call failures degrade to the standard fallback tuple."""

    from src.enrichment.ai_analyzer import analyze_content_quality

    monkeypatch.setattr("src.config.get_config", _config_one_attempt)

    def boom(**_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.enrichment.ai_analyzer.chat_completion", boom)

    score, explanation = analyze_content_quality(_item(), Mock())
    assert score == 0.0
    assert "degraded" in explanation.lower()


def test_extract_topics_openai_failure_degrades(monkeypatch):
    """OpenAI call failures return empty topics list."""

    from src.enrichment.ai_analyzer import extract_topics_and_themes

    monkeypatch.setattr("src.config.get_config", _config_one_attempt)

    def boom(**_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.enrichment.ai_analyzer.chat_completion", boom)

    topics = extract_topics_and_themes(_item(), Mock())
    assert topics == []


def test_research_additional_context_empty_content_degrades(monkeypatch):
    """Empty response content degrades to fallback string."""

    from src.enrichment.ai_analyzer import research_additional_context

    monkeypatch.setattr("src.config.get_config", _config_one_attempt)
    monkeypatch.setattr(
        "src.enrichment.ai_analyzer.chat_completion",
        lambda **_kwargs: _mock_response(""),
    )

    text = research_additional_context(_item(), ["python"], Mock())
    assert text == "Research unavailable"


def test_analyze_content_quality_missing_score_key_degrades(monkeypatch):
    """Missing required keys in JSON degrades to fallback tuple."""

    from src.enrichment.ai_analyzer import analyze_content_quality

    monkeypatch.setattr("src.config.get_config", _config_one_attempt)
    monkeypatch.setattr(
        "src.enrichment.ai_analyzer.chat_completion",
        lambda **_kwargs: _mock_response('{"explanation": "x"}'),
    )

    score, explanation = analyze_content_quality(_item(), Mock())
    assert score == 0.0
    assert "degraded" in explanation.lower()


@pytest.mark.parametrize(
    "content",
    [
        "[]",
        "[1, 2]",
        '["python", 3]',
    ],
)
def test_extract_topics_invalid_list_contents_returns_empty(monkeypatch, content: str):
    """Non-string or empty topic lists return empty list."""

    from src.enrichment.ai_analyzer import extract_topics_and_themes

    monkeypatch.setattr("src.config.get_config", _config_one_attempt)
    monkeypatch.setattr(
        "src.enrichment.ai_analyzer.chat_completion",
        lambda **_kwargs: _mock_response(content),
    )

    topics = extract_topics_and_themes(_item(), Mock())
    assert topics == []
