"""Smoke tests for multi-candidate selection system.

Tests verify that components accept correct inputs and produce reasonable
outputs. Focus is on functional behavior, not internal implementation details.
"""

from unittest.mock import Mock

from openai import OpenAI

from src.illustrations.ai_mermaid_generator import GeneratedMermaidDiagram
from src.illustrations.mermaid_quality_selector import (
    MermaidCandidateResult,
    MermaidQualitySelector,
)


class TestMermaidQualitySelector:
    """Smoke tests for multi-candidate Mermaid diagram generation."""

    def test_selector_instantiation_with_defaults(self):
        """Selector can be created with minimal configuration."""
        client = Mock(spec=OpenAI)
        selector = MermaidQualitySelector(client)

        assert selector is not None
        assert selector.n_candidates == 3
        assert selector.validation_threshold == 0.7

    def test_selector_with_custom_parameters(self):
        """Selector accepts and stores custom parameters."""
        client = Mock(spec=OpenAI)
        selector = MermaidQualitySelector(
            client, n_candidates=5, validation_threshold=0.8
        )

        assert selector.n_candidates == 5
        assert selector.validation_threshold == 0.8

    def test_candidate_result_with_diagram(self):
        """CandidateResult stores diagram and metadata correctly."""
        diagram = GeneratedMermaidDiagram(
            diagram_type="flowchart",
            content="flowchart TD\n  A --> B --> C",
            alt_text="Process flow",
            prompt_cost=0.0005,
            completion_cost=0.0015,
        )

        result = MermaidCandidateResult(
            diagram=diagram,
            candidates_tested=3,
            best_score=0.85,
            all_rejected=False,
            total_cost=0.009,
        )

        assert result.diagram is not None
        assert result.diagram.content == "flowchart TD\n  A --> B --> C"
        assert result.candidates_tested == 3
        assert result.best_score == 0.85
        assert result.all_rejected is False

    def test_candidate_result_with_rejection(self):
        """CandidateResult handles all-rejected case."""
        result = MermaidCandidateResult(
            diagram=None,
            candidates_tested=3,
            best_score=0.45,
            all_rejected=True,
            total_cost=0.009,
        )

        assert result.diagram is None
        assert result.all_rejected is True
        assert result.best_score < 0.7

    def test_diagram_cost_accumulation(self):
        """Generated diagrams accumulate costs correctly."""
        diagrams = [
            GeneratedMermaidDiagram(
                diagram_type="flowchart",
                content="flowchart TD\n  A --> B",
                alt_text="Diagram 1",
                prompt_cost=0.001,
                completion_cost=0.001,
            ),
            GeneratedMermaidDiagram(
                diagram_type="sequence",
                content="sequenceDiagram\n  A->>B: Call",
                alt_text="Diagram 2",
                prompt_cost=0.001,
                completion_cost=0.001,
            ),
        ]

        # Total cost should be sum of all diagrams
        total_cost = sum(d.total_cost for d in diagrams)
        assert total_cost == 0.004

    def test_selector_n_candidates_bounds(self):
        """Selector accepts reasonable candidate count values."""
        client = Mock(spec=OpenAI)

        # Test low end
        low = MermaidQualitySelector(client, n_candidates=1)
        assert low.n_candidates == 1

        # Test high end
        high = MermaidQualitySelector(client, n_candidates=5)
        assert high.n_candidates == 5

    def test_validation_threshold_bounds(self):
        """Selector accepts reasonable validation thresholds."""
        client = Mock(spec=OpenAI)

        # Test low threshold
        low_threshold = MermaidQualitySelector(client, validation_threshold=0.5)
        assert low_threshold.validation_threshold == 0.5

        # Test high threshold
        high_threshold = MermaidQualitySelector(client, validation_threshold=0.9)
        assert high_threshold.validation_threshold == 0.9
