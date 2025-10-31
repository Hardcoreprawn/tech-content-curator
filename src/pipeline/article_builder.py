"""Article title, slug, and metadata generation.

This module handles the AI-powered generation of article components:
- Compelling titles that are SEO-friendly and catchy
- URL-safe slugs derived from titles
- Frontmatter metadata for static site generators

Uses GPT-4o-mini for cost-effective, high-quality generation.
"""

import json
from datetime import UTC, datetime

from openai import OpenAI
from rich.console import Console

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
    # OpenAI API Pricing (as of Oct 2024)
    PRICING = {
        "gpt-4o-mini": {"input": 0.150 / 1_000_000, "output": 0.600 / 1_000_000},
        "gpt-3.5-turbo": {"input": 0.500 / 1_000_000, "output": 1.500 / 1_000_000},
    }
    
    if model not in PRICING:
        return 0.0
    
    pricing = PRICING[model]
    return (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])


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


def generate_article_slug(title: str, client: OpenAI) -> tuple[str, float]:
    """Generate SEO-friendly slug from article title using gpt-4o-mini.

    Uses a cheap AI model to create readable, unique slugs.

    Args:
        title: The article title
        client: Configured OpenAI client

    Returns:
        Tuple of (URL-safe slug string, cost in USD)
    """
    prompt = f"""Convert this title to a short, SEO-friendly URL slug:

Rules:
- 3-6 words maximum
- Use hyphens between words
- Lowercase only
- No special characters
- Capture the key topic

Title: {title}

Respond with ONLY the slug, nothing else."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=30,
        )

        slug = response.choices[0].message.content
        if not slug:
            raise ValueError("Empty response from AI")
        slug = slug.strip()
        # Clean up any quotes or extra characters
        slug = slug.strip("\"'").lower()
        # Ensure it's safe
        slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug)
        # Remove multiple hyphens
        while "--" in slug:
            slug = slug.replace("--", "-")
        
        # Calculate cost
        usage = response.usage
        cost = calculate_text_cost(
            "gpt-4o-mini",
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )
        return slug.strip("-")[:60], cost

    except Exception as e:
        console.print(
            f"[yellow]⚠[/yellow] AI slug generation failed, using fallback: {e}"
        )
        # Fallback: simple title-based slug
        slug = title.lower().replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        return slug[:60], 0.0


def generate_article_title(
    item: EnrichedItem, content: str, client: OpenAI
) -> tuple[str, float]:
    """Generate a compelling article title using gpt-4o-mini.

    Uses gpt-4o-mini (cheap, fast, high quality) to create a catchy title.

    Args:
        item: The enriched item
        content: Generated article content
        client: Configured OpenAI client

    Returns:
        Tuple of (title, cost)
    """

    # Get first 800 chars of article for context
    article_preview = content[:800]

    prompt = f"""Create a compelling, snappy blog article title for this article.

ARTICLE PREVIEW:
{article_preview}

TOPICS: {", ".join(item.topics)}

Requirements:
- Under 60 characters (for SEO)
- Snappy and eye-catching - make people WANT to click
- Clear and descriptive - readers should know what they're getting
- NOT clickbait - be honest and direct
- Tech/professional audience appropriate
- Should accurately reflect the actual article content

Examples of good titles:
- "Why Your Database Migrations Keep Breaking"
- "The Docker Security Flaw Nobody Talks About"
- "I Built a Compiler in Rust and Here's What I Learned"
- "Stop Using Environment Variables for Secrets"

Return ONLY the title, no quotes or explanation."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
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
        return title, cost

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Title generation failed: {e}")
        # Create fallback title from topics
        if item.topics:
            return f"Understanding {item.topics[0].title()}: A Deep Dive", 0.0
        else:
            return "Tech Insights: What You Need to Know", 0.0


def create_article_metadata(item: EnrichedItem, title: str, content: str) -> dict:
    """Create frontmatter metadata for the article.

    This creates the YAML frontmatter that static site generators use.

    Args:
        item: The enriched item
        title: Article title
        content: Article content

    Returns:
        Dictionary of metadata
    """
    word_count = len(content.split())

    return {
        "title": title,
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "tags": item.topics[:5],  # Limit to 5 tags
        "summary": f"An in-depth look at {', '.join(item.topics[:2])} based on insights from the tech community.",
        "source": {
            "platform": item.original.source,
            "author": item.original.author,
            "url": normalize_url(str(item.original.url)),
            "collected_at": item.original.collected_at.isoformat(),
        },
        "quality_score": item.quality_score,
        "word_count": word_count,
        "reading_time": f"{max(1, round(word_count / 200))} min read",
        "cover": {
            "image": "",
            "alt": "",
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }
