"""Tests for illustration system components.

Tests for concept detection, generator awareness, SVG templates, and Mermaid generation.
"""

from datetime import UTC, datetime

import pytest

from src.illustrations.detector import ConceptDetector, Concept, detect_concepts
from src.illustrations.generator_analyzer import (
    generator_includes_visuals,
    has_existing_visuals,
    should_add_illustrations,
    get_generator_config,
)
from src.illustrations.svg_library import SVGTemplateLibrary, SVGTemplate
from src.illustrations.mermaid_generator import MermaidDiagramGenerator, MermaidDiagram
from src.models import CollectedItem, EnrichedItem, GeneratedArticle


# ============================================================================
# Concept Detection Tests
# ============================================================================


class TestConceptDetector:
    """Tests for concept detection engine."""

    def test_detect_network_topology_concepts(self):
        """Detects network topology concepts from keywords."""
        content = """
        Understanding NAT (Network Address Translation) is crucial for modern networks.
        The router performs IP address translation for packets flowing through it.
        Each packet must be routed through the gateway appropriately.
        """
        detector = ConceptDetector()
        concepts = detector.detect(content)

        assert len(concepts) > 0
        assert any(c.name == "network_topology" for c in concepts)

        network_concept = next(c for c in concepts if c.name == "network_topology")
        assert network_concept.confidence >= 0.7
        assert "svg" in network_concept.visual_types
        assert "mermaid" in network_concept.visual_types

    def test_detect_data_flow_concepts(self):
        """Detects data flow concepts from keywords."""
        content = """
        The data pipeline consists of several stages:
        1. Extract raw data from source
        2. Transform and clean the data
        3. Load into the warehouse
        This workflow ensures data quality throughout processing.
        """
        detector = ConceptDetector()
        concepts = detector.detect(content)

        assert any(c.name == "data_flow" for c in concepts)

    def test_detect_system_architecture_concepts(self):
        """Detects system architecture from keywords."""
        content = """
        The microservices architecture includes multiple components:
        - API gateway for request routing
        - Service layers for business logic
        - Database layers for persistence
        These modules work together in a layered design.
        """
        detector = ConceptDetector()
        concepts = detector.detect(content)

        assert any(c.name == "system_architecture" for c in concepts)

    def test_detect_multiple_concepts(self):
        """Detects multiple concepts in complex content."""
        content = """
        In this architecture, the network topology includes routers and gateways.
        Data flows through a pipeline with extraction, transformation, and loading stages.
        The system uses microservices with multiple components.
        """
        detector = ConceptDetector()
        concepts = detector.detect(content)

        assert len(concepts) >= 2
        concept_names = {c.name for c in concepts}
        assert "network_topology" in concept_names or "system_architecture" in concept_names
        assert "data_flow" in concept_names

    def test_concepts_sorted_by_confidence(self):
        """Concepts are sorted by confidence (highest first)."""
        content = """
        Network topology with routers and gateways.
        Data flows through pipeline.
        """
        detector = ConceptDetector()
        concepts = detector.detect(content)

        # Should be sorted in descending order of confidence
        confidences = [c.confidence for c in concepts]
        assert confidences == sorted(confidences, reverse=True)

    def test_filter_by_confidence(self):
        """Filters concepts by confidence threshold."""
        content = "NAT router IP packet gateway network topology"
        detector = ConceptDetector()
        all_concepts = detector.detect(content)

        high_confidence = detector.filter_by_confidence(all_concepts, 0.8)
        low_confidence = detector.filter_by_confidence(all_concepts, 0.5)

        # High confidence should be a subset of low confidence
        assert len(high_confidence) <= len(low_confidence)

    def test_limit_by_type_svg(self):
        """Limits concepts to those supporting SVG visualization."""
        content = "Network topology system architecture"
        detector = ConceptDetector()
        concepts = detector.detect(content)

        svg_concepts = detector.limit_by_type(concepts, "svg")
        for concept in svg_concepts:
            assert "svg" in concept.visual_types

    def test_empty_content_returns_empty_concepts(self):
        """Empty or irrelevant content returns no concepts."""
        detector = ConceptDetector()
        concepts = detector.detect("The quick brown fox jumps over the lazy dog")

        assert len(concepts) == 0

    def test_detect_concepts_convenience_function(self):
        """Convenience function works correctly."""
        content = "NAT translation and packet routing through network topology"
        concepts = detect_concepts(content, min_confidence=0.7)

        assert len(concepts) > 0
        assert all(c.confidence >= 0.7 for c in concepts)

    def test_concept_dataclass(self):
        """Concept dataclass is properly structured."""
        concept = Concept(
            name="test_concept",
            keywords=["test", "sample"],
            confidence=0.85,
            visual_types=["svg", "mermaid"],
            description="Test concept description",
        )

        assert concept.name == "test_concept"
        assert concept.confidence == 0.85
        assert len(concept.keywords) == 2


# ============================================================================
# Generator Awareness Tests
# ============================================================================


class TestGeneratorAwareness:
    """Tests for generator-aware illustration logic."""

    def test_has_existing_visuals_detects_code_blocks(self):
        """Detects code blocks as existing visuals."""
        content = """
        Here's an example:
        ```python
        def hello():
            print("world")
        ```
        """
        assert has_existing_visuals(content) is True

    def test_has_existing_visuals_detects_images(self):
        """Detects markdown images as existing visuals."""
        content = "Check out this diagram: ![architecture](architecture.png)"
        assert has_existing_visuals(content) is True

    def test_has_existing_visuals_detects_svg(self):
        """Detects embedded SVG as existing visuals."""
        content = "Here's an SVG: <svg>...</svg>"
        assert has_existing_visuals(content) is True

    def test_has_existing_visuals_detects_ascii_art(self):
        """Detects ASCII art patterns as existing visuals."""
        content = """
        Here's a diagram:
            +---+
            | A |
            +---+
        """
        assert has_existing_visuals(content) is True

    def test_has_existing_visuals_text_only(self):
        """Returns False for text-only content."""
        content = "This is just plain text content without any visual elements."
        assert has_existing_visuals(content) is False

    def test_generator_includes_visuals_integrative_list(self):
        """IntegrativeListGenerator is marked as providing visuals."""
        assert generator_includes_visuals("Integrative List Generator") is True

    def test_generator_includes_visuals_general_article(self):
        """GeneralArticleGenerator is marked as not providing visuals."""
        assert generator_includes_visuals("General Article Generator") is False

    def test_generator_includes_visuals_scientific_article(self):
        """ScientificArticleGenerator is marked as not providing visuals."""
        assert generator_includes_visuals("Scientific Article Generator") is False

    def test_generator_includes_visuals_unknown_generator(self):
        """Unknown generators return False (conservative approach)."""
        assert generator_includes_visuals("Unknown Generator") is False

    def test_should_add_illustrations_skip_if_generator_provides(self):
        """Skip illustrations if generator already provides them."""
        content = "Some article content"
        result = should_add_illustrations("Integrative List Generator", content)
        assert result is False

    def test_should_add_illustrations_skip_if_content_has_visuals(self):
        """Skip illustrations if content already has visual elements."""
        content = "Article with code:\n```python\nprint('hello')\n```"
        result = should_add_illustrations("General Article Generator", content)
        assert result is False

    def test_should_add_illustrations_add_for_text_only(self):
        """Add illustrations for text-only content from non-visual generators."""
        content = "Plain text article about network architecture and routing"
        result = should_add_illustrations("General Article Generator", content)
        assert result is True

    def test_get_generator_config_returns_config(self):
        """Returns config for known generators."""
        config = get_generator_config("Integrative List Generator")
        assert config is not None
        assert "skip_illustration" in config
        assert config["skip_illustration"] is True

    def test_get_generator_config_returns_none_for_unknown(self):
        """Returns None for unknown generators."""
        config = get_generator_config("Unknown Generator Type")
        assert config is None


# ============================================================================
# SVG Template Library Tests
# ============================================================================


class TestSVGTemplateLibrary:
    """Tests for SVG template library."""

    def test_library_loads_templates(self):
        """Library initializes with templates."""
        library = SVGTemplateLibrary()
        templates = library.list_templates()

        assert len(templates) >= 5
        template_names = {t.name for t in templates}
        assert "nat_translation" in template_names
        assert "packet_flow" in template_names

    def test_get_template_by_name(self):
        """Can retrieve template by name."""
        library = SVGTemplateLibrary()
        template = library.get("nat_translation")

        assert template is not None
        assert template.name == "nat_translation"
        assert "NAT" in template.title
        assert "<svg" in template.svg_content

    def test_get_nonexistent_template_returns_none(self):
        """Returns None for non-existent templates."""
        library = SVGTemplateLibrary()
        template = library.get("nonexistent_template")

        assert template is None

    def test_find_templates_by_concept(self):
        """Can find templates by concept."""
        library = SVGTemplateLibrary()
        templates = library.find_by_concept("network_topology")

        assert len(templates) > 0
        assert all("network_topology" in t.concepts for t in templates)

    def test_find_templates_by_tag(self):
        """Can find templates by tag."""
        library = SVGTemplateLibrary()
        templates = library.find_by_tag("networking")

        assert len(templates) > 0
        assert all("networking" in t.tags for t in templates)

    def test_template_has_alt_text(self):
        """All templates have accessibility alt-text."""
        library = SVGTemplateLibrary()
        templates = library.list_templates()

        for template in templates:
            assert template.alt_text
            assert len(template.alt_text) > 10

    def test_template_has_valid_svg(self):
        """All templates contain valid SVG markup."""
        library = SVGTemplateLibrary()
        templates = library.list_templates()

        for template in templates:
            assert "<svg" in template.svg_content
            assert "</svg>" in template.svg_content

    def test_nat_translation_svg_complete(self):
        """NAT translation template is complete and functional."""
        library = SVGTemplateLibrary()
        template = library.get("nat_translation")

        assert template is not None
        assert "192.168" in template.svg_content  # Private IP example
        assert "203.0.113" in template.svg_content  # Public IP example
        assert "Translation" in template.svg_content


# ============================================================================
# Mermaid Generator Tests
# ============================================================================


class TestMermaidDiagramGenerator:
    """Tests for Mermaid diagram generation."""

    def test_generate_simple_flow(self):
        """Can generate simple flow diagram."""
        generator = MermaidDiagramGenerator()
        diagram = generator.generate("simple_flow")

        assert diagram is not None
        assert diagram.diagram_type == "flowchart"
        assert "Input" in diagram.content
        assert "Output" in diagram.content

    def test_generate_decision_tree(self):
        """Can generate decision tree diagram."""
        generator = MermaidDiagramGenerator()
        diagram = generator.generate("decision_tree")

        assert diagram.diagram_type == "flowchart"
        assert "Decision" in diagram.content
        assert "Action" in diagram.content

    def test_generate_system_components(self):
        """Can generate system components diagram."""
        generator = MermaidDiagramGenerator()
        diagram = generator.generate("system_components")

        assert diagram.diagram_type == "graph"
        assert "Client" in diagram.content
        assert "Database" in diagram.content

    def test_generate_data_pipeline(self):
        """Can generate data pipeline diagram."""
        generator = MermaidDiagramGenerator()
        diagram = generator.generate("data_pipeline")

        assert diagram.content.startswith("flowchart")
        assert "Extract" in diagram.content
        assert "Transform" in diagram.content
        assert "Load" in diagram.content

    def test_generate_for_concept_network(self):
        """Generates appropriate diagram for network concept."""
        generator = MermaidDiagramGenerator()
        diagram = generator.generate_for_concept("network_topology")

        assert diagram is not None
        assert "Source" in diagram.content or "Router" in diagram.content

    def test_generate_for_concept_data_flow(self):
        """Generates appropriate diagram for data flow concept."""
        generator = MermaidDiagramGenerator()
        diagram = generator.generate_for_concept("data_flow")

        assert diagram is not None
        assert diagram.diagram_type == "flowchart"

    def test_generate_for_unknown_concept_returns_none(self):
        """Returns None for unknown concepts."""
        generator = MermaidDiagramGenerator()
        diagram = generator.generate_for_concept("unknown_concept_xyz")

        assert diagram is None

    def test_unknown_pattern_raises_error(self):
        """Raises ValueError for unknown patterns."""
        generator = MermaidDiagramGenerator()

        with pytest.raises(ValueError):
            generator.generate("nonexistent_pattern")

    def test_format_for_markdown(self):
        """Formats diagram for markdown inclusion."""
        generator = MermaidDiagramGenerator()
        diagram = generator.generate("simple_flow", custom_title="Test Flow")
        markdown = generator.format_for_markdown(diagram)

        assert "```mermaid" in markdown
        assert "```" in markdown
        assert "Test Flow" in markdown
        assert diagram.content in markdown

    def test_create_custom_flow(self):
        """Can create custom flowchart."""
        generator = MermaidDiagramGenerator()
        nodes = ["Start", "Process", "Check", "End"]
        edges = [
            ("Start", "Process"),
            ("Process", "Check"),
            ("Check", "End"),
        ]
        diagram = generator.create_custom_flow(nodes, edges, title="Custom Process")

        assert "custom_flow" in diagram.name
        assert "Process" in diagram.content
        assert "Start" in diagram.content

    def test_create_custom_flow_no_nodes_raises_error(self):
        """Raises error if no nodes provided."""
        generator = MermaidDiagramGenerator()

        with pytest.raises(ValueError):
            generator.create_custom_flow([], [])

    def test_list_patterns(self):
        """Can list all available patterns."""
        generator = MermaidDiagramGenerator()
        patterns = generator.list_patterns()

        assert len(patterns) > 0
        assert "simple_flow" in patterns
        assert "decision_tree" in patterns

    def test_get_pattern_info(self):
        """Can retrieve pattern information."""
        generator = MermaidDiagramGenerator()
        info = generator.get_pattern_info("simple_flow")

        assert info is not None
        assert "template" in info
        assert "type" in info
        assert "description" in info

    def test_mermaid_diagram_dataclass(self):
        """MermaidDiagram dataclass works correctly."""
        diagram = MermaidDiagram(
            name="test",
            diagram_type="flowchart",
            content="flowchart TD\n    A --> B",
            alt_text="Test diagram",
            title="Test",
        )

        assert diagram.name == "test"
        assert diagram.diagram_type == "flowchart"


# ============================================================================
# Integration Tests
# ============================================================================


class TestIllustrationIntegration:
    """Integration tests for illustration system components."""

    def test_detect_and_find_svg_templates(self):
        """Can detect concepts and find matching SVG templates."""
        content = "Network topology with routers and gateways forwarding packets"
        detector = ConceptDetector()
        library = SVGTemplateLibrary()

        concepts = detector.detect(content)
        assert len(concepts) > 0

        # Find templates for first concept
        concept = concepts[0]
        templates = library.find_by_concept(concept.name)
        assert len(templates) > 0

    def test_detect_and_generate_mermaid(self):
        """Can detect concepts and generate Mermaid diagrams."""
        content = "Data flows through extraction, transformation, and loading stages"
        detector = ConceptDetector()
        generator = MermaidDiagramGenerator()

        concepts = detector.detect(content)
        assert len(concepts) > 0

        # Generate diagram for first concept
        concept = concepts[0]
        diagram = generator.generate_for_concept(concept.name)
        assert diagram is not None

    def test_full_workflow_text_only_article(self):
        """Full workflow for text-only article."""
        content = """
        Understanding NAT is important for network architecture.
        The router translates IP addresses for packets flowing through.
        """

        # Check if illustrations should be added
        can_add = should_add_illustrations("General Article Generator", content)
        assert can_add is True

        # Detect concepts
        concepts = detect_concepts(content)
        assert len(concepts) > 0

        # Find SVG template
        library = SVGTemplateLibrary()
        templates = library.find_by_concept("network_topology")
        assert len(templates) > 0

    def test_full_workflow_skip_integrative_list(self):
        """Full workflow skips illustrations for IntegrativeListGenerator."""
        content = """
        - Item 1
        - Item 2
        - Item 3
        ```
        code example
        ```
        """

        # Should skip for IntegrativeListGenerator
        can_add = should_add_illustrations("Integrative List Generator", content)
        assert can_add is False
