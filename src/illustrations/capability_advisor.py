"""Intelligent advisor for text-based vs other illustration formats.

Routes illustration generation to the most appropriate format (text, mermaid, svg)
based on concept type, complexity, and content characteristics. Provides confidence
scores and reasoning for orchestrator decision-making.
"""

from collections.abc import Callable

from ..utils.logging import get_logger

logger = get_logger(__name__)


class TextIllustrationCapabilityAdvisor:
    """Tell orchestrator if text-based diagrams are appropriate for a concept.

    Analyzes concept characteristics to recommend whether to use text-based ASCII
    diagrams or route to other formats (mermaid, svg). Returns routing decision
    with confidence and rationale.
    """

    def should_use_text(
        self,
        concept_type: str,
        complexity: float,
        content_length: int,
        requirements: dict | None = None,
    ) -> tuple[bool, str, float]:
        """Determine if text-based diagram is recommended for this concept.

        Args:
            concept_type: Type of concept (e.g., 'hierarchy', 'process_flow')
            complexity: Complexity score from 0.0 (simple) to 1.0 (complex)
            content_length: Number of items/steps/nodes in the content
            requirements: Optional dict with specific requirements

        Returns:
            Tuple of (should_use_text: bool, reason: str, confidence: float)
            - should_use_text: True if text diagram recommended
            - reason: String describing the routing decision
            - confidence: Confidence in recommendation (0.0-1.0)

        Examples:
            >>> advisor = TextIllustrationCapabilityAdvisor()
            >>> advisor.should_use_text("hierarchy", 0.5, 4)
            (True, "hierarchy_simple_tree", 0.95)
            >>> advisor.should_use_text("system_architecture", 0.9, 8)
            (False, "system_complex_use_svg", 0.85)
        """
        logger.debug(
            f"Routing decision for {concept_type}: complexity={complexity}, length={content_length}"
        )
        requirements = requirements or {}

        # Decision tree using type-safe function dispatch
        def _check_hierarchy(comp: float, length: int) -> tuple[bool, str, float]:
            if comp < 0.7 and length <= 6:
                return (True, "hierarchy_text_tree_simple", 0.95)
            elif comp < 0.6 and length <= 8:
                return (True, "hierarchy_text_tree_moderate", 0.80)
            return (False, "hierarchy_complex_use_svg", 0.85)

        def _check_process_flow(comp: float, length: int) -> tuple[bool, str, float]:
            if length <= 3 and comp < 0.6:
                return (True, "process_text_simple_linear", 0.90)
            elif length <= 5 and comp < 0.5:
                return (True, "process_text_simple_sequence", 0.75)
            return (False, "process_complex_use_mermaid", 0.85)

        def _check_comparison(comp: float, length: int) -> tuple[bool, str, float]:
            if length <= 8:
                return (True, "comparison_text_table_ideal", 0.95)
            return (False, "comparison_complex_use_svg", 0.80)

        def _check_timeline(comp: float, length: int) -> tuple[bool, str, float]:
            if length <= 5 and comp < 0.6:
                return (True, "timeline_text_simple", 0.90)
            return (False, "timeline_complex_use_mermaid", 0.85)

        def _check_data_flow(comp: float, length: int) -> tuple[bool, str, float]:
            if length <= 4 and comp < 0.5:
                return (True, "data_flow_text_simple", 0.85)
            return (False, "data_flow_complex_use_mermaid", 0.90)

        def _check_data_structure(comp: float, length: int) -> tuple[bool, str, float]:
            if comp < 0.6 and length <= 5:
                return (True, "data_structure_text_simple", 0.85)
            return (False, "data_structure_complex_use_svg", 0.80)

        def _check_network_topology(
            comp: float, length: int
        ) -> tuple[bool, str, float]:
            if length <= 4 and comp < 0.6:
                return (True, "network_text_simple", 0.80)
            return (False, "network_complex_use_mermaid", 0.90)

        def _check_scientific_process(
            comp: float, length: int
        ) -> tuple[bool, str, float]:
            if comp < 0.5 and length <= 5:
                return (True, "scientific_text_simple", 0.75)
            return (False, "scientific_complex_use_mermaid", 0.85)

        def _check_algorithm(comp: float, length: int) -> tuple[bool, str, float]:
            if comp < 0.6 and length <= 6:
                return (True, "algorithm_text_simple", 0.80)
            return (False, "algorithm_complex_use_mermaid", 0.90)

        def _check_system_architecture(
            comp: float, length: int
        ) -> tuple[bool, str, float]:
            if comp < 0.5 and length <= 4:
                return (True, "architecture_text_simple", 0.70)
            return (False, "architecture_complex_use_svg", 0.90)

        # Safe dispatch via dictionary
        concept_checkers: dict[str, Callable[[float, int], tuple[bool, str, float]]] = {
            "hierarchy": _check_hierarchy,
            "process_flow": _check_process_flow,
            "comparison": _check_comparison,
            "timeline": _check_timeline,
            "data_flow": _check_data_flow,
            "data_structure": _check_data_structure,
            "network_topology": _check_network_topology,
            "scientific_process": _check_scientific_process,
            "algorithm": _check_algorithm,
            "system_architecture": _check_system_architecture,
        }

        checker = concept_checkers.get(concept_type)
        if checker:
            return checker(complexity, content_length)

        # Default: unknown type
        logger.warning(f"Unknown concept type: {concept_type}")
        return (False, "unknown_concept_type", 0.5)

    def get_all_recommendations(
        self,
        concept_type: str,
        complexity: float,
        content_length: int,
    ) -> dict:
        """Get detailed recommendations including all candidate formats.

        Args:
            concept_type: Type of concept
            complexity: Complexity score
            content_length: Content length

        Returns:
            Dict with text recommendation plus rationale and alternatives
        """
        text_use, text_reason, text_confidence = self.should_use_text(
            concept_type, complexity, content_length
        )

        recommendations = {
            "text": {
                "recommended": text_use,
                "reason": text_reason,
                "confidence": text_confidence,
                "cost_multiplier": 1.0,
                "quality_range": "0.6-0.95",
            },
            "mermaid": {
                "recommended": not text_use or text_confidence < 0.75,
                "reason": "Good for flows and diagrams",
                "confidence": 0.85,
                "cost_multiplier": 0.8,
                "quality_range": "0.8-1.0",
            },
            "svg": {
                "recommended": complexity > 0.7 or content_length > 8,
                "reason": "Best for complex visuals",
                "confidence": 0.90,
                "cost_multiplier": 2.0,
                "quality_range": "0.9-1.0",
            },
        }

        return recommendations
