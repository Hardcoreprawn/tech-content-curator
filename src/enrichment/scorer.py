"""Fast heuristic scoring for content quality assessment.

This module provides quick quality assessment without AI API calls,
using measurable content features and engagement metrics.

The heuristic scorer evaluates:
- Content length and structure
- Technical keywords and depth indicators
- Engagement metrics (likes, shares, replies)
- Educational and news value
- Authority signals
- Negative indicators (personal content, excessive emoji, etc.)

Score ranges:
- 0.8-1.0: Exceptional content (viral engagement, deep technical)
- 0.6-0.7: High quality (good engagement, solid technical depth)
- 0.4-0.5: Decent content (moderate value)
- 0.2-0.3: Low quality (minimal value, niche)
- 0.0-0.1: Not suitable (personal, shallow, off-topic)

The heuristic score is combined with AI quality assessment to
produce the final enrichment score. This two-stage approach
saves API costs by filtering low-quality content early.
"""

import re

from ..models import CollectedItem
from ..utils.logging import get_logger
from .adaptive_scoring import ScoringAdapter

logger = get_logger(__name__)


def calculate_heuristic_score(
    item: CollectedItem, adapter: ScoringAdapter | None = None
) -> tuple[float, str]:
    """Calculate quality score using fast heuristics with adaptive improvements.

    This provides a baseline score using measurable factors:
    - Content length and structure
    - Technical keywords and indicators
    - Engagement metrics from source platform
    - Language and formatting quality
    - Adaptive adjustments learned from AI feedback

    Args:
        item: The collected item to analyze
        adapter: Optional scoring adapter for learned improvements

    Returns:
        Tuple of (heuristic_score, explanation)
    """
    logger.debug(f"Calculating heuristic score for item: {item.id}")
    score = 0.0
    factors = []

    content = item.content.lower()
    original_content = item.content

    # Length factors (sweet spot: 100-800 chars)
    length = len(original_content)
    if length < 50:
        factors.append("too short")
    elif length < 100:
        score += 0.1
        factors.append("short but viable")
    elif 100 <= length <= 400:
        score += 0.3
        factors.append("good length")
    elif 400 < length <= 800:
        score += 0.2
        factors.append("substantial length")
    else:
        score += 0.1
        factors.append("very long")

    # Technical keyword indicators
    tech_keywords = [
        "python",
        "javascript",
        "rust",
        "go",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "algorithm",
        "database",
        "api",
        "framework",
        "library",
        "open source",
        "machine learning",
        "ai",
        "devops",
        "cloud",
        "architecture",
        "performance",
        "security",
        "blockchain",
        "web3",
        "git",
        "linux",
        "unix",
        "programming",
        "software",
        "hardware",
        "network",
        "protocol",
        "stack",
        "backend",
        "frontend",
    ]

    tech_count = sum(1 for keyword in tech_keywords if keyword in content)
    if tech_count >= 3:
        score += 0.3
        factors.append(f"{tech_count} tech keywords")
    elif tech_count >= 1:
        score += 0.2
        factors.append(f"{tech_count} tech keyword(s)")

    # Structure indicators (links, code blocks, lists)
    if "http" in content:
        score += 0.1
        factors.append("includes links")

    if any(marker in original_content for marker in ["```", "`", "    "]):
        score += 0.2
        factors.append("includes code")

    if original_content.count("\n") >= 2:
        score += 0.1
        factors.append("structured text")

    # Engagement metrics (if available) - MUCH MORE IMPORTANT
    if hasattr(item, "metadata") and item.metadata:
        likes = item.metadata.get("favourites_count", 0)
        shares = item.metadata.get("reblogs_count", 0)
        replies = item.metadata.get("replies_count", 0)

        # Calculate weighted engagement (replies = discussion depth)
        engagement = likes + (shares * 2) + (replies * 3)

        # More granular engagement scoring
        if engagement >= 1000:
            score += 0.35
            factors.append(f"viral engagement ({engagement})")
        elif engagement >= 500:
            score += 0.30
            factors.append(f"very high engagement ({engagement})")
        elif engagement >= 100:
            score += 0.25
            factors.append(f"high engagement ({engagement})")
        elif engagement >= 50:
            score += 0.15
            factors.append(f"good engagement ({engagement})")
        elif engagement >= 10:
            score += 0.10
            factors.append(f"some engagement ({engagement})")

        # Discussion depth bonus (high replies relative to likes)
        if replies > 20 and replies > likes * 0.05:
            score += 0.1
            factors.append("active discussion")

    # Authority signals - official/known accounts
    author = item.author.lower() if hasattr(item, "author") and item.author else ""
    authority_accounts = [
        "psf",
        "thepsf",
        "python",
        "github",
        "gitlab",
        "microsoft",
        "mozilla",
        "rust",
        "golang",
        "docker",
        "kubernetes",
        "linuxfoundation",
        "torvalds",
        "gvanrossum",
        "dhh",
        "kentcdodds",
        "dan_abramov",
        "bagder",
        "nixcraft",
        "climagic",
        "b0rk",
        "jezenthomas",
    ]

    if any(auth in author for auth in authority_accounts):
        score += 0.15
        factors.append("authority account")

    # Project/organization accounts (often have more valuable content)
    org_indicators = ["foundation", "project", "team", "official", "core"]
    if any(ind in author for ind in org_indicators):
        score += 0.10
        factors.append("organization account")

    # Negative indicators
    personal_indicators = [
        "i feel",
        "my day",
        "my life",
        "personally",
        "imo",
        "just me",
    ]
    if any(indicator in content for indicator in personal_indicators):
        score -= 0.2
        factors.append("personal content")

    # News/announcement indicators (timely, important)
    news_indicators = [
        "announcing",
        "released",
        "launched",
        "new version",
        "breaking",
        "vulnerability",
        "security",
        "critical",
        "update",
        "available now",
        "just released",
        "today",
        "major",
        "important",
    ]
    news_count = sum(1 for indicator in news_indicators if indicator in content)
    if news_count >= 2:
        score += 0.20
        factors.append("newsworthy announcement")
    elif news_count >= 1:
        score += 0.10
        factors.append("announcement content")

    # Educational/tutorial indicators
    educational_indicators = [
        "how to",
        "tutorial",
        "guide",
        "learn",
        "explained",
        "introduction",
        "getting started",
        "step by step",
        "walkthrough",
        "best practices",
        "tips",
        "tricks",
        "examples",
    ]
    edu_count = sum(1 for indicator in educational_indicators if indicator in content)
    if edu_count >= 2:
        score += 0.15
        factors.append("educational content")
    elif edu_count >= 1:
        score += 0.08
        factors.append("somewhat educational")

    # Technical depth indicators
    depth_indicators = [
        "architecture",
        "implementation",
        "performance",
        "benchmark",
        "optimization",
        "analysis",
        "deep dive",
        "internals",
        "how it works",
        "under the hood",
        "technical details",
        "design",
        "algorithm",
    ]
    depth_count = sum(1 for indicator in depth_indicators if indicator in content)
    if depth_count >= 2:
        score += 0.15
        factors.append("technical depth")
    elif depth_count >= 1:
        score += 0.08
        factors.append("some depth")

    # Excessive emoji/symbols (but be less harsh)
    emoji_count = sum(1 for char in original_content if ord(char) > 127)
    if emoji_count > 20:
        score -= 0.15
        factors.append("emoji heavy")
    elif emoji_count > 10:
        score -= 0.05
        factors.append("some emoji")

    # Content richness penalties - what's MISSING matters
    # No code examples in a tech post?
    has_code = any(
        marker in original_content
        for marker in ["```", "`", "    ", "def ", "function ", "class ", "import "]
    )
    if not has_code and tech_count >= 2:
        score -= 0.10
        factors.append("no code examples")

    # Shallow content - just links without substance
    link_count = content.count("http")
    word_count = len(original_content.split())
    if link_count > 0 and word_count < 50:
        score -= 0.15
        factors.append("link-only, shallow")

    # Missing multiple sources (single link posts are weaker)
    if link_count == 1:
        score -= 0.08
        factors.append("single source")
    elif link_count == 0 and word_count > 100:
        score -= 0.12
        factors.append("no sources cited")

    # Lack of actionable content
    action_indicators = [
        "try",
        "use",
        "install",
        "download",
        "check out",
        "see",
        "read",
        "should",
        "can",
        "how",
        "step",
        "guide",
        "tutorial",
    ]
    action_count = sum(1 for indicator in action_indicators if indicator in content)
    if action_count == 0 and word_count > 50:
        score -= 0.08
        factors.append("not actionable")

    # Vague or clickbait language (diminishes quality)
    vague_indicators = [
        "amazing",
        "incredible",
        "mind-blowing",
        "insane",
        "crazy",
        "wow",
        "omg",
    ]
    vague_count = sum(1 for indicator in vague_indicators if indicator in content)
    if vague_count >= 2:
        score -= 0.10
        factors.append("vague/clickbait language")

    # Thread/continuation posts often lack context
    if "🧵" in original_content or "1/" in original_content or "thread" in content:
        score -= 0.05
        factors.append("thread post (may lack context)")

    # ALL CAPS or excessive punctuation (be acronym-aware)
    # Normalize common acronyms so they don't count against caps ratio
    KNOWN_ACRONYMS = {
        "RISC-V",
        "CPU",
        "GPU",
        "API",
        "HTTP",
        "HTTPS",
        "SQL",
        "NoSQL",
        "AWS",
        "GCP",
        "GDPR",
        "CLI",
        "LLM",
        "AI",
        "ML",
        "NLP",
        "KVM",
        "SSH",
        "TCP",
        "UDP",
        "TLS",
        "SSL",
        "JSON",
        "YAML",
        "CSV",
        "OCR",
        "IDE",
        "CI",
        "CD",
        "CI/CD",
        "SRE",
        "DNS",
        "K8S",
        "CUDA",
    }

    def _lowercase_acronyms(text: str) -> str:
        # Replace known acronyms first
        for ac in KNOWN_ACRONYMS:
            text = re.sub(rf"\b{re.escape(ac)}\b", ac.lower(), text)

        # Replace generic acronym-like tokens (2-8 chars of A-Z/0-9 possibly with hyphens)
        def repl(m: re.Match) -> str:
            token = m.group(0)
            # Allow hyphenated/digit-containing short tokens commonly used as acronyms
            if 2 <= len(token) <= 8 and re.fullmatch(r"[A-Z0-9-]+", token):
                return token.lower()
            return token

        return re.sub(r"\b[A-Z0-9-]{2,10}\b", repl, text)

    normalized_for_caps = _lowercase_acronyms(original_content)
    caps_ratio = sum(1 for c in normalized_for_caps if c.isupper()) / max(
        1, len(normalized_for_caps)
    )
    # Also detect shouting: long runs of uppercase letters excluding acronyms
    has_shouting = bool(re.search(r"[A-Z]{6,}", normalized_for_caps))
    if caps_ratio > 0.35 or has_shouting:
        score -= 0.10
        factors.append("excessive caps")

    exclamation_count = original_content.count("!")
    if exclamation_count > 3:
        score -= 0.08
        factors.append("excessive punctuation")

    # Penalize low-effort curated lists (e.g., GitHub "awesome" repositories)
    source_name = (
        item.metadata.get("source_name", "") if item.metadata else ""
    ).lower()
    repo_context = (item.title + " " + item.content).lower()
    topics_text = (
        " ".join(item.metadata.get("topics", [])).lower()
        if (item.metadata and item.metadata.get("topics"))
        else ""
    )
    awesome_indicators = [
        "awesome-",
        "awesome ",
        "awesome\n",
        "free-programming-books",
        "awesome-selfhosted",
        "awesome selfhosted",
    ]
    if "github" in source_name and (
        any(ind in repo_context for ind in awesome_indicators)
        or "awesome" in topics_text
    ):
        score -= 0.15
        factors.append("curated list repository")

    # Apply adaptive adjustments based on learned patterns
    adaptive_adjustment = 0.0
    adaptive_reasons = []

    if adapter:
        adaptive_adjustment, adaptive_reasons = adapter.get_adaptive_adjustments(item)
        score += adaptive_adjustment
        factors.extend(adaptive_reasons)

    # Ensure score doesn't go negative (but allow > 1.0 for exceptional content)
    score = max(0.0, score)

    explanation = (
        f"Heuristic: {', '.join(factors)}" if factors else "Basic heuristic analysis"
    )
    if adaptive_adjustment > 0:
        explanation += f" (+{adaptive_adjustment:.2f} adaptive)"

    return score, explanation
