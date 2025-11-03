"""Tests for MermaidQualitySelector."""

from unittest.mock import Mock

from openai import OpenAI

from src.illustrations.ai_mermaid_generator import GeneratedMermaidDiagram
from src.illustrations.mermaid_quality_selector import (
    MermaidCandidateResult,
    MermaidQualitySelector,
)


class TestMermaidQualitySelector:
    """Tests for multi-candidate Mermaid generation."""

    def test_selects_best_candidate(self):
        """Selects highest-scoring valid candidate."""
        client = Mock(spec=OpenAI)

        # Setup mocks for 3 generation attempts
        diagrams = [
            GeneratedMermaidDiagram(
                diagram_type="flowchart",
                content="flowchart TD\n  A --> B --> C",
                alt_text="Generic flow",
                prompt_cost=0.0005,
                completion_cost=0.0015,
            ),
            GeneratedMermaidDiagram(
                diagram_type="flowchart",
                content="flowchart TD\n  Read --> Eval --> Print --> Loop",
                alt_text="REPL process",
                prompt_cost=0.0005,
                completion_cost=0.0015,
            ),
            GeneratedMermaidDiagram(
                diagram_type="flowchart",
                content="flowchart LR\n  X --> Y",
                alt_text="Simple flow",
                prompt_cost=0.0005,
                completion_cost=0.0015,
            ),
        ]

        # Setup validation responses
        validation_responses = [
            '{"accuracy": 0.5, "value_add": 0.4, "reason": "Generic"}',
            '{"accuracy": 0.9, "value_add": 0.8, "reason": "Accurate"}',
            '{"accuracy": 0.2, "value_add": 0.1, "reason": "Poor"}',
        ]

        # Mock generator and validator
        gen_call_count = [0]
        val_call_count = [0]

        def mock_generate(*args, **kwargs):
            result = diagrams[gen_call_count[0]]
            gen_call_count[0] += 1
            return result

        def mock_validate(*args, **kwargs):
            from src.illustrations.diagram_validator import ValidationResult

            response_text = validation_responses[val_call_count[0]]
            val_call_count[0] += 1

            import json

            data = json.loads(response_text)
            accuracy = float(data.get("accuracy", 0.0))
            value = float(data.get("value_add", 0.0))
            combined = (accuracy * 0.6) + (value * 0.4)

            return ValidationResult(
                is_valid=combined >= 0.7,
                accuracy_score=accuracy,
                value_score=value,
                combined_score=combined,
                reason=data.get("reason", ""),
                cost=0.0001,
            )

        selector = MermaidQualitySelector(client, n_candidates=3)
        selector.generator.generate_for_section = mock_generate
        selector.validator.validate_diagram = mock_validate

        result = selector.generate_best(
            section_title="REPL Process",
            section_content="The Read-Eval-Print Loop...",
            concept_type="scientific_process",
        )

        assert result.diagram is not None
        assert result.best_score >= 0.7
        assert result.candidates_tested == 3
        assert not result.all_rejected
        assert "Eval" in result.diagram.content

    def test_rejects_all_low_quality_candidates(self):
        """Rejects all candidates when below threshold."""
        client = Mock(spec=OpenAI)

        diagrams = [
            GeneratedMermaidDiagram(
                diagram_type="flowchart",
                content="flowchart TD\n  A --> B",
                alt_text="Generic",
                prompt_cost=0.0005,
                completion_cost=0.0015,
            ),
            GeneratedMermaidDiagram(
                diagram_type="flowchart",
                content="flowchart TD\n  X --> Y",
                alt_text="Generic 2",
                prompt_cost=0.0005,
                completion_cost=0.0015,
            ),
            GeneratedMermaidDiagram(
                diagram_type="flowchart",
                content="flowchart TD\n  P --> Q",
                alt_text="Generic 3",
                prompt_cost=0.0005,
                completion_cost=0.0015,
            ),
        ]

        validation_responses = [
            '{"accuracy": 0.3, "value_add": 0.2, "reason": "Poor"}',
            '{"accuracy": 0.4, "value_add": 0.3, "reason": "Poor"}',
            '{"accuracy": 0.35, "value_add": 0.25, "reason": "Poor"}',
        ]

        gen_call_count = [0]
        val_call_count = [0]

        def mock_generate(*args, **kwargs):
            result = diagrams[gen_call_count[0]]
            gen_call_count[0] += 1
            return result

        def mock_validate(*args, **kwargs):
            from src.illustrations.diagram_validator import ValidationResult

            response_text = validation_responses[val_call_count[0]]
            val_call_count[0] += 1

            import json

            data = json.loads(response_text)
            accuracy = float(data.get("accuracy", 0.0))
            value = float(data.get("value_add", 0.0))
            combined = (accuracy * 0.6) + (value * 0.4)

            return ValidationResult(
                is_valid=combined >= 0.7,
                accuracy_score=accuracy,
                value_score=value,
                combined_score=combined,
                reason=data.get("reason", ""),
                cost=0.0001,
            )

        selector = MermaidQualitySelector(client, n_candidates=3, validation_threshold=0.7)
        selector.generator.generate_for_section = mock_generate
        selector.validator.validate_diagram = mock_validate

        result = selector.generate_best(
            section_title="Test",
            section_content="Test content",
            concept_type="test_concept",
        )

        assert result.diagram is None
        assert result.all_rejected is True
        assert result.candidates_tested == 3

    def test_cost_accumulation(self):
        """Accumulates cost from all candidates."""
        client = Mock(spec=OpenAI)

        diagram = GeneratedMermaidDiagram(
            diagram_type="flowchart",
            content="flowchart TD\n  A --> B",
            alt_text="Test",
            prompt_cost=0.001,
            completion_cost=0.001,
        )

        gen_count = [0]
        val_count = [0]

        def mock_generate(*args, **kwargs):
            gen_count[0] += 1
            return diagram

        def mock_validate(*args, **kwargs):
            from src.illustrations.diagram_validator import ValidationResult

            val_count[0] += 1
            return ValidationResult(
                is_valid=True,
                accuracy_score=0.85,
                value_score=0.8,
                combined_score=0.83,
                reason="Good",
                cost=0.0001,
            )

        selector = MermaidQualitySelector(client, n_candidates=3)
        selector.generator.generate_for_section = mock_generate
        selector.validator.validate_diagram = mock_validate

        result = selector.generate_best(
            section_title="Test",
            section_content="Test content",
            concept_type="test",
        )

        # 3 candidates * (0.002 generation + 0.0001 validation) = 0.0063
        expected_cost = 3 * (0.002 + 0.0001)
        # Allow some floating point tolerance
        assert abs(result.total_cost - expected_cost) < 0.0001

    def test_candidate_result_dataclass(self):
        """MermaidCandidateResult has all required fields."""
        result = MermaidCandidateResult(
            diagram=None,
            candidates_tested=3,
            best_score=0.5,
            all_rejected=True,
            total_cost=0.006,
        )

        assert result.diagram is None
        assert result.candidates_tested == 3
        assert result.best_score == 0.5
        assert result.all_rejected is True
        assert result.total_cost == 0.006

    def test_no_candidates_generated(self):
        """Handles case where no candidates are generated."""
        client = Mock(spec=OpenAI)

        def mock_generate(*args, **kwargs):
            return None

        selector = MermaidQualitySelector(client, n_candidates=3)
        selector.generator.generate_for_section = mock_generate

        result = selector.generate_best(
            section_title="Test",
            section_content="Test content",
            concept_type="test",
        )

        assert result.diagram is None
        assert result.candidates_tested == 0
        assert result.all_rejected is True
        assert result.total_cost == 0.0

    def test_n_candidates_configurable(self):
        """Number of candidates is configurable."""
        client = Mock(spec=OpenAI)

        selector = MermaidQualitySelector(client, n_candidates=2)
        assert selector.n_candidates == 2

        selector = MermaidQualitySelector(client, n_candidates=5)
        assert selector.n_candidates == 5

    def test_validation_threshold_configurable(self):
        """Validation threshold is configurable."""
        client = Mock(spec=OpenAI)

        selector = MermaidQualitySelector(client, validation_threshold=0.5)
        assert selector.validation_threshold == 0.5

        selector = MermaidQualitySelector(client, validation_threshold=0.8)
        assert selector.validation_threshold == 0.8
