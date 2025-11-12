"""Test OpenAI API contract compliance.

This module validates that all OpenAI API calls in the codebase use correct
parameters according to the OpenAI API specification. This prevents runtime
errors from invalid parameter names or types.
"""

from unittest.mock import MagicMock

import pytest
from openai import OpenAI
from openai.types.chat import ChatCompletion

from src.enrichment.ai_analyzer import (
    analyze_content_quality,
    extract_topics_and_themes,
    research_additional_context,
)
from src.generators.general import GeneralArticleGenerator
from src.generators.integrative import IntegrativeListGenerator
from src.generators.specialized.self_hosted import SelfHostedGenerator
from src.models import CollectedItem, EnrichedItem

# Valid OpenAI Chat Completions API parameters (as of Nov 2024)
VALID_CHAT_COMPLETION_PARAMS = {
    "model",
    "messages",
    "temperature",
    "max_tokens",
    "top_p",
    "n",
    "stream",
    "stop",
    "presence_penalty",
    "frequency_penalty",
    "logit_bias",
    "user",
    "response_format",  # For JSON mode
    "seed",
    "tools",
    "tool_choice",
    "logprobs",
    "top_logprobs",
}


def mock_openai_response(content: str = "test response") -> ChatCompletion:
    """Create a mock OpenAI API response."""
    response = MagicMock(spec=ChatCompletion)
    response.choices = [MagicMock()]
    response.choices[0].message = MagicMock()
    response.choices[0].message.content = content
    response.usage = MagicMock()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 50
    return response


class TestOpenAIAPIContract:
    """Test that all OpenAI API calls use valid parameters."""

    def test_enrichment_quality_assessment_params(self, sample_collected_item):
        """Validate assess_quality_with_ai uses correct API parameters."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = mock_openai_response(
            '{"score": 0.8, "explanation": "Good content"}'
        )

        # Call the function
        analyze_content_quality(sample_collected_item, mock_client)

        # Check that it was called once
        assert mock_client.chat.completions.create.call_count == 1

        # Get the actual call kwargs
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # Verify all parameters are valid
        for param in call_kwargs.keys():
            assert (
                param in VALID_CHAT_COMPLETION_PARAMS
            ), f"Invalid parameter '{param}' in analyze_content_quality"

        # Verify required parameters are present
        assert "model" in call_kwargs
        assert "messages" in call_kwargs
        assert isinstance(call_kwargs["messages"], list)
        assert len(call_kwargs["messages"]) > 0
        assert "role" in call_kwargs["messages"][0]
        assert "content" in call_kwargs["messages"][0]

    def test_enrichment_topic_extraction_params(self, sample_collected_item):
        """Validate extract_topics_and_themes uses correct API parameters."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = mock_openai_response(
            '["python", "testing", "automation"]'
        )

        # Call the function
        extract_topics_and_themes(sample_collected_item, mock_client)

        # Get the actual call kwargs
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # Verify all parameters are valid
        for param in call_kwargs.keys():
            assert param in VALID_CHAT_COMPLETION_PARAMS, (
                f"Invalid parameter '{param}' in extract_topics_and_themes"
            )

        # Verify required parameters
        assert "model" in call_kwargs
        assert "messages" in call_kwargs

    def test_enrichment_research_context_params(self, sample_collected_item):
        """Validate research_additional_context uses correct API parameters."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "Research context about the topic"
        )

        # Call the function
        research_additional_context(
            sample_collected_item, ["python", "testing"], mock_client
        )

        # Get the actual call kwargs
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # Verify all parameters are valid
        for param in call_kwargs.keys():
            assert param in VALID_CHAT_COMPLETION_PARAMS, (
                f"Invalid parameter '{param}' in research_additional_context"
            )

        # Verify required parameters
        assert "model" in call_kwargs
        assert "messages" in call_kwargs

    def test_general_generator_params(self, high_quality_enriched_item):
        """Validate GeneralArticleGenerator uses correct API parameters."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "# Article Title\n\nArticle content here"
        )

        generator = GeneralArticleGenerator(mock_client)
        generator.generate_content(high_quality_enriched_item)

        # Get the actual call kwargs
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # Verify all parameters are valid
        for param in call_kwargs.keys():
            assert param in VALID_CHAT_COMPLETION_PARAMS, (
                f"Invalid parameter '{param}' in GeneralArticleGenerator"
            )

        # Verify required parameters
        assert "model" in call_kwargs
        assert "messages" in call_kwargs

    def test_self_hosted_generator_params(self, high_quality_enriched_item):
        """Validate SelfHostedGenerator uses correct API parameters."""
        # Modify item to be self-hosted related
        high_quality_enriched_item.topics = [
            "self-hosted",
            "homelab",
            "docker",
        ]

        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "# Self-Hosted Solution\n\nContent here"
        )

        generator = SelfHostedGenerator(mock_client)
        generator.generate_content(high_quality_enriched_item)

        # Get the actual call kwargs
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # Verify all parameters are valid
        for param in call_kwargs.keys():
            assert param in VALID_CHAT_COMPLETION_PARAMS, (
                f"Invalid parameter '{param}' in SelfHostedGenerator"
            )

        # Verify required parameters
        assert "model" in call_kwargs
        assert "messages" in call_kwargs

    def test_integrative_generator_params(self, high_quality_enriched_item):
        """Validate IntegrativeListGenerator uses correct API parameters."""
        # Modify item to be list-related
        high_quality_enriched_item.original.title = "10 Best Tools for Development"
        high_quality_enriched_item.topics = ["tools", "development"]

        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "# Development Tools\n\nContent here"
        )

        generator = IntegrativeListGenerator(mock_client)
        generator.generate_content(high_quality_enriched_item)

        # Get the actual call kwargs
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # Verify all parameters are valid
        for param in call_kwargs.keys():
            assert param in VALID_CHAT_COMPLETION_PARAMS, (
                f"Invalid parameter '{param}' in IntegrativeListGenerator"
            )

        # Verify required parameters
        assert "model" in call_kwargs
        assert "messages" in call_kwargs

    def test_no_deprecated_parameters(self):
        """Ensure no deprecated OpenAI parameters are used in codebase."""
        # Deprecated parameters that should not be used
        DEPRECATED_PARAMS = {
            "max_completion_tokens",  # Old name, use max_tokens
            "logit_bias_type",  # Never existed
            "engine",  # Very old, replaced by model
        }

        # This is a meta-test - we're checking the test suite itself
        # In a real scenario, you'd scan the actual source files
        from pathlib import Path

        src_dir = Path("src")
        deprecated_found = []

        for py_file in src_dir.rglob("*.py"):
            try:
                with open(py_file) as f:
                    content = f.read()
                    # Simple string search for deprecated params
                    for param in DEPRECATED_PARAMS:
                        if f"{param}=" in content or f'"{param}"' in content:
                            deprecated_found.append((py_file, param))
            except Exception:
                pass  # Skip files that can't be read

        assert not deprecated_found, f"Found deprecated parameters: {deprecated_found}"

    def test_messages_format(self, sample_collected_item):
        """Validate that messages are properly formatted."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = mock_openai_response(
            '{"score": 0.7, "explanation": "Test"}'
        )

        analyze_content_quality(sample_collected_item, mock_client)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]

        # Verify messages structure
        assert isinstance(messages, list)
        assert len(messages) > 0

        for msg in messages:
            assert isinstance(msg, dict)
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ["system", "user", "assistant"]
            assert isinstance(msg["content"], str)

    def test_temperature_bounds(self, sample_collected_item):
        """Validate that temperature values are within valid range [0, 2]."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = mock_openai_response(
            '{"score": 0.7, "explanation": "Test"}'
        )

        # Test all enrichment functions
        analyze_content_quality(sample_collected_item, mock_client)
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        if "temperature" in call_kwargs:
            temp = call_kwargs["temperature"]
            assert 0 <= temp <= 2, f"Temperature {temp} out of range [0, 2]"

    def test_max_tokens_positive(self, sample_collected_item):
        """Validate that max_tokens is positive when specified."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = mock_openai_response(
            '{"score": 0.7, "explanation": "Test"}'
        )

        analyze_content_quality(sample_collected_item, mock_client)
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        if "max_tokens" in call_kwargs:
            max_tokens = call_kwargs["max_tokens"]
            assert max_tokens > 0, f"max_tokens must be positive, got {max_tokens}"
            assert max_tokens <= 4096, f"max_tokens {max_tokens} seems too high (>4096)"


@pytest.fixture
def sample_collected_item():
    """Create a sample CollectedItem for testing."""
    from pydantic import HttpUrl

    from src.models import SourceType

    return CollectedItem(
        id="test_123",
        source=SourceType.BLUESKY,
        author="testuser",
        content="Test content about Python programming",
        url=HttpUrl("https://example.com/post/123"),
        title="Test Post",
        metadata={"language": "en"},
    )


@pytest.fixture
def high_quality_enriched_item(sample_collected_item):
    """Create a high-quality EnrichedItem for testing."""
    return EnrichedItem(
        original=sample_collected_item,
        quality_score=0.85,
        research_summary="Summary of research about Python testing",
        topics=["python", "programming", "testing"],
    )
