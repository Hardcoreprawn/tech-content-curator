"""Article title, slug, and metadata generation.

This module handles the AI-powered generation of article components:
- Compelling titles that are SEO-friendly and catchy
- URL-safe slugs derived from titles
- Frontmatter metadata for static site generators

Uses GPT-4o-mini for cost-effective, high-quality generation.
"""

import re
from datetime import UTC, datetime

from ..utils.logging import get_logger
from ..utils.openai_client import create_chat_completion
from ..utils.sanitization import safe_filename

logger = get_logger(__name__)

from openai import OpenAI
from rich.console import Console

from ..config import QUALITY_THRESHOLDS
from ..content.categorizer import ArticleCategorizer
from ..content.readability import ReadabilityAnalyzer
from ..models import EnrichedItem
from ..utils.url_tools import normalize_url

console = Console()


def calculate_text_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for a text generation API call.

    Args:
        model: Model name (e.g., "gpt-4o-mini")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    logger.debug(
        f"Calculating text cost: {model} ({input_tokens} in, {output_tokens} out)"
    )
    # OpenAI API Pricing (as of Oct 2024)
    PRICING = {
        "gpt-4o-mini": {"input": 0.150 / 1_000_000, "output": 0.600 / 1_000_000},
        "gpt-3.5-turbo": {"input": 0.500 / 1_000_000, "output": 1.500 / 1_000_000},
    }

    if model not in PRICING:
        logger.warning(f"Unknown model for pricing: {model}, returning 0.0")
        return 0.0

    pricing = PRICING[model]
    cost = (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])
    logger.debug(f"Calculated cost: ${cost:.8f}")
    return cost


def calculate_image_cost(model: str = "dall-e-3-hd-1792x1024") -> float:
    """Calculate cost for an image generation API call.

    Args:
        model: Image model specification

    Returns:
        Cost in USD
    """
    PRICING = {
        "dall-e-3-hd-1792x1024": 0.080,  # HD quality wide image
        "dall-e-3-standard-1024x1024": 0.040,  # Standard quality square
    }
    return PRICING.get(model, 0.0)


def generate_article_slug(title: str) -> str:
    """Generate SEO-friendly slug from article title.

    Uses python-slugify for robust Unicode handling and safe character conversion.
    Prevents directory traversal and other path-based attacks.

    Args:
        title: The article title

    Returns:
        URL-safe slug string (lowercase, hyphenated, filesystem-safe)

    Raises:
        ValueError: If title is empty or becomes empty after sanitization
    """
    logger.debug(f"Generating slug for title: {title[:50]}...")

    if not title or not isinstance(title, str):
        raise ValueError(
            f"Invalid title: expected non-empty string, got {type(title).__name__}"
        )

    # Strip whitespace
    title = title.strip()
    if not title:
        # Fallback for empty/whitespace-only titles
        return "untitled-article"

    try:
        # Use safe_filename to generate slug with sanitization
        # This uses python-slugify internally and validates filesystem safety
        slug = safe_filename(title, max_length=60)
    except ValueError:
        # Fallback if sanitization fails (e.g., only special chars)
        logger.warning(f"Failed to sanitize slug from title '{title}', using fallback")
        slug = "untitled-article"

    logger.debug(f"Generated slug: {slug}")
    return slug


def generate_article_title(
    item: EnrichedItem,
    content: str,
    client: OpenAI,
    recent_titles: list[str] | None = None,
) -> tuple[str, float]:
    """Generate a compelling article title using gpt-4o-mini.

    Uses gpt-4o-mini (cheap, fast, high quality) to create a catchy title.

    Args:
        item: The enriched item
        content: Generated article content
        client: Configured OpenAI client
        recent_titles: Optional list of recently generated titles to avoid repetition

    Returns:
        Tuple of (title, cost)
    """
    logger.debug(f"Generating article title for: {str(item.original.url)[:60]}...")

    # Get first 800 chars of article for context
    article_preview = content[:800]

    # Add recent titles context to avoid repetition
    recent_context = ""
    if recent_titles:
        recent_context = "\n\nRECENT TITLES (avoid similar patterns):\n" + "\n".join(
            f"- {t}" for t in recent_titles[-5:]
        )

    prompt = f"""Create a compelling, snappy blog article title for this article.

ARTICLE PREVIEW:
{article_preview}

TOPICS: {", ".join(item.topics)}{recent_context}

Requirements:
- Under 60 characters (for SEO)
- Snappy and eye-catching - make people WANT to click
- Clear and descriptive - readers should know what they're getting
- NOT clickbait - be honest and direct
- Tech/professional audience appropriate
- Should accurately reflect the actual article content
- VARY YOUR STYLE - don't repeat opening words or patterns from recent titles

Examples of good titles:
- "Why Your Database Migrations Keep Breaking"
- "The Docker Security Flaw Nobody Talks About"
- "I Built a Compiler in Rust and Here's What I Learned"
- "Stop Using Environment Variables for Secrets"

Return ONLY the title, no quotes or explanation."""

    try:
        from ..config import get_config

        config = get_config()

        logger.debug(f"Requesting title from OpenAI ({config.title_model})")
        response = create_chat_completion(
            client=client,
            model=config.title_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=50,
        )

        response_content = response.choices[0].message.content
        if response_content is None or not response_content.strip():
            raise ValueError("Empty response from OpenAI")

        title = response_content.strip().strip("\"'")

        # Fallback if too long
        if len(title) > 60:
            # Try to truncate at word boundary
            words = title.split()
            truncated = ""
            for word in words:
                if len(truncated + " " + word) <= 57:  # Leave room for "..."
                    truncated += " " + word if truncated else word
                else:
                    break
            title = truncated + "..." if truncated != title else title[:57] + "..."

        # Calculate cost
        usage = response.usage
        cost = calculate_text_cost(
            "gpt-4o-mini",
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )
        logger.info(f"Generated title: {title} (cost: ${cost:.8f})")
        return title, cost

    except Exception as e:
        logger.error(f"Title generation failed: {e}", exc_info=True)
        console.print(f"[yellow]⚠[/yellow] Title generation failed: {e}")
        # Create fallback title from topics
        if item.topics:
            return f"Understanding {item.topics[0].title()}: A Deep Dive", 0.0
        else:
            return "Tech Insights: What You Need to Know", 0.0


def extract_article_summary(content: str, max_length: int = 200) -> str:
    """Extract a compelling summary from article content.

    Intelligently extracts substantive content, skipping generic openings.
    Looks for sentences with key information rather than meta-descriptions.
    Fast, free, and guaranteed to reflect actual article content.

    Args:
        content: The article content (markdown)
        max_length: Maximum character length for summary (default 200)

    Returns:
        Summary string extracted from content, truncated at word boundaries
    """
    # Remove markdown formatting for cleaner summary
    cleaned = content.replace("## ", "").replace("# ", "")

    # Split into sentences (split on period, question mark, exclamation)
    sentences = re.split(r"[.!?]+", cleaned)

    # Filter out very short sentences and generic filler
    generic_phrases = {
        "based on",
        "in this article",
        "we will explore",
        "let's look at",
        "understanding",
        "introduction",
        "overview",
    }

    substantive_sentences = []
    for sentence in sentences:
        s = sentence.strip()
        if not s or len(s) < 15:
            continue

        # Skip if it's mostly generic
        lower_s = s.lower()
        if any(phrase in lower_s for phrase in generic_phrases) and len(s) < 60:
            continue

        substantive_sentences.append(s)

    # Build summary from substantive sentences
    summary = ""

    # Prefer a mixture: if we have at least 2 substantive sentences,
    # skip the first one if it's very generic, use the next one(s)
    start_idx = 0
    if len(substantive_sentences) > 1:
        first_s = substantive_sentences[0].lower()
        if any(phrase in first_s for phrase in generic_phrases):
            start_idx = 1

    # Take 1-2 substantive sentences
    for i in range(start_idx, min(start_idx + 2, len(substantive_sentences))):
        candidate = (summary + " " + substantive_sentences[i]).strip()
        if len(candidate) <= max_length:
            summary = candidate
        else:
            break

    # Clean up whitespace
    summary = " ".join(summary.split())

    # Fallback if nothing worked
    if not summary or len(summary) < 20:
        # Use first non-empty sentence
        for s in sentences:
            s = s.strip()
            if len(s) > 20:
                summary = s
                break

    if not summary:
        # Last resort: first max_length chars
        summary = cleaned.strip()

    # Clean up whitespace
    summary = " ".join(summary.split())

    # Truncate at word boundary if needed
    if len(summary) > max_length:
        # Reserve space for ellipsis if needed
        target_length = max_length - 3  # Reserve for "..."
        # Find last space before target_length
        truncated = summary[:target_length].rsplit(" ", 1)[0]
        # Add ellipsis if we actually truncated mid-sentence
        if not truncated.endswith((".", "!", "?")):
            summary = truncated + "..."
        else:
            summary = truncated
    elif summary and not summary.endswith(("!", "?", ".")):
        # Add period if it's not there and we didn't truncate
        summary += "."

    return summary


def analyze_article_quality(content: str, difficulty_level: str) -> tuple[dict, bool]:
    """Analyze article quality using readability and quality scoring.

    Args:
        content: The article content
        difficulty_level: Target difficulty level (beginner, intermediate, advanced)

    Returns:
        Tuple of (quality_metrics dict, passed_threshold bool)
    """
    readability_analyzer = ReadabilityAnalyzer()

    # Analyze readability
    readability = readability_analyzer.analyze(content)

    # Check if readability matches target
    matches_target, match_explanation = readability_analyzer.matches_target_difficulty(
        readability, difficulty_level
    )

    # Get quality thresholds for this difficulty level
    thresholds = QUALITY_THRESHOLDS.get(
        difficulty_level, QUALITY_THRESHOLDS["intermediate"]
    )

    # Check if meets minimum thresholds
    passed = (
        readability.flesch_reading_ease >= thresholds["min_flesch_ease"]
        and readability.grade_level <= thresholds["max_grade_level"]
    )

    quality_metrics = {
        "readability_score": readability.flesch_reading_ease,
        "grade_level": readability.grade_level,
        "fog_index": readability.fog_index,
        "smog_index": readability.smog_index,
        "overall_rating": readability.overall_rating,
        "matches_target": matches_target,
        "match_explanation": match_explanation,
        "recommendations": readability.recommendations,
        "passed_threshold": passed,
    }

    if not passed:
        console.print(
            f"[yellow]⚠[/yellow] Article readability below threshold: {match_explanation}"
        )

    return quality_metrics, passed


def create_article_metadata(item: EnrichedItem, title: str, content: str) -> dict:
    """Create frontmatter metadata for the article.

    This creates the YAML frontmatter that static site generators use.
    Automatically extracts summary from the article content and performs
    quality analysis.

    Args:
        item: The enriched item
        title: Article title
        content: Article content

    Returns:
        Dictionary of metadata
    """
    logger.debug(f"Creating metadata for article: {title}")
    word_count = len(content.split())
    summary = extract_article_summary(content)
    logger.debug(f"Extracted summary ({len(summary)} chars) for article")

    # Add categorization (content type, difficulty, audience)
    categorizer = ArticleCategorizer()
    categories = categorizer.categorize(item, content)
    logger.debug(
        f"Categorized article: {categories['content_type']}, difficulty={categories['difficulty_level']}"
    )

    # Analyze article quality (Phase 1.3)
    quality_metrics, _ = analyze_article_quality(
        content, categories["difficulty_level"]
    )
    logger.debug(
        f"Quality analysis: flesch={quality_metrics['readability_score']:.1f}, grade={quality_metrics['grade_level']:.1f}"
    )

    # Normalize and limit tags
    from ..content.tag_normalizer import normalize_tags

    normalized_tags = normalize_tags(item.topics, max_tags=5)

    metadata = {
        "title": title,
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "tags": normalized_tags,  # Normalized canonical tags (max 5)
        "summary": summary,
        "source": {
            "platform": item.original.source,
            "author": item.original.author,
            "url": normalize_url(str(item.original.url)),
            "collected_at": item.original.collected_at.isoformat(),
        },
        "quality_score": item.quality_score,
        "word_count": word_count,
        "reading_time": f"{max(1, round(word_count / 200))} min read",
        # Categorization fields (Phase 1.2)
        "content_type": categories["content_type"],
        "difficulty": categories["difficulty_level"],
        "audience": categories["audience"],
        "estimated_read_time": categories["estimated_read_time"],
        # Readability metrics (Phase 1.3)
        "readability": {
            "flesch_score": round(quality_metrics["readability_score"], 1),
            "grade_level": round(quality_metrics["grade_level"], 1),
            "rating": quality_metrics["overall_rating"],
            "matches_target": quality_metrics["matches_target"],
        },
        "cover": {
            "image": "",
            "alt": "",
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }
    logger.info(f"Created metadata: {word_count} words, {len(item.topics)} topics")
    return metadata
