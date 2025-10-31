"""Data models for the content curator pipeline.

ARCHITECTURE NOTE: These are the ONLY classes in this project.
- They're Pydantic models = typed data containers with validation
- Everything else uses functions, not classes
- This keeps the code simple and Pythonic
- If you're tempted to add a class, write a function instead
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


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
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Source-specific data"
    )

    class Config:
        """Pydantic config."""

        use_enum_values = True


class EnrichedItem(BaseModel):
    """Content item after research and enrichment."""

    original: CollectedItem = Field(..., description="Original collected item")
    research_summary: str = Field(..., description="AI-generated research summary")
    related_sources: list[HttpUrl] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list, description="Extracted topics/tags")
    quality_score: float = Field(ge=0.0, le=1.0, description="Quality assessment score")
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


class PipelineConfig(BaseModel):
    """Configuration for the content pipeline."""

    # API Keys
    openai_api_key: str
    bluesky_handle: str | None = None
    bluesky_app_password: str | None = None
    mastodon_instances: list[str] = ["https://hachyderm.io"]  # Tech-focused instances
    mastodon_access_token: str | None = None
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None

    # Pipeline settings
    articles_per_run: int = Field(default=3, ge=1, le=10)
    min_content_length: int = Field(default=100, ge=50)
    max_content_length: int = Field(default=2000, le=5000)
    
    # Hugo site configuration
    hugo_base_url: str = Field(
        default="",
        description="Base URL for Hugo site (e.g., 'https://site.com/blog'). Used for absolute image URLs."
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

    class Config:
        """Pydantic config."""

        env_prefix = ""  # Load from environment variables directly
