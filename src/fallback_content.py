"""Fallback content generation when API is unavailable.

This module provides graceful degradation strategies when OpenAI API credits
are exhausted or the API is unavailable. It includes:

1. Template-based article generation
2. Cached content retrieval
3. Skeletal article generation from metadata
4. Placeholder content generation

These fallback mechanisms ensure the pipeline continues operating even when
the primary API is unavailable, just with reduced quality/automation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from .models import EnrichedItem, GeneratedArticle

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class FallbackTemplate:
    """A template for generating articles without API calls."""

    name: str
    structure: list[str]  # Section names
    template: str  # Markdown template with {placeholders}


# Simple fallback templates
FALLBACK_TEMPLATES = {
    "quick_summary": FallbackTemplate(
        name="Quick Summary",
        structure=[
            "Introduction",
            "Key Points",
            "Why It Matters",
            "Next Steps",
        ],
        template="""# {title}

**Summary:** {summary}

## Key Points

- {point_1}
- {point_2}
- {point_3}

## Why It Matters

{significance}

## Next Steps

- Learn more: [Original source]({source_url})
- Related topics: {related_topics}

---

**Note:** This is a generated summary created with fallback templates.
Full article generation was unavailable at the time of creation.

*Generated on {generated_date}*
""",
    ),
    "detailed_outline": FallbackTemplate(
        name="Detailed Outline",
        structure=[
            "Overview",
            "Background",
            "Main Points",
            "Analysis",
            "Conclusions",
            "References",
        ],
        template="""# {title}

## Overview

{summary}

## Background

{background}

## Main Points

1. {point_1}
2. {point_2}
3. {point_3}

## Analysis

### Point 1: {point_1_title}
{point_1_analysis}

### Point 2: {point_2_title}
{point_2_analysis}

### Point 3: {point_3_title}
{point_3_analysis}

## Conclusions

{conclusion}

## References

- Original source: {source_url}
- Topics: {topics}

---

**Generated:** {generated_date}
**Status:** Fallback template (API unavailable)
""",
    ),
    "bullet_points": FallbackTemplate(
        name="Bullet Points",
        structure=["Title", "Summary", "Key Takeaways"],
        template="""# {title}

## Summary
{summary}

## Key Takeaways

- **Overview:** {point_1}
- **Implications:** {point_2}
- **Action Items:** {point_3}
- **Resources:** {point_4}

## Source Information

- Original: {source_url}
- Topics: {topics}
- Generated: {generated_date}

---

*This article was generated using fallback templates due to API unavailability.*
""",
    ),
}


def extract_fallback_data(item: EnrichedItem) -> dict[str, Any]:
    """Extract maximum usable information from an enriched item.

    Args:
        item: The enriched item

    Returns:
        Dictionary of data suitable for template substitution
    """
    topics = ", ".join(item.topics[:5]) if item.topics else "General"
    summary = (
        item.research_summary[:500] if item.research_summary else item.original.title
    )

    # Try to extract key points from summary
    sentences = summary.split(". ")
    points = [s.strip() for s in sentences[:4] if s.strip()]
    while len(points) < 4:
        points.append("Additional information available in source")

    return {
        "title": item.original.title,
        "summary": summary[:300],
        "background": f"This article covers developments in {topics}.",
        "point_1": points[0] if len(points) > 0 else "Key point 1",
        "point_2": points[1] if len(points) > 1 else "Key point 2",
        "point_3": points[2] if len(points) > 2 else "Key point 3",
        "point_4": points[3] if len(points) > 3 else "Key point 4",
        "point_1_title": f"Aspect of {topics.split(',')[0]}",
        "point_1_analysis": "See source material for detailed analysis.",
        "point_2_title": "Current developments",
        "point_2_analysis": "Following the latest industry trends and updates.",
        "point_3_title": "Future implications",
        "point_3_analysis": "Expected impact and next steps.",
        "significance": (
            f"Understanding these developments in {topics} is crucial for "
            "staying informed about the latest industry trends."
        ),
        "conclusion": (
            f"The information covered in this article highlights important "
            f"aspects of {topics} that deserve attention and further exploration."
        ),
        "source_url": str(item.original.url),
        "topics": topics,
        "generated_date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    }


def generate_fallback_article(
    item: EnrichedItem,
    template_name: str = "quick_summary",
) -> GeneratedArticle:
    """Generate a fallback article using templates.

    Args:
        item: The enriched item
        template_name: Name of the template to use

    Returns:
        A GeneratedArticle with template-based content
    """
    template = (
        FALLBACK_TEMPLATES.get(template_name) or FALLBACK_TEMPLATES["quick_summary"]
    )
    data = extract_fallback_data(item)

    # Generate content from template
    try:
        content = template.template.format(**data)
    except KeyError as e:
        logger.warning(f"Missing template data for {e}, using partial content")
        # Fallback to basic template if substitution fails
        content = f"# {data['title']}\n\n{data['summary']}\n\n**Source:** {data['source_url']}"

    # Calculate approximate word count
    word_count = len(content.split())

    # Generate slug from title
    slug = item.original.title.lower().replace(" ", "-").replace(":", "")[:50]

    article = GeneratedArticle(
        title=item.original.title,
        content=content,
        summary=data["summary"],
        sources=[item],
        tags=item.topics[:5],
        word_count=word_count,
        generated_at=datetime.now(UTC),
        filename=f"{datetime.now(UTC).strftime('%Y-%m-%d')}-{slug}.md",
        generation_costs={"fallback_generation": 0.0},  # No API cost
        generator_name="FallbackTemplateGenerator",
        illustrations_count=0,
        voice_profile="default",
        voice_metadata={"mode": "fallback", "template": template_name},
    )

    logger.info(f"Generated fallback article: {article.title}")
    return article


def load_cached_article(cache_path: Path, item_url: str) -> GeneratedArticle | None:
    """Try to load a cached article for the given URL.

    Args:
        cache_path: Path to the cache file
        item_url: URL of the original item

    Returns:
        Cached GeneratedArticle if found, None otherwise
    """
    if not cache_path.exists():
        return None

    try:
        with open(cache_path) as f:
            cache = json.load(f)

        for cached in cache.get("articles", []):
            if cached.get("source_url") == item_url:
                logger.info(f"Loaded cached article for {item_url}")
                # This would need proper deserialization in real code
                return None  # Placeholder

    except Exception as e:
        logger.warning(f"Failed to load cache: {e}")

    return None


def get_fallback_strategy(degradation_mode: str) -> str:
    """Get recommended fallback template based on degradation mode.

    Args:
        degradation_mode: Current degradation mode ("degraded", "template", "offline")

    Returns:
        Name of recommended template
    """
    strategies = {
        "full": "quick_summary",  # Normal mode
        "degraded": "detailed_outline",  # Still some capacity, use more detailed template
        "template": "bullet_points",  # Limited capacity, use simple template
        "cached": "quick_summary",  # Using cache
        "offline": "bullet_points",  # Minimal template
    }
    return strategies.get(degradation_mode, "quick_summary")


def create_status_page(
    error_summary: dict[str, Any],
    fallback_mode: str,
) -> str:
    """Create a status page for display when API is unavailable.

    Args:
        error_summary: Summary of API errors
        fallback_mode: Current fallback mode

    Returns:
        Markdown content for status page
    """
    mode_descriptions = {
        "full": "🟢 Normal - API operational",
        "degraded": "🟡 Degraded - API available but limited",
        "template": "🟠 Limited - Using templates only",
        "cached": "🟠 Limited - Using cached content",
        "offline": "🔴 Offline - No API available",
    }

    status_html = f"""# System Status Report

**Current Status:** {mode_descriptions.get(fallback_mode, "Unknown")}

**Generated:** {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")}

## API Status

- **Total Errors:** {error_summary.get("total_errors", 0)}
- **Recent Errors (24h):** {error_summary.get("recent_errors_24h", 0)}
- **Current Mode:** {error_summary.get("current_mode", "unknown")}

## Error Types

"""

    for error_type, count in error_summary.get("error_types", {}).items():
        status_html += f"- {error_type}: {count}\n"

    if error_summary.get("last_error"):
        last_error = error_summary["last_error"]
        status_html += f"""

## Last Error

- **Type:** {last_error.get("type", "unknown")}
- **Time:** {last_error.get("timestamp", "unknown")}
- **Message:** {last_error.get("message", "N/A")}
"""

    status_html += """

## What's Happening

When the system enters a degraded or offline mode:

1. **Degraded Mode**: Articles are still generated but use cached prompts and templates
2. **Template Mode**: Articles use simple Markdown templates without API calls
3. **Offline Mode**: Only cached content and templates are available

## Recovery

The system will automatically recover to normal operation when:

- API credentials are valid and service is accessible
- Quota limits are reset
- Rate limits expire (typically within 60 seconds)
- Network connectivity is restored

For immediate help:
- Check OpenAI API status: https://status.openai.com
- Verify API key in configuration
- Check network connectivity
- Review error logs for more details

---

*Generated by API Credit Manager*
"""
    return status_html
