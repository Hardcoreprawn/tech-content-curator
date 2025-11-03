"""Validation service for generated diagrams.

Scores diagrams on content accuracy and explanatory value to prevent
nonsensical or low-quality visualizations from being injected.
"""

import json
from dataclasses import dataclass

from openai import OpenAI


@dataclass
class ValidationResult:
    """Result of diagram validation."""

    is_valid: bool
    """Whether diagram passes validation threshold"""

    accuracy_score: float
    """How well diagram matches content (0.0-1.0)"""

    value_score: float
    """How much value it adds over text (0.0-1.0)"""

    combined_score: float
    """Combined validation score (0.0-1.0)"""

    reason: str
    """Explanation of validation decision"""

    cost: float
    """Cost of validation API call"""


class DiagramValidator:
    """Validates generated diagrams against source content."""

    PRICING = {
        "gpt-3.5-turbo": {
            "prompt": 0.0005,
            "completion": 0.0015,
        }
    }

    def __init__(
        self,
        client: OpenAI,
        model: str = "gpt-3.5-turbo",
        threshold: float = 0.7,
    ):
        """Initialize validator.

        Args:
            client: OpenAI client for API calls
            model: Model to use for validation
            threshold: Minimum combined score to pass (0.0-1.0)
        """
        self.client = client
        self.model = model
        self.threshold = threshold

    def validate_diagram(
        self,
        section_title: str,
        section_content: str,
        diagram_content: str,
        diagram_type: str,
    ) -> ValidationResult:
        """Validate a generated diagram against source content.

        Args:
            section_title: Title of the section
            section_content: Full section content
            diagram_content: Generated diagram (Mermaid syntax or ASCII)
            diagram_type: Type of diagram ("mermaid" or "ascii")

        Returns:
            ValidationResult with scores and pass/fail decision
        """
        prompt = self._build_validation_prompt(
            section_title,
            section_content,
            diagram_content,
            diagram_type,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert at evaluating diagram quality and relevance. "
                            "Score diagrams objectively on accuracy and explanatory value."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # Low temperature for consistent scoring
                max_tokens=150,
            )

            content = response.choices[0].message.content
            if not content:
                return self._create_failed_result("No response from validator")

            # Parse JSON response
            result = json.loads(content.strip())

            accuracy = float(result.get("accuracy", 0.0))
            value = float(result.get("value_add", 0.0))
            reason = result.get("reason", "No reason provided")

            # Combined score (weighted average)
            combined = (accuracy * 0.6) + (value * 0.4)

            # Calculate cost
            usage = response.usage
            if usage:
                cost = (usage.prompt_tokens / 1000) * self.PRICING[self.model][
                    "prompt"
                ] + (usage.completion_tokens / 1000) * self.PRICING[self.model][
                    "completion"
                ]
            else:
                cost = 0.0

            return ValidationResult(
                is_valid=combined >= self.threshold,
                accuracy_score=accuracy,
                value_score=value,
                combined_score=combined,
                reason=reason,
                cost=cost,
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            return self._create_failed_result(f"Parse error: {e}")
        except Exception as e:
            return self._create_failed_result(f"Validation error: {e}")

    def _build_validation_prompt(
        self,
        section_title: str,
        section_content: str,
        diagram_content: str,
        diagram_type: str,
    ) -> str:
        """Build validation prompt."""
        # Truncate content for cost efficiency
        content_preview = section_content[:800]
        diagram_preview = diagram_content[:500]

        return f"""Evaluate this {diagram_type} diagram's quality for a technical article.

SECTION: "{section_title}"
CONTENT:
{content_preview}
{"..." if len(section_content) > 800 else ""}

GENERATED DIAGRAM:
{diagram_preview}
{"..." if len(diagram_content) > 500 else ""}

Rate on two dimensions (0.0 to 1.0):

1. ACCURACY: Does the diagram accurately represent concepts from the section content?
   - 1.0 = Perfect match, visualizes actual content
   - 0.5 = Generic/vague, could apply to anything
   - 0.0 = Completely wrong or unrelated

2. VALUE_ADD: Does the diagram explain concepts better than just reading the text?
   - 1.0 = Significantly clarifies complex relationships
   - 0.5 = Marginal value, just restates text
   - 0.0 = Adds confusion or clutter

Reply with ONLY this JSON:
{{
  "accuracy": 0.0-1.0,
  "value_add": 0.0-1.0,
  "reason": "brief explanation (20 words max)"
}}"""

    def _create_failed_result(self, reason: str) -> ValidationResult:
        """Create a failed validation result."""
        return ValidationResult(
            is_valid=False,
            accuracy_score=0.0,
            value_score=0.0,
            combined_score=0.0,
            reason=reason,
            cost=0.0,
        )
