"""Tests for illustration quality configuration options."""

from src.models import PipelineConfig


class TestIllustrationQualityConfig:
    """Tests for diagram validation and quality configuration."""

    def test_diagram_validation_threshold_default(self):
        """Default diagram validation threshold is 0.7."""
        config = PipelineConfig(openai_api_key="test-key")
        assert config.diagram_validation_threshold == 0.7

    def test_diagram_validation_threshold_custom(self):
        """Can set custom diagram validation threshold."""
        config = PipelineConfig(
            openai_api_key="test-key",
            diagram_validation_threshold=0.8,
        )
        assert config.diagram_validation_threshold == 0.8

    def test_mermaid_candidates_default(self):
        """Default number of Mermaid candidates is 3."""
        config = PipelineConfig(openai_api_key="test-key")
        assert config.mermaid_candidates == 3

    def test_mermaid_candidates_custom(self):
        """Can set custom number of Mermaid candidates."""
        config = PipelineConfig(
            openai_api_key="test-key",
            mermaid_candidates=5,
        )
        assert config.mermaid_candidates == 5

    def test_ascii_candidates_default(self):
        """Default number of ASCII candidates is 3."""
        config = PipelineConfig(openai_api_key="test-key")
        assert config.ascii_candidates == 3

    def test_text_illustration_candidates_default(self):
        """Default number of text illustration candidates is 3."""
        config = PipelineConfig(openai_api_key="test-key")
        assert config.text_illustration_candidates == 3

    def test_text_illustration_quality_threshold_default(self):
        """Default quality threshold for ASCII diagrams is 0.6."""
        config = PipelineConfig(openai_api_key="test-key")
        assert config.text_illustration_quality_threshold == 0.6

    def test_text_illustration_quality_threshold_custom(self):
        """Can set custom quality threshold for ASCII diagrams."""
        config = PipelineConfig(
            openai_api_key="test-key",
            text_illustration_quality_threshold=0.75,
        )
        assert config.text_illustration_quality_threshold == 0.75

    def test_skip_list_sections_default(self):
        """Default is to skip list-heavy sections."""
        config = PipelineConfig(openai_api_key="test-key")
        assert config.skip_list_sections is True

    def test_skip_list_sections_disabled(self):
        """Can disable list section skipping."""
        config = PipelineConfig(
            openai_api_key="test-key",
            skip_list_sections=False,
        )
        assert config.skip_list_sections is False

    def test_validation_threshold_bounds(self):
        """Validation threshold must be between 0.0 and 1.0."""
        # Valid bounds
        config = PipelineConfig(
            openai_api_key="test-key",
            diagram_validation_threshold=0.0,
        )
        assert config.diagram_validation_threshold == 0.0

        config = PipelineConfig(
            openai_api_key="test-key",
            diagram_validation_threshold=1.0,
        )
        assert config.diagram_validation_threshold == 1.0

    def test_candidates_bounds(self):
        """Number of candidates must be between 1 and 5."""
        # Valid bounds
        config = PipelineConfig(
            openai_api_key="test-key",
            mermaid_candidates=1,
        )
        assert config.mermaid_candidates == 1

        config = PipelineConfig(
            openai_api_key="test-key",
            mermaid_candidates=5,
        )
        assert config.mermaid_candidates == 5

    def test_illustration_quality_config_together(self):
        """All quality config options work together."""
        config = PipelineConfig(
            openai_api_key="test-key",
            diagram_validation_threshold=0.75,
            mermaid_candidates=2,
            ascii_candidates=2,
            text_illustration_candidates=2,
            text_illustration_quality_threshold=0.65,
            skip_list_sections=False,
        )

        assert config.diagram_validation_threshold == 0.75
        assert config.mermaid_candidates == 2
        assert config.ascii_candidates == 2
        assert config.text_illustration_candidates == 2
        assert config.text_illustration_quality_threshold == 0.65
        assert config.skip_list_sections is False
