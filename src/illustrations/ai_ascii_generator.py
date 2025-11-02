"""AI-powered ASCII art generation using OpenAI API.

Generates context-aware ASCII diagrams, tables, and structured text
for processes, comparisons, and network topologies.
"""

from dataclasses import dataclass

from openai import OpenAI


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

    @property
    def total_cost(self) -> float:
        """Total cost for ASCII generation."""
        return self.prompt_cost + self.completion_cost


class AIAsciiGenerator:
    """Generates context-aware ASCII art using OpenAI API.

    Creates structured ASCII diagrams, tables, and flowcharts that work
    in plain text and markdown. Perfect for processes, comparisons, and
    network diagrams.
    """

    PRICING = {
        "gpt-3.5-turbo": {
            "prompt": 0.0005,
            "completion": 0.0015,
        }
    }

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
    ) -> GeneratedAsciiArt | None:
        """Generate ASCII art for a specific article section.

        Args:
            section_title: Title of the article section
            section_content: The actual content of the section
            concept_type: Type of concept

        Returns:
            GeneratedAsciiArt if successful, None if generation failed
        """
        prompt = self._build_prompt(section_title, section_content, concept_type)
        art_type = self._determine_art_type(concept_type)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at creating clear ASCII diagrams and tables. "
                        "Generate well-formatted ASCII art that visualizes the concept. "
                        "Use box drawing characters (─, │, ┌, ┐, └, ┘, ├, ┤, ┬, ┴, ┼) for clarity. "
                        "Return ONLY the ASCII art, no explanations or markdown formatting.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=800,
            )

            ascii_content = (response.choices[0].message.content or "").strip()

            # Calculate costs
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0

            prompt_cost = (prompt_tokens / 1000) * self.PRICING[self.model]["prompt"]
            completion_cost = (
                completion_tokens / 1000
            ) * self.PRICING[self.model]["completion"]

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
            print(f"Failed to generate ASCII art: {e}")
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
