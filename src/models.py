"""Data models for the content curator pipeline.

ARCHITECTURE NOTE: These are the ONLY classes in this project.
- They're Pydantic models = typed data containers with validation
- Everything else uses functions, not classes
- This keeps the code simple and Pythonic
- If you're tempted to add a class, write a function instead
"""

from datetime import datetime
from enum import Enum
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CollectedItemMetadata(TypedDict, total=False):
    """Type definition for metadata in collected items.

    Uses total=False to make all fields optional since different sources
    provide different metadata. Known fields:
    - Mastodon: favourites_count, reblogs_count, replies_count, language, instance, source_type
    - Reddit: score, upvote_ratio, num_comments, subreddit, created_utc, is_self, over_18
    - HackerNews: score, comments, time, story_type
    - GitHub: stars, forks, watchers, language, topics, open_issues
    """

    # Engagement metrics
    score: int
    upvote_ratio: float
    num_comments: int
    comments: int
    favourites_count: int
    reblogs_count: int
    replies_count: int

    # Time fields
    created_at: str
    created_utc: float
    time: int

    # Source-specific
    subreddit: str
    language: str
    instance: str
    source_type: str
    source_name: str
    story_type: str
    is_self: bool
    over_18: bool

    # GitHub
    stars: int
    forks: int
    watchers: int
    topics: list[str]
    open_issues: int


class GeneratedArticleVoiceMetadata(TypedDict, total=False):
    """Type definition for voice-related metadata in generated articles.

    Fields:
    - complexity_score: Quality/complexity score when voice is selected based on content
    - mode: Generation mode (normal, fallback, etc.)
    - template: Template name if using templated content
    - selection_details: Details about voice selection criteria
    """

    complexity_score: float
    mode: str
    template: str
    selection_details: str


class GeneratedArticleQualityDimensions(TypedDict, total=False):
    """Type definition for quality dimension scores in generated articles."""

    relevance: float
    clarity: float
    structure: float
    accuracy: float
    originality: float


class SourceType(str, Enum):
    """Supported content sources."""

    MASTODON = "mastodon"
    BLUESKY = "bluesky"
    REDDIT = "reddit"
    GITHUB = "github"
    HACKERNEWS = "hackernews"


class CollectedItem(BaseModel):
    """Raw content collected from social media."""

    id: str = Field(..., description="Unique identifier from the source")
    title: str = Field(..., description="Title or first line of content")
    content: str = Field(..., description="Full text content")
    source: SourceType = Field(..., description="Which platform this came from")
    url: HttpUrl = Field(..., description="Original URL")
    author: str = Field(..., description="Username/handle of author")
    collected_at: datetime = Field(default_factory=datetime.now)
    metadata: CollectedItemMetadata = Field(
        default_factory=dict,
        description="Source-specific data",  # type: ignore[assignment]
    )

    model_config = ConfigDict(use_enum_values=True)


class EnrichedItem(BaseModel):
    """Content item after research and enrichment."""

    original: CollectedItem = Field(..., description="Original collected item")
    research_summary: str = Field(..., description="AI-generated research summary")
    related_sources: list[HttpUrl] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list, description="Extracted topics/tags")
    quality_score: float = Field(
        ge=0.0, le=1.0, description="Quality assessment score (AI-based)"
    )
    heuristic_score: float = Field(
        default=0.0, ge=0.0, description="Heuristic pre-filter score for analysis"
    )
    ai_score: float = Field(
        default=0.0, ge=0.0, description="AI quality score (same as quality_score)"
    )
    enriched_at: datetime = Field(default_factory=datetime.now)


class GeneratedArticle(BaseModel):
    """Final generated blog article."""

    title: str = Field(..., description="Article title")
    content: str = Field(..., description="Full markdown content")
    summary: str = Field(..., description="Brief summary")
    sources: list[EnrichedItem] = Field(..., description="Source items used")
    tags: list[str] = Field(default_factory=list)
    word_count: int = Field(ge=0)
    generated_at: datetime = Field(default_factory=datetime.now)
    filename: str = Field(..., description="Output filename for the article")
    generation_costs: dict[str, float] = Field(
        default_factory=dict, description="Cost breakdown for generating this article"
    )
    action_run_id: str | None = Field(
        default=None, description="GitHub Actions run ID that generated this article"
    )
    generator_name: str = Field(
        ..., description="Name of generator that created this article"
    )
    illustrations_count: int = Field(
        default=0, description="Number of illustrations added to article"
    )
    # Categorization fields (added in Phase 1.2)
    content_type: str = Field(
        default="general",
        description="Article type: tutorial, news, analysis, research, guide, or general",
    )
    difficulty_level: str = Field(
        default="intermediate",
        description="Article difficulty: beginner, intermediate, or advanced",
    )
    target_audience: list[str] = Field(
        default_factory=list,
        description="List of target audience segments for this article",
    )
    estimated_read_time: str | None = Field(
        default=None,
        description="Human-readable reading time (e.g., '5 min read')",
    )
    # Quality scoring fields (added in Phase 1.3)
    readability_score: float | None = Field(
        default=None,
        description="Flesch Reading Ease score (0-100, higher = easier)",
    )
    grade_level: float | None = Field(
        default=None,
        description="Flesch-Kincaid Grade Level (U.S. school grade)",
    )
    quality_score: float | None = Field(
        default=None,
        description="Overall quality score (0-100)",
    )
    quality_dimensions: GeneratedArticleQualityDimensions | None = Field(
        default=None,
        description="Scores for each quality dimension",
    )
    quality_passed: bool = Field(
        default=False,
        description="Whether article meets minimum quality standards",
    )
    # Voice variation fields (added in Phase 1)
    voice_profile: str = Field(
        default="default",
        description="Voice ID used for this article (taylor, sam, aria, quinn, riley, jordan, emerson)",
    )
    voice_metadata: GeneratedArticleVoiceMetadata = Field(
        default_factory=dict,
        description="Metadata about voice selection (complexity_score, selection_details, etc)",  # type: ignore[assignment]
    )


class TimeoutConfig(BaseModel):
    """HTTP and API timeout settings (in seconds)."""

    openai_api_timeout: float = Field(
        default=120.0,
        gt=0,
        description="Timeout for OpenAI API calls",
    )
    enrichment_timeout: float = Field(
        default=60.0,
        gt=0,
        description="Timeout for enrichment API calls",
    )
    http_client_timeout: float = Field(
        default=30.0,
        gt=0,
        description="Timeout for general HTTP client requests (images, collectors)",
    )
    fact_check_timeout: float = Field(
        default=5.0,
        gt=0,
        description="Timeout for fact-checking URL validation",
    )
    citation_resolver_timeout: int = Field(
        default=10,
        gt=0,
        description="Timeout for citation resolver requests",
    )


class RetryConfig(BaseModel):
    """Retry and exponential backoff configuration."""

    max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of retry attempts",
    )
    backoff_multiplier: float = Field(
        default=1.0,
        gt=0,
        description="Multiplier for exponential backoff",
    )
    backoff_min: float = Field(
        default=2.0,
        gt=0,
        description="Minimum backoff time in seconds",
    )
    backoff_max: float = Field(
        default=30.0,
        gt=0,
        description="Maximum backoff time in seconds",
    )
    jitter: float = Field(
        default=0.1,
        ge=0,
        le=1,
        description="Jitter factor (0-1) to add randomness to backoff",
    )


class ConfidenceThresholds(BaseModel):
    """Confidence score thresholds (0.0-1.0 range)."""

    dedup_confidence: float = Field(
        default=0.8,
        ge=0,
        le=1,
        description="Minimum confidence for learned deduplication patterns",
    )
    citation_baseline: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Baseline confidence for unverified citations",
    )
    citation_exact_year_match: float = Field(
        default=0.9,
        ge=0,
        le=1,
        description="Confidence boost for exact publication year match",
    )
    citation_partial_year_match: float = Field(
        default=0.6,
        ge=0,
        le=1,
        description="Confidence for approximate year match (+/- 1 year)",
    )
    citation_extracted_url: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Confidence for extracted URL citations",
    )
    citation_extracted_metadata: float = Field(
        default=0.9,
        ge=0,
        le=1,
        description="Confidence for metadata-extracted citations",
    )
    citation_extracted_bibtex: float = Field(
        default=0.85,
        ge=0,
        le=1,
        description="Confidence for BibTeX-extracted citations",
    )


class SleepIntervals(BaseModel):
    """Inter-request sleep intervals (in seconds)."""

    between_subreddit_requests: float = Field(
        default=0.5,
        ge=0,
        description="Sleep between subreddit API requests to avoid rate limits",
    )
    between_hackernews_requests: float = Field(
        default=0.1,
        ge=0,
        description="Sleep between HackerNews API requests",
    )
    rate_limit_minimum_interval: float = Field(
        default=0.01,
        ge=0,
        description="Minimum sleep interval in rate limiter",
    )


class PipelineConfig(BaseModel):
    """Configuration for the content pipeline."""

    # Nested config sections (Priority 4 - centralized configuration)
    timeouts: TimeoutConfig = Field(
        default_factory=TimeoutConfig,
        description="API and HTTP timeout settings",
    )
    retries: RetryConfig = Field(
        default_factory=RetryConfig,
        description="Retry and backoff configuration",
    )
    confidences: ConfidenceThresholds = Field(
        default_factory=ConfidenceThresholds,
        description="Confidence score thresholds",
    )
    sleep_intervals: SleepIntervals = Field(
        default_factory=SleepIntervals,
        description="Inter-request sleep intervals",
    )

    # API Keys
    openai_api_key: str
    mastodon_instances: list[str] = ["https://hachyderm.io"]  # Tech-focused instances
    mastodon_access_token: str | None = None
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None

    # AI Model Configuration
    content_model: str = Field(
        default="gpt-4o-mini",
        description="Model for main article content generation",
    )
    title_model: str = Field(
        default="gpt-4o-mini",
        description="Model for title and slug generation",
    )
    review_model: str = Field(
        default="gpt-4o-mini",
        description="Model for article review and quality assessment",
    )
    enrichment_model: str = Field(
        default="gpt-4o-mini",
        description="Model for content enrichment and research",
    )

    # Pipeline settings
    articles_per_run: int = Field(default=3, ge=1, le=10)
    min_content_length: int = Field(default=100, ge=50)
    max_content_length: int = Field(default=2000, le=5000)

    # Hugo site configuration
    hugo_base_url: str = Field(
        default="",
        description="Base URL for Hugo site (e.g., 'https://site.com/blog'). Used for absolute image URLs.",
    )

    # Reddit rate limiting and retry behavior
    reddit_requests_per_minute: int = Field(
        default=30, ge=1, description="Max Reddit API requests per minute"
    )
    reddit_burst: int = Field(
        default=5, ge=1, description="Burst size for Reddit requests"
    )
    reddit_request_interval_seconds: float = Field(
        default=1.0, ge=0.0, description="Minimum delay between subreddit fetches"
    )
    reddit_max_retries: int = Field(
        default=3,
        ge=0,
        description="Max retries on transient Reddit errors (including 429)",
    )
    reddit_backoff_base: float = Field(
        default=2.0, ge=1.0, description="Base for exponential backoff"
    )
    reddit_backoff_max: float = Field(
        default=60.0, ge=1.0, description="Max backoff in seconds"
    )

    # Content relevance filtering
    allow_tech_content: bool = Field(
        default=True, description="Allow technical content (always recommended)"
    )
    allow_science_content: bool = Field(
        default=True, description="Allow science/research content"
    )
    allow_policy_content: bool = Field(
        default=True, description="Allow tech policy/regulation content"
    )
    relevance_negative_keywords: str = Field(
        default="recipe,baking,cooking,gardening,jigsaw,puzzle,sports,fashion,music,movie",
        description="Comma-separated list of keywords to filter out",
    )

    # Image strategy
    image_strategy: str = Field(
        default="reuse",
        description="Image strategy: 'reuse' (library variants), 'generate' (AI), or 'reuse_then_generate'",
    )
    image_generate_fallback: bool = Field(
        default=False,
        description="If true and strategy is reuse, fallback to AI generation when no library base exists",
    )

    # Citation resolution
    enable_citations: bool = Field(
        default=True,
        description="Enable automatic academic citation resolution to DOIs/arXiv links",
    )
    citations_cache_ttl_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Time-to-live for citation cache entries in days",
    )

    # Image selection - multi-source fallback
    unsplash_api_key: str = Field(
        default="",
        description="Unsplash API key for free stock photos",
    )
    pexels_api_key: str = Field(
        default="",
        description="Pexels API key for free stock photos",
    )
    image_source_timeout: int = Field(
        default=10,
        ge=5,
        le=60,
        description="Timeout in seconds for image source API requests",
    )

    # Illustration system configuration
    enable_illustrations: bool = Field(
        default=True,
        description="Enable automatic illustration generation for articles",
    )
    illustration_budget_per_article: float = Field(
        default=0.06,
        ge=0.0,
        description="Maximum budget for AI-generated illustrations per article in USD",
    )
    illustration_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for adding free tier illustrations",
    )
    illustration_ai_confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for adding paid AI-generated illustrations",
    )
    max_illustrations_per_article: int = Field(
        default=3,
        ge=1,
        description="Maximum number of illustrations to add per article",
    )

    # Diagram validation configuration
    diagram_validation_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum combined validation score (0.0-1.0) to accept diagrams",
    )
    mermaid_candidates: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Number of Mermaid diagram candidates to generate for selection",
    )
    ascii_candidates: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Number of ASCII diagram candidates to generate for selection",
    )
    text_illustration_candidates: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Number of text illustration candidates to generate for selection",
    )
    text_illustration_quality_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum quality score for ASCII diagrams",
    )
    skip_list_sections: bool = Field(
        default=True,
        description="Skip illustration generation for list-heavy sections",
    )

    # Article review configuration
    enable_article_review: bool = False
    article_review_min_threshold: float = 6.5
    enable_review_regeneration: bool = False
    max_regeneration_attempts: int = 2

    # Quality gate configuration (two-tier system)
    enable_quality_gate: bool = False
    quality_gate_threshold: float = 70.0  # Tier 1: Free quality scorer threshold
    enable_auto_review_on_failure: bool = True  # Tier 2: AI review if Tier 1 fails
    enable_auto_regeneration: bool = True  # Auto-regenerate on review failure
    review_score_threshold: float = 6.5  # Tier 2: AI review threshold (0-10)

    # Voice adaptation and tracking
    enable_voice_metrics: bool = Field(
        default=True,
        description="Track voice performance metrics and enable adaptation suggestions",
    )

    # Secondary source research
    enable_secondary_sources: bool = Field(
        default=False,
        description="Fetch primary source articles and extract additional references for meta-content",
    )
    max_secondary_references: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of additional references to extract from primary sources",
    )
