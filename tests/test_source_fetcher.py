"""Tests for source fetching module."""

from datetime import datetime

from pydantic import HttpUrl

from src.enrichment.source_fetcher import extract_urls_from_content, is_meta_content
from src.models import CollectedItem, SourceType


def create_test_item(content: str, title: str = "Test Post") -> CollectedItem:
    """Helper to create test collected items."""
    return CollectedItem(
        id="test-123",
        title=title,
        content=content,
        source=SourceType.MASTODON,
        url=HttpUrl("https://example.com/123"),
        author="test_user",
        collected_at=datetime.now(),
    )


class TestExtractUrls:
    """Tests for URL extraction."""

    def test_extracts_article_urls(self):
        """Should extract URLs from content."""
        content = "Check out this article: https://example.com/blog/post"
        urls = extract_urls_from_content(content)
        assert len(urls) == 1
        assert "example.com" in urls[0]

    def test_extracts_multiple_urls(self):
        """Should extract multiple URLs."""
        content = "See https://blog.example.com/1 and https://news.site.org/2"
        urls = extract_urls_from_content(content)
        assert len(urls) == 2

    def test_filters_social_media(self):
        """Should filter out pure social media URLs."""
        content = "https://twitter.com/user/status/123"
        urls = extract_urls_from_content(content)
        assert len(urls) == 0

    def test_filters_reddit_posts(self):
        """Should filter out direct Reddit post URLs."""
        content = "https://reddit.com/r/programming/comments/abc123"
        urls = extract_urls_from_content(content)
        assert len(urls) == 0

    def test_includes_blog_domains(self):
        """Should include blog and article domains."""
        test_cases = [
            "https://medium.com/@user/post",
            "https://dev.to/article",
            "https://example.blog/post",
            "https://news.ycombinator.com/item?id=123",
            "https://arxiv.org/abs/1234.5678",
            "https://user.github.io/project",
        ]
        for url_content in test_cases:
            urls = extract_urls_from_content(url_content)
            assert len(urls) == 1, f"Failed for {url_content}"

    def test_handles_no_urls(self):
        """Should return empty list when no URLs."""
        urls = extract_urls_from_content("No links here, just text")
        assert urls == []

    def test_stops_at_whitespace(self):
        """Should stop URL extraction at whitespace."""
        content = "See https://example.com/post for details"
        urls = extract_urls_from_content(content)
        assert urls[0] == "https://example.com/post"
        assert "for" not in urls[0]


class TestIsMetaContent:
    """Tests for meta-content detection."""

    def test_detects_article_discussion(self):
        """Should detect when post discusses an article."""
        item = create_test_item(
            "Sharon Begley wrote an obituary: https://statnews.com/watson",
            title="Begley's Watson Obituary",
        )
        urls = ["https://statnews.com/watson"]
        assert is_meta_content(item, urls) is True

    def test_detects_published_piece(self):
        """Should detect 'published article' pattern."""
        item = create_test_item(
            "Just published article on AI safety: https://example.com/ai",
            title="New AI Article",
        )
        urls = ["https://example.com/ai"]
        assert is_meta_content(item, urls) is True

    def test_detects_essay_reference(self):
        """Should detect essay/piece references."""
        item = create_test_item(
            "Great essay on functional programming: https://blog.example.com/fp",
            title="FP Essay",
        )
        urls = ["https://blog.example.com/fp"]
        assert is_meta_content(item, urls) is True

    def test_not_meta_without_indicators(self):
        """Should not flag as meta without strong indicators."""
        item = create_test_item(
            "Cool project: https://github.com/user/repo",
            title="GitHub Project",
        )
        urls = ["https://github.com/user/repo"]
        # Single weak indicator ("project") + URL not enough
        assert is_meta_content(item, urls) is False

    def test_not_meta_without_urls(self):
        """Should not flag as meta without URLs."""
        item = create_test_item(
            "I wrote some code today and it was great",
            title="Coding Progress",
        )
        urls = []
        assert is_meta_content(item, urls) is False

    def test_requires_sufficient_indicators(self):
        """Should require at least 2 indicators for meta-content."""
        item = create_test_item(
            "This article discusses research findings",  # "article" + "research"
            title="Research Discussion",
        )
        urls = ["https://example.com/research"]
        assert is_meta_content(item, urls) is True

    def test_strong_indicator_alone_sufficient(self):
        """Should detect meta-content with single strong indicator."""
        item = create_test_item(
            "New piece on climate change: https://example.com/climate",
            title="Climate Piece",
        )
        urls = ["https://example.com/climate"]
        assert is_meta_content(item, urls) is True

    def test_obituary_pattern(self):
        """Should detect obituary discussions."""
        item = create_test_item(
            "Obituary for James Watson by Sharon Begley: https://stat.news/watson",
            title="Watson Obituary",
        )
        urls = ["https://stat.news/watson"]
        assert is_meta_content(item, urls) is True

    def test_paper_announcement(self):
        """Should detect paper/study announcements."""
        item = create_test_item(
            "New study shows improved results: https://arxiv.org/abs/1234",
            title="Research Study",
        )
        urls = ["https://arxiv.org/abs/1234"]
        assert is_meta_content(item, urls) is True
