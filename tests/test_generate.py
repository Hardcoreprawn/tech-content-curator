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

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import HttpUrl, TypeAdapter

from src.generators.base import BaseGenerator
from src.models import CollectedItem, EnrichedItem, PipelineConfig, SourceType
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
        url=TypeAdapter(HttpUrl).validate_python("https://example.com/k8s-article"),
        source=SourceType.MASTODON,
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
    mock_response.usage = make_usage(100, 50)

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


@pytest.fixture
def pipeline_config():
    """Provide a real PipelineConfig for governance-aware tests."""
    return PipelineConfig(openai_api_key="sk-test")


def make_usage(prompt_tokens: int, completion_tokens: int) -> SimpleNamespace:
    """Create a simple usage struct for mocked OpenAI responses."""
    return SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


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
        assert cost == 0.020


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

    @patch("src.pipeline.article_builder.chat_completion")
    def test_generate_article_title(
        self, mock_chat_completion, high_quality_enriched_item, mock_openai_client
    ):
        """Generate title from article content."""
        content = "# Test\n\nArticle about Kubernetes architecture."

        # Mock the API response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="Understanding Kubernetes Architecture")
            )
        ]
        mock_response.usage = make_usage(100, 50)
        mock_chat_completion.return_value = mock_response

        title, cost = generate_article_title(
            high_quality_enriched_item, content, mock_openai_client
        )

        assert isinstance(title, str)
        assert len(title) > 0
        assert cost >= 0
        mock_chat_completion.assert_called_once()

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
        self,
        high_quality_enriched_item,
        mock_generator,
        mock_openai_client,
        pipeline_config,
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
                usage=make_usage(50, 25),
            ),
        ]

        with patch("src.pipeline.orchestrator.get_config") as mock_get_config:
            mock_get_config.return_value = pipeline_config
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
        with patch(
            "src.pipeline.orchestrator.check_article_exists_for_source"
        ) as mock_check:
            mock_check.return_value = Path("/existing/article.md")

            article = generate_single_article(
                high_quality_enriched_item,
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
        pipeline_config,
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
                usage=make_usage(50, 25),
            ),
            MagicMock(
                choices=[MagicMock(message=MagicMock(content="new-title"))],
                usage=make_usage(30, 10),
            ),
        ]

        with patch("src.pipeline.orchestrator.get_config") as mock_get_config:
            mock_get_config.return_value = pipeline_config
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
        mock_generator.generate_content.side_effect = Exception("API Error")

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

        # Should return None on failure
        assert article is None


# ============================================================================
# Test Defensive Attribute Access
# ============================================================================


class TestDefensiveAttributeAccess:
    """Test that generators safely handle optional attributes on models.

    This test class ensures we don't repeat the difficulty_level bug where
    the generator tried to access an attribute that only exists on the
    GeneratedArticle model (post-categorization) but not on EnrichedItem
    (pre-generation).
    """

    def test_general_generator_handles_missing_difficulty_level(
        self, high_quality_enriched_item, mock_openai_client
    ):
        """GeneralArticleGenerator should handle EnrichedItem without difficulty_level.

        EnrichedItem doesn't have difficulty_level field - it's added during
        categorization after generation. The generator must use safe attribute
        access (getattr) to avoid AttributeError.
        """
        from src.generators.general import GeneralArticleGenerator

        generator = GeneralArticleGenerator(mock_openai_client)

        # Verify EnrichedItem doesn't have difficulty_level
        assert not hasattr(high_quality_enriched_item, "difficulty_level")

        # Mock the OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="# Test Article\n\nContent here"))
        ]
        mock_response.usage = make_usage(500, 1000)
        mock_openai_client.chat.completions.create.return_value = mock_response

        # This should NOT raise AttributeError despite missing difficulty_level
        with patch(
            "src.pipeline.quality_feedback.get_quality_prompt_enhancements"
        ) as mock_enhancements:
            mock_enhancements.return_value = "Quality guidance"
            content, input_tokens, output_tokens = generator.generate_content(
                high_quality_enriched_item
            )

        assert content is not None
        assert len(content) > 0
        assert input_tokens > 0
        assert output_tokens > 0

    def test_general_generator_handles_optional_attributes(
        self, high_quality_enriched_item, mock_openai_client
    ):
        """Generator should safely handle any optional attributes using getattr.

        Verifies that getattr() with default values is used for any fields
        that might not exist on EnrichedItem.
        """
        from src.generators.general import GeneralArticleGenerator

        generator = GeneralArticleGenerator(mock_openai_client)

        # List of attributes that should be optionally accessed
        optional_attrs = ["difficulty_level", "content_type_hint", "target_audience"]

        for attr in optional_attrs:
            if hasattr(high_quality_enriched_item, attr):
                continue  # Skip if it happens to exist

            # Mock OpenAI response
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="# Test\n\nContent"))
            ]
            mock_response.usage = make_usage(100, 200)
            mock_openai_client.chat.completions.create.return_value = mock_response

            # Generate should work fine even without these optional attributes
            with patch(
                "src.pipeline.quality_feedback.get_quality_prompt_enhancements"
            ) as mock_enhancements:
                mock_enhancements.return_value = ""
                content, _, _ = generator.generate_content(high_quality_enriched_item)

            assert content is not None

    def test_enriched_item_model_lacks_difficulty_level(self, sample_collected_item):
        """Verify EnrichedItem model doesn't have difficulty_level field.

        This documents the design intent: difficulty_level is populated
        during categorization (after generation), not before generation.
        """
        item = EnrichedItem(
            original=sample_collected_item,
            research_summary="Test research",
            related_sources=[],
            topics=["test"],
            quality_score=0.8,
            enriched_at=datetime.now(UTC),
        )

        # EnrichedItem should not have difficulty_level
        assert not hasattr(item, "difficulty_level")

        # But using getattr with default should work safely
        level = getattr(item, "difficulty_level", None)
        assert level is None

        # And we can provide a fallback
        level = getattr(item, "difficulty_level", None) or "intermediate"
        assert level == "intermediate"
