"""Tests for enrichment/orchestrator.py."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest

from src.enrichment.orchestrator import enrich_collected_items, enrich_single_item
from src.models import CollectedItem, EnrichedItem, PipelineConfig


def make_item(
    content: str = "Test content about Python programming",
    title: str = "Test Article",
    url: str = "https://example.com/test",
    metadata: dict | None = None,
) -> CollectedItem:
    """Helper to create test CollectedItem with valid defaults."""
    return CollectedItem(
        id="test-id",
        source="mastodon",
        author="testuser",
        content=content,
        title=title,
        url=url,
        collected_at=datetime.now(UTC),
        metadata=metadata or {},
    )


def make_config() -> PipelineConfig:
    """Helper to create test PipelineConfig."""
    return PipelineConfig(
        openai_api_key="test-key",
        content_dirs={"posts": "content/posts"},
        use_semantic_dedup=False,
    )


class TestEnrichSingleItem:
    """Test the single item enrichment orchestration."""

    @patch("src.enrichment.orchestrator.OpenAI")
    @patch("src.enrichment.orchestrator.calculate_heuristic_score")
    @patch("src.enrichment.orchestrator.analyze_content_quality")
    @patch("src.enrichment.orchestrator.extract_topics_and_themes")
    @patch("src.enrichment.orchestrator.research_additional_context")
    def test_full_enrichment_flow(
        self, mock_research, mock_topics, mock_ai, mock_heuristic, mock_openai
    ):
        """High-quality item gets full enrichment pipeline."""
        item = make_item()
        config = make_config()

        # Mock scoring responses
        mock_heuristic.return_value = (0.5, "Good heuristic score")
        mock_ai.return_value = (0.8, "High AI quality")
        mock_topics.return_value = ["Python", "Programming", "Tech"]
        mock_research.return_value = "Detailed research summary"

        result = enrich_single_item(item, config)

        # Verify enrichment completed
        assert result is not None
        assert isinstance(result, EnrichedItem)
        assert result.quality_score == pytest.approx(0.71, abs=0.01)  # 0.5*0.3 + 0.8*0.7
        assert result.topics == ["Python", "Programming", "Tech"]
        assert result.research_summary == "Detailed research summary"

        # Verify all steps were called
        mock_heuristic.assert_called_once()
        mock_ai.assert_called_once()
        mock_topics.assert_called_once()
        mock_research.assert_called_once()

    @patch("src.enrichment.orchestrator.OpenAI")
    @patch("src.enrichment.orchestrator.calculate_heuristic_score")
    def test_early_exit_low_heuristic(self, mock_heuristic, mock_openai):
        """Very low heuristic score exits early without AI call."""
        item = make_item()
        config = make_config()

        # Mock very low heuristic score
        mock_heuristic.return_value = (0.1, "Poor heuristic score")

        result = enrich_single_item(item, config)

        # Verify early exit enrichment
        assert result is not None
        assert result.quality_score == 0.1
        assert "Heuristic score too low" in result.research_summary
        assert result.topics == []

    @patch("src.enrichment.orchestrator.OpenAI")
    @patch("src.enrichment.orchestrator.calculate_heuristic_score")
    @patch("src.enrichment.orchestrator.analyze_content_quality")
    @patch("src.enrichment.orchestrator.extract_topics_and_themes")
    def test_skip_research_low_combined_score(
        self, mock_topics, mock_ai, mock_heuristic, mock_openai
    ):
        """Low combined score skips research but extracts topics."""
        item = make_item()
        config = make_config()

        # Mock moderate heuristic but low AI score
        mock_heuristic.return_value = (0.3, "Moderate heuristic")
        mock_ai.return_value = (0.2, "Low AI quality")
        mock_topics.return_value = ["Topic1"]

        result = enrich_single_item(item, config)

        # Verify partial enrichment (topics but no research)
        assert result is not None
        assert result.quality_score == pytest.approx(0.23, abs=0.01)  # 0.3*0.3 + 0.2*0.7
        assert result.topics == ["Topic1"]
        assert "below threshold" in result.research_summary.lower()

    @patch("src.enrichment.orchestrator.OpenAI")
    @patch("src.enrichment.orchestrator.calculate_heuristic_score")
    @patch("src.enrichment.orchestrator.analyze_content_quality")
    @patch("src.enrichment.orchestrator.extract_topics_and_themes")
    @patch("src.enrichment.orchestrator.research_additional_context")
    def test_research_included_for_high_score(
        self, mock_research, mock_topics, mock_ai, mock_heuristic, mock_openai
    ):
        """Score >= 0.4 includes detailed research."""
        item = make_item()
        config = make_config()

        # Mock scores that combine to >= 0.4
        mock_heuristic.return_value = (0.5, "Good score")
        mock_ai.return_value = (0.5, "Good AI score")
        mock_topics.return_value = ["Tech"]
        mock_research.return_value = "Research details"

        result = enrich_single_item(item, config)

        # Verify research was included
        assert result is not None
        assert result.quality_score == pytest.approx(0.5, abs=0.01)  # 0.5*0.3 + 0.5*0.7
        assert result.research_summary == "Research details"
        mock_research.assert_called_once()

    @patch("src.enrichment.orchestrator.OpenAI")
    @patch("src.enrichment.orchestrator.calculate_heuristic_score")
    def test_exception_handling(self, mock_heuristic, mock_openai):
        """Exception during enrichment returns None."""
        item = make_item()
        config = make_config()

        # Mock exception during scoring
        mock_heuristic.side_effect = Exception("API error")

        result = enrich_single_item(item, config)

        # Verify graceful failure
        assert result is None

    @patch("src.enrichment.orchestrator.OpenAI")
    @patch("src.enrichment.orchestrator.calculate_heuristic_score")
    @patch("src.enrichment.orchestrator.analyze_content_quality")
    def test_adaptive_scoring_feedback(self, mock_ai, mock_heuristic, mock_openai):
        """Adaptive scoring adapter receives feedback."""
        item = make_item()
        config = make_config()
        adapter = Mock()

        # Mock scores
        mock_heuristic.return_value = (0.5, "Good")
        mock_ai.return_value = (0.7, "High")

        enrich_single_item(item, config, adapter)

        # Verify feedback was recorded
        adapter.record_feedback.assert_called_once()

    @patch("src.enrichment.orchestrator.OpenAI")
    @patch("src.enrichment.orchestrator.calculate_heuristic_score")
    @patch("src.enrichment.orchestrator.analyze_content_quality")
    def test_score_weighting(self, mock_ai, mock_heuristic, mock_openai):
        """Final score is weighted 30% heuristic, 70% AI."""
        item = make_item()
        config = make_config()

        # Test with known scores
        mock_heuristic.return_value = (1.0, "Perfect heuristic")
        mock_ai.return_value = (0.0, "Poor AI")

        result = enrich_single_item(item, config)

        # Verify weighting: 1.0*0.3 + 0.0*0.7 = 0.3
        assert result is not None
        assert result.quality_score == pytest.approx(0.3, abs=0.01)


class TestEnrichCollectedItems:
    """Test the batch enrichment orchestration."""

    @patch("src.enrichment.orchestrator.enrich_single_item")
    @patch("src.enrichment.orchestrator.get_config")
    @patch("src.enrichment.orchestrator.ScoringAdapter")
    def test_sequential_enrichment(self, mock_adapter_class, mock_config, mock_enrich):
        """Items are enriched sequentially."""
        items = [make_item(title=f"Item {i}") for i in range(3)]
        mock_config.return_value = make_config()

        # Mock successful enrichment
        def mock_enrich_fn(item, config, adapter):
            return EnrichedItem(
                original=item,
                research_summary="Test",
                related_sources=[],
                topics=[],
                quality_score=0.5,
                enriched_at=datetime.now(UTC),
            )

        mock_enrich.side_effect = mock_enrich_fn

        # Create mock adapter instance
        mock_adapter = Mock()
        mock_adapter_class.return_value = mock_adapter

        results = enrich_collected_items(items)

        # Verify all items were enriched
        assert len(results) == 3
        assert mock_enrich.call_count == 3

        # Verify adapter lifecycle
        mock_adapter.update_learned_patterns.assert_called_once()
        mock_adapter.save_feedback.assert_called_once()
        mock_adapter.print_analysis_report.assert_called_once()

    @patch("src.enrichment.orchestrator.enrich_single_item")
    @patch("src.enrichment.orchestrator.get_config")
    @patch("src.enrichment.orchestrator.ScoringAdapter")
    def test_handles_failures(self, mock_adapter_class, mock_config, mock_enrich):
        """Failed enrichments are handled gracefully."""
        items = [make_item(title=f"Item {i}") for i in range(3)]
        mock_config.return_value = make_config()
        mock_adapter_class.return_value = Mock()

        # Mock mix of success and failure
        def mock_enrich_fn(item, config, adapter):
            if "Item 1" in item.title:
                return None  # Simulate failure
            return EnrichedItem(
                original=item,
                research_summary="Test",
                related_sources=[],
                topics=[],
                quality_score=0.5,
                enriched_at=datetime.now(UTC),
            )

        mock_enrich.side_effect = mock_enrich_fn

        results = enrich_collected_items(items)

        # Verify only successful items returned
        assert len(results) == 2

    @patch("src.enrichment.orchestrator.enrich_single_item")
    @patch("src.enrichment.orchestrator.get_config")
    @patch("src.enrichment.orchestrator.ScoringAdapter")
    def test_empty_input(self, mock_adapter_class, mock_config, mock_enrich):
        """Empty input list returns empty results."""
        mock_config.return_value = make_config()
        mock_adapter_class.return_value = Mock()

        results = enrich_collected_items([])

        # Verify empty result
        assert results == []
        mock_enrich.assert_not_called()

    @patch("src.enrichment.orchestrator.enrich_single_item")
    @patch("src.enrichment.orchestrator.get_config")
    @patch("src.enrichment.orchestrator.ScoringAdapter")
    def test_max_workers_parameter(self, mock_adapter_class, mock_config, mock_enrich):
        """max_workers parameter is accepted for compatibility."""
        items = [make_item(title=f"Item {i}") for i in range(10)]
        mock_config.return_value = make_config()
        mock_adapter_class.return_value = Mock()

        # Mock enrichment
        mock_enrich.return_value = EnrichedItem(
            original=items[0],
            research_summary="Test",
            related_sources=[],
            topics=[],
            quality_score=0.5,
            enriched_at=datetime.now(UTC),
        )

        # Test with max_workers parameter (kept for compatibility)
        results = enrich_collected_items(items, max_workers=3)

        # Verify all items processed sequentially
        assert len(results) == 10
        assert mock_enrich.call_count == 10
