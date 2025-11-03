"""Multi-candidate Mermaid generation with quality selection.

Generates N Mermaid diagram candidates and selects the best based on
validation scores. Similar to TextIllustrationQualitySelector for ASCII.
"""

from dataclasses import dataclass

from openai import OpenAI

from .ai_mermaid_generator import AIMermaidGenerator, GeneratedMermaidDiagram
from .diagram_validator import DiagramValidator


@dataclass
class MermaidCandidateResult:
    """Result from multi-candidate Mermaid generation."""

    diagram: GeneratedMermaidDiagram | None
    """Best diagram, or None if all rejected"""

    candidates_tested: int
    """Number of candidates generated"""

    best_score: float
    """Highest validation score achieved"""

    all_rejected: bool
    """True if all candidates failed validation"""

    total_cost: float
    """Total cost for all generation + validation"""


class MermaidQualitySelector:
    """Generate multiple Mermaid candidates and select best."""

    def __init__(
        self,
        client: OpenAI,
        model: str = "gpt-3.5-turbo",
        n_candidates: int = 3,
        validation_threshold: float = 0.7,
    ):
        """Initialize quality selector.

        Args:
            client: OpenAI client for API calls
            model: Model to use
            n_candidates: Number of candidates to generate
            validation_threshold: Minimum score to accept diagram
        """
        self.generator = AIMermaidGenerator(client, model)
        self.validator = DiagramValidator(client, model, validation_threshold)
        self.n_candidates = n_candidates
        self.validation_threshold = validation_threshold

    def generate_best(
        self,
        section_title: str,
        section_content: str,
        concept_type: str,
    ) -> MermaidCandidateResult:
        """Generate N candidates, validate all, return best.

        Args:
            section_title: Title of the article section
            section_content: The actual content of the section
            concept_type: Type of concept

        Returns:
            MermaidCandidateResult with best diagram or None
        """
        candidates: list[tuple[float, GeneratedMermaidDiagram, float]] = []
        total_cost = 0.0

        # Generate N candidates
        for _i in range(self.n_candidates):
            diagram = self.generator.generate_for_section(
                section_title,
                section_content,
                concept_type,
            )

            if diagram:
                # Validate candidate
                validation = self.validator.validate_diagram(
                    section_title=section_title,
                    section_content=section_content,
                    diagram_content=diagram.content,
                    diagram_type="mermaid",
                )

                total_cost += diagram.total_cost + validation.cost

                candidates.append(
                    (validation.combined_score, diagram, diagram.total_cost)
                )

        # Sort by validation score (descending)
        candidates.sort(key=lambda x: x[0], reverse=True)

        if not candidates:
            return MermaidCandidateResult(
                diagram=None,
                candidates_tested=0,
                best_score=0.0,
                all_rejected=True,
                total_cost=total_cost,
            )

        best_score, best_diagram, _gen_cost = candidates[0]

        # Check if best passes threshold
        if best_score < self.validation_threshold:
            return MermaidCandidateResult(
                diagram=None,
                candidates_tested=len(candidates),
                best_score=best_score,
                all_rejected=True,
                total_cost=total_cost,
            )

        return MermaidCandidateResult(
            diagram=best_diagram,
            candidates_tested=len(candidates),
            best_score=best_score,
            all_rejected=False,
            total_cost=total_cost,
        )
