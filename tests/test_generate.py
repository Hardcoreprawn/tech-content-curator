"""Tests for article generation pipeline.

Tests cover:
- Article candidate selection and filtering
- Generator routing and selection
- Title and slug generation
- Metadata creation
- Deduplication (source URL, cooldown period)
- File saving with frontmatter
- Cost tracking
- Integration with citations and images
"""

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.generators.base import BaseGenerator
from src.generators.general import GeneralArticleGenerator
from src.models import CollectedItem, EnrichedItem
from src.pipeline import (
    calculate_image_cost,
    calculate_text_cost,
    check_article_exists_for_source,
    collect_existing_source_urls,
    create_article_metadata,
    generate_article_slug,
    generate_article_title,
    generate_single_article,
    is_source_in_cooldown,
    select_article_candidates,
    select_generator,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_collected_item():
    """Create a sample collected item for testing."""
    return CollectedItem(
        id="test-123",
        title="Understanding Kubernetes Architecture",
        content="""Deep dive into how Kubernetes works internally with the scheduler and API server.
        
This article covers the core components of K8s architecture including:
- The API server and etcd for state management
- The scheduler for pod placement decisions
- Kubelet agents on each node
- Container runtime integration (CRI)

Learn how these components work together to orchestrate containers at scale.
Check out the official docs at https://kubernetes.io for more details.
        """,
        url="https://example.com/k8s-article",
        source="mastodon",
        collected_at=datetime.now(UTC),
        author="tech_expert",
        metadata={
            "favourites_count": 100,
            "reblogs_count": 20,
        },
    )


@pytest.fixture
def high_quality_enriched_item(sample_collected_item):
    """Create a high-quality enriched item."""
    return EnrichedItem(
        original=sample_collected_item,
        research_summary="Kubernetes is a container orchestration platform...",
        related_sources=[],
        topics=["kubernetes", "devops", "cloud computing"],
        quality_score=0.75,
        enriched_at=datetime.now(UTC),
    )


@pytest.fixture
def low_quality_enriched_item(sample_collected_item):
    """Create a low-quality enriched item."""
    return EnrichedItem(
        original=sample_collected_item,
        research_summary="Brief mention of topic.",
        related_sources=[],
        topics=["general"],
        quality_score=0.25,
        enriched_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    client = MagicMock()

    # Mock chat completion response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    client.chat.completions.create.return_value = mock_response

    return client


@pytest.fixture
def mock_generator():
    """Create a mock article generator."""
    generator = MagicMock(spec=BaseGenerator)
    generator.name = "TestGenerator"
    generator.priority = 1
    generator.can_handle.return_value = True
    generator.generate_content.return_value = (
        "# Test Article\n\nThis is test content.",
        100,  # input tokens
        200,  # output tokens
    )
    return generator


@pytest.fixture
def temp_content_dir():
    """Create a temporary content directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# Test Cost Calculations
# ============================================================================


class TestCostCalculations:
    """Test API cost calculation functions."""

    def test_calculate_text_cost_gpt4o_mini(self):
        """Calculate cost for GPT-4o-mini usage."""
        cost = calculate_text_cost("gpt-4o-mini", 1000, 500)

        # Expected: (1000 * 0.150/1M) + (500 * 0.600/1M)
        expected = (1000 * 0.150 / 1_000_000) + (500 * 0.600 / 1_000_000)
        assert cost == pytest.approx(expected, rel=1e-6)
        assert cost > 0

    def test_calculate_text_cost_unknown_model(self):
        """Unknown model should return 0 cost."""
        cost = calculate_text_cost("unknown-model", 1000, 500)
        assert cost == 0.0

    def test_calculate_image_cost_hd(self):
        """Calculate cost for HD image generation."""
        cost = calculate_image_cost("dall-e-3-hd-1792x1024")
        assert cost == 0.080

    def test_calculate_image_cost_standard(self):
        """Calculate cost for standard image generation."""
        cost = calculate_image_cost("dall-e-3-standard-1024x1024")
        assert cost == 0.040


# ============================================================================
# Test Article Candidate Selection
# ============================================================================


class TestArticleCandidateSelection:
    """Test selection of items for article generation."""

    def test_select_high_quality_items(
        self, high_quality_enriched_item, low_quality_enriched_item
    ):
        """Select only items with quality score >= threshold."""
        items = [high_quality_enriched_item, low_quality_enriched_item]

        with patch("src.config.get_content_dir") as mock_get_dir:
            mock_get_dir.return_value = Path("/tmp/content")
            # Mock check_article_exists_for_source to avoid file system calls
            with patch(
                "src.pipeline.candidate_selector.check_article_exists_for_source"
            ) as mock_check:
                mock_check.return_value = None

                # Disable adaptive filtering to simplify test
                candidates = select_article_candidates(
                    items,
                    min_quality=0.5,
                    use_adaptive_filtering=False,
                    deduplicate_stories=False,
                )

        # Only high quality item should be selected
        assert len(candidates) == 1
        assert candidates[0].quality_score >= 0.5

    def test_filter_existing_sources(self, high_quality_enriched_item):
        """Filter out items that already have articles."""
        items = [high_quality_enriched_item]

        # Need to patch both get_content_dir and check_article_exists_for_source
        with patch("src.config.get_content_dir") as mock_get_dir:
            mock_get_dir.return_value = Path("/tmp/content")
            with patch(
                "src.pipeline.candidate_selector.check_article_exists_for_source"
            ) as mock_check:
                # Return a path indicating article exists
                mock_check.return_value = Path("/tmp/content/existing-article.md")

                candidates = select_article_candidates(
                    items,
                    min_quality=0.5,
                    use_adaptive_filtering=False,
                    deduplicate_stories=False,
                )

        # Should be filtered out
        assert len(candidates) == 0


# ============================================================================
# Test Generator Selection
# ============================================================================


class TestGeneratorSelection:
    """Test routing items to appropriate generators."""

    def test_select_generator_first_match(self, high_quality_enriched_item):
        """Select first generator that can handle the item."""
        gen1 = MagicMock(spec=BaseGenerator)
        gen1.priority = 1
        gen1.can_handle.return_value = True

        gen2 = MagicMock(spec=BaseGenerator)
        gen2.priority = 2
        gen2.can_handle.return_value = True

        generators = [gen1, gen2]
        selected = select_generator(high_quality_enriched_item, generators)

        # Should select gen1 (higher priority)
        assert selected == gen1
        gen1.can_handle.assert_called_once_with(high_quality_enriched_item)

    def test_select_generator_fallback(self, high_quality_enriched_item):
        """Fallback to next generator if first can't handle."""
        gen1 = MagicMock(spec=BaseGenerator)
        gen1.priority = 1
        gen1.can_handle.return_value = False

        gen2 = MagicMock(spec=BaseGenerator)
        gen2.priority = 2
        gen2.can_handle.return_value = True

        generators = [gen1, gen2]
        selected = select_generator(high_quality_enriched_item, generators)

        # Should select gen2 (gen1 declined)
        assert selected == gen2


# ============================================================================
# Test Title and Slug Generation
# ============================================================================


class TestTitleGeneration:
    """Test AI-powered title generation."""

    def test_generate_article_title(
        self, high_quality_enriched_item, mock_openai_client
    ):
        """Generate title from article content."""
        content = "# Test\n\nArticle about Kubernetes architecture."

        # Mock the API response
        mock_openai_client.chat.completions.create.return_value.choices[
            0
        ].message.content = "Understanding Kubernetes Architecture"

        title, cost = generate_article_title(
            high_quality_enriched_item, content, mock_openai_client
        )

        assert isinstance(title, str)
        assert len(title) > 0
        assert cost >= 0
        mock_openai_client.chat.completions.create.assert_called_once()

    def test_generate_article_slug(self, mock_openai_client):
        """Generate URL-friendly slug from title."""
        title = "Understanding Kubernetes Architecture in 2024"

        slug = generate_article_slug(title)

        assert isinstance(slug, str)
        assert " " not in slug  # No spaces in slug
        assert len(slug) > 0
        assert slug == "understanding-kubernetes-architecture-in-2024"


# ============================================================================
# Test Metadata Creation
# ============================================================================


class TestMetadataCreation:
    """Test article metadata/frontmatter creation."""

    def test_create_article_metadata(self, high_quality_enriched_item):
        """Create frontmatter metadata for article."""
        title = "Test Article"
        content = "This is a test article with some content here."

        metadata = create_article_metadata(high_quality_enriched_item, title, content)

        assert metadata["title"] == title
        assert "date" in metadata
        assert "tags" in metadata
        assert len(metadata["tags"]) <= 5
        assert "source" in metadata
        assert metadata["source"]["platform"] == "mastodon"
        assert metadata["source"]["url"] == str(high_quality_enriched_item.original.url)
        assert metadata["quality_score"] == 0.75
        assert "word_count" in metadata
        assert "reading_time" in metadata


# ============================================================================
# Test Source Deduplication
# ============================================================================


class TestSourceDeduplication:
    """Test source URL-based deduplication."""

    def test_check_article_exists_no_match(self, temp_content_dir):
        """No existing article for this source."""
        source_url = "https://example.com/new-article"

        result = check_article_exists_for_source(source_url, temp_content_dir)

        assert result is None

    def test_check_article_exists_with_match(self, temp_content_dir):
        """Find existing article for this source."""
        source_url = "https://example.com/existing-article"

        # Create an article file with this source URL in frontmatter
        article_content = f"""---
title: Test Article
source:
  url: {source_url}
---

Content here.
"""
        article_file = temp_content_dir / "2024-10-31-test-article.md"
        article_file.write_text(article_content, encoding="utf-8")

        result = check_article_exists_for_source(source_url, temp_content_dir)

        assert result is not None
        assert result == article_file

    def test_collect_existing_source_urls(self, temp_content_dir):
        """Collect all source URLs from existing articles."""
        # Create multiple articles
        for i in range(3):
            content = f"""---
title: Article {i}
source:
  url: https://example.com/article-{i}
---
Content.
"""
            (temp_content_dir / f"article-{i}.md").write_text(content, encoding="utf-8")

        urls = collect_existing_source_urls(temp_content_dir)

        assert len(urls) == 3
        assert "https://example.com/article-0" in urls
        assert "https://example.com/article-1" in urls
        assert "https://example.com/article-2" in urls


# ============================================================================
# Test Source Cooldown
# ============================================================================


class TestSourceCooldown:
    """Test cooldown period for same sources."""

    def test_source_not_in_cooldown_no_articles(self, temp_content_dir):
        """Source with no prior articles is not in cooldown."""
        result = is_source_in_cooldown(
            "https://github.com/user/repo", temp_content_dir, cooldown_days=7
        )
        assert result is False

    def test_source_in_cooldown_recent_article(self, temp_content_dir):
        """Source with recent article is in cooldown."""
        # Create article from 3 days ago
        three_days_ago = (datetime.now(UTC) - timedelta(days=3)).strftime("%Y-%m-%d")
        content = f"""---
title: Recent Article
date: {three_days_ago}
sources:
  - url: https://github.com/user/repo
---
Content.
"""
        (temp_content_dir / f"{three_days_ago}-article.md").write_text(
            content, encoding="utf-8"
        )

        result = is_source_in_cooldown(
            "https://github.com/user/repo", temp_content_dir, cooldown_days=7
        )
        assert result is True

    def test_source_not_in_cooldown_old_article(self, temp_content_dir):
        """Source with old article is not in cooldown."""
        # Create article from 30 days ago
        thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
        content = f"""---
title: Old Article
date: {thirty_days_ago}
sources:
  - url: https://github.com/user/repo
---
Content.
"""
        (temp_content_dir / f"{thirty_days_ago}-article.md").write_text(
            content, encoding="utf-8"
        )

        result = is_source_in_cooldown(
            "https://github.com/user/repo", temp_content_dir, cooldown_days=7
        )
        assert result is False


# ============================================================================
# Test Article Generation Integration
# ============================================================================


class TestArticleGeneration:
    """Test complete article generation pipeline."""

    def test_generate_single_article_success(
        self, high_quality_enriched_item, mock_generator, mock_openai_client
    ):
        """Successfully generate a complete article."""
        # Ensure mock_generator returns a proper string, not a MagicMock
        mock_generator.name = "TestGenerator"
        mock_generator.generate_content.return_value = (
            "# Test Article\n\nThis is test content with some details.",
            100,  # input tokens
            200,  # output tokens
        )

        # Mock title generation (slug generation now uses deterministic parsing)
        mock_openai_client.chat.completions.create.side_effect = [
            # Title generation
            MagicMock(
                choices=[MagicMock(message=MagicMock(content="Test Article Title"))],
                usage=MagicMock(prompt_tokens=50, completion_tokens=25),
            ),
        ]

        with patch(
            "src.pipeline.orchestrator.check_article_exists_for_source"
        ) as mock_check:
            mock_check.return_value = None
            with patch("src.pipeline.orchestrator.select_generator") as mock_select:
                mock_select.return_value = mock_generator

                article = generate_single_article(
                    high_quality_enriched_item,
                    [mock_generator],
                    mock_openai_client,
                )

        assert article is not None
        assert article.title == "Test Article Title"
        assert len(article.content) > 0
        assert article.word_count > 0
        assert "content_generation" in article.generation_costs
        assert "title_generation" in article.generation_costs

    def test_generate_single_article_skip_existing(
        self, high_quality_enriched_item, mock_generator, mock_openai_client
    ):
        """Skip generation if article already exists."""
        config = MagicMock()

        with patch(
            "src.pipeline.orchestrator.check_article_exists_for_source"
        ) as mock_check:
            mock_check.return_value = Path("/existing/article.md")

            article = generate_single_article(
                high_quality_enriched_item,
                config,
                [mock_generator],
                mock_openai_client,
                force_regenerate=False,
            )

        # Should return None (skipped)
        assert article is None

    def test_generate_single_article_force_regenerate(
        self,
        high_quality_enriched_item,
        mock_generator,
        mock_openai_client,
        temp_content_dir,
    ):
        """Force regeneration of existing article."""
        existing_file = temp_content_dir / "existing-article.md"
        existing_file.write_text("Old content", encoding="utf-8")

        # Ensure mock_generator returns a proper string, not a MagicMock
        mock_generator.name = "TestGenerator"
        mock_generator.generate_content.return_value = (
            "# New Article\n\nThis is regenerated content.",
            100,  # input tokens
            200,  # output tokens
        )

        # Mock title and slug generation
        mock_openai_client.chat.completions.create.side_effect = [
            MagicMock(
                choices=[MagicMock(message=MagicMock(content="New Title"))],
                usage=MagicMock(prompt_tokens=50, completion_tokens=25),
            ),
            MagicMock(
                choices=[MagicMock(message=MagicMock(content="new-title"))],
                usage=MagicMock(prompt_tokens=30, completion_tokens=10),
            ),
        ]

        with patch(
            "src.pipeline.orchestrator.check_article_exists_for_source"
        ) as mock_check:
            mock_check.return_value = existing_file
            with patch("src.pipeline.orchestrator.select_generator") as mock_select:
                mock_select.return_value = mock_generator

                article = generate_single_article(
                    high_quality_enriched_item,
                    [mock_generator],
                    mock_openai_client,
                    force_regenerate=True,
                )

        # Should generate new article and delete old file
        assert article is not None
        assert not existing_file.exists()


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test graceful error handling in generation."""

    def test_generate_article_api_failure(
        self, high_quality_enriched_item, mock_generator, mock_openai_client
    ):
        """Handle OpenAI API failure gracefully."""
        config = MagicMock()
        mock_generator.generate_content.side_effect = Exception("API Error")

        with patch(
            "src.pipeline.orchestrator.check_article_exists_for_source"
        ) as mock_check:
            mock_check.return_value = None
            with patch("src.pipeline.orchestrator.select_generator") as mock_select:
                mock_select.return_value = mock_generator

                article = generate_single_article(
                    high_quality_enriched_item,
                    config,
                    [mock_generator],
                    mock_openai_client,
                )

        # Should return None on failure
        assert article is None
