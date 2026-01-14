"""AI-powered SVG generation.

Generates context-aware SVG infographics and diagrams for complex system
architecture, network topology, and visual explanations.

All LLM calls route through the instrumented wrapper so costs/telemetry are
consistent and spend caps apply.
"""

from dataclasses import dataclass

from openai import OpenAI

from ..models import PipelineConfig
from ..utils.logging import get_logger
from ..utils.openai_wrapper import chat_completion
from ..utils.pricing import estimate_text_cost_components

logger = get_logger(__name__)


@dataclass
class GeneratedSvg:
    """An AI-generated SVG graphic with cost tracking."""

    graphic_type: str
    """Type of SVG: 'infographic', 'diagram', 'flowchart'"""

    content: str
    """The SVG code (inline)"""

    alt_text: str
    """Accessibility description"""

    width: int
    """SVG width in pixels"""

    height: int
    """SVG height in pixels"""

    prompt_cost: float
    """Cost in dollars for this generation"""

    completion_cost: float
    """Cost in dollars for completion tokens"""

    @property
    def total_cost(self) -> float:
        """Total cost for SVG generation."""
        return self.prompt_cost + self.completion_cost


class AISvgGenerator:
    """Generates context-aware SVG graphics using OpenAI API.

    Creates scalable vector graphics for system architecture, network
    diagrams, and complex visualizations. SVGs are CSS-stylable and
    perfect for web content.
    """

    def __init__(self, client: OpenAI, model: str = "gpt-3.5-turbo"):
        """Initialize AI SVG generator.

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
        width: int = 800,
        height: int = 600,
        *,
        config: PipelineConfig | None = None,
        article_id: str | None = None,
    ) -> GeneratedSvg | None:
        """Generate SVG graphic for a specific article section.

        Args:
            section_title: Title of the article section
            section_content: The actual content of the section
            concept_type: Type of concept
            width: SVG width in pixels
            height: SVG height in pixels

        Returns:
            GeneratedSvg if successful, None if generation failed
        """
        logger.debug(
            f"Generating SVG for {section_title} ({concept_type}): {width}x{height}"
        )
        prompt = self._build_prompt(
            section_title, section_content, concept_type, width, height
        )
        graphic_type = self._determine_graphic_type(concept_type)

        try:
            response = chat_completion(
                client=self.client,
                model=self.model,
                stage="svg_generation",
                config=config,
                article_id=article_id,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert SVG designer. Generate valid SVG code that visualizes the concept. "
                        "Use clear colors, labels, and proper scaling. "
                        "Return ONLY valid SVG code wrapped in <svg></svg> tags, no explanations.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2000,  # SVG can be lengthy
            )

            svg_content = response.choices[0].message.content
            if svg_content is None:
                logger.error("SVG generation failed: No content returned from API")
                return None
            svg_content = svg_content.strip()

            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0

            prompt_cost, completion_cost = estimate_text_cost_components(
                self.model,
                prompt_tokens,
                completion_tokens,
            )
            total_cost = prompt_cost + completion_cost
            logger.debug(
                f"SVG generated: {len(svg_content)} chars, cost: ${total_cost:.4f}"
            )

            # Generate alt-text
            alt_text = self._generate_alt_text(section_title, concept_type)

            return GeneratedSvg(
                graphic_type=graphic_type,
                content=svg_content,
                alt_text=alt_text,
                width=width,
                height=height,
                prompt_cost=prompt_cost,
                completion_cost=completion_cost,
            )

        except Exception as e:
            logger.error(
                "SVG generation failed: %s: %s",
                type(e).__name__,
                e,
                exc_info=True,
            )
            return None

    def _build_prompt(
        self,
        section_title: str,
        section_content: str,
        concept_type: str,
        width: int,
        height: int,
    ) -> str:
        """Build a targeted prompt for SVG generation."""
        concept_prompts = {
            "network_topology": (
                f"Create an SVG diagram showing the network topology described in this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Show network nodes as circles/boxes with connections. Use colors to differentiate components. "
                f"Size: {width}x{height}px. Include labels for each component."
            ),
            "system_architecture": (
                f"Create an SVG infographic showing the system architecture from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Show layers or components with clear relationships. Use different colors for different layers. "
                f"Size: {width}x{height}px. Make it visually appealing and professional."
            ),
            "data_flow": (
                f"Create an SVG diagram showing the data flow/pipeline from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Show data movement with arrows and transformation steps. "
                f"Size: {width}x{height}px. Use visual hierarchy to show flow direction."
            ),
            "scientific_process": (
                f"Create an SVG diagram showing the scientific process from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Show methodology steps visually with clear progression. "
                f"Size: {width}x{height}px. Include decision points and feedback loops."
            ),
            "comparison": (
                f"Create an SVG infographic comparing concepts from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Show two or more items side-by-side with their attributes. "
                f"Size: {width}x{height}px. Use visual contrast to highlight differences."
            ),
            "algorithm": (
                f"Create an SVG flowchart of the algorithm from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Show algorithm steps with decision diamonds and flow arrows. "
                f"Size: {width}x{height}px. Use colors to differentiate decision points."
            ),
        }

        return concept_prompts.get(
            concept_type,
            (
                f"Create an SVG diagram visualizing the content from this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:400]}\n\n"
                f"Make it clear, professional, and visually engaging. "
                f"Size: {width}x{height}px."
            ),
        )

    def _determine_graphic_type(self, concept_type: str) -> str:
        """Determine the best SVG graphic type for the concept."""
        type_map = {
            "network_topology": "diagram",
            "system_architecture": "infographic",
            "data_flow": "diagram",
            "scientific_process": "diagram",
            "comparison": "infographic",
            "algorithm": "flowchart",
        }
        return type_map.get(concept_type, "diagram")

    def _generate_alt_text(self, section_title: str, concept_type: str) -> str:
        """Generate alt-text for the SVG."""
        descriptions = {
            "network_topology": f"SVG network topology diagram for {section_title}",
            "system_architecture": f"SVG system architecture infographic for {section_title}",
            "data_flow": f"SVG data flow diagram for {section_title}",
            "scientific_process": f"SVG scientific process diagram for {section_title}",
            "comparison": f"SVG comparison infographic for {section_title}",
            "algorithm": f"SVG algorithm flowchart for {section_title}",
        }
        return descriptions.get(concept_type, f"SVG diagram for {section_title}")

    def calculate_cost_for_concept(
        self, section_content: str, concept_type: str
    ) -> dict:
        """Estimate cost to generate SVG.

        Args:
            section_content: The section content
            concept_type: Type of concept

        Returns:
            Dict with estimated costs
        """
        estimated_prompt_tokens = 250
        estimated_completion_tokens = 400  # SVG code can be lengthy

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
