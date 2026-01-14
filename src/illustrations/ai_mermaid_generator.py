"""AI-powered Mermaid diagram generation using OpenAI API.

Generates context-aware Mermaid diagrams based on article content by using
Claude/GPT with targeted prompts. This replaces static templates with
dynamic, relevant diagrams matched to the specific article section.
"""

from dataclasses import dataclass

from ..utils.logging import get_logger
from ..utils.openai_wrapper import chat_completion
from ..utils.pricing import estimate_text_cost_components

logger = get_logger(__name__)

from openai import OpenAI

from ..models import PipelineConfig
from ..utils.logging import get_logger


@dataclass
class GeneratedMermaidDiagram:
    """An AI-generated Mermaid diagram with cost tracking."""

    diagram_type: str
    """Type of Mermaid diagram: 'flowchart', 'graph', 'sequence', etc."""

    content: str
    """The Mermaid diagram syntax"""

    alt_text: str
    """Accessibility description of the diagram"""

    prompt_cost: float
    """Cost in dollars for this diagram generation"""

    completion_cost: float
    """Cost in dollars for completion tokens"""

    extra_costs: float = 0.0
    """Additional costs (e.g., validation/review) in USD."""

    @property
    def total_cost(self) -> float:
        """Total cost for diagram generation."""
        return self.prompt_cost + self.completion_cost + self.extra_costs


class AIMermaidGenerator:
    """Generates context-aware Mermaid diagrams using OpenAI API.

    Uses GPT-3.5 Turbo (cheap) or Claude Haiku to generate Mermaid syntax
    based on the specific article section content. This ensures diagrams are
    relevant and accurate to the actual content being illustrated.
    """

    def __init__(self, client: OpenAI, model: str = "gpt-3.5-turbo"):
        """Initialize AI Mermaid generator.

        Args:
            client: OpenAI client for API calls
            model: Model to use (default: gpt-3.5-turbo for cost efficiency)
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
    ) -> GeneratedMermaidDiagram | None:
        """Generate a Mermaid diagram for a specific article section.

        Uses AI to create a custom diagram based on the section content,
        ensuring it's relevant and accurate to the specific topic.

        Args:
            section_title: Title of the article section
            section_content: The actual content of the section
            concept_type: Type of concept (network_topology, data_flow, system_architecture, etc.)

        Returns:
            GeneratedMermaidDiagram if successful, None if generation failed
        """
        logger.debug(f"Generating Mermaid diagram for {section_title} ({concept_type})")
        # Build a targeted prompt based on concept type
        prompt = self._build_prompt(section_title, section_content, concept_type)

        try:
            response = chat_completion(
                client=self.client,
                model=self.model,
                stage="illustration_mermaid_generate",
                config=config,
                article_id=article_id,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at creating clear, accurate Mermaid diagrams. "
                        "Generate valid Mermaid syntax that visualizes the concept described. "
                        "Return ONLY valid Mermaid syntax, no explanations.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )

            # Extract the Mermaid diagram from response
            mermaid_content = response.choices[0].message.content
            if mermaid_content is None:
                logger.error("Mermaid generation failed: No content in response")
                return None
            mermaid_content = mermaid_content.strip()

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
                f"Mermaid diagram generated: {len(mermaid_content)} chars, cost: ${total_cost:.4f}"
            )

            # Generate alt-text using the section content
            alt_text = self._generate_alt_text(
                section_title, concept_type, mermaid_content
            )

            return GeneratedMermaidDiagram(
                diagram_type="flowchart",  # Will be detected from content
                content=mermaid_content,
                alt_text=alt_text,
                prompt_cost=prompt_cost,
                completion_cost=completion_cost,
            )

        except Exception as e:
            logger.error(
                f"Mermaid generation failed: {type(e).__name__}: {e}",
                exc_info=True,
            )
            return None

    def _build_prompt(
        self, section_title: str, section_content: str, concept_type: str
    ) -> str:
        """Build a targeted prompt for Mermaid generation.

        Args:
            section_title: Article section title
            section_content: Section content to visualize
            concept_type: Type of concept to visualize

        Returns:
            Prompt optimized for the concept type
        """
        concept_prompts = {
            "network_topology": (
                f"Create a Mermaid diagram showing the network topology described in this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:500]}\n\n"
                f"Show network nodes, connections, and data flow. Use LR or TD direction for clarity."
            ),
            "system_architecture": (
                f"Create a Mermaid diagram showing the system architecture described in this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:500]}\n\n"
                f"Show components, layers, and their relationships. Use LR direction."
            ),
            "data_flow": (
                f"Create a Mermaid diagram showing the data pipeline/flow described in this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:500]}\n\n"
                f"Show data stages, transformations, and flow direction. Use LR or TD direction."
            ),
            "scientific_process": (
                f"Create a Mermaid diagram showing the scientific process/methodology described in this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:500]}\n\n"
                f"Show steps, decision points, and process flow. Use TD direction."
            ),
            "comparison": (
                f"Create a Mermaid diagram comparing the items/concepts described in this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:500]}\n\n"
                f"Show differences and similarities clearly using flowchart or graph format."
            ),
            "algorithm": (
                f"Create a Mermaid diagram showing the algorithm/procedure described in this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:500]}\n\n"
                f"Show steps, loops, conditions, and decision points. Use TD direction with diamond nodes for decisions."
            ),
        }

        return concept_prompts.get(
            concept_type,
            (
                f"Create a Mermaid diagram visualizing the content described in this section:\n\n"
                f"Section: {section_title}\n"
                f"Content: {section_content[:500]}\n\n"
                f"Make it clear and easy to understand."
            ),
        )

    def _generate_alt_text(
        self, section_title: str, concept_type: str, mermaid_content: str
    ) -> str:
        """Generate alt-text for the Mermaid diagram.

        Args:
            section_title: Article section title
            concept_type: Type of concept
            mermaid_content: The generated Mermaid syntax

        Returns:
            Alt-text description of the diagram
        """
        # Map concept types to human-readable descriptions
        descriptions = {
            "network_topology": f"Network topology diagram for {section_title}",
            "system_architecture": f"System architecture diagram for {section_title}",
            "data_flow": f"Data flow/pipeline diagram for {section_title}",
            "scientific_process": f"Scientific process diagram for {section_title}",
            "comparison": f"Comparison diagram for {section_title}",
            "algorithm": f"Algorithm flowchart for {section_title}",
        }

        return descriptions.get(concept_type, f"Diagram illustrating {section_title}")

    def calculate_cost_for_concept(
        self, section_content: str, concept_type: str
    ) -> dict:
        """Estimate the cost to generate a diagram for a concept.

        Args:
            section_content: The section content length estimate
            concept_type: Type of concept

        Returns:
            Dict with estimated costs
        """
        # Rough estimates:
        # Prompt: ~100-200 tokens for prompt
        # Completion: ~50-150 tokens for Mermaid diagram
        estimated_prompt_tokens = 200
        estimated_completion_tokens = 100

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
