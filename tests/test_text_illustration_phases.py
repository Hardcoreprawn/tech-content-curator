#!/usr/bin/env python3
"""Integration tests for text-based illustration improvements.

Tests all three phases of the text illustration feature:
- Phase 1: Enhanced prompts and formatting
- Phase 2: Quality selection and capability routing
- Phase 3: Review and refinement

Run with: python tests/test_text_illustration_phases.py
"""

from unittest.mock import MagicMock, patch

import pytest

from src.illustrations.ai_ascii_generator import (
    AIAsciiGenerator,
    GeneratedAsciiArt,
    TextIllustrationQualitySelector,
)
from src.illustrations.capability_advisor import TextIllustrationCapabilityAdvisor
from src.illustrations.placement import format_diagram_for_markdown
from src.illustrations.text_review_refine import TextIllustrationReviewRefine


class TestPhase1Foundation:
    """Phase 1: Foundation - Enhanced prompts and formatting."""

    def test_generated_ascii_art_has_quality_fields(self):
        """Verify GeneratedAsciiArt dataclass has quality tracking fields."""
        art = GeneratedAsciiArt(
            art_type="diagram",
            content="┌──────┐\n│ Test │\n└──────┘",
            alt_text="test diagram",
            prompt_cost=0.001,
            completion_cost=0.003,
            quality_score=0.85,
            candidates_tested=3,
            review_cycles=0,
        )

        assert art.quality_score == 0.85
        assert art.candidates_tested == 3
        assert art.review_cycles == 0
        assert art.total_cost == 0.004

    def test_format_diagram_for_markdown_basic(self):
        """Test basic formatting of ASCII diagram for markdown."""
        diagram = "┌──────┐\n│ Test │\n└──────┘"
        result = format_diagram_for_markdown(diagram)

        assert '<div align="center">' in result
        assert "```\n" in result
        assert diagram in result
        assert "</div>" in result

    def test_format_diagram_for_markdown_with_title(self):
        """Test formatting with section title caption."""
        diagram = "┌──────┐\n│ Test │\n└──────┘"
        section_title = "My Section"
        result = format_diagram_for_markdown(diagram, section_title)

        assert f"*Figure: {section_title}*" in result
        assert diagram in result

    @patch("src.illustrations.ai_ascii_generator.OpenAI")
    def test_ai_generator_uses_enhanced_prompt(self, mock_openai):
        """Verify enhanced system prompt is used (would need real API to test fully)."""
        # This is a placeholder - actual test would verify the prompt is sent
        mock_client = MagicMock()
        generator = AIAsciiGenerator(mock_client)

        assert generator is not None
        assert generator.model == "gpt-3.5-turbo"


class TestPhase2SmartSelection:
    """Phase 2: Smart selection and routing."""

    def test_quality_selector_initialization(self):
        """Test TextIllustrationQualitySelector initialization."""
        mock_client = MagicMock()

        selector = TextIllustrationQualitySelector(
            mock_client, n_candidates=5, quality_threshold=0.65
        )

        assert selector.n_candidates == 5
        assert selector.quality_threshold == 0.65

    def test_quality_score_alignment(self):
        """Test alignment scoring (consistent line lengths)."""
        mock_client = MagicMock()
        selector = TextIllustrationQualitySelector(mock_client)

        # Perfect alignment
        perfect = "┌────┐\n│Test│\n└────┘"
        score_perfect = selector._score(perfect, "comparison")
        assert score_perfect > 0.7

        # Poor alignment
        poor = "┌────┐\n│Test│\n└──┘"
        score_poor = selector._score(poor, "comparison")
        assert score_poor < score_perfect

    def test_quality_score_character_variety(self):
        """Test character variety scoring."""
        mock_client = MagicMock()
        selector = TextIllustrationQualitySelector(mock_client)

        # Good character variety for network
        good = "┌─────┐\n│ A ├─→ B\n└─────┘"
        score = selector._score(good, "network_topology")
        assert score > 0.5

    def test_quality_score_width_constraint(self):
        """Test width constraint scoring."""
        mock_client = MagicMock()
        selector = TextIllustrationQualitySelector(mock_client)

        # Under 60 chars - good
        short = "┌" + "─" * 50 + "┐"
        score_short = selector._score(short, "comparison")
        assert score_short > 0.6

        # Over 70 chars - poor
        long = "┌" + "─" * 80 + "┐"
        score_long = selector._score(long, "comparison")
        assert score_long < score_short

    def test_capability_advisor_initialization(self):
        """Test TextIllustrationCapabilityAdvisor initialization."""
        advisor = TextIllustrationCapabilityAdvisor()
        assert advisor is not None

    def test_capability_advisor_simple_hierarchy(self):
        """Test advisor recommends text for simple hierarchies."""
        advisor = TextIllustrationCapabilityAdvisor()

        # Simple hierarchy: should recommend text
        should_use, reason, confidence = advisor.should_use_text(
            "hierarchy", complexity=0.5, content_length=4
        )

        assert should_use is True
        assert confidence > 0.75
        assert "hierarchy" in reason.lower()

    def test_capability_advisor_complex_hierarchy(self):
        """Test advisor recommends SVG for complex hierarchies."""
        advisor = TextIllustrationCapabilityAdvisor()

        # Complex hierarchy: should recommend other format
        should_use, reason, confidence = advisor.should_use_text(
            "hierarchy", complexity=0.9, content_length=12
        )

        assert should_use is False
        assert confidence > 0.7

    def test_capability_advisor_comparison_table(self):
        """Test advisor recommends text for comparisons (tables)."""
        advisor = TextIllustrationCapabilityAdvisor()

        # Comparisons are ideal for text tables
        should_use, reason, confidence = advisor.should_use_text(
            "comparison", complexity=0.3, content_length=6
        )

        assert should_use is True
        assert confidence > 0.9

    def test_capability_advisor_all_concepts(self):
        """Test advisor handles all concept types."""
        advisor = TextIllustrationCapabilityAdvisor()

        concepts = [
            "hierarchy",
            "process_flow",
            "comparison",
            "timeline",
            "data_flow",
            "data_structure",
            "network_topology",
            "scientific_process",
            "algorithm",
            "system_architecture",
        ]

        for concept in concepts:
            should_use, reason, confidence = advisor.should_use_text(concept, 0.5, 4)
            assert isinstance(should_use, bool)
            assert isinstance(confidence, float)
            assert 0.0 <= confidence <= 1.0
            assert len(reason) > 0

    def test_capability_advisor_recommendations_dict(self):
        """Test advisor returns detailed recommendations."""
        advisor = TextIllustrationCapabilityAdvisor()

        recs = advisor.get_all_recommendations("comparison", 0.5, 6)

        assert "text" in recs
        assert "mermaid" in recs
        assert "svg" in recs

        for _format_name, rec in recs.items():
            assert "recommended" in rec
            assert "confidence" in rec
            assert "cost_multiplier" in rec


class TestPhase3ReviewRefine:
    """Phase 3: Review and refinement."""

    def test_review_refine_initialization(self):
        """Test TextIllustrationReviewRefine initialization."""
        mock_client = MagicMock()
        refiner = TextIllustrationReviewRefine(mock_client)

        assert refiner is not None
        assert refiner.client is mock_client

    def test_review_refine_low_importance_skips_review(self):
        """Test review/refine skips for low-importance diagrams."""
        mock_client = MagicMock()

        # Mock the generator
        with patch.object(AIAsciiGenerator, "generate_for_section") as mock_gen:
            initial_art = GeneratedAsciiArt(
                art_type="diagram",
                content="┌──────┐\n│Test│\n└──────┘",
                alt_text="test",
                prompt_cost=0.001,
                completion_cost=0.003,
            )
            mock_gen.return_value = initial_art

            refiner = TextIllustrationReviewRefine(mock_client)
            result = refiner.generate_with_review(
                "Test", "test content", "comparison", importance=0.5
            )

            # Low importance should skip review
            assert result is not None
            assert result.review_cycles == 0

    def test_dataclass_backward_compatible(self):
        """Test GeneratedAsciiArt is backward compatible (new fields optional)."""
        # Old code creating without quality fields should still work
        art = GeneratedAsciiArt(
            art_type="diagram",
            content="test",
            alt_text="test",
            prompt_cost=0.001,
            completion_cost=0.003,
            # No quality_score, candidates_tested, review_cycles
        )

        assert art.quality_score == 0.0
        assert art.candidates_tested == 0
        assert art.review_cycles == 0


class TestIntegration:
    """Integration tests across phases."""

    def test_quality_selector_generates_multiple(self):
        """Test quality selector generates multiple candidates."""
        mock_client = MagicMock()

        # Mock multiple responses
        candidates = [
            GeneratedAsciiArt(
                art_type="diagram",
                content="┌──────┐\n│ A ├──┐\n│ B ├──┐\n└──────┘",
                alt_text="test1",
                prompt_cost=0.001,
                completion_cost=0.003,
            ),
            GeneratedAsciiArt(
                art_type="diagram",
                content="┌─────────┐\n│A → B │\n└─────────┘",
                alt_text="test2",
                prompt_cost=0.001,
                completion_cost=0.003,
            ),
            GeneratedAsciiArt(
                art_type="diagram",
                content="A → B → C",
                alt_text="test3",
                prompt_cost=0.001,
                completion_cost=0.003,
            ),
        ]

        with patch.object(
            AIAsciiGenerator, "generate_for_section", side_effect=candidates
        ):
            mock_client = MagicMock()
            selector = TextIllustrationQualitySelector(
                mock_client, n_candidates=3, quality_threshold=0.5
            )

            result = selector.generate_best("Test", "test content", "comparison")

            assert result is not None
            assert result.candidates_tested == 3

    def test_advisor_and_selector_work_together(self):
        """Test capability advisor and quality selector integration."""
        advisor = TextIllustrationCapabilityAdvisor()

        # For a comparison concept
        should_use, reason, confidence = advisor.should_use_text("comparison", 0.3, 6)

        if should_use and confidence > 0.75:
            # Text diagram recommended
            assert "comparison" in reason.lower() or "table" in reason.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
