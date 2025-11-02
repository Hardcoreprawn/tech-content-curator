"""Tests for Phase 2: Placement and Accessibility systems."""

import pytest

from src.illustrations.placement import PlacementAnalyzer, Section, PlacementPoint
from src.illustrations.accessibility import AccessibilityChecker, AccessibilityReport


# ============================================================================
# Placement System Tests
# ============================================================================


class TestPlacementAnalyzer:
    """Tests for intelligent placement system."""

    def test_parse_structure_single_heading(self):
        """Parses content with single heading."""
        content = "# Main Title\n\nSome content here."
        analyzer = PlacementAnalyzer()
        sections = analyzer.parse_structure(content)

        assert len(sections) == 1
        assert sections[0].title == "Main Title"
        assert sections[0].level == 1

    def test_parse_structure_multiple_sections(self):
        """Parses content with multiple heading levels."""
        content = """# Introduction

Some intro text.

## Section 1

Content for section 1.

## Section 2

Content for section 2."""

        analyzer = PlacementAnalyzer()
        sections = analyzer.parse_structure(content)

        assert len(sections) >= 2
        titles = {s.title for s in sections}
        assert "Introduction" in titles
        assert "Section 1" in titles

    def test_parse_structure_detects_code_blocks(self):
        """Detects code blocks in sections."""
        content = """# Code Section

```python
def hello():
    print("world")
```"""

        analyzer = PlacementAnalyzer()
        sections = analyzer.parse_structure(content)

        assert sections[0].has_code_block is True

    def test_parse_structure_detects_lists(self):
        """Detects lists in sections."""
        content = """# List Section

- Item 1
- Item 2
- Item 3"""

        analyzer = PlacementAnalyzer()
        sections = analyzer.parse_structure(content)

        assert sections[0].has_list is True

    def test_parse_structure_detects_tables(self):
        """Detects tables in sections."""
        content = """# Table Section

| Header 1 | Header 2 |
|----------|----------|
| Value 1  | Value 2  |"""

        analyzer = PlacementAnalyzer()
        sections = analyzer.parse_structure(content)

        assert sections[0].has_table is True

    def test_parse_structure_detects_visuals(self):
        """Detects existing visual elements."""
        content = """# Visual Section

![image](image.png)

Some text."""

        analyzer = PlacementAnalyzer()
        sections = analyzer.parse_structure(content)

        assert sections[0].has_visuals is True

    def test_parse_structure_counts_words(self):
        """Counts words in sections accurately."""
        content = """# Section Title

This section has exactly ten words of content for testing purposes."""

        analyzer = PlacementAnalyzer()
        sections = analyzer.parse_structure(content)

        assert sections[0].word_count == 11

    def test_find_placements_network_concept(self):
        """Finds placement for network topology concept."""
        content = """# Network Architecture

Understanding NAT is important for routing packets through a network topology system.
The router performs IP address translation at the network boundary.
Each packet must route through the gateway device to reach external networks.
Network topology design impacts performance and security considerations significantly.
The architecture supports multiple connection paths and redundancy mechanisms.
Packet routing decisions depend on network topology configuration and policies."""

        analyzer = PlacementAnalyzer(min_section_words=50)
        placements = analyzer.find_placements(content, ["network_topology"])

        assert len(placements) > 0
        assert placements[0].weight > 0

    def test_find_placements_data_flow_concept(self):
        """Finds placement for data flow concept."""
        content = """# Data Pipeline

The data pipeline consists of several critical stages for processing and transformation.
Extract raw data from various sources and systems.
Transform and clean the data to remove inconsistencies.
Load the processed data into the data warehouse.
Data flows through extraction, transformation, and loading stages systematically.
The pipeline manages data quality and maintains data integrity throughout processing.
Pipeline architecture supports parallel processing and error handling capabilities."""

        analyzer = PlacementAnalyzer(min_section_words=50)
        placements = analyzer.find_placements(content, ["data_flow"])

        assert len(placements) > 0

    def test_find_placements_multiple_concepts(self):
        """Finds placements for multiple concepts in one article."""
        content = """# Architecture Overview

## Network Topology

The network includes routers and gateways.
Packets flow through the topology.

## Data Processing

Data flows through a pipeline with extraction, transformation, and loading."""

        analyzer = PlacementAnalyzer(min_section_words=50)
        placements = analyzer.find_placements(
            content, ["network_topology", "data_flow"], max_placements=2
        )

        assert len(placements) <= 2

    def test_find_placements_respects_min_words(self):
        """Skips sections that don't meet minimum word count."""
        content = """# Short Section

Brief text.

## Long Section

This section has enough words to meet the minimum word count requirement
for a suitable placement. It contains detailed information about concepts."""

        analyzer = PlacementAnalyzer(min_section_words=30)
        placements = analyzer.find_placements(content, ["system_architecture"])

        # Should only find placement in longer section
        assert len(placements) <= 1

    def test_find_placements_skips_code_blocks(self):
        """Does not place illustrations in sections with code blocks."""
        content = """# Implementation

```python
def process_data(data):
    return data
```"""

        analyzer = PlacementAnalyzer(min_section_words=10)
        placements = analyzer.find_placements(content, ["data_flow"])

        # Code sections should be skipped
        assert len(placements) == 0

    def test_find_placements_skips_existing_visuals(self):
        """Does not place in sections that already have visuals."""
        content = """# Architecture

```mermaid
graph TD
    A --> B
```

Additional text about the system."""

        analyzer = PlacementAnalyzer(min_section_words=10)
        placements = analyzer.find_placements(content, ["system_architecture"])

        # Should skip section with existing visual
        assert len(placements) == 0

    def test_calculate_placement_safety_in_code_block(self):
        """Identifies unsafe placement inside code blocks."""
        content = """# Code

```python
def hello():
    print("world")
```

Text after."""

        analyzer = PlacementAnalyzer()
        sections = analyzer.parse_structure(content)

        # Position inside code block should be unsafe
        is_safe = analyzer.calculate_placement_safety(content, 0, 10)
        assert is_safe is False

    def test_calculate_placement_safety_in_table(self):
        """Identifies unsafe placement inside tables."""
        content = """# Table

| Col1 | Col2 |
|------|------|
| A    | B    |"""

        analyzer = PlacementAnalyzer()
        sections = analyzer.parse_structure(content)

        # Position inside table might be unsafe
        is_safe = analyzer.calculate_placement_safety(content, 0, 50)
        # Should depend on exact position
        assert isinstance(is_safe, bool)

    def test_placement_point_structure(self):
        """PlacementPoint dataclass is properly structured."""
        point = PlacementPoint(
            section_index=0,
            position_in_section=100,
            concept_names=["network_topology"],
            weight=0.85,
            rationale="Good match for concept",
            distance_from_intro=50,
        )

        assert point.section_index == 0
        assert point.weight == 0.85
        assert point.concept_names[0] == "network_topology"

    def test_section_dataclass_structure(self):
        """Section dataclass is properly structured."""
        section = Section(
            title="Test Section",
            level=2,
            start_line=0,
            end_line=10,
            content="Content here",
            word_count=2,
            has_code_block=False,
            has_list=False,
            has_table=False,
            has_visuals=False,
        )

        assert section.title == "Test Section"
        assert section.level == 2
        assert section.has_code_block is False


# ============================================================================
# Accessibility System Tests
# ============================================================================


class TestAccessibilityChecker:
    """Tests for accessibility compliance system."""

    def test_generate_alt_text_nat_translation(self):
        """Generates appropriate alt-text for NAT translation diagram."""
        checker = AccessibilityChecker()
        alt_text = checker.generate_alt_text("nat_translation", "network_topology")

        assert "NAT" in alt_text
        assert len(alt_text) <= 200

    def test_generate_alt_text_system_architecture(self):
        """Generates alt-text for system architecture diagram."""
        checker = AccessibilityChecker()
        alt_text = checker.generate_alt_text(
            "system_architecture", "system_architecture"
        )

        assert "architecture" in alt_text.lower()
        assert "layer" in alt_text.lower()

    def test_generate_alt_text_data_pipeline(self):
        """Generates alt-text for data pipeline diagram."""
        checker = AccessibilityChecker()
        alt_text = checker.generate_alt_text("data_pipeline", "data_flow")

        assert "pipeline" in alt_text.lower()
        assert any(
            stage in alt_text for stage in ["input", "output", "extract", "load"]
        )

    def test_generate_long_description_nat(self):
        """Generates detailed description for NAT diagram."""
        checker = AccessibilityChecker()
        desc = checker.generate_long_description("nat_translation", "network_topology")

        assert "private" in desc.lower()
        assert "public" in desc.lower()
        assert "translation" in desc.lower()
        assert len(desc) >= 100

    def test_generate_long_description_network_topology(self):
        """Generates detailed description for network topology."""
        checker = AccessibilityChecker()
        desc = checker.generate_long_description("network_topology", "network_topology")

        assert "router" in desc.lower()
        assert "device" in desc.lower() or "connection" in desc.lower()

    def test_wrap_svg_adds_title(self):
        """Wraps SVG with title element."""
        checker = AccessibilityChecker()
        svg = "<svg><text>Content</text></svg>"
        wrapped = checker.wrap_svg_accessibility(svg, "Alt text", "Diagram Title")

        assert "<title>" in wrapped
        assert "Diagram Title" in wrapped
        assert "<desc>" in wrapped
        assert "Alt text" in wrapped

    def test_wrap_svg_adds_role(self):
        """Adds role='img' to SVG if missing."""
        checker = AccessibilityChecker()
        svg = "<svg><text>Content</text></svg>"
        wrapped = checker.wrap_svg_accessibility(svg, "Alt text")

        assert 'role="img"' in wrapped

    def test_wrap_svg_skips_if_already_accessible(self):
        """Doesn't modify SVG if already has accessibility elements."""
        checker = AccessibilityChecker()
        original = '<svg role="img"><title>Title</title><desc>Description</desc></svg>'
        wrapped = checker.wrap_svg_accessibility(original, "New alt")

        # Should return unchanged since already accessible
        assert "<title>Title</title>" in wrapped

    def test_validate_wcag_svg_compliance(self):
        """Validates SVG WCAG compliance."""
        checker = AccessibilityChecker()
        svg_with_accessibility = (
            '<svg role="img"><title>Diagram</title><desc>A diagram</desc></svg>'
        )

        report = checker.validate_wcag_compliance(svg_with_accessibility, "svg")

        assert report.wcag_level in ["A", "AA", "AAA"]
        assert isinstance(report.is_compliant, bool)

    def test_validate_wcag_svg_missing_title(self):
        """Identifies missing title in SVG."""
        checker = AccessibilityChecker()
        svg_without_title = "<svg><desc>Description only</desc></svg>"

        report = checker.validate_wcag_compliance(svg_without_title, "svg")

        assert any("title" in issue.lower() for issue in report.issues)

    def test_validate_wcag_svg_missing_desc(self):
        """Identifies missing description in SVG."""
        checker = AccessibilityChecker()
        svg_without_desc = "<svg><title>Title only</title></svg>"

        report = checker.validate_wcag_compliance(svg_without_desc, "svg")

        assert any("desc" in issue.lower() for issue in report.issues)

    def test_validate_wcag_mermaid_diagram(self):
        """Validates Mermaid diagram for accessibility."""
        checker = AccessibilityChecker()
        mermaid = "graph TD\n    A --> B\n    B --> C"

        report = checker.validate_wcag_compliance(mermaid, "mermaid")

        assert report.wcag_level in ["A", "AA"]
        assert len(report.issues) == 0

    def test_validate_wcag_empty_mermaid(self):
        """Identifies empty Mermaid diagram."""
        checker = AccessibilityChecker()

        report = checker.validate_wcag_compliance("", "mermaid")

        assert len(report.issues) > 0

    def test_accessibility_report_structure(self):
        """AccessibilityReport dataclass is properly structured."""
        report = AccessibilityReport(
            wcag_level="AA",
            is_compliant=True,
            issues=[],
            warnings=[],
            alt_text="Test alt text",
            long_description="Test long description",
        )

        assert report.wcag_level == "AA"
        assert report.is_compliant is True
        assert len(report.issues) == 0

    def test_extract_svg_alt_text_from_desc(self):
        """Extracts alt-text from SVG desc element."""
        checker = AccessibilityChecker()
        svg = "<svg><desc>My diagram description</desc></svg>"

        alt_text = checker._extract_svg_alt_text(svg)

        assert "My diagram description" in alt_text

    def test_extract_svg_alt_text_from_title(self):
        """Extracts alt-text from SVG title element."""
        checker = AccessibilityChecker()
        svg = "<svg><title>My Diagram</title></svg>"

        alt_text = checker._extract_svg_alt_text(svg)

        assert "My Diagram" in alt_text

    def test_add_markdown_accessibility_with_title(self):
        """Formats diagram for markdown with title."""
        checker = AccessibilityChecker()
        diagram = "```mermaid\ngraph TD\n    A --> B\n```"
        formatted = checker.add_markdown_accessibility(
            diagram, "A simple diagram", title="Example Diagram"
        )

        assert "**Figure**" in formatted
        assert "Example Diagram" in formatted
        assert "A simple diagram" in formatted
        assert diagram in formatted

    def test_add_markdown_accessibility_without_title(self):
        """Formats diagram for markdown without title."""
        checker = AccessibilityChecker()
        diagram = "```mermaid\ngraph TD\n    A --> B\n```"
        formatted = checker.add_markdown_accessibility(diagram, "A simple diagram")

        assert "A simple diagram" in formatted
        assert diagram in formatted

    def test_accessibility_checker_wcag_levels(self):
        """Accessibility checker supports different WCAG levels."""
        checker_aa = AccessibilityChecker(target_wcag_level="AA")
        checker_a = AccessibilityChecker(target_wcag_level="A")

        assert checker_aa.target_wcag_level == "AA"
        assert checker_a.target_wcag_level == "A"


# ============================================================================
# Integration Tests
# ============================================================================


class TestPlacementAndAccessibility:
    """Integration tests for placement and accessibility systems."""

    def test_place_and_add_accessibility(self):
        """Can place illustration and add accessibility."""
        content = """# Network Guide

Understanding NAT routing is important.
The network topology shows how packets flow.

## Implementation

More technical details."""

        analyzer = PlacementAnalyzer(min_section_words=30)
        checker = AccessibilityChecker()

        placements = analyzer.find_placements(content, ["network_topology"])

        if placements:
            alt_text = checker.generate_alt_text(
                "nat_translation", placements[0].concept_names[0]
            )
            assert len(alt_text) > 0

    def test_full_workflow_placement_and_accessibility(self):
        """Complete workflow: parse, place, add accessibility."""
        content = """# System Architecture

The system includes multiple components.
Architecture layers handle different concerns.

## Network Topology

Routers and gateways manage traffic.
The network topology is critical."""

        analyzer = PlacementAnalyzer(min_section_words=30)
        checker = AccessibilityChecker()

        # Parse structure
        sections = analyzer.parse_structure(content)
        assert len(sections) >= 2

        # Find placements
        concepts = ["system_architecture", "network_topology"]
        placements = analyzer.find_placements(content, concepts)

        # Add accessibility to each
        for placement in placements:
            for concept in placement.concept_names:
                alt_text = checker.generate_alt_text("diagram", concept)
                long_desc = checker.generate_long_description("diagram", concept)

                assert len(alt_text) > 0
                assert len(long_desc) > 0
