"""Test suite for OpenAI client utility wrapper.

Tests parameter mapping, model family detection, and validation.
"""

from unittest.mock import MagicMock

import pytest
from openai import OpenAI

from src.utils.openai_client import (
    MODEL_CONFIGS,
    create_chat_completion,
    get_model_config,
    get_model_family,
    validate_model_config,
)


class TestModelFamilyDetection:
    """Test model family detection logic."""

    def test_gpt5_family_detection(self):
        """GPT-5 models should be detected correctly."""
        assert get_model_family("gpt-5-nano") == "gpt5"
        assert get_model_family("gpt-5-mini") == "gpt5"
        assert get_model_family("gpt-5") == "gpt5"
        assert get_model_family("gpt-5-pro") == "gpt5"

    def test_gpt4_family_detection(self):
        """GPT-4 models should be detected correctly."""
        assert get_model_family("gpt-4o") == "gpt4"
        assert get_model_family("gpt-4o-mini") == "gpt4"
        assert get_model_family("gpt-4-turbo") == "gpt4"

    def test_o1_family_detection(self):
        """o1 models should be detected correctly."""
        assert get_model_family("o1-preview") == "o1"
        assert get_model_family("o1-mini") == "o1"

    def test_o3_family_detection(self):
        """o3 models should be detected correctly."""
        assert get_model_family("o3-mini") == "o3"

    def test_unknown_model(self):
        """Unknown models should return 'unknown'."""
        assert get_model_family("claude-3") == "unknown"
        assert get_model_family("llama-2") == "unknown"


class TestModelConfiguration:
    """Test model configuration retrieval."""

    def test_get_gpt5_config(self):
        """Should retrieve GPT-5 config."""
        config = get_model_config("gpt-5-mini")
        assert config["prefix"] == "gpt-5"
        # max_tokens is unsupported (causes empty responses due to reasoning)
        assert "max_tokens" in config["unsupported"]
        assert "max_tokens" not in config["param_map"]

    def test_get_gpt4_config(self):
        """Should retrieve GPT-4 config."""
        config = get_model_config("gpt-4o-mini")
        assert config["prefix"] == "gpt-4"
        assert "max_tokens" in config["param_map"]
        assert config["param_map"]["max_tokens"] == "max_tokens"

    def test_get_o1_config(self):
        """Should retrieve o1 config."""
        config = get_model_config("o1-preview")
        assert config["prefix"] == "o1"
        assert "temperature" in config["unsupported"]

    def test_unknown_model_raises_error(self):
        """Unknown model should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown model family"):
            get_model_config("claude-3-opus")


class TestParameterMapping:
    """Test parameter mapping for different models."""

    def test_gpt5_max_tokens_mapping(self):
        """GPT-5 should filter out max_tokens (causes empty responses)."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        create_chat_completion(
            client=mock_client,
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        # max_tokens should be filtered out for GPT-5 (causes empty responses)
        assert "max_completion_tokens" not in call_kwargs
        assert "max_tokens" not in call_kwargs

    def test_gpt4_max_tokens_mapping(self):
        """GPT-4 should use max_tokens."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        create_chat_completion(
            client=mock_client,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "max_tokens" in call_kwargs
        assert "max_completion_tokens" not in call_kwargs
        assert call_kwargs["max_tokens"] == 100

    def test_temperature_mapping_consistent(self):
        """Temperature should map consistently for models that support it."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        # Test GPT-5 (temperature not supported, should be skipped)
        create_chat_completion(
            client=mock_client,
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "test"}],
            temperature=0.7,
        )
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "temperature" not in call_kwargs  # GPT-5 doesn't support it

        # Test GPT-4 (temperature supported)
        create_chat_completion(
            client=mock_client,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            temperature=0.7,
        )
        assert mock_client.chat.completions.create.call_args[1]["temperature"] == 0.7

    def test_response_format_mapping(self):
        """Response format should map consistently."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        json_format = {"type": "json_object"}

        create_chat_completion(
            client=mock_client,
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "test"}],
            response_format=json_format,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["response_format"] == json_format


class TestUnsupportedParameters:
    """Test handling of unsupported parameters."""

    def test_o1_skips_temperature(self):
        """o1 models should skip temperature parameter silently."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        # Should not raise - temperature should be skipped
        create_chat_completion(
            client=mock_client,
            model="o1-preview",
            messages=[{"role": "user", "content": "test"}],
            temperature=0.7,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "temperature" not in call_kwargs

    def test_o1_accepts_supported_params(self):
        """o1 models should accept supported parameters."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        # Should not raise
        create_chat_completion(
            client=mock_client,
            model="o1-preview",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "max_completion_tokens" in call_kwargs


class TestNoneParameterHandling:
    """Test that None parameters are excluded from API calls."""

    def test_none_parameters_excluded(self):
        """Parameters with None values should not be in API call."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        create_chat_completion(
            client=mock_client,
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=None,
            temperature=None,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "max_completion_tokens" not in call_kwargs
        assert "temperature" not in call_kwargs
        assert "messages" in call_kwargs  # Required param still there

    def test_zero_values_included(self):
        """Zero values should be included for models that support them."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        # Use GPT-4 which supports temperature
        create_chat_completion(
            client=mock_client,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            temperature=0.0,  # Valid temperature
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "temperature" in call_kwargs
        assert call_kwargs["temperature"] == 0.0


class TestMessagesParameter:
    """Test that messages parameter is always included correctly."""

    def test_messages_always_included(self):
        """Messages should always be in the API call."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        messages = [{"role": "user", "content": "test"}]

        create_chat_completion(
            client=mock_client,
            model="gpt-5-mini",
            messages=messages,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "messages" in call_kwargs
        assert call_kwargs["messages"] == messages

    def test_messages_structure_preserved(self):
        """Complex message structures should be preserved."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "Tell me more"},
        ]

        create_chat_completion(
            client=mock_client,
            model="gpt-5-mini",
            messages=messages,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["messages"] == messages


class TestAllParametersSupported:
    """Test that all common parameters work correctly."""

    def test_all_gpt5_parameters(self):
        """Test all supported GPT-5 parameters (limited set)."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        create_chat_completion(
            client=mock_client,
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,  # Will be filtered out
            temperature=0.7,  # Will be skipped
            top_p=0.9,  # Will be skipped
            stop=["END"],
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        # GPT-5 only supports these parameters
        assert call_kwargs["stop"] == ["END"]
        # These are not supported by GPT-5 (filtered out)
        assert "max_tokens" not in call_kwargs
        assert "max_completion_tokens" not in call_kwargs  # Also filtered
        assert "temperature" not in call_kwargs
        assert "top_p" not in call_kwargs
        assert "frequency_penalty" not in call_kwargs
        assert "presence_penalty" not in call_kwargs


class TestConfigValidation:
    """Test configuration validation logic."""

    def test_config_validation_passes(self):
        """Current config should pass validation."""
        warnings = validate_model_config()
        assert len(warnings) == 0, f"Config has warnings: {warnings}"

    def test_all_configs_have_messages_mapping(self):
        """All configs must map 'messages' parameter."""
        for config in MODEL_CONFIGS:
            assert "messages" in config["param_map"], (
                f"Config '{config['prefix']}' missing messages mapping"
            )

    def test_no_duplicate_prefixes(self):
        """Model prefixes should be unique."""
        prefixes = [config["prefix"] for config in MODEL_CONFIGS]
        assert len(prefixes) == len(set(prefixes)), "Duplicate prefixes found"


class TestStreamingSupport:
    """Test streaming parameter handling."""

    def test_stream_false_by_default(self):
        """Stream should default to False."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        create_chat_completion(
            client=mock_client,
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "test"}],
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        # stream=False shouldn't be in kwargs (it's the default)
        assert call_kwargs.get("stream", False) is False

    def test_stream_true_included(self):
        """Stream=True should be included in API call."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        create_chat_completion(
            client=mock_client,
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "test"}],
            stream=True,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["stream"] is True


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_unknown_model_raises_valueerror(self):
        """Unknown models should raise descriptive errors."""
        mock_client = MagicMock(spec=OpenAI)

        with pytest.raises(ValueError) as exc_info:
            create_chat_completion(
                client=mock_client,
                model="unknown-model-xyz",
                messages=[{"role": "user", "content": "test"}],
            )

        assert "Unknown model family" in str(exc_info.value)
        assert "unknown-model-xyz" in str(exc_info.value)

    def test_empty_messages_still_works(self):
        """Empty messages list should still make the call."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        # Should not raise - API will validate
        create_chat_completion(
            client=mock_client,
            model="gpt-5-mini",
            messages=[],
        )

        assert mock_client.chat.completions.create.called

    def test_model_parameter_always_included(self):
        """Model parameter should always be in API call."""
        mock_client = MagicMock(spec=OpenAI)
        mock_client.chat.completions.create.return_value = MagicMock()

        create_chat_completion(
            client=mock_client,
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "test"}],
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "model" in call_kwargs
        assert call_kwargs["model"] == "gpt-5-mini"
