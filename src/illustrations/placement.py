"""Intelligent placement system for optimal illustration positioning.

Analyzes article markdown structure to find optimal insertion points for illustrations
that enhance comprehension without disrupting reading flow. Uses section analysis,
concept matching, and density controls to maintain article quality.
"""

import re
from dataclasses import dataclass


def format_diagram_for_markdown(diagram: str, section_title: str = "") -> str:
    """Wrap ASCII diagram with centering and proper spacing for markdown.

    Args:
        diagram: The ASCII diagram content
        section_title: Optional section title for figure caption

    Returns:
        Formatted diagram block with centering and spacing
    """
    formatted = f'\n<div align="center">\n\n```\n{diagram}\n```\n\n</div>\n'
    if section_title:
        formatted += f"\n*Figure: {section_title}*\n"
    return formatted


@dataclass
class Section:
    """A logical section of an article (usually defined by headings)."""

    title: str
    """Section heading"""

    level: int
    """Heading level (1 for #, 2 for ##, etc.)"""

    start_line: int
    """Starting line number (0-indexed)"""

    end_line: int
    """Ending line number (0-indexed)"""

    content: str
    """Full section content including heading"""

    word_count: int
    """Number of words in section"""

    has_code_block: bool
    """Whether section contains code blocks"""

    has_list: bool
    """Whether section contains lists"""

    has_table: bool
    """Whether section contains tables"""

    has_visuals: bool
    """Whether section already has images/diagrams"""

    section_type: str = "narrative"
    """Section type: 'list' if >50% lines are list items, else 'narrative'"""


@dataclass
class PlacementPoint:
    """A potential location for placing an illustration."""

    section_index: int
    """Index of containing section"""

    position_in_section: int
    """Character offset within section"""

    concept_names: list[str]
    """Concepts relevant to this placement"""

    weight: float
    """Placement quality score (0.0 to 1.0)"""

    rationale: str
    """Why this location is suitable"""

    distance_from_intro: int
    """Words from section introduction (lower is better)"""


class PlacementAnalyzer:
    """Analyzes article structure to find optimal illustration placements."""

    def __init__(
        self,
        min_section_words: int = 400,
        min_between_distance: int = 200,
        prefer_after_intro: bool = True,
    ):
        """Initialize placement analyzer.

        Args:
            min_section_words: Minimum words needed in section to consider placement
            min_between_distance: Minimum word distance between illustrations
            prefer_after_intro: If True, prefer placement after section introduction
        """
        self.min_section_words = min_section_words
        self.min_between_distance = min_between_distance
        self.prefer_after_intro = prefer_after_intro

    def parse_structure(self, content: str) -> list[Section]:
        """Parse markdown content into logical sections.

        Sections are defined by heading levels (# ## ### etc). Returns list of
        sections with metadata for analysis.

        Args:
            content: Article markdown content

        Returns:
            List of Section objects representing article structure
        """
        sections = []
        lines = content.split("\n")

        current_heading = None
        current_level = 0
        section_start = 0

        for line_num, line in enumerate(lines):
            # Detect heading
            heading_match = re.match(r"^(#{1,6})\s+(.+?)$", line)

            if heading_match:
                # Save previous section if any
                if current_heading is not None:
                    section_content = "\n".join(lines[section_start:line_num])
                    sections.append(
                        self._create_section(
                            current_heading,
                            current_level,
                            section_start,
                            line_num - 1,
                            section_content,
                        )
                    )

                # Start new section
                current_level = len(heading_match.group(1))
                current_heading = heading_match.group(2).strip()
                section_start = line_num

        # Don't forget the last section
        if current_heading is not None:
            section_content = "\n".join(lines[section_start:])
            sections.append(
                self._create_section(
                    current_heading,
                    current_level,
                    section_start,
                    len(lines) - 1,
                    section_content,
                )
            )

        return sections

    def _create_section(
        self, title: str, level: int, start_line: int, end_line: int, content: str
    ) -> Section:
        """Helper to create a Section object with analyzed metadata."""
        # Count only body words (exclude heading)
        lines = content.split("\n")
        body_lines = [l for l in lines[1:] if l.strip()]  # Skip heading line
        body_text = "\n".join(body_lines)
        word_count = len(body_text.split())

        has_code = bool(re.search(r"```", content))
        has_list = bool(re.search(r"^\s*[-*+]\s|^\s*\d+\.", content, re.MULTILINE))
        has_table = bool(re.search(r"\|", content))
        has_visuals = bool(re.search(r"!\[|<svg|<img|mermaid", content))
        section_type = self._analyze_section_type(content)

        return Section(
            title=title,
            level=level,
            start_line=start_line,
            end_line=end_line,
            content=content,
            word_count=word_count,
            has_code_block=has_code,
            has_list=has_list,
            has_table=has_table,
            has_visuals=has_visuals,
            section_type=section_type,
        )

    def _analyze_section_type(self, content: str) -> str:
        """Determine if section is list-based or narrative.

        Analyzes the section content to classify it as either "list" or "narrative".
        A section is considered "list" if more than 50% of non-empty lines are list items.

        Args:
            content: Section content to analyze

        Returns:
            "list" if >50% of lines are list items, else "narrative"
        """
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        if not lines:
            return "narrative"

        # Skip the first line (heading)
        if len(lines) > 1:
            lines = lines[1:]

        if not lines:
            return "narrative"

        # Count lines starting with list markers
        list_pattern = re.compile(r"^[-*•\d]+\.?\s")
        list_lines = sum(1 for line in lines if list_pattern.match(line))

        list_ratio = list_lines / len(lines)
        return "list" if list_ratio > 0.5 else "narrative"

    def find_placements(
        self, content: str, concept_names: list[str], max_placements: int = 3
    ) -> list[PlacementPoint]:
        """Find optimal placement points for illustrations.

        Args:
            content: Article markdown content
            concept_names: List of concepts to place (e.g., ['network_topology', 'data_flow'])
            max_placements: Maximum number of placements to return

        Returns:
            Sorted list of PlacementPoint objects (best first)
        """
        if not concept_names:
            return []

        sections = self.parse_structure(content)
        placements: list[PlacementPoint] = []

        # For each concept, find best placement
        for concept in concept_names:
            placement = self._find_best_placement_for_concept(sections, concept)
            if placement:
                placements.append(placement)

        # Sort by weight (best first)
        placements.sort(key=lambda p: p.weight, reverse=True)

        # Apply density limits: ensure sufficient word distance between placements
        validated = self._validate_placement_density(
            content, placements, self.min_between_distance
        )

        return validated[:max_placements]

    def _find_best_placement_for_concept(
        self, sections: list[Section], concept: str
    ) -> PlacementPoint | None:
        """Find best placement point for a specific concept.

        Args:
            sections: Parsed article sections
            concept: Concept name (e.g., 'network_topology')

        Returns:
            Best PlacementPoint for this concept, or None if not suitable
        """
        # Keywords associated with each concept
        concept_keywords = {
            "network_topology": [
                "network",
                "nat",
                "router",
                "packet",
                "topology",
                "ip",
            ],
            "system_architecture": [
                "architecture",
                "system",
                "components",
                "layers",
                "microservices",
            ],
            "data_flow": ["pipeline", "data flow", "processing", "transform", "etl"],
            "scientific_process": ["methodology", "process", "experiment", "lifecycle"],
            "comparison": ["comparison", "versus", "pros and cons", "tradeoff"],
            "algorithm": ["algorithm", "steps", "procedure"],
        }

        keywords = concept_keywords.get(concept, [])
        best_placement = None
        best_weight = 0.0

        print(f"[DEBUG] Looking for concept '{concept}' with keywords: {keywords}")
        print(f"[DEBUG]   min_section_words={self.min_section_words}")

        for section_idx, section in enumerate(sections):
            # Skip sections that aren't suitable
            if section.word_count < self.min_section_words:
                print(
                    f"[DEBUG]   Section {section_idx} '{section.title}': SKIP (only {section.word_count} words, need {self.min_section_words})"
                )
                continue
            # Note: Removed strict filtering for code_block, list, table - these are common in tech content
            # Instead, we'll place diagrams after these elements intelligently
            if section.has_visuals:
                # Skip only if section already has visuals
                print(
                    f"[DEBUG]   Section {section_idx} '{section.title}': SKIP (already has visuals)"
                )
                continue

            # Calculate concept match weight
            content_lower = section.content.lower()
            keyword_matches = sum(1 for kw in keywords if kw in content_lower)

            if keyword_matches == 0:
                print(
                    f"[DEBUG]   Section {section_idx} '{section.title}': SKIP (no keyword matches)"
                )
                continue

            print(
                f"[DEBUG]   Section '{section.title}': {section.word_count} words, {keyword_matches} keyword matches"
            )

            # Calculate section weight
            concept_match = min(1.0, keyword_matches / len(keywords))

            # Prefer placement after section intro (first 100 words)
            intro_text = " ".join(section.content.split()[:100])
            distance_from_intro = len(section.content.split()) - len(intro_text.split())

            placement_weight = (
                concept_match * 0.7
                + (1.0 - (distance_from_intro / max(section.word_count, 1))) * 0.3
            )

            if placement_weight > best_weight:
                best_weight = placement_weight
                # Calculate position after first paragraph
                paragraphs = section.content.split("\n\n")
                if len(paragraphs) > 1:
                    position = len(paragraphs[0]) + len(paragraphs[1]) // 2
                else:
                    position = len(section.content) // 2

                best_placement = PlacementPoint(
                    section_index=section_idx,
                    position_in_section=position,
                    concept_names=[concept],
                    weight=placement_weight,
                    rationale=f"Found {keyword_matches} concept keywords, section has {section.word_count} words",
                    distance_from_intro=distance_from_intro,
                )

        return best_placement

    def _validate_placement_density(
        self, content: str, placements: list[PlacementPoint], min_distance: int
    ) -> list[PlacementPoint]:
        """Validate that placements maintain minimum word distance.

        Ensures illustrations aren't too close together by checking word count
        between placements. Removes or adjusts overlapping placements.

        Args:
            content: Article content for word counting
            placements: Proposed placements
            min_distance: Minimum words between illustrations

        Returns:
            Validated placements that meet density requirements
        """
        if not placements:
            return []

        validated = [placements[0]]

        for placement in placements[1:]:
            # Check distance from last validated placement
            # Simple heuristic: section positions roughly correlate to article position
            if placement.section_index - validated[-1].section_index >= 2:
                validated.append(placement)
            elif len(validated) >= 3:
                # Already have max for typical article
                break

        return validated

    def calculate_placement_safety(
        self, content: str, section_idx: int, position: int
    ) -> bool:
        """Check if a placement position is safe (won't break formatting).

        Args:
            content: Article content
            section_idx: Section index
            position: Position within section

        Returns:
            True if placement is safe, False if it might break formatting
        """
        sections = self.parse_structure(content)

        if section_idx >= len(sections):
            return False

        section = sections[section_idx]

        # Don't place in middle of special elements
        section_content = section.content

        # Check if position is in code block
        code_blocks = re.finditer(r"```.*?```", section_content, re.DOTALL)
        for match in code_blocks:
            if match.start() <= position <= match.end():
                return False

        # Check if position is in table
        if section.has_table:
            table_start = section_content.find("|")
            if table_start != -1 and position > table_start:
                return False

        return True
