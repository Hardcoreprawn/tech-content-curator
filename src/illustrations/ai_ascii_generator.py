"""AI-powered ASCII art generation using OpenAI API.

Generates context-aware ASCII diagrams, tables, and structured text
for processes, comparisons, and network topologies.
"""

from dataclasses import dataclass

from ..utils.logging import get_logger
from ..utils.openai_wrapper import chat_completion
from ..utils.pricing import estimate_text_cost_components

logger = get_logger(__name__)

from openai import OpenAI

from ..models import PipelineConfig


@dataclass
class GeneratedAsciiArt:
    """An AI-generated ASCII art with cost tracking."""

    art_type: str
    """Type of ASCII art: 'table', 'diagram', 'process_flow', 'network'"""

    content: str
    """The ASCII art content (monospace formatted)"""

    alt_text: str
    """Accessibility description of the diagram"""

    prompt_cost: float
    """Cost in dollars for this generation"""

    completion_cost: float
    """Cost in dollars for completion tokens"""

    extra_costs: float = 0.0
    """Additional costs (e.g., validation/review) in USD."""

    quality_score: float = 0.0
    """Quality score from 0.0 to 1.0 (set by quality selector)"""

    candidates_tested: int = 0
    """Number of candidates tested (set by quality selector)"""

    review_cycles: int = 0
    """Number of review/refinement cycles (set by review refiner)"""

    @property
    def total_cost(self) -> float:
        """Total cost for ASCII generation."""
        return self.prompt_cost + self.completion_cost + self.extra_costs


class AIAsciiGenerator:
    """Generates context-aware ASCII art using OpenAI API.

    Creates structured ASCII diagrams, tables, and flowcharts that work
    in plain text and markdown. Perfect for processes, comparisons, and
    network diagrams.
    """

    def __init__(self, client: OpenAI, model: str = "gpt-3.5-turbo"):
        """Initialize AI ASCII generator.

        Args:
            client: OpenAI client for API calls
            model: Model to use (default: gpt-3.5-turbo)
        """
        self.client = client
        self.model = model

    def generate_for_section(
        self,
        section_title: str,
        section_content: str,
        concept_type: str,
        *,
        config: PipelineConfig | None = None,
        article_id: str | None = None,
    ) -> GeneratedAsciiArt | None:
        """Generate ASCII art for a specific article section.

        Args:
            section_title: Title of the article section
            section_content: The actual content of the section
            concept_type: Type of concept

        Returns:
            GeneratedAsciiArt if successful, None if generation failed
        """
        logger.debug(f"Generating ASCII art for {section_title} ({concept_type})")
        prompt = self._build_prompt(section_title, section_content, concept_type)
        art_type = self._determine_art_type(concept_type)

        try:
            response = chat_completion(
                client=self.client,
                model=self.model,
                stage="illustration_ascii_generate",
                config=config,
                article_id=article_id,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a specialist in creating professional Unicode-based diagrams for technical articles.

CONSTRAINTS:
- Width: 50-60 characters maximum (for mobile readability when centered)
- Alignment: All lines perfectly aligned in monospace font
- Return ONLY the diagram, no markdown or explanation

CHARACTER SETS:
- Box drawing: ┌ ┐ └ ┘ ─ │ ├ ┤ ┬ ┴ ┼
- Junctions: ├ ┤ ┬ ┴ ┼
- Arrows: → ↓ ← ↑ (for flow)
- Accents: ◆ ★ ✓ ✗ ● (for markers)
- Use appropriate Unicode—not ASCII dashes/pipes

QUALITY CHECKLIST:
✓ Consistent line lengths (within 2 chars)
✓ Proper character pairing (no broken corners/lines)
✓ Clear labels and hierarchy
✓ Minimal clutter—clean and professional
✓ Readable at 50-60 character width

COMMON PATTERNS:
- Trees: Use ├─ for branches, proper indentation
- Flows: Use → and ▼ for direction, box structure
- Tables: Use ┌─┬─┐ for headers, │ for columns
- Networks: Use ┌─┐ boxes with ─ connections""",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=800,
            )

            ascii_content = (response.choices[0].message.content or "").strip()

            # Calculate costs (shared pricing table)
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = (
                response.usage.completion_tokens if response.usage else 0
            )

            prompt_cost, completion_cost = estimate_text_cost_components(
                self.model, prompt_tokens, completion_tokens
            )
            total_cost = prompt_cost + completion_cost
            logger.debug(
                f"ASCII art generated: {len(ascii_content)} chars, cost: ${total_cost:.4f}"
            )

            # Generate alt-text
            alt_text = self._generate_alt_text(section_title, concept_type)

            return GeneratedAsciiArt(
                art_type=art_type,
                content=ascii_content,
                alt_text=alt_text,
                prompt_cost=prompt_cost,
                completion_cost=completion_cost,
            )

        except Exception as e:
            logger.error(
                f"ASCII art generation failed: {type(e).__name__}: {e}",
                exc_info=True,
            )
            return None

    def _build_prompt(
        self, section_title: str, section_content: str, concept_type: str
    ) -> str:
        """Build a targeted prompt for ASCII generation."""
        concept_prompts = {
            "network_topology": (
                f"Create an ASCII diagram showing the network topology from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Use ASCII art with boxes and arrows to show network flow and connections. "
                f"Example format:\n"
                f"┌─────────┐      ┌─────────┐\n"
                f"│ Source  │──────│ Router  │\n"
                f"└─────────┘      └─────────┘"
            ),
            "data_flow": (
                f"Create an ASCII flowchart showing the data flow from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Show steps with arrows and boxes. Use monospace formatting."
            ),
            "comparison": (
                f"Create an ASCII table comparing concepts from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Format as a clear ASCII table with columns and rows separated by ─, │, and ┼ characters."
            ),
            "scientific_process": (
                f"Create an ASCII flowchart of the scientific process from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Show methodology steps with clear flow and decision points."
            ),
            "algorithm": (
                f"Create an ASCII flowchart of the algorithm from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Show steps, loops, and decision points clearly."
            ),
            "system_architecture": (
                f"Create an ASCII diagram of the system architecture from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Show components and their relationships vertically or horizontally."
            ),
        }

        return concept_prompts.get(
            concept_type,
            (
                f"Create a clear ASCII diagram showing the content from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Use ASCII art with boxes and arrows."
            ),
        )

    def _determine_art_type(self, concept_type: str) -> str:
        """Determine the best ASCII art type for the concept."""
        type_map = {
            "network_topology": "network",
            "data_flow": "process_flow",
            "comparison": "table",
            "scientific_process": "process_flow",
            "algorithm": "process_flow",
            "system_architecture": "diagram",
        }
        return type_map.get(concept_type, "diagram")

    def _generate_alt_text(self, section_title: str, concept_type: str) -> str:
        """Generate alt-text for the ASCII art."""
        descriptions = {
            "network_topology": f"ASCII network diagram for {section_title}",
            "data_flow": f"ASCII data flow diagram for {section_title}",
            "comparison": f"ASCII comparison table for {section_title}",
            "scientific_process": f"ASCII process flow for {section_title}",
            "algorithm": f"ASCII algorithm flowchart for {section_title}",
            "system_architecture": f"ASCII architecture diagram for {section_title}",
        }
        return descriptions.get(concept_type, f"ASCII diagram for {section_title}")

    def calculate_cost_for_concept(
        self, section_content: str, concept_type: str
    ) -> dict:
        """Estimate cost to generate ASCII art.

        Args:
            section_content: The section content
            concept_type: Type of concept

        Returns:
            Dict with estimated costs
        """
        estimated_prompt_tokens = 200
        estimated_completion_tokens = 150  # ASCII tends to be longer than Mermaid

        prompt_cost = (estimated_prompt_tokens / 1000) * self.PRICING[self.model][
            "prompt"
        ]
        completion_cost = (estimated_completion_tokens / 1000) * self.PRICING[
            self.model
        ]["completion"]

        return {
            "prompt_cost": prompt_cost,
            "completion_cost": completion_cost,
            "total_cost": prompt_cost + completion_cost,
            "model": self.model,
        }


class TextIllustrationQualitySelector:
    """Generate multiple candidates and select best based on quality scoring.

    Generates N candidate diagrams for a section and scores each on alignment,
    character variety, structure clarity, content density, and width constraints.
    Returns the highest-scoring candidate with metadata about testing.
    """

    def __init__(
        self,
        client: OpenAI,
        model: str = "gpt-3.5-turbo",
        n_candidates: int = 3,
        quality_threshold: float = 0.6,
    ):
        """Initialize quality selector.

        Args:
            client: OpenAI client for API calls
            model: Model to use (default: gpt-3.5-turbo)
            n_candidates: Number of candidates to generate (default: 3, configurable)
            quality_threshold: Minimum quality score to use diagram (0.0-1.0)
        """
        self.generator = AIAsciiGenerator(client, model)
        self.n_candidates = n_candidates
        self.quality_threshold = quality_threshold

    def generate_best(
        self,
        section_title: str,
        section_content: str,
        concept_type: str,
        *,
        config: PipelineConfig | None = None,
        article_id: str | None = None,
    ) -> GeneratedAsciiArt | None:
        """Generate N candidates and return the best-scoring one.

        Args:
            section_title: Title of the article section
            section_content: The actual content of the section
            concept_type: Type of concept

        Returns:
            GeneratedAsciiArt with highest quality score, or None if all below threshold
        """
        logger.debug(
            f"Generating {self.n_candidates} ASCII art candidates for {section_title}"
        )
        candidates = []

        for _i in range(self.n_candidates):
            art = self.generator.generate_for_section(
                section_title,
                section_content,
                concept_type,
                config=config,
                article_id=article_id,
            )
            if art:
                score = self._score(art.content, concept_type)
                candidates.append((score, art))

        if not candidates:
            return None

        # Sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_art = candidates[0]

        # Add metadata
        best_art.quality_score = best_score
        best_art.candidates_tested = len(candidates)

        if best_score >= self.quality_threshold:
            logger.info(
                f"Best ASCII art selected: score={best_score:.2f} (tested {len(candidates)} candidates)"
            )
            return best_art
        else:
            logger.warning(
                f"Best ASCII art score {best_score:.2f} below threshold {self.quality_threshold}"
            )
            return None

    def _score(self, content: str, concept_type: str) -> float:
        """Score diagram on multiple quality dimensions.

        Scoring breakdown:
        - Alignment (30%): Consistent line lengths
        - Character variety (20%): Appropriate Unicode chars for concept
        - Structure clarity (20%): Has proper box/flow structure
        - Content density (15%): Not too sparse or crowded
        - Width constraint (15%): Stays under 60 chars

        Args:
            content: The ASCII diagram content
            concept_type: Type of concept for context-aware scoring

        Returns:
            Combined quality score (0.0-1.0)
        """
        score = 0.0
        lines = content.split("\n")

        # 1. Alignment (30%) - do lines have consistent length?
        if lines:
            lengths = [len(l) for l in lines if l.strip()]
            if lengths:
                avg_len = sum(lengths) / len(lengths)
                # Calculate variance
                variance = (
                    sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
                    if lengths
                    else 0
                )
                # Lower variance = better alignment (1.0 is perfect)
                alignment = max(0.0, 1.0 - min(1.0, variance / 100))
                score += alignment * 0.30
            else:
                score += 0.0  # No non-empty lines

        # 2. Character variety (20%) - appropriate chars for concept?
        char_sets = {
            "network_topology": ["─", "│", "┌", "┐", "└", "┘"],
            "data_flow": ["─", "→", "│", "▼"],
            "comparison": ["│", "─", "┼", "┤", "├"],
            "hierarchy": ["├", "─", "│", "└"],
            "scientific_process": ["─", "→", "│", "●"],
            "algorithm": ["─", "→", "│", "◆"],
            "system_architecture": ["┌", "┐", "└", "┘", "─", "│"],
        }
        chars = char_sets.get(concept_type, ["─", "│", "┌", "┐", "└", "┘"])
        if chars:
            matches = sum(1 for c in chars if c in content)
            char_score = min(1.0, matches / max(len(chars), 1))
            score += char_score * 0.20

        # 3. Clarity (20%) - proper structure?
        has_structure = any(c in content for c in ["┌", "├", "┬", "→", "▼"])
        structure_score = 1.0 if has_structure else 0.3
        score += structure_score * 0.20

        # 4. Content density (15%) - not too sparse/crowded?
        non_ws = sum(1 for c in content if c.strip())
        total = len(content)
        density = min(1.0, non_ws / max(total, 1))
        # Ideal density is around 0.3-0.5
        if 0.3 <= density <= 0.5:
            density_score = 1.0
        elif 0.2 <= density < 0.3 or 0.5 < density <= 0.6:
            density_score = 0.8
        else:
            density_score = 0.5
        score += density_score * 0.15

        # 5. Width constraint (15%) - under 60 chars?
        max_width = max(len(l) for l in lines) if lines else 0
        width_score = 1.0 if max_width <= 60 else (1.0 if max_width <= 70 else 0.3)
        score += width_score * 0.15

        return min(1.0, score)
