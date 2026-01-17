"""Tests for pipeline/file_io.py."""

import json
from datetime import UTC, datetime
from typing import cast
from unittest.mock import Mock, patch

import frontmatter
from pydantic import HttpUrl, TypeAdapter

from src.citations.extractor import Citation
from src.citations.formatter import FormattedCitation
from src.citations.resolver import ResolvedCitation
from src.models import (
    CollectedItem,
    EnrichedItem,
    GeneratedArticle,
    PipelineConfig,
    SourceType,
)
from src.pipeline.file_io import load_enriched_items, save_article_to_file


def test_save_article_persists_external_cover_image(monkeypatch, tmp_path):
    """External cover URLs are persisted and frontmatter stores Hugo-local paths."""

    import frontmatter

    from src.models import GeneratedArticle, PipelineConfig

    # Ensure we don't write into the real content dir
    monkeypatch.setattr("src.config.get_content_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "src.pipeline.file_io.find_article_by_slug", lambda *a, **k: None
    )

    # Force the image selection path to return an external URL
    monkeypatch.setattr(
        "src.pipeline.file_io.select_or_create_cover_image",
        lambda *a, **k: (
            "https://example.com/hero.png",
            "https://example.com/icon.png",
        ),
    )

    # Make downloading/persisting return local Hugo paths
    monkeypatch.setattr(
        "src.pipeline.file_io.download_and_persist",
        lambda *a, **k: ("/images/test-slug.png", "/images/test-slug-icon.png"),
    )

    config = PipelineConfig(openai_api_key="test")
    config.image_strategy = "reuse"

    article = GeneratedArticle(
        title="Test Article",
        content="Hello world",
        summary="Summary",
        sources=[make_enriched_item()],
        word_count=2,
        filename="2026-01-12-test-slug.md",
        generator_name="test",
    )

    out = save_article_to_file(
        article,
        config,
        generate_image=True,
        client=None,
        update_existing=False,
    )

    post = cast(frontmatter.Post, frontmatter.load(str(out)))
    metadata = cast(dict[str, object], post.metadata)
    cover = cast(dict[str, object], metadata["cover"])
    assert cast(str, cover["image"]).startswith("/images/")
    assert cover["image"] == "/images/test-slug.png"
    assert metadata["icon"] == "/images/test-slug-icon.png"


def make_collected_item(
    item_id: str = "test-1",
    source: SourceType = SourceType.MASTODON,
    author: str = "testuser",
    url: HttpUrl = TypeAdapter(HttpUrl).validate_python("https://example.com/article"),
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
        generation_costs={"content_generation": [0.001]},
        generated_at=datetime(2025, 10, 31, 12, 0, 0, tzinfo=UTC),
        action_run_id="test-run-123",
        generator_name="General Article Generator",
        illustrations_count=0,
    )


def make_config() -> PipelineConfig:
    """Helper to create test PipelineConfig."""
    return PipelineConfig(
        openai_api_key="test-key",
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
            post = cast(frontmatter.Post, frontmatter.load(f))

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
            post = cast(frontmatter.Post, frontmatter.load(f))

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
            post = cast(frontmatter.Post, frontmatter.load(f))

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
                url=TypeAdapter(HttpUrl).validate_python(
                    "https://example.com/article2"
                ),
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
            post = cast(frontmatter.Post, frontmatter.load(f))

        assert "## References" in post.content
        assert "@testuser" in post.content
        assert "@author2" in post.content

    def test_references_include_inline_urls(self, tmp_path):
        """Inline URL citations are included in references."""
        article = make_generated_article(
            content="See [Docs](https://example.com/docs) for details."
        )
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        with open(filepath, encoding="utf-8") as f:
            post = cast(frontmatter.Post, frontmatter.load(f))

        assert "## References" in post.content
        assert "https://example.com/docs" in post.content

    def test_detects_github_source(self, tmp_path):
        """GitHub URLs are detected and labeled correctly."""
        enriched = EnrichedItem(
            original=make_collected_item(
                source=SourceType.GITHUB,
                url=TypeAdapter(HttpUrl).validate_python(
                    "https://github.com/user/repo"
                ),
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
            post = cast(frontmatter.Post, frontmatter.load(f))

        assert "GitHub" in post.content

    def test_detects_arxiv_source(self, tmp_path):
        """arXiv URLs are detected and labeled correctly."""
        enriched = EnrichedItem(
            original=make_collected_item(
                source=SourceType.GITHUB,  # Use valid source, URL detection is what matters
                url=TypeAdapter(HttpUrl).validate_python(
                    "https://arxiv.org/abs/2301.00001"
                ),
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
            post = cast(frontmatter.Post, frontmatter.load(f))

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
            post = cast(frontmatter.Post, frontmatter.load(f))

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
            post = cast(frontmatter.Post, frontmatter.load(f))

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
            post = cast(frontmatter.Post, frontmatter.load(f))

        sources = cast(list[dict[str, object]], post["sources"])
        assert len(sources) == 1
        source = sources[0]
        assert source["platform"] == "mastodon"
        assert source["author"] == "testuser"
        assert source["url"] == "https://example.com/article"
        assert source["quality_score"] == 0.85

    def test_generation_costs_included(self, tmp_path):
        """Generation costs are included in metadata."""
        article = make_generated_article()
        article.generation_costs = {
            "text": [0.001],
            "image": [0.080],
            "total": [0.081],
        }
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify costs
        with open(filepath, encoding="utf-8") as f:
            post = cast(frontmatter.Post, frontmatter.load(f))

        generation_costs = cast(dict[str, object], post["generation_costs"])
        assert generation_costs["total"] == [0.081]
        assert generation_costs["text"] == [0.001]

    def test_cover_image_placeholder(self, tmp_path):
        """Cover image fields use a local fallback when missing."""
        article = make_generated_article()
        config = make_config()

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        # Verify cover placeholder
        with open(filepath, encoding="utf-8") as f:
            post = cast(frontmatter.Post, frontmatter.load(f))

        cover = cast(dict[str, object], post["cover"])
        assert str(cover["image"]).startswith("/images/")
        assert cover["alt"] == article.title

    @patch("src.pipeline.file_io.CitationExtractor")
    @patch("src.pipeline.file_io.CitationResolver")
    @patch("src.pipeline.file_io.CitationFormatter")
    @patch("src.pipeline.file_io.CitationCache")
    def test_processes_citations_when_enabled(
        self, mock_cache, mock_formatter, mock_resolver, mock_extractor, tmp_path
    ):
        """Citations are processed when enabled in config."""
        article = make_generated_article(
            content="Article with Smith (2024) references."
        )
        config = make_config()
        config.enable_citations = True

        # Mock citation processing with proper Citation objects
        citation = Citation(
            authors="Smith et al.",
            year=2024,
            original_text="Smith et al. (2024)",
            position=(14, 32),
            confidence=0.95,
        )
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract.return_value = [citation]
        mock_extractor.return_value = mock_extractor_instance

        mock_resolver_instance = Mock()
        resolved_citation = ResolvedCitation(
            doi="10.1234/test",
            arxiv_id=None,
            pmid=None,
            url="https://doi.org/10.1234/test",
            confidence=0.9,
            source_uri="https://doi.org/10.1234/test",
        )
        mock_resolver_instance.resolve.return_value = resolved_citation
        mock_resolver.return_value = mock_resolver_instance

        # Create a proper FormattedCitation with metadata
        formatted_citation = FormattedCitation(
            markdown="[Smith et al. (2024)](https://doi.org/10.1234/test)",
            original="Smith et al. (2024)",
            was_resolved=True,
            citation=citation,
            resolved=resolved_citation,
        )

        mock_formatter_instance = Mock()
        mock_formatter_instance.format.return_value = formatted_citation
        mock_formatter_instance.apply_to_text.return_value = "Article content"
        mock_formatter_instance.build_bibliography.return_value = [
            "- [Smith et al. (2024)](https://doi.org/10.1234/test)"
        ]
        mock_formatter.return_value = mock_formatter_instance

        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            save_article_to_file(article, config)

        # Verify citation processing called
        mock_extractor_instance.extract.assert_called_once()
        mock_formatter_instance.format.assert_called()
        mock_formatter_instance.apply_to_text.assert_called_once()
        mock_formatter_instance.build_bibliography.assert_called_once()

    @patch("src.pipeline.file_io.CitationExtractor")
    @patch("src.pipeline.file_io.CitationResolver")
    @patch("src.pipeline.file_io.CitationFormatter")
    @patch("src.pipeline.file_io.CitationCache")
    def test_drops_references_without_urls(
        self, mock_cache, mock_formatter, mock_resolver, mock_extractor, tmp_path
    ):
        """References section is omitted when only non-URL citations exist."""
        article = make_generated_article(
            content="Article with Smith (2024) references."
        )
        article.sources = []
        config = make_config()
        config.enable_citations = True

        citation = Citation(
            authors="Smith et al.",
            year=2024,
            original_text="Smith et al. (2024)",
            position=(14, 32),
            confidence=0.95,
        )
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract.return_value = [citation]
        mock_extractor.return_value = mock_extractor_instance

        mock_resolver_instance = Mock()
        resolved_citation = ResolvedCitation(
            doi=None,
            arxiv_id=None,
            pmid=None,
            url=None,
            confidence=0.0,
            source_uri=None,
        )
        mock_resolver_instance.resolve.return_value = resolved_citation
        mock_resolver.return_value = mock_resolver_instance

        formatted_citation = FormattedCitation(
            markdown="Smith et al. (2024)",
            original="Smith et al. (2024)",
            was_resolved=False,
            citation=citation,
            resolved=resolved_citation,
        )

        mock_formatter_instance = Mock()
        mock_formatter_instance.format.return_value = formatted_citation
        mock_formatter_instance.apply_to_text.return_value = "Article content"
        mock_formatter_instance.build_bibliography.return_value = [
            "- Smith et al. (2024)"
        ]
        mock_formatter.return_value = mock_formatter_instance

        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        with patch("src.pipeline.file_io.get_content_dir", return_value=tmp_path):
            filepath = save_article_to_file(article, config)

        with open(filepath, encoding="utf-8") as f:
            post = cast(frontmatter.Post, frontmatter.load(f))

        assert "## References" not in post.content

    def test_handles_citation_errors_gracefully(self, tmp_path):
        """Citation processing errors don't break article save."""
        article = make_generated_article()
        config = make_config()
        config.enable_citations = True

        with patch("src.pipeline.file_io.CitationExtractor") as mock_extractor:
            mock_extractor.side_effect = ValueError("Citation error")
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
