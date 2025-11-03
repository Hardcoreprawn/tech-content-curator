"""Tests for content/categorizer.py."""

from datetime import UTC, datetime

from src.content.categorizer import ArticleCategorizer, ContentType, DifficultyLevel
from src.models import CollectedItem, EnrichedItem


def make_enriched_item(
    title: str = "Test Article",
    topics: list[str] | None = None,
    quality_score: float = 0.75,
) -> EnrichedItem:
    """Helper to create test EnrichedItem."""
    return EnrichedItem(
        original=CollectedItem(
            id="test-id",
            source="mastodon",
            author="testuser",
            content="Test article content",
            title=title,
            url="https://example.com/article",
            collected_at=datetime.now(UTC),
            metadata={},
        ),
        research_summary="Research summary",
        related_sources=[],
        topics=topics or ["Python", "Tech"],
        quality_score=quality_score,
        enriched_at=datetime.now(UTC),
    )


class TestContentTypeDetection:
    """Test content type detection."""

    def test_detects_tutorial(self):
        """Detects tutorial content type."""
        item = make_enriched_item(
            title="How to Build a Web App", topics=["python", "web"]
        )
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, "This is a tutorial content")
        assert result["content_type"] == ContentType.TUTORIAL.value

    def test_detects_news(self):
        """Detects news content type."""
        item = make_enriched_item(
            title="Python 3.14 Released Today", topics=["python", "news"]
        )
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, "Python 3.14 was announced today")
        assert result["content_type"] == ContentType.NEWS.value

    def test_detects_analysis(self):
        """Detects analysis content type."""
        item = make_enriched_item(
            title="Python vs Rust: Deep Dive", topics=["python", "rust"]
        )
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, "This article compares Python and Rust")
        assert result["content_type"] == ContentType.ANALYSIS.value

    def test_detects_research(self):
        """Detects research content type."""
        item = make_enriched_item(
            title="Research Study on AI", topics=["ai", "research"]
        )
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, "This study found important findings")
        assert result["content_type"] == ContentType.RESEARCH.value

    def test_defaults_to_general(self):
        """Defaults to general when no specific type detected."""
        item = make_enriched_item(title="Random Article", topics=["misc"])
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, "Some generic content")
        assert result["content_type"] == ContentType.GENERAL.value


class TestDifficultyDetection:
    """Test difficulty level detection."""

    def test_detects_beginner(self):
        """Detects beginner difficulty."""
        item = make_enriched_item()
        content = "This is an introduction to programming for beginners. Getting started is easy and simple."
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, content)
        assert result["difficulty_level"] == DifficultyLevel.BEGINNER.value

    def test_detects_advanced(self):
        """Detects advanced difficulty."""
        item = make_enriched_item()
        content = """This is an advanced deep dive into compiler internals.
        ```python
        complex_code_1()
        ```
        ```python
        complex_code_2()
        ```
        ```python
        complex_code_3()
        ```
        The architecture involves sophisticated low-level optimizations.
        ```python
        complex_code_4()
        ```
        ```python
        complex_code_5()
        ```
        ```python
        complex_code_6()
        ```
        """
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, content)
        assert result["difficulty_level"] == DifficultyLevel.ADVANCED.value

    def test_defaults_to_intermediate(self):
        """Defaults to intermediate when no clear signals."""
        item = make_enriched_item()
        content = "This is a standard technical article about web development"
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, content)
        assert result["difficulty_level"] == DifficultyLevel.INTERMEDIATE.value


class TestAudienceDetection:
    """Test target audience detection."""

    def test_detects_devops_audience(self):
        """Detects DevOps audience from topics."""
        item = make_enriched_item(topics=["kubernetes", "devops", "docker"])
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, "Content about docker")
        assert "DevOps Engineers" in result["audience"]

    def test_detects_developers_audience(self):
        """Detects developers audience."""
        item = make_enriched_item(topics=["python", "programming"])
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, "Content about python")
        assert "Software Developers" in result["audience"]

    def test_detects_security_audience(self):
        """Detects security professionals audience."""
        item = make_enriched_item(topics=["security", "encryption", "privacy"])
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, "Security content")
        assert "Security Professionals" in result["audience"]

    def test_detects_data_scientists_audience(self):
        """Detects data scientists audience."""
        item = make_enriched_item(topics=["machine learning", "data", "ai"])
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, "ML content")
        assert "Data Scientists" in result["audience"]

    def test_multiple_audiences(self):
        """Can detect multiple audiences."""
        item = make_enriched_item(topics=["python", "machine learning", "security"])
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, "Content")
        assert len(result["audience"]) >= 2
        assert "Software Developers" in result["audience"]
        assert "Data Scientists" in result["audience"]


class TestReadTimeCalculation:
    """Test reading time estimation."""

    def test_calculates_read_time(self):
        """Calculates reading time correctly."""
        item = make_enriched_item()
        # ~225 words per minute, so 450 words = 2 min
        content = " ".join(["word"] * 450)
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, content)
        assert result["estimated_read_time"] == "2 min read"

    def test_minimum_one_minute(self):
        """Minimum reading time is 1 minute."""
        item = make_enriched_item()
        content = "Just a few words"  # ~3 words
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, content)
        assert result["estimated_read_time"] == "1 min read"

    def test_longer_content(self):
        """Longer content gets longer reading time."""
        item = make_enriched_item()
        # ~225 words per minute, so 2250 words = 10 min
        content = " ".join(["word"] * 2250)
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, content)
        assert result["estimated_read_time"] == "10 min read"


class TestCategorizeMethod:
    """Test the main categorize method."""

    def test_returns_all_fields(self):
        """Categorize returns all expected fields."""
        item = make_enriched_item(title="How to Learn Python")
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, "Tutorial content")

        assert "content_type" in result
        assert "difficulty_level" in result
        assert "audience" in result
        assert "estimated_read_time" in result

    def test_categorical_consistency(self):
        """Detected categories are consistent with input."""
        item = make_enriched_item(
            title="Kubernetes vs Docker: A Comparison",
            topics=["kubernetes", "devops"],
        )
        content = """
        This analysis examines trade-offs between two popular technologies.
        Architecture involves complex orchestration. Under the hood...
        ```code
        ```
        ```code
        ```
        """
        categorizer = ArticleCategorizer()
        result = categorizer.categorize(item, content)

        # "comparison" keyword triggers analysis
        assert result["content_type"] == ContentType.ANALYSIS.value
        assert result["difficulty_level"] == DifficultyLevel.ADVANCED.value
        assert "DevOps Engineers" in result["audience"]
