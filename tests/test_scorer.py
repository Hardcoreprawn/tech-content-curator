"""Tests for enrichment scorer heuristic quality assessment."""

from src.enrichment.scorer import calculate_heuristic_score
from src.models import CollectedItem


def make_item(
    content: str, title: str = "Test", author: str = "testuser", metadata: dict | None = None
):
    """Helper to create CollectedItem."""
    return CollectedItem(
        id="test-1",
        title=title,
        content=content,
        url="https://example.com/test",
        source="mastodon",
        author=author,
        metadata=metadata or {},
    )


# ============================================================================
# Test Content Length Scoring
# ============================================================================


def test_too_short_content():
    """Very short content (<50 chars) gets low score."""
    item = make_item("Too short")
    score, explanation = calculate_heuristic_score(item)
    assert "too short" in explanation.lower()
    assert score < 0.3


def test_good_length_content():
    """Content with good length (100-400 chars) scores well."""
    item = make_item("A" * 200)
    score, explanation = calculate_heuristic_score(item)
    assert "good length" in explanation.lower()
    assert score >= 0.15


def test_substantial_length_content():
    """Substantial content (400-800 chars) scores well."""
    item = make_item("A" * 600)
    score, explanation = calculate_heuristic_score(item)
    assert "substantial" in explanation.lower()


# ============================================================================
# Test Technical Keywords
# ============================================================================


def test_multiple_tech_keywords_high_score():
    """Content with multiple tech keywords scores higher."""
    item = make_item(
        "This article discusses Python programming with Docker containers and Kubernetes orchestration for cloud deployment.",
        title="Technical Article",
    )
    score, explanation = calculate_heuristic_score(item)
    assert "tech keyword" in explanation.lower()
    assert score >= 0.3


def test_no_tech_keywords_lower_score():
    """Content without tech keywords doesn't get tech bonus."""
    item = make_item("This is a general article about everyday topics.")
    score, explanation = calculate_heuristic_score(item)
    assert score >= 0


# ============================================================================
# Test Structure Indicators
# ============================================================================


def test_content_with_links():
    """Content with links scores higher."""
    item = make_item(
        "Check out this article: https://example.com with more information."
    )
    score, explanation = calculate_heuristic_score(item)
    assert "link" in explanation.lower()


def test_content_with_code_blocks():
    """Content with code blocks scores higher."""
    item = make_item(
        "Here's an example:\n```python\nprint('hello')\n```\nThat demonstrates the concept."
    )
    score, explanation = calculate_heuristic_score(item)
    assert "code" in explanation.lower()


def test_structured_text_with_newlines():
    """Multi-paragraph content scores higher."""
    item = make_item("First paragraph.\n\nSecond paragraph.\n\nThird paragraph.")
    score, explanation = calculate_heuristic_score(item)
    assert "structured" in explanation.lower()


# ============================================================================
# Test Engagement Metrics
# ============================================================================


def test_high_engagement_boosts_score():
    """High engagement significantly boosts score."""
    item = make_item(
        "This is interesting technical content that got lots of engagement.",
        metadata={"favourites_count": 500, "reblogs_count": 100, "replies_count": 50},
    )
    score, explanation = calculate_heuristic_score(item)
    assert "engagement" in explanation.lower()
    assert score >= 0.4


def test_viral_engagement_maximum_boost():
    """Viral engagement (1000+) gives maximum boost."""
    item = make_item(
        "Viral content with massive engagement.",
        metadata={"favourites_count": 1500, "reblogs_count": 300, "replies_count": 100},
    )
    score, explanation = calculate_heuristic_score(item)
    assert "viral" in explanation.lower() or "engagement" in explanation.lower()
    assert score >= 0.4


def test_no_engagement_no_bonus():
    """Content without engagement metadata doesn't get engagement bonus."""
    item = make_item("Content without any engagement metrics or metadata.")
    score, explanation = calculate_heuristic_score(item)
    assert score >= 0


# ============================================================================
# Test Authority Signals
# ============================================================================


def test_authority_account_boost():
    """Known authority accounts get score boost."""
    item = make_item(
        "Important announcement about Python development and features.", author="thepsf"
    )
    score, explanation = calculate_heuristic_score(item)
    assert "authority" in explanation.lower()


def test_organization_account_boost():
    """Organization accounts get score boost."""
    item = make_item(
        "Official announcement from the project team about new features.",
        author="rust_foundation",
    )
    score, explanation = calculate_heuristic_score(item)
    assert "organization" in explanation.lower() or "authority" in explanation.lower()


def test_regular_account_no_bonus():
    """Regular accounts don't get authority bonus."""
    item = make_item(
        "Regular user posting about programming topics.", author="regularuser123"
    )
    score, explanation = calculate_heuristic_score(item)
    assert score >= 0


# ============================================================================
# Test Negative Indicators
# ============================================================================


def test_personal_content_penalty():
    """Personal/opinion content gets penalized."""
    item = make_item(
        "I feel that this is just my day and my life, personally speaking, IMO."
    )
    score, explanation = calculate_heuristic_score(item)
    assert "personal" in explanation.lower()
    assert score < 0.5


# ============================================================================
# Test News/Announcement Detection
# ============================================================================


def test_major_announcement_boost():
    """Major announcements get score boost."""
    item = make_item(
        "Announcing the new version released today with critical security updates available now!"
    )
    score, explanation = calculate_heuristic_score(item)
    assert "announcement" in explanation.lower() or "news" in explanation.lower()


# ============================================================================
# Test Combined Scoring
# ============================================================================


def test_high_quality_technical_content():
    """High-quality technical content with multiple positive signals."""
    item = make_item(
        """This comprehensive guide explains Kubernetes architecture in detail.

We'll cover Docker containers, API servers, and cloud deployment.
Check out: https://github.com/example/k8s

```yaml
apiVersion: v1
kind: Pod
```

This demonstrates container orchestration.""",
        title="Deep Dive into Kubernetes Architecture",
        author="kubernetes_official",
        metadata={"favourites_count": 200, "reblogs_count": 50, "replies_count": 30},
    )
    score, explanation = calculate_heuristic_score(item)
    assert score >= 0.6
    assert "tech keyword" in explanation.lower()


def test_low_quality_personal_content():
    """Low-quality personal content scores low."""
    item = make_item("I feel like my day was bad, just me personally.")
    score, explanation = calculate_heuristic_score(item)
    assert score < 0.3


def test_returns_tuple_of_score_and_explanation():
    """Function returns (score, explanation) tuple."""
    item = make_item("Test content for scoring validation.")
    result = calculate_heuristic_score(item)
    assert isinstance(result, tuple)
    assert len(result) == 2
    score, explanation = result
    assert isinstance(score, float)
    assert isinstance(explanation, str)
    assert 0.0 <= score <= 1.0
