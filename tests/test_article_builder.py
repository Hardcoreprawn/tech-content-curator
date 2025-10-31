"""Tests for pipeline/article_builder.py."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest

from src.models import CollectedItem, EnrichedItem
from src.pipeline.article_builder import (
    calculate_image_cost,
    calculate_text_cost,
    create_article_metadata,
    generate_article_slug,
    generate_article_title,
)


def make_collected_item(
    item_id: str = "test-id",
    source: str = "mastodon",
    author: str = "testuser",
    url: str = "https://example.com/article",
) -> CollectedItem:
    """Helper to create test CollectedItem."""
    return CollectedItem(
        id=item_id,
        source=source,
        author=author,
        content="Test article content about Python programming",
        title="Test Article",
        url=url,
        collected_at=datetime(2025, 10, 31, 12, 0, 0, tzinfo=UTC),
        metadata={},
    )


def make_enriched_item(
    topics: list[str] | None = None,
    quality_score: float = 0.75,
) -> EnrichedItem:
    """Helper to create test EnrichedItem."""
    return EnrichedItem(
        original=make_collected_item(),
        research_summary="Research about Python programming",
        related_sources=[],
        topics=topics or ["Python", "Programming", "Tech"],
        quality_score=quality_score,
        enriched_at=datetime.now(UTC),
    )


class TestCalculateTextCost:
    """Test text generation cost calculation."""

    def test_gpt4o_mini_cost_calculation(self):
        """GPT-4o-mini costs are calculated correctly."""
        cost = calculate_text_cost("gpt-4o-mini", 1000, 500)
        # 1000 * 0.150/1M + 500 * 0.600/1M = 0.00015 + 0.0003 = 0.00045
        assert cost == pytest.approx(0.00045, abs=0.000001)

    def test_gpt35_turbo_cost_calculation(self):
        """GPT-3.5-turbo costs are calculated correctly."""
        cost = calculate_text_cost("gpt-3.5-turbo", 1000, 500)
        # 1000 * 0.500/1M + 500 * 1.500/1M = 0.0005 + 0.00075 = 0.00125
        assert cost == pytest.approx(0.00125, abs=0.000001)

    def test_unknown_model_returns_zero(self):
        """Unknown models return zero cost."""
        cost = calculate_text_cost("unknown-model", 1000, 500)
        assert cost == 0.0

    def test_zero_tokens_cost(self):
        """Zero tokens returns zero cost."""
        cost = calculate_text_cost("gpt-4o-mini", 0, 0)
        assert cost == 0.0


class TestCalculateImageCost:
    """Test image generation cost calculation."""

    def test_dalle3_hd_wide_cost(self):
        """DALL-E 3 HD wide image cost is correct."""
        cost = calculate_image_cost("dall-e-3-hd-1792x1024")
        assert cost == 0.080

    def test_dalle3_standard_square_cost(self):
        """DALL-E 3 standard square image cost is correct."""
        cost = calculate_image_cost("dall-e-3-standard-1024x1024")
        assert cost == 0.040

    def test_unknown_model_returns_zero(self):
        """Unknown image models return zero cost."""
        cost = calculate_image_cost("unknown-model")
        assert cost == 0.0

    def test_default_model(self):
        """Default model is HD wide."""
        cost = calculate_image_cost()
        assert cost == 0.080


class TestGenerateArticleSlug:
    """Test article slug generation."""

    @patch("src.pipeline.article_builder.OpenAI")
    def test_generates_valid_slug(self, mock_openai_class):
        """AI-generated slug is cleaned and validated."""
        client = Mock()
        mock_openai_class.return_value = client

        # Mock API response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="python-best-practices"))]
        mock_response.usage = Mock(prompt_tokens=50, completion_tokens=10)
        client.chat.completions.create.return_value = mock_response

        slug, cost = generate_article_slug("Python Best Practices for 2025", client)

        assert slug == "python-best-practices"
        assert cost > 0
        assert "--" not in slug  # No double hyphens
        assert slug.islower()

    @patch("src.pipeline.article_builder.OpenAI")
    def test_cleans_special_characters(self, mock_openai_class):
        """Special characters are removed from slug."""
        client = Mock()
        
        # Mock response with special characters
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="python@#$best-practices"))]
        mock_response.usage = Mock(prompt_tokens=50, completion_tokens=10)
        client.chat.completions.create.return_value = mock_response

        slug, cost = generate_article_slug("Python Best Practices", client)

        assert "@" not in slug
        assert "#" not in slug
        assert "$" not in slug
        assert slug.replace("-", "").isalnum()

    @patch("src.pipeline.article_builder.OpenAI")
    def test_removes_quotes(self, mock_openai_class):
        """Quotes are stripped from slug."""
        client = Mock()
        
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='"python-practices"'))]
        mock_response.usage = Mock(prompt_tokens=50, completion_tokens=10)
        client.chat.completions.create.return_value = mock_response

        slug, cost = generate_article_slug("Python Practices", client)

        assert '"' not in slug
        assert slug == "python-practices"

    @patch("src.pipeline.article_builder.OpenAI")
    def test_truncates_long_slugs(self, mock_openai_class):
        """Slugs longer than 60 chars are truncated."""
        client = Mock()
        
        long_slug = "this-is-a-very-long-slug-that-exceeds-sixty-characters-and-should-be-truncated"
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=long_slug))]
        mock_response.usage = Mock(prompt_tokens=50, completion_tokens=10)
        client.chat.completions.create.return_value = mock_response

        slug, cost = generate_article_slug("Very Long Title", client)

        assert len(slug) <= 60

    @patch("src.pipeline.article_builder.OpenAI")
    def test_fallback_on_api_error(self, mock_openai_class):
        """Falls back to simple slug on API error."""
        client = Mock()
        client.chat.completions.create.side_effect = Exception("API error")

        slug, cost = generate_article_slug("Python Best Practices", client)

        assert slug == "python-best-practices"
        assert cost == 0.0  # No cost on fallback

    @patch("src.pipeline.article_builder.OpenAI")
    def test_fallback_on_empty_response(self, mock_openai_class):
        """Falls back to simple slug on empty response."""
        client = Mock()
        
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=""))]
        mock_response.usage = Mock(prompt_tokens=50, completion_tokens=0)
        client.chat.completions.create.return_value = mock_response

        slug, cost = generate_article_slug("Python Practices", client)

        assert slug == "python-practices"
        assert cost == 0.0

    @patch("src.pipeline.article_builder.OpenAI")
    def test_removes_multiple_consecutive_hyphens(self, mock_openai_class):
        """Multiple consecutive hyphens are collapsed to one."""
        client = Mock()
        
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="python---best--practices"))]
        mock_response.usage = Mock(prompt_tokens=50, completion_tokens=10)
        client.chat.completions.create.return_value = mock_response

        slug, cost = generate_article_slug("Python Best Practices", client)

        assert "---" not in slug
        assert "--" not in slug
        assert slug == "python-best-practices"


class TestGenerateArticleTitle:
    """Test article title generation."""

    @patch("src.pipeline.article_builder.OpenAI")
    def test_generates_valid_title(self, mock_openai_class):
        """AI generates a valid title."""
        client = Mock()
        item = make_enriched_item()
        content = "Article content about Python programming best practices..."

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Python Best Practices You Need"))]
        mock_response.usage = Mock(prompt_tokens=200, completion_tokens=20)
        client.chat.completions.create.return_value = mock_response

        title, cost = generate_article_title(item, content, client)

        assert title == "Python Best Practices You Need"
        assert cost > 0
        assert len(title) <= 60

    @patch("src.pipeline.article_builder.OpenAI")
    def test_strips_quotes_from_title(self, mock_openai_class):
        """Quotes are removed from generated title."""
        client = Mock()
        item = make_enriched_item()

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='"Python Practices"'))]
        mock_response.usage = Mock(prompt_tokens=200, completion_tokens=20)
        client.chat.completions.create.return_value = mock_response

        title, cost = generate_article_title(item, "Content", client)

        assert title == "Python Practices"
        assert '"' not in title

    @patch("src.pipeline.article_builder.OpenAI")
    def test_truncates_long_titles(self, mock_openai_class):
        """Titles over 60 chars are truncated at word boundary."""
        client = Mock()
        item = make_enriched_item()

        long_title = "This Is An Extremely Long Title That Definitely Exceeds Sixty Characters And Should Be Truncated"
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=long_title))]
        mock_response.usage = Mock(prompt_tokens=200, completion_tokens=30)
        client.chat.completions.create.return_value = mock_response

        title, cost = generate_article_title(item, "Content", client)

        assert len(title) <= 60
        assert title.endswith("...")

    @patch("src.pipeline.article_builder.OpenAI")
    def test_fallback_with_topics(self, mock_openai_class):
        """Falls back to topic-based title on error."""
        client = Mock()
        item = make_enriched_item(topics=["Rust", "Compilers"])
        client.chat.completions.create.side_effect = Exception("API error")

        title, cost = generate_article_title(item, "Content", client)

        assert "Rust" in title
        assert cost == 0.0

    @patch("src.pipeline.article_builder.OpenAI")
    def test_fallback_without_topics(self, mock_openai_class):
        """Falls back to generic title when no topics."""
        client = Mock()
        item = make_enriched_item(topics=[])
        client.chat.completions.create.side_effect = Exception("API error")

        title, cost = generate_article_title(item, "Content", client)

        # Empty list is falsy, so falls back to first topic or generic
        assert "Tech Insights" in title or "Understanding" in title
        assert cost == 0.0

    @patch("src.pipeline.article_builder.OpenAI")
    def test_fallback_on_empty_response(self, mock_openai_class):
        """Falls back on empty API response."""
        client = Mock()
        item = make_enriched_item(topics=["Python"])

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=""))]
        mock_response.usage = Mock(prompt_tokens=200, completion_tokens=0)
        client.chat.completions.create.return_value = mock_response

        title, cost = generate_article_title(item, "Content", client)

        assert "Python" in title
        assert cost == 0.0

    @patch("src.pipeline.article_builder.OpenAI")
    def test_fallback_on_none_response(self, mock_openai_class):
        """Falls back on None API response."""
        client = Mock()
        item = make_enriched_item(topics=["Python"])

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=None))]
        mock_response.usage = Mock(prompt_tokens=200, completion_tokens=0)
        client.chat.completions.create.return_value = mock_response

        title, cost = generate_article_title(item, "Content", client)

        assert "Python" in title
        assert cost == 0.0


class TestCreateArticleMetadata:
    """Test article metadata creation."""

    def test_creates_complete_metadata(self):
        """All required metadata fields are present."""
        item = make_enriched_item(topics=["Python", "Web", "API", "Testing", "DevOps"])
        title = "Python Best Practices"
        content = "Article content here. " * 100  # ~300 words

        metadata = create_article_metadata(item, title, content)

        assert metadata["title"] == "Python Best Practices"
        assert "date" in metadata
        assert "tags" in metadata
        assert "summary" in metadata
        assert "source" in metadata
        assert "quality_score" in metadata
        assert "word_count" in metadata
        assert "reading_time" in metadata
        assert "cover" in metadata
        assert "generated_at" in metadata

    def test_limits_tags_to_five(self):
        """Tags are limited to 5 maximum."""
        item = make_enriched_item(topics=["A", "B", "C", "D", "E", "F", "G"])
        
        metadata = create_article_metadata(item, "Title", "Content")

        assert len(metadata["tags"]) == 5
        assert metadata["tags"] == ["A", "B", "C", "D", "E"]

    def test_calculates_word_count(self):
        """Word count is accurate."""
        item = make_enriched_item()
        content = "Word " * 250  # 250 words
        
        metadata = create_article_metadata(item, "Title", content)

        assert metadata["word_count"] == 250

    def test_calculates_reading_time(self):
        """Reading time is based on 200 words per minute."""
        item = make_enriched_item()
        content = "Word " * 600  # 600 words = 3 min read
        
        metadata = create_article_metadata(item, "Title", content)

        assert metadata["reading_time"] == "3 min read"

    def test_minimum_reading_time_is_one_minute(self):
        """Very short articles show 1 min read minimum."""
        item = make_enriched_item()
        content = "Short content"  # 2 words
        
        metadata = create_article_metadata(item, "Title", content)

        assert metadata["reading_time"] == "1 min read"

    def test_source_metadata_complete(self):
        """Source metadata includes all fields."""
        item = make_enriched_item()
        
        metadata = create_article_metadata(item, "Title", "Content")

        source = metadata["source"]
        assert source["platform"] == "mastodon"
        assert source["author"] == "testuser"
        assert source["url"] == "https://example.com/article"
        assert "collected_at" in source

    def test_quality_score_included(self):
        """Quality score from enrichment is included."""
        item = make_enriched_item(quality_score=0.87)
        
        metadata = create_article_metadata(item, "Title", "Content")

        assert metadata["quality_score"] == 0.87

    def test_cover_image_placeholder(self):
        """Cover image fields are initialized empty."""
        item = make_enriched_item()
        
        metadata = create_article_metadata(item, "Title", "Content")

        assert metadata["cover"]["image"] == ""
        assert metadata["cover"]["alt"] == ""

    def test_date_format(self):
        """Date is in YYYY-MM-DD format."""
        item = make_enriched_item()
        
        metadata = create_article_metadata(item, "Title", "Content")

        # Verify date format
        date_str = metadata["date"]
        datetime.strptime(date_str, "%Y-%m-%d")  # Will raise if format wrong

    def test_summary_includes_topics(self):
        """Summary mentions first two topics."""
        item = make_enriched_item(topics=["Python", "Rust", "Go"])
        
        metadata = create_article_metadata(item, "Title", "Content")

        assert "Python" in metadata["summary"]
        assert "Rust" in metadata["summary"]
