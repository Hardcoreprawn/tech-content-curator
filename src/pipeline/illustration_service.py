"""Illustration generation service for article content.

This module provides a thread-safe service for generating and injecting
illustrations into article content. Optimized for batched API calls and
prepared for Python 3.14 free-threading.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openai import OpenAI
from rich.console import Console

from ..config import PipelineConfig
from ..illustrations.ai_ascii_generator import TextIllustrationQualitySelector
from ..illustrations.ai_mermaid_generator import AIMermaidGenerator
from ..illustrations.capability_advisor import TextIllustrationCapabilityAdvisor
from ..illustrations.detector import detect_concepts
from ..illustrations.diagram_validator import DiagramValidator
from ..illustrations.generator_analyzer import should_add_illustrations
from ..illustrations.mermaid_quality_selector import MermaidQualitySelector
from ..illustrations.placement import PlacementAnalyzer, format_diagram_for_markdown

if TYPE_CHECKING:
    from ..illustrations.ai_ascii_generator import GeneratedAsciiArt
    from ..illustrations.ai_mermaid_generator import GeneratedMermaidDiagram
    from ..illustrations.placement import ContentSection

console = Console()
logger = logging.getLogger(__name__)

# Format selection mapping: routes concepts to best format(s)
CONCEPT_TO_FORMAT: dict[str, list[str]] = {
    "network_topology": ["ascii", "mermaid"],
    "system_architecture": ["mermaid", "ascii"],
    "data_flow": ["mermaid", "ascii"],
    "scientific_process": ["mermaid", "ascii"],
    "comparison": ["ascii"],
    "algorithm": ["mermaid"],
}


@dataclass
class ConceptSectionMatch:
    """A scored pairing of concept and section for illustration."""

    concept: str
    section: ContentSection
    score: float
    selected_format: str | None = None


@dataclass
class IllustrationResult:
    """Result of generating illustrations for an article."""

    content: str
    count: int
    costs: dict[str, float]
    format_distribution: dict[str, int]


class IllustrationService:
    """Service for generating and injecting illustrations into articles.

    This class encapsulates all illustration generation logic and is designed
    to be thread-safe for Python 3.14's free-threading support.
    """

    def __init__(
        self,
        client: OpenAI,
        config: PipelineConfig,
    ) -> None:
        """Initialize the illustration service.

        Args:
            client: OpenAI client for API calls
            config: Pipeline configuration
        """
        self.client = client
        self.config = config
        self.text_advisor = TextIllustrationCapabilityAdvisor()
        self.text_selector = TextIllustrationQualitySelector(
            client,
            n_candidates=getattr(config, "text_illustration_candidates", 3),
            quality_threshold=getattr(
                config, "text_illustration_quality_threshold", 0.6
            ),
        )
        self.diagram_validator = DiagramValidator(
            client,
            threshold=getattr(config, "diagram_validation_threshold", 0.7),
        )
        self.mermaid_selector = MermaidQualitySelector(
            client,
            n_candidates=getattr(config, "mermaid_candidates", 3),
            validation_threshold=getattr(config, "diagram_validation_threshold", 0.7),
        )

    def should_generate_illustrations(self, generator_name: str, content: str) -> bool:
        """Determine if illustrations should be generated for this content.

        Args:
            generator_name: Name of the content generator
            content: Article content

        Returns:
            True if illustrations should be generated
        """
        return should_add_illustrations(generator_name, content)

    def _score_concept_section_pairs_batch(
        self,
        concept_names: list[str],
        suitable_sections: list[tuple[int, ContentSection]],
    ) -> list[ConceptSectionMatch]:
        """Score all concept-section pairs in batched API calls.

        This replaces the nested loop with a single batched request per section,
        dramatically reducing API calls from O(concepts * sections) to O(sections).

        Args:
            concept_names: List of detected concept names
            suitable_sections: List of (index, section) tuples

        Returns:
            List of scored matches above threshold (0.3)
        """
        matches: list[ConceptSectionMatch] = []

        # Process each section with all concepts in a single prompt
        for _idx, section in suitable_sections:
            try:
                # Batch all concepts for this section in one API call
                concepts_str = ", ".join(f'"{c}"' for c in concept_names)
                section_preview = section.content[:200].replace("\n", " ")

                prompt = (
                    f"Rate relevance of each concept to this section on 0-1 scale.\n\n"
                    f'Section: "{section.title}"\n'
                    f"Content preview: {section_preview}...\n\n"
                    f"Concepts: {concepts_str}\n\n"
                    f'Reply with ONLY JSON: {{"concept_name": score, ...}}'
                )

                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=100,
                )

                content = response.choices[0].message.content
                if not content:
                    continue

                # Parse JSON response
                scores_dict = json.loads(content.strip())

                # Create matches for scores above threshold
                for concept, score in scores_dict.items():
                    if isinstance(score, (int, float)) and score > 0.3:
                        matches.append(
                            ConceptSectionMatch(
                                concept=concept,
                                section=section,
                                score=float(score),
                            )
                        )

            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Failed to parse scores for section {section.title}: {e}"
                )
                continue
            except Exception as e:
                logger.error(f"Error scoring section {section.title}: {e}")
                continue

        return matches

    def _select_format_for_match(
        self, match: ConceptSectionMatch
    ) -> tuple[str, GeneratedAsciiArt | GeneratedMermaidDiagram | None]:
        """Select best format and generate diagram for a concept-section match.

        Args:
            match: The concept-section match to generate for

        Returns:
            Tuple of (selected_format, generated_diagram)
        """
        section_words = len(match.section.content.split())
        complexity = min(1.0, section_words / 300.0)
        content_length = len(match.section.content.split())

        # Get text advisor recommendation
        text_recommended, text_reason, text_confidence = (
            self.text_advisor.should_use_text(match.concept, complexity, content_length)
        )

        # Determine fallback formats
        fallback_formats = CONCEPT_TO_FORMAT.get(match.concept, ["mermaid"])

        # Select format based on recommendation
        if text_recommended and text_confidence > 0.75:
            selected_format = "ascii"
            console.print(
                f"  [dim]  → {match.concept}: text recommended "
                f"({text_reason}, confidence: {text_confidence:.2f})[/dim]"
            )
        else:
            selected_format = fallback_formats[0]
            console.print(
                f"  [dim]  → {match.concept}: routing to {selected_format} "
                f"({text_reason}, confidence: {text_confidence:.2f})[/dim]"
            )

        # Generate diagram
        diagram: GeneratedAsciiArt | GeneratedMermaidDiagram | None = None

        if selected_format == "ascii":
            # Try ASCII with quality selector
            diagram = self.text_selector.generate_best(
                section_title=match.section.title,
                section_content=match.section.content,
                concept_type=match.concept,
            )

            if (
                diagram
                and diagram.quality_score >= self.text_selector.quality_threshold
            ):
                console.print(
                    f"  [dim]    ✓ ASCII generated "
                    f"(score: {diagram.quality_score:.2f}, "
                    f"tested {diagram.candidates_tested} candidates)[/dim]"
                )
            elif diagram:
                # Quality too low, fallback
                console.print(
                    f"  [yellow]    ⚠ ASCII score too low ({diagram.quality_score:.2f}), "
                    f"falling back to {fallback_formats[1] if len(fallback_formats) > 1 else 'mermaid'}[/yellow]"
                )
                selected_format = (
                    fallback_formats[1] if len(fallback_formats) > 1 else "mermaid"
                )
                diagram = None
            else:
                console.print(
                    "  [yellow]    ⚠ ASCII generation failed, falling back[/yellow]"
                )
                selected_format = (
                    fallback_formats[1] if len(fallback_formats) > 1 else "mermaid"
                )

        # Fallback to Mermaid if ASCII failed or not selected
        if diagram is None and selected_format != "ascii":
            # Use multi-candidate selection for better quality
            mermaid_result = self.mermaid_selector.generate_best(
                section_title=match.section.title,
                section_content=match.section.content,
                concept_type=match.concept,
            )
            diagram = mermaid_result.diagram
            
            if diagram:
                console.print(
                    f"  [dim]    Generated {mermaid_result.candidates_tested} "
                    f"Mermaid candidates, selected with score {mermaid_result.best_score:.2f}[/dim]"
                )
            elif mermaid_result.all_rejected:
                console.print(
                    f"  [yellow]    ⚠ All {mermaid_result.candidates_tested} Mermaid "
                    f"candidates rejected by validation[/yellow]"
                )

        # Validate diagram if generated (skip Mermaid as it's pre-validated via multi-candidate)
        if diagram and selected_format != "mermaid":
            validation = self.diagram_validator.validate_diagram(
                section_title=match.section.title,
                section_content=match.section.content,
                diagram_content=diagram.content,
                diagram_type=selected_format,
            )

            if not validation.is_valid:
                console.print(
                    f"  [yellow]    ✗ Diagram rejected "
                    f"(score: {validation.combined_score:.2f}): {validation.reason}[/yellow]"
                )
                diagram = None  # Reject diagram
            else:
                console.print(
                    f"  [dim]    ✓ Diagram validated "
                    f"(accuracy: {validation.accuracy_score:.2f}, "
                    f"value: {validation.value_score:.2f})[/dim]"
                )

        return selected_format, diagram

    def _inject_diagram(
        self,
        content: str,
        section_title: str,
        diagram: GeneratedAsciiArt | GeneratedMermaidDiagram,
        format_type: str,
    ) -> str:
        """Inject a diagram into the content after a section header.

        Args:
            content: The article content
            section_title: Title of the section to inject after
            diagram: The generated diagram
            format_type: The format type ("ascii" or "mermaid")

        Returns:
            Modified content with diagram injected
        """
        if format_type == "ascii":
            diagram_markdown = format_diagram_for_markdown(
                diagram.content, section_title
            )
        else:  # Mermaid
            # Clean up mermaid content
            mermaid_content = diagram.content.strip()

            # Remove any existing code fences
            while mermaid_content.startswith("```mermaid"):
                mermaid_content = mermaid_content[10:].lstrip()
            while mermaid_content.startswith("```"):
                mermaid_content = mermaid_content[3:].lstrip()
            while mermaid_content.endswith("```"):
                mermaid_content = mermaid_content[:-3].rstrip()

            diagram_markdown = f"```mermaid\n{mermaid_content}\n```"

        # Create accessible block
        accessible_block = (
            f"<!-- {format_type.upper()}: {diagram.alt_text} -->\n{diagram_markdown}"
        )

        # Inject after section header
        return content.replace(
            f"## {section_title}",
            f"## {section_title}\n\n{accessible_block}",
            1,  # Only replace first occurrence
        )

    def generate_illustrations(
        self, generator_name: str, content: str
    ) -> IllustrationResult:
        """Generate and inject illustrations into article content.

        This is the main entry point for illustration generation, coordinating
        concept detection, section analysis, scoring, and diagram generation.

        Args:
            generator_name: Name of the content generator
            content: Article content to illustrate

        Returns:
            IllustrationResult with modified content and metadata
        """
        if not self.should_generate_illustrations(generator_name, content):
            console.print(
                "  [dim]Skipping illustrations - no benefit for this content[/dim]"
            )
            return IllustrationResult(
                content=content,
                count=0,
                costs={},
                format_distribution={},
            )

        try:
            # Step 1: Detect concepts
            concepts_detected = detect_concepts(content)
            concept_names = (
                [c.name for c in concepts_detected] if concepts_detected else []
            )

            if not concept_names:
                return IllustrationResult(
                    content=content,
                    count=0,
                    costs={},
                    format_distribution={},
                )

            # Step 2: Parse sections
            parser = PlacementAnalyzer()
            sections = parser.parse_structure(content)

            # Filter suitable sections (>75 words, no existing visuals, not list-based)
            suitable_sections = [
                (idx, sec)
                for idx, sec in enumerate(sections)
                if sec.word_count >= 75
                and not sec.has_visuals
                and sec.section_type == "narrative"  # Skip list-heavy sections
            ]

            console.print(
                f"  [dim]Concepts: {concept_names}, "
                f"Sections: {len(suitable_sections)}/{len(sections)}[/dim]"
            )

            if not suitable_sections:
                return IllustrationResult(
                    content=content,
                    count=0,
                    costs={},
                    format_distribution={},
                )

            # Step 3: Batch score all concept-section pairs (MAJOR OPTIMIZATION)
            matches = self._score_concept_section_pairs_batch(
                concept_names, suitable_sections
            )

            # Sort by score and take top 3
            matches.sort(key=lambda x: x.score, reverse=True)
            top_matches = matches[:3]

            console.print(
                f"  [dim]Selected top {len(top_matches)} concept-section pairs[/dim]"
            )

            # Step 4: Generate diagrams for top matches
            injected_content = content
            illustrations_added = 0
            illustration_costs: dict[str, float] = {}
            format_distribution: dict[str, int] = {}
            rejected_count = 0

            for match in top_matches:
                try:
                    selected_format, diagram = self._select_format_for_match(match)

                    if diagram:
                        injected_content = self._inject_diagram(
                            injected_content,
                            match.section.title,
                            diagram,
                            selected_format,
                        )

                        illustrations_added += 1
                        # Track total cost including validation
                        total_cost = diagram.total_cost
                        # Validation cost is already part of diagram generation,
                        # but we could add separate tracking if needed
                        illustration_costs[f"diagram_{illustrations_added}"] = (
                            total_cost
                        )
                        format_distribution[selected_format] = (
                            format_distribution.get(selected_format, 0) + 1
                        )
                    else:
                        rejected_count += 1

                except Exception as e:
                    logger.warning(
                        f"Diagram generation failed for {match.concept}: {e}"
                    )
                    console.print(
                        f"  [yellow]⚠ Diagram skipped: {str(e)[:50]}[/yellow]"
                    )
                    rejected_count += 1
                    continue

            # Print summary
            if illustrations_added > 0:
                console.print(
                    f"  [cyan]✓ {illustrations_added} diagram(s) generated[/cyan]"
                )
                if format_distribution:
                    fmt_str = ", ".join(
                        f"{k}:{v}" for k, v in sorted(format_distribution.items())
                    )
                    console.print(f"  [dim]  Formats: {fmt_str}[/dim]")
                if illustration_costs:
                    total = sum(illustration_costs.values())
                    console.print(f"  [dim]  Cost: ${total:.6f}[/dim]")

            return IllustrationResult(
                content=injected_content,
                count=illustrations_added,
                costs=illustration_costs,
                format_distribution=format_distribution,
            )

        except Exception as e:
            logger.error(f"Illustration generation error: {e}", exc_info=True)
            console.print(f"  [yellow]⚠ Illustration error: {e}[/yellow]")
            return IllustrationResult(
                content=content,
                count=0,
                costs={},
                format_distribution={},
            )
