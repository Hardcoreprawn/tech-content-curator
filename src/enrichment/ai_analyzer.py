"""AI-powered content analysis using OpenAI API.

This module handles all OpenAI API calls for content enrichment:
- Quality assessment
- Topic extraction
- Research context generation

Includes retry logic for transient failures and error handling
for graceful degradation when the API is unavailable.
"""

import json

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from rich.console import Console
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..api.openai_error_handler import handle_openai_error
from ..models import CollectedItem
from ..utils.logging import get_logger
from ..utils.openai_client import create_chat_completion

console = Console()
logger = get_logger(__name__)


def log_retry_attempt(retry_state: RetryCallState) -> None:
    """Custom callback to log retry attempts with Rich console."""
    attempt_num = retry_state.attempt_number
    if retry_state.outcome and retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
        logger.debug(f"Retry attempt {attempt_num}: {type(exception).__name__}")
        console.print(f"[yellow]⏳ Attempt {attempt_num}: retrying...[/yellow]")


def lazy_openai_retry(func):  # type: ignore[no-untyped-def]
    """Decorator that applies retry logic with lazy config loading.

    This decorator defers config loading until the function is actually called,
    preventing import-time errors when the config isn't available (e.g., in CI tests).
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        from ..config import get_config

        config = get_config()
        decorator = retry(
            stop=stop_after_attempt(config.retries.max_attempts),
            wait=wait_exponential(
                multiplier=config.retries.backoff_multiplier,
                min=config.retries.backoff_min,
                max=config.retries.backoff_max,
            ),
            retry=retry_if_exception_type(
                (APITimeoutError, APIConnectionError, RateLimitError)
            ),
            before_sleep=log_retry_attempt,
        )
        decorated_func = decorator(func)
        return decorated_func(*args, **kwargs)

    return wrapper


@lazy_openai_retry
def analyze_content_quality(item: CollectedItem, client: OpenAI) -> tuple[float, str]:
    """Analyze content quality with more selective, realistic scoring.

    This uses a more discriminating scale that better reflects the reality
    that most social media content isn't article-worthy. Includes special
    consideration for educational/historical tech content featuring
    underrepresented figures in science and technology.

    Args:
        item: The collected item to analyze
        client: OpenAI client instance

    Returns:
        Tuple of (quality_score, explanation)
        Score is 0.0-1.0 with more realistic distribution
    """
    logger.debug(f"Starting AI quality analysis for item: {item.id}")
    # Create a more specific prompt that forces the AI to actually analyze the content
    prompt = f"""
    Analyze this social media post and give it a realistic quality score for a tech blog.

    POST CONTENT: "{item.content[:500]}"

    First, identify what this post is actually about:
    - Is it technical content (programming, systems, tools, science)?
    - Is it personal/social content (life updates, opinions, politics)?
    - Is it entitled whining or first-world problems disguised as insights?
    - Does it contain actionable insights or just commentary?
    - Is there enough technical depth to expand into an article?
    - Is it educational/historical content about tech or science (biographies, foundational discoveries)?

    Consider these factors:
    - Technical depth and actionability
    - Broader applicability vs niche concerns
    - Whether it provides useful insights vs just complaints
    - Signal-to-noise ratio for a general tech audience
    - For historical content: Does it highlight underrepresented figures? Is it about foundational breakthroughs?

    Then score it:
    - 0.8-1.0: Major technical breakthrough, deep insight, or historically significant discovery
    - 0.6-0.7: Solid technical content with practical value OR important historical figure/discovery
    - 0.5-0.55: Educational/historical content about underrepresented tech pioneers or foundational science
    - 0.4-0.5: Some technical merit, basic but useful
    - 0.2-0.3: Minimal technical value, niche, or mostly commentary
    - 0.0-0.1: Not technical, purely personal, or no actionable value

    SPECIAL CATEGORY - Historical Tech Content (0.5-0.55):
    If this post highlights an underrepresented figure in tech/science (especially women or minorities),
    or describes a foundational technological/scientific breakthrough with educational value, score it
    at 0.5-0.55 even if it lacks current-day actionability. These pieces preserve important history
    that's often overlooked in tech spaces.

    Be realistic but fair. Consider if the content would be useful to a meaningful portion of readers.

    Respond ONLY with JSON:
    {{"score": 0.X, "explanation": "Specific reason based on actual content analysis"}}
    """

    try:
        from ..config import get_config

        config = get_config()

        response = create_chat_completion(
            client=client,
            model=config.enrichment_model,  # Quality assessment
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,  # Slightly higher for more variation
            max_tokens=150,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from OpenAI")

        result_text = content.strip()
        result = json.loads(result_text)

        return float(result["score"]), str(result["explanation"])

    except Exception as e:
        # Classify and log error, but don't stop pipeline for analysis failures
        handle_openai_error(e, context="quality analysis", should_raise=False)
        # Return degraded response
        return 0.5, "Analysis failed - using default score"


@lazy_openai_retry
def extract_topics_and_themes(item: CollectedItem, client: OpenAI) -> list[str]:
    """Extract main topics and themes from content.

    This identifies what the post is actually about so we can:
    - Group related content together
    - Find additional research sources
    - Generate appropriate tags for articles

    Args:
        item: The collected item to analyze
        client: OpenAI client instance

    Returns:
        List of topic strings (e.g., ["machine learning", "python", "data science"])
    """
    prompt = f"""
    Extract the main technical topics and themes from this social media post.

    Content: "{item.content}"

    Identify 5-7 specific topics that this post covers. Focus on:
    - Programming languages (python, rust, javascript, etc.)
    - Technical concepts (machine learning, devops, cybersecurity, etc.)
    - Tools and frameworks (kubernetes, docker, react, etc.)
    - Core technologies (databases, cloud computing, networking, etc.)

    Return topics as a simple JSON array of strings:
    ["topic1", "topic2", "topic3"]

    Examples:
    - ["python", "web development", "data science"]
    - ["kubernetes", "devops", "containers"]
    - ["machine learning", "neural networks", "deep learning"]

    Use common, standard terminology. Avoid overly specific phrases.
    Prefer "web development" over "building web applications".
    Prefer "machine learning" over "ML model training".
    """

    try:
        from ..config import get_config

        config = get_config()

        response = create_chat_completion(
            client=client,
            model=config.enrichment_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=150,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from OpenAI")

        result_text = content.strip()
        topics = json.loads(result_text)

        # Validate and clean up topics
        if isinstance(topics, list) and all(isinstance(t, str) for t in topics):
            return [topic.lower().strip() for topic in topics if topic.strip()]
        else:
            console.print(f"[yellow]⚠[/yellow] Invalid topics format for {item.id}")
            return []

    except Exception as e:
        # Classify and log error, but don't stop pipeline for extraction failures
        handle_openai_error(e, context="topic extraction", should_raise=False)
        return []


@lazy_openai_retry
def research_additional_context(
    item: CollectedItem, topics: list[str], client: OpenAI
) -> str:
    """Generate research summary and context for the content.

    This creates additional context that would be useful for turning
    the social media post into a full article. Detects and handles
    meta-content (posts about other articles) specially.

    Args:
        item: The collected item
        topics: Extracted topics for context
        client: OpenAI client instance

    Returns:
        Research summary string
    """
    from .source_fetcher import extract_urls_from_content, is_meta_content

    # Detect if this is meta-content (post about an article)
    urls = extract_urls_from_content(item.content)
    is_meta = is_meta_content(item, urls)

    if is_meta and urls:
        # Meta-content: Focus on the specific article being discussed
        logger.info(f"Meta-content detected with URL: {urls[0]}")
        prompt = f"""
    You are researching context for a tech blog article about THIS SPECIFIC source:

    Original Post: "{item.content}"
    Source URL: {urls[0]}
    Topics: {", ".join(topics)}

    This post is discussing or sharing an existing article/piece. Provide research context
    that would help a writer engage with the SPECIFIC content being discussed:

    1. **Subject Context**: What is the main subject or claim being discussed? Who are the key people/projects involved?
    2. **Significance**: Why is this particular article/piece noteworthy? What makes it worth discussing?
    3. **Background**: What context do readers need to understand the significance?
    4. **Key Angles**: What aspects of this specific piece would be most interesting to highlight?

    Write 2-3 paragraphs focused on helping the writer discuss THIS SPECIFIC article,
    not generic background on the topic. Emphasize what makes this source notable.
    """
    else:
        # Standard content: Provide general background context
        prompt = f"""
    You are researching background for a tech blog article based on this social media post.

    Original Content: "{item.content}"
    Topics: {", ".join(topics)}

    Provide a research summary that would help expand this into a full blog article. Include:

    1. **Background Context**: What background knowledge would readers need?
    2. **Current State**: Where does this topic stand in the current tech landscape?
    3. **Key Questions**: What questions would readers have about this topic?
    4. **Related Concepts**: What related technologies or concepts should be covered?

    Write 2-3 paragraphs that would serve as research notes for article writing.
    Focus on factual, technical information rather than opinions.
    """

    try:
        from ..config import get_config

        config = get_config()

        response = create_chat_completion(
            client=client,
            model=config.enrichment_model,  # Research context
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from OpenAI")
        return content.strip()

    except Exception as e:
        # Classify and log error, but don't stop pipeline for research failures
        handle_openai_error(e, context="research generation", should_raise=False)
        return "Research unavailable"
