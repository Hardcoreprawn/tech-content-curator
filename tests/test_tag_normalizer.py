"""Tests for tag normalization and canonicalization system."""

from src.content.tag_normalizer import (
    get_canonical_tags,
    normalize_tag,
    normalize_tags,
    suggest_canonical_tag,
)


class TestNormalizeTag:
    """Test single tag normalization."""

    def test_direct_mapping_ai_variations(self):
        """AI variations map to canonical tag."""
        assert normalize_tag("ai") == "artificial-intelligence"
        assert normalize_tag("AI") == "artificial-intelligence"
        assert normalize_tag("a.i.") == "artificial-intelligence"
        assert normalize_tag("artificial intelligence") == "artificial-intelligence"
        assert normalize_tag("GenAI") == "artificial-intelligence"

    def test_direct_mapping_ml_variations(self):
        """ML variations map to canonical tag."""
        assert normalize_tag("ml") == "machine-learning"
        assert normalize_tag("ML") == "machine-learning"
        assert normalize_tag("machine learning") == "machine-learning"

    def test_already_canonical(self):
        """Canonical tags pass through unchanged."""
        assert normalize_tag("python") == "python"
        assert normalize_tag("kubernetes") == "kubernetes"
        assert normalize_tag("rust") == "rust"

    def test_fuzzy_matching(self):
        """Close matches are recognized."""
        # Fuzzy matching works for typos and close variants
        assert normalize_tag("kubernetess") == "kubernetes"  # Typo
        assert normalize_tag("devop") == "devops"  # Missing 's'
        assert normalize_tag("javascrpt") == "javascript"  # Typo

    def test_removes_prefixes(self):
        """Common prefixes are removed."""
        assert normalize_tag("the python") == "python"
        assert normalize_tag("a tutorial") == "tutorial"

    def test_handles_underscores(self):
        """Underscores converted to hyphens."""
        assert normalize_tag("machine_learning") == "machine-learning"
        assert normalize_tag("web_development") == "web-development"

    def test_unrecognized_tags_return_none(self):
        """Unrecognized tags are discarded."""
        assert normalize_tag("random nonsense tag") is None
        assert normalize_tag("very specific niche topic") is None

    def test_empty_input(self):
        """Handles empty/invalid input."""
        assert normalize_tag("") is None
        assert normalize_tag(None) is None
        assert normalize_tag("   ") is None


class TestNormalizeTags:
    """Test batch tag normalization."""

    def test_normalizes_multiple_tags(self):
        """Normalizes a list of tags."""
        tags = ["AI", "python programming", "web dev", "kubernetes"]
        result = normalize_tags(tags)
        assert "artificial-intelligence" in result
        assert "python" in result
        assert "web-development" in result
        assert "kubernetes" in result

    def test_removes_duplicates(self):
        """Duplicate canonical tags are removed."""
        tags = ["AI", "artificial intelligence", "machine learning", "ML"]
        result = normalize_tags(tags)
        # AI and artificial intelligence both map to same canonical tag
        assert result.count("artificial-intelligence") == 1
        assert result.count("machine-learning") == 1

    def test_limits_to_max_tags(self):
        """Enforces max_tags limit."""
        tags = ["python", "rust", "go", "java", "javascript", "typescript", "ruby"]
        result = normalize_tags(tags, max_tags=5)
        assert len(result) == 5

    def test_discards_unrecognized_tags(self):
        """Unrecognized tags are discarded."""
        tags = ["python", "random nonsense", "kubernetes", "invalid tag"]
        result = normalize_tags(tags)
        assert "python" in result
        assert "kubernetes" in result
        assert "random nonsense" not in result
        assert "invalid tag" not in result

    def test_empty_input(self):
        """Handles empty input."""
        assert normalize_tags([]) == []
        assert normalize_tags(None) == []

    def test_preserves_order(self):
        """Tags maintain original order (after normalization)."""
        tags = ["rust", "python", "javascript"]
        result = normalize_tags(tags)
        assert result.index("rust") < result.index("python")
        assert result.index("python") < result.index("javascript")


class TestGetCanonicalTags:
    """Test canonical tag retrieval."""

    def test_returns_set(self):
        """Returns a set of strings."""
        tags = get_canonical_tags()
        assert isinstance(tags, set)
        assert all(isinstance(tag, str) for tag in tags)

    def test_has_common_tags(self):
        """Contains expected common tags."""
        tags = get_canonical_tags()
        assert "python" in tags
        assert "javascript" in tags
        assert "artificial-intelligence" in tags
        assert "machine-learning" in tags
        assert "kubernetes" in tags
        assert "rust" in tags

    def test_reasonable_size(self):
        """Has reasonable number of tags (50-150)."""
        tags = get_canonical_tags()
        assert 50 <= len(tags) <= 150


class TestSuggestCanonicalTag:
    """Test tag suggestion system."""

    def test_suggests_similar_tags(self):
        """Suggests similar canonical tags."""
        suggestions = suggest_canonical_tag("pyton")  # Typo of python
        assert "python" in suggestions or len(suggestions) > 0

    def test_returns_multiple_suggestions(self):
        """Returns up to 5 suggestions."""
        suggestions = suggest_canonical_tag("data")
        assert len(suggestions) <= 5
        assert len(suggestions) > 0

    def test_handles_typos(self):
        """Suggests corrections for typos."""
        suggestions = suggest_canonical_tag("kubernetess")
        assert "kubernetes" in suggestions


class TestIntegrationScenarios:
    """Test real-world scenarios."""

    def test_article_with_varied_tags(self):
        """Normalizes a realistic article tag set."""
        # Typical AI-generated tags with variations
        tags = [
            "Python programming",
            "AI",
            "machine learning",
            "web dev",
            "data science",
            "ML models",
            "artificial intelligence",  # Duplicate of AI
        ]
        result = normalize_tags(tags, max_tags=5)

        # Should get 5 unique canonical tags
        assert len(result) == 5
        assert "python" in result
        assert "artificial-intelligence" in result
        assert "machine-learning" in result
        assert "web-development" in result
        assert "data-science" in result

    def test_all_unrecognized_tags(self):
        """Handles case where no tags are recognized."""
        tags = ["very specific topic", "niche area", "uncommon technology"]
        result = normalize_tags(tags)
        # Should return empty list
        assert len(result) == 0

    def test_mixed_quality_tags(self):
        """Handles mix of good and bad tags."""
        tags = ["python", "some random thing", "kubernetes", "invalid", "rust"]
        result = normalize_tags(tags)
        assert "python" in result
        assert "kubernetes" in result
        assert "rust" in result
        assert len(result) == 3  # Only 3 valid tags
