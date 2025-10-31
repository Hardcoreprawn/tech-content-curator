"""Tests for pipeline/file_io.py."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import frontmatter
import pytest

from src.models import CollectedItem, EnrichedItem, GeneratedArticle, PipelineConfig
from src.pipeline.file_io import load_enriched_items, save_article_to_file


def make_collected_item(
    item_id: str = "test-1",
    source: str = "mastodon",
    author: str = "testuser",
    url: str = "https://example.com/article",
) -> CollectedItem:
    """Helper to create test CollectedItem."""
    return CollectedItem(
        id=item_id,
        source=source,
        author=author,
        content="Test content about Python programming",
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
        research_summary="Research about Python",
        related_sources=[],
        topics=topics or ["Python", "Programming"],
        quality_score=quality_score,
        enriched_at=datetime.now(UTC),
    )


def make_generated_article(
    title: str = "Test Article",
    content: str = "Article content here.",
    filename: str = "test-article.md",
) -> GeneratedArticle:
    """Helper to create test GeneratedArticle."""
    return GeneratedArticle(
        title=title,
        content=content,
        summary="Test summary",
        tags=["Python", "Tech"],
        filename=filename,
        sources=[make_enriched_item()],
        word_count=100,
        generation_costs={"total": 0.001},
        generated_at=datetime(2025, 10, 31, 12, 0, 0, tzinfo=UTC),
        action_run_id="test-run-123",
    )


def make_config() -> PipelineConfig:
    """Helper to create test PipelineConfig."""
    return PipelineConfig(
        openai_api_key="test-key",
        content_dirs={"posts": "content/posts"},
        use_semantic_dedup=False,
        enable_citations=False,
    )


class TestSaveArticleToFile:
    """Test saving articles to markdown files."""

    def test_saves_article_with_frontmatter(self, tmp_path):
        """Article is saved with proper YAML frontmatter."""
        article = make_generated_article()
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify file exists
        assert filepath.exists()
        assert filepath.name == "test-article.md"

        # Verify frontmatter
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        assert post["title"] == "Test Article"
        assert post["tags"] == ["Python", "Tech"]
        assert post["summary"] == "Test summary"
        assert post["word_count"] == 100
        assert "sources" in post
        assert post["action_run_id"] == "test-run-123"

    def test_article_content_preserved(self, tmp_path):
        """Article content is written correctly."""
        article = make_generated_article(content="# My Article\n\nSome content here.")
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify content
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        assert "# My Article" in post.content
        assert "Some content here." in post.content

    def test_handles_filename_conflicts(self, tmp_path):
        """Duplicate filenames get unique suffix."""
        article1 = make_generated_article(filename="article.md")
        article2 = make_generated_article(filename="article.md")
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath1 = save_article_to_file(article1, config)
            filepath2 = save_article_to_file(article2, config)

        # Verify different filenames
        assert filepath1.name == "article.md"
        assert filepath2.name == "article-2.md"
        assert filepath1.exists()
        assert filepath2.exists()

    def test_multiple_filename_conflicts(self, tmp_path):
        """Multiple conflicts increment suffix correctly."""
        article = make_generated_article(filename="article.md")
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            # Create first three
            save_article_to_file(article, config)
            article2 = make_generated_article(filename="article.md")
            save_article_to_file(article2, config)
            article3 = make_generated_article(filename="article.md")
            filepath3 = save_article_to_file(article3, config)

        # Third conflict should be -3
        assert filepath3.name == "article-3.md"

    def test_creates_attribution_block(self, tmp_path):
        """Attribution block is added for primary source."""
        enriched = make_enriched_item()
        article = make_generated_article()
        article.sources = [enriched]
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify attribution
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        assert "> **Attribution:**" in post.content
        assert "@testuser" in post.content
        assert "mastodon" in post.content.lower()

    def test_creates_references_section(self, tmp_path):
        """References section lists all sources."""
        enriched1 = make_enriched_item()
        enriched2 = EnrichedItem(
            original=make_collected_item(
                item_id="test-2",
                author="author2",
                url="https://example.com/article2",
            ),
            research_summary="Research",
            related_sources=[],
            topics=["Tech"],
            quality_score=0.8,
            enriched_at=datetime.now(UTC),
        )
        article = make_generated_article()
        article.sources = [enriched1, enriched2]
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify references
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        assert "## References" in post.content
        assert "@testuser" in post.content
        assert "@author2" in post.content

    def test_detects_github_source(self, tmp_path):
        """GitHub URLs are detected and labeled correctly."""
        enriched = EnrichedItem(
            original=make_collected_item(
                source="github",
                url="https://github.com/user/repo",
            ),
            research_summary="Research",
            related_sources=[],
            topics=["Tech"],
            quality_score=0.8,
            enriched_at=datetime.now(UTC),
        )
        article = make_generated_article()
        article.sources = [enriched]
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify GitHub detected
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        assert "GitHub" in post.content

    def test_detects_arxiv_source(self, tmp_path):
        """arXiv URLs are detected and labeled correctly."""
        enriched = EnrichedItem(
            original=make_collected_item(
                source="github",  # Use valid source, URL detection is what matters
                url="https://arxiv.org/abs/2301.00001",
            ),
            research_summary="Research",
            related_sources=[],
            topics=["ML"],
            quality_score=0.9,
            enriched_at=datetime.now(UTC),
        )
        article = make_generated_article()
        article.sources = [enriched]
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify arXiv detected
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        assert "arXiv" in post.content

    def test_reading_time_calculation(self, tmp_path):
        """Reading time is calculated at 200 words per minute."""
        article = make_generated_article()
        article.word_count = 600  # Should be 3 min read
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify reading time
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        assert post["reading_time"] == "3 min read"

    def test_minimum_reading_time(self, tmp_path):
        """Minimum reading time is 1 minute."""
        article = make_generated_article()
        article.word_count = 50  # Very short
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify minimum
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        assert post["reading_time"] == "1 min read"

    def test_sources_metadata_structure(self, tmp_path):
        """Sources in frontmatter have correct structure."""
        enriched = make_enriched_item(quality_score=0.85)
        article = make_generated_article()
        article.sources = [enriched]
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify sources structure
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        assert len(post["sources"]) == 1
        source = post["sources"][0]
        assert source["platform"] == "mastodon"
        assert source["author"] == "testuser"
        assert source["url"] == "https://example.com/article"
        assert source["quality_score"] == 0.85

    def test_generation_costs_included(self, tmp_path):
        """Generation costs are included in metadata."""
        article = make_generated_article()
        article.generation_costs = {
            "text": 0.001,
            "image": 0.080,
            "total": 0.081,
        }
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify costs
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        assert post["generation_costs"]["total"] == 0.081
        assert post["generation_costs"]["text"] == 0.001

    def test_cover_image_placeholder(self, tmp_path):
        """Cover image fields are initialized empty."""
        article = make_generated_article()
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify cover placeholder
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        assert post["cover"]["image"] == ""
        assert post["cover"]["alt"] == ""

    @patch("src.pipeline.file_io.CitationExtractor")
    @patch("src.pipeline.file_io.CitationResolver")
    @patch("src.pipeline.file_io.CitationFormatter")
    @patch("src.pipeline.file_io.CitationCache")
    def test_processes_citations_when_enabled(
        self, mock_cache, mock_formatter, mock_resolver, mock_extractor, tmp_path
    ):
        """Citations are processed when enabled in config."""
        article = make_generated_article(
            content="Article with [Citation needed] references."
        )
        config = make_config()
        config.enable_citations = True

        # Mock citation processing
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract.return_value = [{"text": "Citation needed"}]
        mock_extractor.return_value = mock_extractor_instance

        mock_resolver_instance = Mock()
        mock_resolver_instance.resolve_batch.return_value = []
        mock_resolver.return_value = mock_resolver_instance

        mock_formatter_instance = Mock()
        mock_formatter_instance.format_inline.return_value = "Article with citations"
        mock_formatter_instance.format_references.return_value = ""
        mock_formatter.return_value = mock_formatter_instance

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            save_article_to_file(article, config)

        # Verify citation processing called
        mock_extractor_instance.extract.assert_called_once()
        mock_resolver_instance.resolve_batch.assert_called_once()
        mock_formatter_instance.format_inline.assert_called_once()

    def test_handles_citation_errors_gracefully(self, tmp_path):
        """Citation processing errors don't break article save."""
        article = make_generated_article()
        config = make_config()
        config.enable_citations = True

        with patch("src.pipeline.file_io.CitationExtractor") as mock_extractor:
            mock_extractor.side_effect = Exception("Citation error")
            with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
                filepath = save_article_to_file(article, config)

        # Article should still be saved
        assert filepath.exists()

    def test_utf8_encoding(self, tmp_path):
        """Files are saved with UTF-8 encoding."""
        article = make_generated_article(
            title="Test 日本語",
            content="Content with émojis 🚀 and ünïcödé",
        )
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify UTF-8 encoding
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        assert "日本語" in content
        assert "🚀" in content
        assert "ünïcödé" in content


class TestLoadEnrichedItems:
    """Test loading enriched items from JSON."""

    def test_loads_enriched_items(self, tmp_path):
        """Enriched items are loaded from JSON file."""
        # Create test data
        enriched = make_enriched_item(topics=["Python", "AI"])
        data = {
            "enriched_at": datetime.now(UTC).isoformat(),
            "total_items": 1,
            "items": [enriched.model_dump()],
        }

        filepath = tmp_path / "enriched.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)

        # Load items
        items = load_enriched_items(filepath)

        assert len(items) == 1
        assert items[0].topics == ["Python", "AI"]
        assert items[0].quality_score == 0.75

    def test_loads_multiple_items(self, tmp_path):
        """Multiple enriched items are loaded."""
        items_data = [
            make_enriched_item(topics=["Python"]).model_dump(),
            make_enriched_item(topics=["Rust"]).model_dump(),
            make_enriched_item(topics=["Go"]).model_dump(),
        ]

        data = {
            "enriched_at": datetime.now(UTC).isoformat(),
            "total_items": 3,
            "items": items_data,
        }

        filepath = tmp_path / "enriched.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)

        items = load_enriched_items(filepath)

        assert len(items) == 3

    def test_handles_malformed_items(self, tmp_path):
        """Malformed items are skipped with warning."""
        good_item = make_enriched_item().model_dump()
        bad_item = {"invalid": "data", "missing": "required_fields"}

        data = {
            "enriched_at": datetime.now(UTC).isoformat(),
            "total_items": 2,
            "items": [good_item, bad_item],
        }

        filepath = tmp_path / "enriched.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)

        items = load_enriched_items(filepath)

        # Only good item loaded
        assert len(items) == 1

    def test_empty_items_list(self, tmp_path):
        """Empty items list returns empty result."""
        data = {
            "enriched_at": datetime.now(UTC).isoformat(),
            "total_items": 0,
            "items": [],
        }

        filepath = tmp_path / "enriched.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)

        items = load_enriched_items(filepath)

        assert items == []

    def test_preserves_item_properties(self, tmp_path):
        """All item properties are preserved during load."""
        enriched = make_enriched_item(
            topics=["Python", "Django"],
            quality_score=0.92,
        )

        data = {
            "enriched_at": datetime.now(UTC).isoformat(),
            "total_items": 1,
            "items": [enriched.model_dump()],
        }

        filepath = tmp_path / "enriched.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)

        items = load_enriched_items(filepath)

        assert items[0].topics == ["Python", "Django"]
        assert items[0].quality_score == 0.92
        assert items[0].research_summary == "Research about Python"
