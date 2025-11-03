"""Tests for diagram validation."""

from unittest.mock import MagicMock, Mock

import pytest
from openai import OpenAI

from src.illustrations.diagram_validator import DiagramValidator, ValidationResult


class TestDiagramValidator:
    """Tests for DiagramValidator."""

    def test_validate_good_diagram(self):
        """Accepts diagrams with high scores."""
        client = Mock(spec=OpenAI)

        # Mock API response
        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = (
            '{"accuracy": 0.9, "value_add": 0.8, "reason": "Clear and accurate"}'
        )
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        client.chat.completions.create.return_value = mock_response

        validator = DiagramValidator(client, threshold=0.7)
        result = validator.validate_diagram(
            section_title="How REPL Works",
            section_content="The Read-Eval-Print Loop executes code...",
            diagram_content="flowchart TD\n  Read --> Eval --> Print",
            diagram_type="mermaid",
        )

        assert result.is_valid is True
        assert result.accuracy_score == 0.9
        assert result.value_score == 0.8
        assert result.combined_score >= 0.7

    def test_validate_bad_diagram(self):
        """Rejects diagrams with low scores."""
        client = Mock(spec=OpenAI)

        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = '{"accuracy": 0.3, "value_add": 0.2, "reason": "Generic, doesn\'t match content"}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        client.chat.completions.create.return_value = mock_response

        validator = DiagramValidator(client, threshold=0.7)
        result = validator.validate_diagram(
            section_title="Clojure Features",
            section_content="- Simplicity\n- Concurrency\n- Interoperability",
            diagram_content="flowchart TD\n  A --> B --> C",
            diagram_type="mermaid",
        )

        assert result.is_valid is False
        assert result.combined_score < 0.7

    def test_combined_score_calculation(self):
        """Combined score is 60% accuracy + 40% value."""
        client = Mock(spec=OpenAI)

        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = '{"accuracy": 0.8, "value_add": 0.6, "reason": "Good"}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        client.chat.completions.create.return_value = mock_response

        validator = DiagramValidator(client, threshold=0.5)
        result = validator.validate_diagram(
            section_title="Test",
            section_content="Test content",
            diagram_content="diagram",
            diagram_type="mermaid",
        )

        # Combined = (0.8 * 0.6) + (0.6 * 0.4) = 0.48 + 0.24 = 0.72
        assert result.combined_score == pytest.approx(0.72, rel=0.01)

    def test_threshold_boundary(self):
        """Diagram exactly at threshold is valid."""
        client = Mock(spec=OpenAI)

        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = '{"accuracy": 0.7, "value_add": 0.7, "reason": "Threshold"}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        client.chat.completions.create.return_value = mock_response

        validator = DiagramValidator(client, threshold=0.7)
        result = validator.validate_diagram(
            section_title="Test",
            section_content="Test content",
            diagram_content="diagram",
            diagram_type="ascii",
        )

        # (0.7 * 0.6) + (0.7 * 0.4) = 0.7
        assert result.is_valid is True
        assert result.combined_score == pytest.approx(0.7, rel=0.01)

    def test_parse_error_handling(self):
        """Invalid JSON response fails gracefully."""
        client = Mock(spec=OpenAI)

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Invalid JSON {{"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        client.chat.completions.create.return_value = mock_response

        validator = DiagramValidator(client)
        result = validator.validate_diagram(
            section_title="Test",
            section_content="Test content",
            diagram_content="diagram",
            diagram_type="mermaid",
        )

        assert result.is_valid is False
        assert "Parse error" in result.reason

    def test_empty_response_handling(self):
        """Empty API response fails gracefully."""
        client = Mock(spec=OpenAI)

        mock_response = MagicMock()
        mock_response.choices[0].message.content = None
        client.chat.completions.create.return_value = mock_response

        validator = DiagramValidator(client)
        result = validator.validate_diagram(
            section_title="Test",
            section_content="Test content",
            diagram_content="diagram",
            diagram_type="mermaid",
        )

        assert result.is_valid is False
        assert "No response" in result.reason

    def test_cost_calculation(self):
        """Cost is calculated from token counts."""
        client = Mock(spec=OpenAI)

        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = '{"accuracy": 0.8, "value_add": 0.7, "reason": "Good"}'
        # 100 prompt tokens: 100/1000 * 0.0005 = 0.00005
        # 50 completion tokens: 50/1000 * 0.0015 = 0.000075
        # Total: 0.000125
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        client.chat.completions.create.return_value = mock_response

        validator = DiagramValidator(client)
        result = validator.validate_diagram(
            section_title="Test",
            section_content="Test content",
            diagram_content="diagram",
            diagram_type="mermaid",
        )

        assert result.cost == pytest.approx(0.000125, rel=0.01)

    def test_validation_prompt_includes_preview(self):
        """Validation prompt includes truncated content and diagram."""
        client = Mock(spec=OpenAI)

        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = '{"accuracy": 0.8, "value_add": 0.7, "reason": "Good"}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        client.chat.completions.create.return_value = mock_response

        validator = DiagramValidator(client)
        validator.validate_diagram(
            section_title="My Section",
            section_content="This is the section content",
            diagram_content="flowchart TD",
            diagram_type="mermaid",
        )

        # Check that API was called
        assert client.chat.completions.create.called

        # Get the call arguments
        call_kwargs = client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]

        # Find the user message
        user_message = next(m for m in messages if m["role"] == "user")
        prompt_content = user_message["content"]

        # Verify prompt includes key information
        assert "My Section" in prompt_content
        assert "This is the section content" in prompt_content
        assert "flowchart TD" in prompt_content
        assert "ACCURACY" in prompt_content
        assert "VALUE_ADD" in prompt_content

    def test_long_content_truncation(self):
        """Long content and diagrams are truncated in prompt."""
        client = Mock(spec=OpenAI)

        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = '{"accuracy": 0.8, "value_add": 0.7, "reason": "Good"}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        client.chat.completions.create.return_value = mock_response

        # Create very long content
        long_content = "x" * 1000
        long_diagram = "y" * 600

        validator = DiagramValidator(client)
        validator.validate_diagram(
            section_title="Test",
            section_content=long_content,
            diagram_content=long_diagram,
            diagram_type="mermaid",
        )

        # Get the call arguments
        call_kwargs = client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        user_message = next(m for m in messages if m["role"] == "user")
        prompt_content = user_message["content"]

        # Verify truncation happened - should have ellipsis markers
        assert "..." in prompt_content  # Should have ellipsis for truncated content
        # Content is truncated to 800 chars, but prompt structure adds overhead
        # so the count of 'x' should be close to 800, with some margin for formatting
        x_count = prompt_content.count("x")
        y_count = prompt_content.count("y")
        assert x_count <= 820  # Allow small margin for formatting
        assert y_count <= 520  # Diagram should be even more truncated

    def test_validation_result_dataclass(self):
        """ValidationResult has all required fields."""
        result = ValidationResult(
            is_valid=True,
            accuracy_score=0.9,
            value_score=0.8,
            combined_score=0.86,
            reason="Test reason",
            cost=0.001,
        )

        assert result.is_valid is True
        assert result.accuracy_score == 0.9
        assert result.value_score == 0.8
        assert result.combined_score == 0.86
        assert result.reason == "Test reason"
        assert result.cost == 0.001
