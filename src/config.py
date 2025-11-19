"""Configuration management for the content curator."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError
from rich.console import Console

from .models import (
    ConfidenceThresholds,
    PipelineConfig,
    RetryConfig,
    SleepIntervals,
    StageModels,
    TimeoutConfig,
)
from .utils.logging import get_logger

logger = get_logger(__name__)
console = Console()

# Load environment variables from .env file
load_dotenv()


def _optional_float(env_var: str) -> float | None:
    value = os.getenv(env_var)
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid float value for {env_var}: {value}") from exc


def _env_model(primary: str, legacy: str, default: str) -> str:
    """Resolve model env vars with backward-compatible fallbacks."""

    return os.getenv(primary) or os.getenv(legacy) or default


def _build_config() -> PipelineConfig:
    """Build and validate configuration from environment variables.

    Called at import time to catch configuration errors immediately.
    """
    # Build nested config sections
    timeouts = TimeoutConfig(
        openai_api_timeout=float(os.getenv("OPENAI_API_TIMEOUT", "120.0")),
        enrichment_timeout=float(os.getenv("ENRICHMENT_TIMEOUT", "60.0")),
        http_client_timeout=float(os.getenv("HTTP_CLIENT_TIMEOUT", "30.0")),
        fact_check_timeout=float(os.getenv("FACT_CHECK_TIMEOUT", "5.0")),
        citation_resolver_timeout=int(os.getenv("CITATION_RESOLVER_TIMEOUT", "10")),
    )

    retries = RetryConfig(
        max_attempts=int(os.getenv("RETRY_MAX_ATTEMPTS", "3")),
        backoff_multiplier=float(os.getenv("RETRY_BACKOFF_MULTIPLIER", "1.0")),
        backoff_min=float(os.getenv("RETRY_BACKOFF_MIN", "2.0")),
        backoff_max=float(os.getenv("RETRY_BACKOFF_MAX", "30.0")),
        jitter=float(os.getenv("RETRY_JITTER", "0.1")),
    )

    confidences = ConfidenceThresholds(
        dedup_confidence=float(os.getenv("CONFIDENCE_DEDUP", "0.8")),
        citation_baseline=float(os.getenv("CONFIDENCE_CITATION_BASELINE", "0.0")),
        citation_exact_year_match=float(
            os.getenv("CONFIDENCE_CITATION_EXACT_YEAR", "0.9")
        ),
        citation_partial_year_match=float(
            os.getenv("CONFIDENCE_CITATION_PARTIAL_YEAR", "0.6")
        ),
        citation_extracted_url=float(os.getenv("CONFIDENCE_CITATION_URL", "1.0")),
        citation_extracted_metadata=float(
            os.getenv("CONFIDENCE_CITATION_METADATA", "0.9")
        ),
        citation_extracted_bibtex=float(
            os.getenv("CONFIDENCE_CITATION_BIBTEX", "0.85")
        ),
    )

    sleep_intervals = SleepIntervals(
        between_subreddit_requests=float(
            os.getenv("SLEEP_BETWEEN_SUBREDDIT_REQUESTS", "0.5")
        ),
        between_hackernews_requests=float(
            os.getenv("SLEEP_BETWEEN_HACKERNEWS_REQUESTS", "0.1")
        ),
        rate_limit_minimum_interval=float(
            os.getenv("SLEEP_RATE_LIMIT_MIN_INTERVAL", "0.01")
        ),
    )

    stage_models = StageModels(
        content_model=_env_model("MODEL_CONTENT", "CONTENT_MODEL", "gpt-5-mini"),
        title_model=_env_model("MODEL_TITLE", "TITLE_MODEL", "gpt-5-nano"),
        review_model=_env_model("MODEL_REVIEW", "REVIEW_MODEL", "gpt-5-mini"),
        enrichment_model=_env_model(
            "MODEL_ENRICHMENT", "ENRICHMENT_MODEL", "gpt-5-nano"
        ),
        image_model=_env_model("MODEL_IMAGE", "IMAGE_MODEL", "dall-e-3"),
        illustration_generation_model=_env_model(
            "MODEL_ILLUSTRATION_GENERATE", "ILLUSTRATION_MODEL", "gpt-3.5-turbo"
        ),
        illustration_review_model=_env_model(
            "MODEL_ILLUSTRATION_REVIEW",
            "ILLUSTRATION_REVIEW_MODEL",
            "gpt-3.5-turbo",
        ),
        diagram_validation_model=_env_model(
            "MODEL_DIAGRAM_VALIDATION",
            "DIAGRAM_VALIDATION_MODEL",
            "gpt-3.5-turbo",
        ),
    )

    config = PipelineConfig(
        stage_models=stage_models,
        timeouts=timeouts,
        retries=retries,
        confidences=confidences,
        sleep_intervals=sleep_intervals,
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        mastodon_instances=os.getenv(
            "MASTODON_INSTANCES", "https://hachyderm.io"
        ).split(","),
        mastodon_access_token=os.getenv("MASTODON_ACCESS_TOKEN"),
        reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
        reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        reddit_user_agent=os.getenv("REDDIT_USER_AGENT"),
        reddit_requests_per_minute=int(os.getenv("REDDIT_REQUESTS_PER_MINUTE", "30")),
        reddit_burst=int(os.getenv("REDDIT_BURST", "5")),
        reddit_request_interval_seconds=float(
            os.getenv("REDDIT_REQUEST_INTERVAL_SECONDS", "1.0")
        ),
        reddit_max_retries=int(os.getenv("REDDIT_MAX_RETRIES", "3")),
        reddit_backoff_base=float(os.getenv("REDDIT_BACKOFF_BASE", "2.0")),
        reddit_backoff_max=float(os.getenv("REDDIT_BACKOFF_MAX", "60.0")),
        articles_per_run=int(os.getenv("ARTICLES_PER_RUN", "10")),
        min_content_length=int(os.getenv("MIN_CONTENT_LENGTH", "100")),
        max_content_length=int(os.getenv("MAX_CONTENT_LENGTH", "2000")),
        # Hugo site configuration
        hugo_base_url=os.getenv(
            "HUGO_BASE_URL", "https://hardcoreprawn.github.io/tech-content-curator"
        ),
        # Content relevance filtering
        allow_tech_content=os.getenv("ALLOW_TECH_CONTENT", "true").lower() == "true",
        allow_science_content=os.getenv("ALLOW_SCIENCE_CONTENT", "true").lower()
        == "true",
        allow_policy_content=os.getenv("ALLOW_POLICY_CONTENT", "true").lower()
        == "true",
        relevance_negative_keywords=os.getenv(
            "RELEVANCE_NEGATIVE_KEYWORDS",
            "recipe,baking,cooking,gardening,jigsaw,puzzle,sports,fashion,music,movie",
        ),
        image_strategy=os.getenv("IMAGE_STRATEGY", "reuse"),
        image_generate_fallback=os.getenv("IMAGE_GENERATE_FALLBACK", "false").lower()
        == "true",
        enable_citations=os.getenv("ENABLE_CITATIONS", "true").lower() == "true",
        citations_cache_ttl_days=int(os.getenv("CITATIONS_CACHE_TTL_DAYS", "30")),
        # Image selection - multi-source fallback
        unsplash_api_key=os.getenv("UNSPLASH_API_KEY", ""),
        pexels_api_key=os.getenv("PEXELS_API_KEY", ""),
        image_source_timeout=int(os.getenv("IMAGE_SOURCE_TIMEOUT", "30")),
        # Illustration system configuration
        enable_illustrations=os.getenv("ENABLE_ILLUSTRATIONS", "true").lower()
        == "true",
        illustration_budget_per_article=float(
            os.getenv("ILLUSTRATION_BUDGET_PER_ARTICLE", "0.06")
        ),
        illustration_confidence_threshold=float(
            os.getenv("ILLUSTRATION_CONFIDENCE_THRESHOLD", "0.7")
        ),
        illustration_ai_confidence_threshold=float(
            os.getenv("ILLUSTRATION_AI_CONFIDENCE_THRESHOLD", "0.8")
        ),
        max_illustrations_per_article=int(
            os.getenv("MAX_ILLUSTRATIONS_PER_ARTICLE", "3")
        ),
        # Diagram validation settings
        diagram_validation_threshold=float(
            os.getenv("DIAGRAM_VALIDATION_THRESHOLD", "0.7")
        ),
        mermaid_candidates=int(os.getenv("MERMAID_CANDIDATES", "3")),
        ascii_candidates=int(os.getenv("ASCII_CANDIDATES", "3")),
        text_illustration_candidates=int(
            os.getenv("TEXT_ILLUSTRATION_CANDIDATES", "3")
        ),
        text_illustration_quality_threshold=float(
            os.getenv("TEXT_ILLUSTRATION_QUALITY_THRESHOLD", "0.6")
        ),
        skip_list_sections=os.getenv("SKIP_LIST_SECTIONS", "true").lower() == "true",
        # Article review and quality improvement (Phase 2)
        enable_article_review=os.getenv("ENABLE_ARTICLE_REVIEW", "false").lower()
        == "true",
        article_review_min_threshold=float(
            os.getenv("ARTICLE_REVIEW_MIN_THRESHOLD", "6.0")
        ),
        enable_review_regeneration=os.getenv(
            "ENABLE_REVIEW_REGENERATION", "false"
        ).lower()
        == "true",
        max_regeneration_attempts=int(os.getenv("MAX_REGENERATION_ATTEMPTS", "2")),
        # Quality gate configuration (two-tier system)
        enable_quality_gate=os.getenv("ENABLE_QUALITY_GATE", "false").lower() == "true",
        quality_gate_threshold=float(os.getenv("QUALITY_GATE_THRESHOLD", "70.0")),
        enable_auto_review_on_failure=os.getenv(
            "ENABLE_AUTO_REVIEW_ON_FAILURE", "true"
        ).lower()
        == "true",
        enable_auto_regeneration=os.getenv("ENABLE_AUTO_REGENERATION", "true").lower()
        == "true",
        review_score_threshold=float(os.getenv("REVIEW_SCORE_THRESHOLD", "6.5")),
        # Voice adaptation and tracking
        enable_voice_metrics=os.getenv("ENABLE_VOICE_METRICS", "true").lower()
        == "true",
        # Secondary source research
        enable_secondary_sources=os.getenv("ENABLE_SECONDARY_SOURCES", "false").lower()
        == "true",
        max_secondary_references=int(os.getenv("MAX_SECONDARY_REFERENCES", "3")),
        max_cost_per_run=_optional_float("MAX_COST_PER_RUN"),
        max_cost_per_article=_optional_float("MAX_COST_PER_ARTICLE"),
    )

    # Validate required keys (except in test environment)
    # Allow missing API key during testing to avoid import-time errors
    if not config.openai_api_key and "pytest" not in os.environ.get("PATH", ""):
        # Additional check: if running tests, allow missing key
        import sys

        if "pytest" not in sys.modules:
            raise ValueError(
                "OPENAI_API_KEY is required. "
                "Add it to your .env file or set as environment variable."
            )

    return config


# Validate configuration at import time
try:
    _validated_config = _build_config()
except (ValidationError, ValueError) as e:
    console.print(f"[red]Configuration error: {e}[/red]")
    console.print("[yellow]Make sure you have:[/yellow]")
    console.print("[yellow]1. Copied .env.example to .env[/yellow]")
    console.print("[yellow]2. Added your OpenAI API key[/yellow]")
    console.print("[yellow]3. Added at least one social media source[/yellow]")
    raise


def get_config() -> PipelineConfig:
    """Get validated configuration from environment variables.

    Configuration is validated at import time, so this function
    simply returns the cached, pre-validated configuration.

    Returns:
        The pre-validated PipelineConfig instance.
    """
    return _validated_config


def _reset_config_cache() -> None:
    """Reset the config cache by rebuilding from environment.

    INTERNAL: This is only meant for testing purposes to allow
    environment variable patching to work correctly.
    """
    global _validated_config
    _validated_config = _build_config()


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """Get the data directory, creating it if needed."""
    data_dir = get_project_root() / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def get_content_dir() -> Path:
    """Get the content directory for generated articles, creating it if needed.

    Articles go in content/posts/ for proper Hugo section structure.
    """
    content_dir = get_project_root() / "content" / "posts"
    content_dir.mkdir(parents=True, exist_ok=True)
    return content_dir


# Quality thresholds for different difficulty levels (Phase 1.3)
QUALITY_THRESHOLDS = {
    "beginner": {
        "min_flesch_ease": 60.0,  # Fairly easy to read
        "max_grade_level": 10.0,  # 10th grade or lower
        "min_quality_score": 70.0,  # Minimum overall quality
    },
    "intermediate": {
        "min_flesch_ease": 50.0,  # Fairly difficult
        "max_grade_level": 14.0,  # College level
        "min_quality_score": 75.0,  # Higher quality expected
    },
    "advanced": {
        "min_flesch_ease": 30.0,  # Difficult (technical writing acceptable)
        "max_grade_level": 18.0,  # Graduate level
        "min_quality_score": 80.0,  # Highest quality expected
    },
}
