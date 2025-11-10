"""Comprehensive tests for Priority 4 config validation.

Tests that all new config sections (TimeoutConfig, RetryConfig,
ConfidenceThresholds, SleepIntervals) are properly validated.
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config import get_config
from src.models import (
    ConfidenceThresholds,
    PipelineConfig,
    RetryConfig,
    SleepIntervals,
    TimeoutConfig,
)


class TestTimeoutConfig:
    """Test TimeoutConfig validation."""

    def test_valid_timeouts(self):
        """Test that valid timeout values are accepted."""
        config = TimeoutConfig(
            openai_api_timeout=120.0,
            enrichment_timeout=60.0,
            http_client_timeout=30.0,
            fact_check_timeout=5.0,
            citation_resolver_timeout=10,
        )
        assert config.openai_api_timeout == 120.0
        assert config.http_client_timeout == 30.0

    def test_default_timeouts(self):
        """Test that default timeout values are sensible."""
        config = TimeoutConfig()
        assert config.openai_api_timeout == 120.0
        assert config.enrichment_timeout == 60.0
        assert config.http_client_timeout == 30.0
        assert config.fact_check_timeout == 5.0
        assert config.citation_resolver_timeout == 10

    def test_timeout_must_be_positive(self):
        """Test that timeouts must be > 0."""
        with pytest.raises(ValidationError):
            TimeoutConfig(openai_api_timeout=0.0)
        with pytest.raises(ValidationError):
            TimeoutConfig(http_client_timeout=-1.0)

    def test_timeout_ranges_make_sense(self):
        """Test that timeout values are in reasonable ranges."""
        config = TimeoutConfig(
            openai_api_timeout=5.0,  # Very short but valid
            http_client_timeout=0.1,  # Fast connection
        )
        assert config.openai_api_timeout == 5.0

    def test_timeout_large_values_accepted(self):
        """Test that large timeout values are accepted."""
        config = TimeoutConfig(
            openai_api_timeout=600.0,  # 10 minutes
            http_client_timeout=300.0,
        )
        assert config.openai_api_timeout == 600.0


class TestRetryConfig:
    """Test RetryConfig validation."""

    def test_valid_retry_config(self):
        """Test that valid retry config is accepted."""
        config = RetryConfig(
            max_attempts=3,
            backoff_multiplier=1.0,
            backoff_min=2.0,
            backoff_max=30.0,
            jitter=0.1,
        )
        assert config.max_attempts == 3
        assert config.backoff_max == 30.0

    def test_default_retry_config(self):
        """Test that default retry values are sensible."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.backoff_multiplier == 1.0
        assert config.backoff_min == 2.0
        assert config.backoff_max == 30.0
        assert config.jitter == 0.1

    def test_max_attempts_must_be_positive(self):
        """Test that max_attempts must be >= 1."""
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=0)
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=-1)

    def test_max_attempts_upper_limit(self):
        """Test that max_attempts has reasonable upper limit."""
        config = RetryConfig(max_attempts=10)  # Max allowed
        assert config.max_attempts == 10
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=11)  # Just over limit

    def test_backoff_multiplier_must_be_positive(self):
        """Test that backoff_multiplier must be > 0."""
        with pytest.raises(ValidationError):
            RetryConfig(backoff_multiplier=0.0)

    def test_backoff_min_max_must_be_positive(self):
        """Test that backoff min/max must be > 0."""
        with pytest.raises(ValidationError):
            RetryConfig(backoff_min=0.0)
        with pytest.raises(ValidationError):
            RetryConfig(backoff_max=-1.0)

    def test_jitter_must_be_between_0_and_1(self):
        """Test that jitter is between 0 and 1."""
        RetryConfig(jitter=0.0)  # Valid
        RetryConfig(jitter=1.0)  # Valid
        with pytest.raises(ValidationError):
            RetryConfig(jitter=-0.1)
        with pytest.raises(ValidationError):
            RetryConfig(jitter=1.5)

    def test_realistic_backoff_values(self):
        """Test realistic backoff configurations."""
        # Fast backoff
        config = RetryConfig(backoff_min=0.5, backoff_max=5.0, backoff_multiplier=2.0)
        assert config.backoff_min < config.backoff_max

        # Slow backoff
        config = RetryConfig(
            backoff_min=10.0, backoff_max=300.0, backoff_multiplier=1.5
        )
        assert config.backoff_min < config.backoff_max


class TestConfidenceThresholds:
    """Test ConfidenceThresholds validation."""

    def test_valid_confidence_thresholds(self):
        """Test that valid confidence values are accepted."""
        config = ConfidenceThresholds(
            dedup_confidence=0.8,
            citation_baseline=0.0,
            citation_exact_year_match=0.9,
            citation_partial_year_match=0.6,
            citation_extracted_url=1.0,
            citation_extracted_metadata=0.9,
            citation_extracted_bibtex=0.85,
        )
        assert config.dedup_confidence == 0.8
        assert config.citation_exact_year_match == 0.9

    def test_default_confidence_thresholds(self):
        """Test that default confidence values are sensible."""
        config = ConfidenceThresholds()
        assert config.dedup_confidence == 0.8
        assert config.citation_baseline == 0.0
        assert config.citation_extracted_url == 1.0
        assert config.citation_extracted_bibtex == 0.85

    def test_all_confidences_between_0_and_1(self):
        """Test that all confidence scores are between 0 and 1."""
        # Valid edge cases
        config = ConfidenceThresholds(
            dedup_confidence=0.0,
            citation_extracted_url=1.0,
        )
        assert config.dedup_confidence == 0.0
        assert config.citation_extracted_url == 1.0

        # Invalid: below 0
        with pytest.raises(ValidationError):
            ConfidenceThresholds(dedup_confidence=-0.1)

        # Invalid: above 1
        with pytest.raises(ValidationError):
            ConfidenceThresholds(citation_exact_year_match=1.1)

    def test_logical_confidence_relationships(self):
        """Test that confidence relationships make logical sense."""
        # Exact year match should typically be >= partial year match
        config = ConfidenceThresholds(
            citation_exact_year_match=0.9,
            citation_partial_year_match=0.6,
        )
        assert config.citation_exact_year_match >= config.citation_partial_year_match

        # Baseline confidence should be low
        config = ConfidenceThresholds(citation_baseline=0.1)
        assert config.citation_baseline <= 0.5

    def test_extracted_confidences_reasonable(self):
        """Test that extracted confidence levels are sensible."""
        config = ConfidenceThresholds(
            citation_extracted_url=0.95,
            citation_extracted_metadata=0.85,
            citation_extracted_bibtex=0.75,
        )
        # URL typically more reliable than metadata
        assert config.citation_extracted_url >= config.citation_extracted_metadata


class TestSleepIntervals:
    """Test SleepIntervals validation."""

    def test_valid_sleep_intervals(self):
        """Test that valid sleep intervals are accepted."""
        config = SleepIntervals(
            between_subreddit_requests=0.5,
            between_hackernews_requests=0.1,
            rate_limit_minimum_interval=0.01,
        )
        assert config.between_subreddit_requests == 0.5
        assert config.rate_limit_minimum_interval == 0.01

    def test_default_sleep_intervals(self):
        """Test that default sleep intervals are sensible."""
        config = SleepIntervals()
        assert config.between_subreddit_requests == 0.5
        assert config.between_hackernews_requests == 0.1
        assert config.rate_limit_minimum_interval == 0.01

    def test_sleep_intervals_non_negative(self):
        """Test that sleep intervals are >= 0."""
        SleepIntervals(between_subreddit_requests=0.0)  # Valid
        with pytest.raises(ValidationError):
            SleepIntervals(between_hackernews_requests=-0.1)

    def test_realistic_sleep_intervals(self):
        """Test realistic sleep interval configurations."""
        # Fast polling
        config = SleepIntervals(
            between_subreddit_requests=0.1,
            between_hackernews_requests=0.01,
            rate_limit_minimum_interval=0.001,
        )
        assert config.between_subreddit_requests > 0

        # Slow polling (respectful rate limits)
        config = SleepIntervals(
            between_subreddit_requests=2.0,
            between_hackernews_requests=1.0,
            rate_limit_minimum_interval=0.1,
        )
        assert config.between_subreddit_requests >= 1.0


class TestNestedConfigIntegration:
    """Test nested config sections in PipelineConfig."""

    def test_pipeline_config_includes_all_sections(self):
        """Test that PipelineConfig includes all nested sections."""
        config = PipelineConfig(
            openai_api_key="test-key",
            timeouts=TimeoutConfig(),
            retries=RetryConfig(),
            confidences=ConfidenceThresholds(),
            sleep_intervals=SleepIntervals(),
        )
        assert config.timeouts.openai_api_timeout == 120.0
        assert config.retries.max_attempts == 3
        assert config.confidences.dedup_confidence == 0.8
        assert config.sleep_intervals.between_subreddit_requests == 0.5

    def test_nested_configs_use_defaults(self):
        """Test that nested configs use defaults if not specified."""
        config = PipelineConfig(openai_api_key="test-key")
        assert config.timeouts.openai_api_timeout == 120.0
        assert config.retries.max_attempts == 3

    def test_invalid_nested_config_fails(self):
        """Test that invalid nested config values fail validation."""
        with pytest.raises(ValidationError):
            PipelineConfig(
                openai_api_key="test-key",
                timeouts=TimeoutConfig(openai_api_timeout=-1.0),
            )

    def test_override_specific_nested_values(self):
        """Test overriding specific values in nested configs."""
        config = PipelineConfig(
            openai_api_key="test-key",
            timeouts=TimeoutConfig(openai_api_timeout=300.0),
        )
        assert config.timeouts.openai_api_timeout == 300.0
        assert config.timeouts.http_client_timeout == 30.0  # Still default


class TestConfigEnvVarLoading:
    """Test loading config sections from environment variables."""

    def test_load_timeout_config_from_env(self):
        """Test loading timeout config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_TIMEOUT": "180.0",
                "HTTP_CLIENT_TIMEOUT": "45.0",
            },
        ):
            from src.config import _reset_config_cache

            _reset_config_cache()
            config = get_config()
            assert config.timeouts.openai_api_timeout == 180.0
            assert config.timeouts.http_client_timeout == 45.0

    def test_load_retry_config_from_env(self):
        """Test loading retry config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "RETRY_MAX_ATTEMPTS": "5",
                "RETRY_BACKOFF_MAX": "60.0",
                "RETRY_JITTER": "0.2",
            },
        ):
            from src.config import _reset_config_cache

            _reset_config_cache()
            config = get_config()
            assert config.retries.max_attempts == 5
            assert config.retries.backoff_max == 60.0
            assert config.retries.jitter == 0.2

    def test_load_confidence_config_from_env(self):
        """Test loading confidence config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "CONFIDENCE_DEDUP": "0.75",
                "CONFIDENCE_CITATION_EXACT_YEAR": "0.95",
            },
        ):
            from src.config import _reset_config_cache

            _reset_config_cache()
            config = get_config()
            assert config.confidences.dedup_confidence == 0.75
            assert config.confidences.citation_exact_year_match == 0.95

    def test_load_sleep_config_from_env(self):
        """Test loading sleep interval config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "SLEEP_BETWEEN_SUBREDDIT_REQUESTS": "1.0",
                "SLEEP_BETWEEN_HACKERNEWS_REQUESTS": "0.5",
            },
        ):
            from src.config import _reset_config_cache

            _reset_config_cache()
            config = get_config()
            assert config.sleep_intervals.between_subreddit_requests == 1.0
            assert config.sleep_intervals.between_hackernews_requests == 0.5

    def test_env_vars_use_defaults_when_not_set(self):
        """Test that env vars use defaults when not in environment."""
        # Create a dict with only essential vars, leaving new Priority 4 vars unset
        env_dict = {k: v for k, v in os.environ.items() if k == "OPENAI_API_KEY"}
        # Add back the required OPENAI_API_KEY for testing
        if "OPENAI_API_KEY" not in env_dict:
            env_dict["OPENAI_API_KEY"] = "test-key-for-testing"

        with patch.dict(os.environ, env_dict, clear=True):
            config = get_config()
            # Should get all defaults
            assert config.timeouts.openai_api_timeout == 120.0
            assert config.retries.max_attempts == 3
            assert config.confidences.dedup_confidence == 0.8
            assert config.sleep_intervals.between_subreddit_requests == 0.5


class TestConfigBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_zero_timeout_invalid(self):
        """Test that zero timeout is invalid."""
        with pytest.raises(ValidationError):
            TimeoutConfig(openai_api_timeout=0)

    def test_very_large_timeout_valid(self):
        """Test that very large timeout values are valid."""
        config = TimeoutConfig(openai_api_timeout=3600.0)  # 1 hour
        assert config.openai_api_timeout == 3600.0

    def test_confidence_exactly_zero_valid(self):
        """Test that confidence of exactly 0 is valid."""
        config = ConfidenceThresholds(citation_baseline=0.0)
        assert config.citation_baseline == 0.0

    def test_confidence_exactly_one_valid(self):
        """Test that confidence of exactly 1 is valid."""
        config = ConfidenceThresholds(citation_extracted_url=1.0)
        assert config.citation_extracted_url == 1.0

    def test_jitter_exactly_zero_valid(self):
        """Test that jitter of exactly 0 is valid (no jitter)."""
        config = RetryConfig(jitter=0.0)
        assert config.jitter == 0.0

    def test_jitter_exactly_one_valid(self):
        """Test that jitter of exactly 1 is valid (full jitter)."""
        config = RetryConfig(jitter=1.0)
        assert config.jitter == 1.0


class TestRealWorldConfigScenarios:
    """Test realistic configuration scenarios."""

    def test_aggressive_fast_retry_strategy(self):
        """Test aggressive fast retry strategy."""
        config = RetryConfig(
            max_attempts=5,
            backoff_multiplier=2.0,
            backoff_min=0.5,
            backoff_max=10.0,
            jitter=0.3,
        )
        assert config.max_attempts == 5
        assert config.backoff_max == 10.0

    def test_conservative_slow_retry_strategy(self):
        """Test conservative slow retry strategy."""
        config = RetryConfig(
            max_attempts=2,
            backoff_multiplier=1.5,
            backoff_min=5.0,
            backoff_max=60.0,
            jitter=0.05,
        )
        assert config.max_attempts == 2
        assert config.backoff_max == 60.0

    def test_strict_confidence_thresholds(self):
        """Test strict confidence thresholds for high quality."""
        config = ConfidenceThresholds(
            dedup_confidence=0.95,
            citation_baseline=0.5,
            citation_exact_year_match=0.99,
            citation_partial_year_match=0.80,
        )
        assert config.dedup_confidence == 0.95

    def test_lenient_confidence_thresholds(self):
        """Test lenient confidence thresholds for inclusivity."""
        config = ConfidenceThresholds(
            dedup_confidence=0.5,
            citation_baseline=0.1,
            citation_exact_year_match=0.7,
            citation_partial_year_match=0.4,
        )
        assert config.dedup_confidence == 0.5
