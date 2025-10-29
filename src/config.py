"""Configuration management for the content curator."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError
from rich.console import Console

from .models import PipelineConfig

console = Console()

# Load environment variables from .env file
load_dotenv()


def get_config() -> PipelineConfig:
    """Get validated configuration from environment variables."""
    try:
        config = PipelineConfig(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            bluesky_handle=os.getenv("BLUESKY_HANDLE"),
            bluesky_app_password=os.getenv("BLUESKY_APP_PASSWORD"),
            mastodon_instances=os.getenv(
                "MASTODON_INSTANCES", "https://hachyderm.io"
            ).split(","),
            mastodon_access_token=os.getenv("MASTODON_ACCESS_TOKEN"),
            reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
            reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            reddit_user_agent=os.getenv("REDDIT_USER_AGENT"),
            reddit_requests_per_minute=int(
                os.getenv("REDDIT_REQUESTS_PER_MINUTE", "30")
            ),
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
            hugo_base_url=os.getenv("HUGO_BASE_URL", "https://hardcoreprawn.github.io/tech-content-curator"),
            # Content relevance filtering
            allow_tech_content=os.getenv("ALLOW_TECH_CONTENT", "true").lower()
            == "true",
            allow_science_content=os.getenv("ALLOW_SCIENCE_CONTENT", "true").lower()
            == "true",
            allow_policy_content=os.getenv("ALLOW_POLICY_CONTENT", "true").lower()
            == "true",
            relevance_negative_keywords=os.getenv(
                "RELEVANCE_NEGATIVE_KEYWORDS",
                "recipe,baking,cooking,gardening,jigsaw,puzzle,sports,fashion,music,movie",
            ),
        )

        # Validate required keys
        if not config.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required. "
                "Add it to your .env file or set as environment variable."
            )

        return config

    except (ValidationError, ValueError) as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print("\n[yellow]Make sure you have:")
        console.print("1. Copied .env.example to .env")
        console.print("2. Added your OpenAI API key")
        console.print("3. Added at least one social media source[/yellow]")
        raise


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
