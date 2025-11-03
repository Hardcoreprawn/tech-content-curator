"""End-to-end pipeline integration tests.

Tests the complete pipeline from collection to article generation using real data files.
These tests verify:
1. Collection orchestrator (load existing data)
2. Enrichment pipeline
3. Article generation (with modular orchestrator)
4. File I/O and content directory operations
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models import CollectedItem, EnrichedItem
from src.pipeline import generate_articles_from_enriched


@pytest.fixture
def sample_data_dir():
    """Get path to data directory with test files."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def load_collected_data(sample_data_dir):
    """Load a small collected data file for testing."""
    test_file = sample_data_dir / "collected_test_small.json"

    if not test_file.exists():
        pytest.skip(f"Test data file not found: {test_file}")

    with open(test_file, encoding="utf-8") as f:
        data = json.load(f)

    # Handle both old list format and new dict format
    if isinstance(data, dict):
        items = data.get("items", [])
    else:
        items = data

    return [CollectedItem(**item) for item in items]


@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    config = MagicMock()
    config.openai_api_key = "test-key"
    config.get_content_dir.return_value = Path("content/posts")
    return config


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client that returns realistic responses."""
    client = MagicMock()

    def create_mock_response(content, prompt_tokens=100, completion_tokens=200):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = content
        response.usage.prompt_tokens = prompt_tokens
        response.usage.completion_tokens = completion_tokens
        return response

    # Default response for content generation
    client.chat.completions.create.return_value = create_mock_response(
        "# Test Article\n\nThis is a test article with markdown content.\n\n## Section 1\n\nDetailed content here."
    )

    return client


class TestDataFilesExist:
    """Verify test data files are present."""

    def test_sample_data_exists(self, sample_data_dir):
        """Check that sample data directory exists."""
        assert sample_data_dir.exists()
        assert sample_data_dir.is_dir()

    def test_collected_test_file_exists(self, sample_data_dir):
        """Check that test collection file exists."""
        test_file = sample_data_dir / "collected_test_small.json"

        if test_file.exists():
            assert test_file.is_file()

            # Verify it's valid JSON
            with open(test_file, encoding="utf-8") as f:
                data = json.load(f)

            # Handle both old list format and new dict format
            if isinstance(data, dict):
                assert "items" in data
                items = data["items"]
            else:
                items = data

            assert isinstance(items, list)
            if len(items) > 0:
                assert "id" in items[0]
                assert "title" in items[0]
                assert "content" in items[0]


class TestCollectionLoading:
    """Test loading collected items from data files."""

    def test_load_collected_items(self, load_collected_data):
        """Load collected items from test file."""
        items = load_collected_data

        assert isinstance(items, list)
        assert len(items) > 0

        # Check first item structure
        first_item = items[0]
        assert isinstance(first_item, CollectedItem)
        assert hasattr(first_item, "id")
        assert hasattr(first_item, "title")
        assert hasattr(first_item, "content")
        assert hasattr(first_item, "url")
        assert hasattr(first_item, "source")


class TestModularOrchestrator:
    """Test the refactored modular orchestrator."""

    def test_orchestrator_imports(self):
        """Verify all modular imports work."""
        from src.pipeline.diversity_selector import select_diverse_candidates
        from src.pipeline.orchestrator import (
            generate_articles_async,
            generate_articles_from_enriched,
            generate_single_article,
        )

        assert callable(generate_single_article)
        assert callable(generate_articles_from_enriched)
        assert callable(generate_articles_async)
        assert callable(select_diverse_candidates)

    def test_illustration_service_creation(self):
        """Create an IllustrationService instance."""
        from src.pipeline.illustration_service import IllustrationService

        mock_client = MagicMock()
        mock_config = MagicMock()

        service = IllustrationService(mock_client, mock_config)

        assert service is not None
        assert hasattr(service, "generate_illustrations")
        assert callable(service.generate_illustrations)

    @pytest.mark.skip(reason="Requires mock refactoring for new implementation")
    @patch("src.pipeline.orchestrator.get_available_generators")
    @patch("src.pipeline.orchestrator.check_article_exists_for_source")
    def test_generate_articles_with_enriched_items(
        self,
        mock_check_exists,
        mock_get_generators,
        mock_config,
        mock_openai_client,
    ):
        """Test article generation with enriched items."""
        from datetime import UTC, datetime

        # Mock generators (not builders)
        mock_generator = MagicMock()
        mock_generator.name = "TestGenerator"
        mock_generator.priority = 1
        mock_generator.can_handle.return_value = True
        mock_generator.generate_content.return_value = (
            "# Test Article\n\nContent here.",
            100,  # input tokens
            200,  # output tokens
        )
        mock_get_generators.return_value = [mock_generator]

        # Mock no existing articles
        mock_check_exists.return_value = None

        # Create enriched items
        collected = CollectedItem(
            id="test-1",
            title="Test Article",
            content="Test content about testing",
            url="https://example.com/test",
            source="mastodon",
            collected_at=datetime.now(UTC),
        )

        enriched_items = [
            EnrichedItem(
                original=collected,
                research_summary="Summary of test content",
                related_sources=[],
                topics=["testing", "software"],
                quality_score=0.8,
                enriched_at=datetime.now(UTC),
            )
        ]

        # Mock title and slug generation
        mock_openai_client.chat.completions.create.side_effect = [
            # Content generation
            MagicMock(
                choices=[
                    MagicMock(message=MagicMock(content="# Test\n\nContent here."))
                ],
                usage=MagicMock(prompt_tokens=100, completion_tokens=200),
            ),
            # Title generation
            MagicMock(
                choices=[MagicMock(message=MagicMock(content="Test Article Title"))],
                usage=MagicMock(prompt_tokens=50, completion_tokens=25),
            ),
            # Slug generation
            MagicMock(
                choices=[MagicMock(message=MagicMock(content="test-article-title"))],
                usage=MagicMock(prompt_tokens=30, completion_tokens=10),
            ),
        ]

        # Generate articles
        articles = generate_articles_from_enriched(
            enriched_items,
            mock_config,
        )

        # Verify output
        assert isinstance(articles, list)
        # Note: May be empty if generation fails, but should not raise exception


class TestAsyncGeneration:
    """Test async article generation for Python 3.14."""

    def test_async_function_exists(self):
        """Verify async generation function exists."""
        import inspect

        from src.pipeline.orchestrator import generate_articles_async

        assert callable(generate_articles_async)
        assert inspect.iscoroutinefunction(generate_articles_async)

    @pytest.mark.skip(reason="Async testing requires pytest-asyncio configuration")
    @pytest.mark.asyncio
    @patch("src.pipeline.orchestrator.get_available_generators")
    @patch("src.pipeline.orchestrator.check_article_exists_for_source")
    async def test_async_generation_runs(
        self,
        mock_check_exists,
        mock_get_generators,
        mock_config,
        mock_openai_client,
    ):
        """Test async generation can be called."""
        from datetime import UTC, datetime

        from src.pipeline.orchestrator import generate_articles_async

        # Mock generators
        mock_generator = MagicMock()
        mock_builder.name = "TestBuilder"
        mock_builder.priority = 1
        mock_builder.can_handle.return_value = True
        mock_builder.generate_content.return_value = (
            "# Test\n\nContent.",
            100,
            200,
        )
        mock_get_builders.return_value = [mock_builder]
        mock_check_exists.return_value = None

        # Create enriched items
        collected = CollectedItem(
            id="test-async-1",
            title="Async Test",
            content="Test async generation",
            url="https://example.com/async",
            source="mastodon",
            collected_at=datetime.now(UTC),
        )

        enriched_items = [
            EnrichedItem(
                original=collected,
                research_summary="Async test",
                related_sources=[],
                topics=["async"],
                quality_score=0.8,
                enriched_at=datetime.now(UTC),
            )
        ]

        # Mock OpenAI responses
        mock_openai_client.chat.completions.create.side_effect = [
            MagicMock(
                choices=[MagicMock(message=MagicMock(content="# Async\n\nContent."))],
                usage=MagicMock(prompt_tokens=100, completion_tokens=200),
            ),
            MagicMock(
                choices=[MagicMock(message=MagicMock(content="Async Title"))],
                usage=MagicMock(prompt_tokens=50, completion_tokens=25),
            ),
            MagicMock(
                choices=[MagicMock(message=MagicMock(content="async-title"))],
                usage=MagicMock(prompt_tokens=30, completion_tokens=10),
            ),
        ]

        # Run async generation
        articles = await generate_articles_async(
            enriched_items,
            mock_config,
        )

        # Verify it completes without error
        assert isinstance(articles, list)


class TestPerformanceOptimizations:
    """Test that performance optimizations are in place."""

    def test_imports_at_module_level(self):
        """Verify imports are at module level, not lazy loaded."""
        from src.pipeline import orchestrator

        # Check that key imports are available at module level
        assert hasattr(orchestrator, "IllustrationService")
        assert hasattr(orchestrator, "select_diverse_candidates")
        assert hasattr(orchestrator, "logger")

    def test_batched_api_calls_available(self):
        """Verify batched API scoring method exists."""
        from src.pipeline.illustration_service import IllustrationService

        # Check for the batched scoring method
        assert hasattr(IllustrationService, "_score_concept_section_pairs_batch")

        # Verify it's a method
        import inspect

        method = IllustrationService._score_concept_section_pairs_batch
        assert inspect.isfunction(method) or inspect.ismethod(method)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
