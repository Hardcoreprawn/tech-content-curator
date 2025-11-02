"""Intelligent illustration system for enhancing article readability.

This module provides AI-powered diagram and visual generation for articles.
Uses context-aware prompts to generate Mermaid diagrams, ASCII art, and SVG
graphics that match the specific article content.

Phase 1 Components:
- Concept detection for identifying illustration opportunities
- Generator awareness to prevent duplicate visuals
- SVG template library with hand-crafted diagrams (legacy)
- Mermaid diagram generation for programmatic variety

Phase 2 Components:
- Intelligent placement system for optimal positioning
- Accessibility module for WCAG compliance and alt-text

Phase 3+ Components:
- AI-powered Mermaid generation using OpenAI API for flowcharts
- AI-powered ASCII generation for tables and text diagrams
- AI-powered SVG generation for infographics and complex visuals
"""

from .accessibility import AccessibilityChecker, AccessibilityReport
from .ai_ascii_generator import AIAsciiGenerator, GeneratedAsciiArt
from .ai_mermaid_generator import AIMermaidGenerator, GeneratedMermaidDiagram
from .ai_svg_generator import AISvgGenerator, GeneratedSvg
from .detector import Concept, ConceptDetector
from .generator_analyzer import (
    generator_includes_visuals,
    should_add_illustrations,
)
from .mermaid_generator import MermaidDiagram, MermaidDiagramGenerator
from .placement import PlacementAnalyzer, PlacementPoint, Section
from .svg_library import SVGTemplate, SVGTemplateLibrary

__all__ = [
    # Phase 1
    "ConceptDetector",
    "Concept",
    "generator_includes_visuals",
    "should_add_illustrations",
    "MermaidDiagramGenerator",
    "MermaidDiagram",
    "SVGTemplateLibrary",
    "SVGTemplate",
    # Phase 2
    "PlacementAnalyzer",
    "PlacementPoint",
    "Section",
    "AccessibilityChecker",
    "AccessibilityReport",
    # Phase 3+: AI Generators
    "AIMermaidGenerator",
    "GeneratedMermaidDiagram",
    "AIAsciiGenerator",
    "GeneratedAsciiArt",
    "AISvgGenerator",
    "GeneratedSvg",
]
