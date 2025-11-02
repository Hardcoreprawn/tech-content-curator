"""Base collector interface and shared utilities.

All collectors should follow this pattern:
1. Implement collect_from_<source>() function
2. Return List[CollectedItem]
3. Handle errors gracefully
4. Use console for user feedback
5. Apply rate limiting

Shared utilities:
- Content filtering functions
- HTML cleaning
- Title extraction
"""

from rich.console import Console

from ..models import PipelineConfig

console = Console()


def is_entitled_whining(content: str) -> bool:
    """Filter out entitled complaints about free/open-source projects.

    We want constructive criticism, not whining about free software.
    This helps maintain a positive, solution-oriented content vibe.

    Args:
        content: Text content to check

    Returns:
        True if content appears to be entitled whining
    """
    content_lower = content.lower()

    # Entitled complaints about free software
    entitled_patterns = [
        "should be free",
        "shouldn't cost",
        "charging for",
        "how dare they",
        "outrageous price",
        "greedy developers",
        "money grab",
        "cash grab",
    ]

    # Context that indicates it's about pricing/monetization
    monetization_context = [
        "price",
        "cost",
        "pay",
        "subscription",
        "license",
        "free",
        "open source",
        "oss",
    ]

    has_entitled = any(pattern in content_lower for pattern in entitled_patterns)
    has_monetization = any(word in content_lower for word in monetization_context)

    return has_entitled and has_monetization


def is_political_content(content: str) -> bool:
    """Filter out purely political content.

    We focus on technology, science, and innovation. Policy discussions
    about tech (regulation, privacy laws, etc.) are OK, but pure politics
    should be filtered out.

    Args:
        content: Text content to check

    Returns:
        True if content is primarily political (not tech-related)
    """
    content_lower = content.lower()

    # Political keywords
    political_words = [
        "democrat",
        "republican",
        "liberal",
        "conservative",
        "leftist",
        "right-wing",
        "left-wing",
        "trump",
        "biden",
        "congress",
        "senate",
        "election",
        "vote",
        "voter",
        "ballot",
        "politician",
        "political party",
    ]

    # Tech policy keywords (these are OK)
    tech_policy_words = [
        "privacy",
        "regulation",
        "antitrust",
        "monopoly",
        "data protection",
        "encryption",
        "surveillance",
        "net neutrality",
        "copyright",
        "patent",
        "open source",
        "security",
        "gdpr",
        "section 230",
    ]

    # Count political vs tech-policy mentions
    political_count = sum(1 for word in political_words if word in content_lower)
    tech_policy_count = sum(1 for word in tech_policy_words if word in content_lower)

    # If it mentions politics without tech policy context, filter it
    return political_count > 0 and tech_policy_count == 0


def is_relevant_content(content: str, title: str, config: PipelineConfig) -> bool:
    """Determine if content is relevant to tech/science topics.

    Uses configurable filters to focus on desired content types while
    excluding off-topic material.

    Args:
        content: Main content text
        title: Content title
        config: Pipeline configuration with content preferences

    Returns:
        True if content is relevant, False otherwise
    """
    text = f"{title} {content}".lower()

    # Parse negative keywords from config
    negative_keywords = [
        kw.strip() for kw in config.relevance_negative_keywords.split(",") if kw.strip()
    ]

    # Check for negative keywords first (quick rejection)
    if any(keyword in text for keyword in negative_keywords):
        return False

    # Tech-related keywords (very broad to avoid false negatives)
    tech_keywords = [
        "software",
        "hardware",
        "code",
        "programming",
        "developer",
        "algorithm",
        "data",
        "api",
        "cloud",
        "server",
        "database",
        "app",
        "application",
        "web",
        "mobile",
        "computer",
        "tech",
        "digital",
        "cyber",
        "internet",
        "network",
        "system",
        "linux",
        "windows",
        "mac",
        "android",
        "ios",
        "python",
        "javascript",
        "rust",
        "golang",
        "java",
        "ai",
        "ml",
        "machine learning",
        "neural",
        "llm",
        "open source",
        "github",
        "git",
        "repository",
    ]

    # Science keywords
    science_keywords = [
        "research",
        "study",
        "scientist",
        "laboratory",
        "experiment",
        "discovery",
        "breakthrough",
        "published",
        "paper",
        "journal",
        "university",
        "professor",
        "phd",
        "doctorate",
        "biology",
        "physics",
        "chemistry",
        "astronomy",
        "mathematics",
        "quantum",
        "genome",
        "molecule",
        "particle",
        "theory",
    ]

    # Policy keywords (tech regulation, etc.)
    policy_keywords = [
        "regulation",
        "privacy",
        "security",
        "encryption",
        "surveillance",
        "antitrust",
        "monopoly",
        "patent",
        "copyright",
        "gdpr",
        "compliance",
        "legislation",
    ]

    # Check if content matches enabled categories
    has_tech = config.allow_tech_content and any(kw in text for kw in tech_keywords)
    has_science = config.allow_science_content and any(
        kw in text for kw in science_keywords
    )
    has_policy = config.allow_policy_content and any(
        kw in text for kw in policy_keywords
    )

    return has_tech or has_science or has_policy


def clean_html_content(html_content: str) -> str:
    """Clean HTML content to plain text.

    Removes HTML tags and normalizes whitespace while preserving
    readability.

    Args:
        html_content: HTML string to clean

    Returns:
        Plain text content
    """
    import re
    from html import unescape

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", html_content)

    # Unescape HTML entities
    text = unescape(text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return text


def extract_title_from_content(content: str, max_length: int = 80) -> str:
    """Extract a title from content if none provided.

    Uses the first sentence or line as the title, truncating if needed.

    Args:
        content: Content text to extract title from
        max_length: Maximum length of extracted title

    Returns:
        Extracted title
    """
    if not content:
        return "Untitled"

    # Get first line or sentence
    lines = content.split("\n")
    first_line = lines[0].strip()

    # If first line is too short, try first sentence
    if len(first_line) < 20 and len(lines) > 1:
        sentences = content.split(".")
        if sentences:
            first_line = sentences[0].strip()

    # Truncate if too long
    if len(first_line) > max_length:
        first_line = first_line[: max_length - 3] + "..."

    return first_line if first_line else "Untitled"
