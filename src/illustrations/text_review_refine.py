"""Two-stage review and refinement system for text-based illustrations.

Optional polish phase: generates, reviews quality, and optionally refines
diagrams based on review feedback. Only runs for high-importance articles.
Adds refinement cycles and quality metrics to diagrams.
"""

import json

from openai import OpenAI

from .ai_ascii_generator import AIAsciiGenerator, GeneratedAsciiArt


class TextIllustrationReviewRefine:
    """Two-stage generation: review quality, optionally refine based on feedback.

    Stage 1: Generate ASCII diagram
    Stage 2: AI-powered review of quality and identification of issues
    Stage 3: Optional refinement based on review findings (only if score < 0.7)

    Only recommended for high-importance diagrams (importance > 0.7) due to
    additional API calls and cost (~$0.002 per diagram for review+refinement).
    """

    def __init__(self, client: OpenAI, model: str = "gpt-3.5-turbo"):
        """Initialize review/refine system.

        Args:
            client: OpenAI client for API calls
            model: Model to use (default: gpt-3.5-turbo)
        """
        self.client = client
        self.model = model
        self.generator = AIAsciiGenerator(client, model)

    def generate_with_review(
        self,
        section_title: str,
        section_content: str,
        concept_type: str,
        importance: float = 0.5,
    ) -> GeneratedAsciiArt | None:
        """Generate ASCII diagram, review quality, optionally refine.

        Args:
            section_title: Title of the article section
            section_content: The actual content of the section
            concept_type: Type of concept
            importance: Importance score 0-1. Review/refinement only runs if > 0.7

        Returns:
            GeneratedAsciiArt with review metadata, or None if generation failed
        """
        # Stage 1: Generate
        initial = self.generator.generate_for_section(
            section_title, section_content, concept_type
        )

        if initial is None:
            return None

        # If low importance, skip review and return quickly
        if importance < 0.7:
            initial.review_cycles = 0
            return initial

        # Stage 2: Review quality
        review_data = self._review_quality(initial, concept_type)
        review_score = review_data.get("score", 0.5)

        # Stage 3: Refinement if needed
        if review_score < 0.7:
            refined = self._refine_based_on_review(initial, concept_type, review_data)
            if refined:
                return refined

        # No refinement needed, return initial with review metadata
        initial.review_cycles = 1
        return initial

    def _review_quality(self, diagram: GeneratedAsciiArt, concept_type: str) -> dict:
        """Review ASCII diagram quality using AI.

        Args:
            diagram: The generated ASCII diagram
            concept_type: Type of concept for context

        Returns:
            Dict with score (0-1), identified issues, and suggested fixes
        """
        review_prompt = f"""Review this {concept_type} Unicode text diagram for quality.
Rate the overall quality from 0.0 (poor) to 1.0 (excellent).
Identify 2-3 specific issues if any (alignment, clarity, clutter, completeness).
Suggest 2-3 specific fixes to improve it.

Diagram:
```
{diagram.content}
```

Respond ONLY with valid JSON (no markdown):
{{"score": 0.5, "issues": ["issue1", "issue2"], "fixes": ["fix1", "fix2"]}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": review_prompt}],
                temperature=0.3,
                max_tokens=300,
            )

            response_text = response.choices[0].message.content or "{}"
            review_data = json.loads(response_text)
            return review_data
        except (json.JSONDecodeError, Exception):
            # If parsing fails, return neutral review
            return {"score": 0.5, "issues": ["parse_error"], "fixes": []}

    def _refine_based_on_review(
        self, initial: GeneratedAsciiArt, concept_type: str, review_data: dict
    ) -> GeneratedAsciiArt | None:
        """Refine diagram based on review feedback.

        Args:
            initial: The initial generated diagram
            concept_type: Type of concept
            review_data: Review dict with issues and fixes

        Returns:
            Refined GeneratedAsciiArt, or None if refinement failed
        """
        issues = review_data.get("issues", [])[:2]
        fixes = review_data.get("fixes", [])[:2]

        if not fixes:
            return None

        refine_prompt = f"""Improve this {concept_type} Unicode text diagram.

Address these issues: {", ".join(issues)}
Apply these improvements: {", ".join(fixes)}

Original diagram:
```
{initial.content}
```

Requirements:
- Width: 50-60 characters max
- All lines perfectly aligned
- Use proper Unicode box-drawing characters
- Return ONLY the improved diagram, no markdown or explanation"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": refine_prompt}],
                temperature=0.3,
                max_tokens=500,
            )

            refined_content = (response.choices[0].message.content or "").strip()

            if not refined_content:
                return None

            # Calculate additional costs for review + refinement
            response_usage = response.usage if response.usage else None
            prompt_tokens = response_usage.prompt_tokens if response_usage else 100
            completion_tokens = (
                response_usage.completion_tokens if response_usage else 150
            )

            additional_prompt_cost = (prompt_tokens / 1000) * 0.0005
            additional_completion_cost = (completion_tokens / 1000) * 0.0015

            # Return refined diagram with updated metadata
            return GeneratedAsciiArt(
                art_type=initial.art_type,
                content=refined_content,
                alt_text=initial.alt_text,
                prompt_cost=initial.prompt_cost + additional_prompt_cost,
                completion_cost=initial.completion_cost + additional_completion_cost,
                quality_score=review_data.get("score", 0.5),
                candidates_tested=0,
                review_cycles=1,
            )

        except Exception:
            return None

    def batch_review_refine(
        self,
        diagrams: list[dict],
        importance: float = 0.5,
    ) -> list[GeneratedAsciiArt]:
        """Review and refine a batch of diagrams.

        Args:
            diagrams: List of dicts with keys: section_title, section_content, concept_type
            importance: Importance score for all diagrams

        Returns:
            List of refined GeneratedAsciiArt objects
        """
        results = []

        for diagram_spec in diagrams:
            try:
                refined = self.generate_with_review(
                    section_title=diagram_spec["section_title"],
                    section_content=diagram_spec["section_content"],
                    concept_type=diagram_spec["concept_type"],
                    importance=importance,
                )
                if refined:
                    results.append(refined)
            except Exception:
                pass

        return results
