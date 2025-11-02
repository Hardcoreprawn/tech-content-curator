"""Intelligent advisor for text-based vs other illustration formats.

Routes illustration generation to the most appropriate format (text, mermaid, svg)
based on concept type, complexity, and content characteristics. Provides confidence
scores and reasoning for orchestrator decision-making.
"""


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
        requirements = requirements or {}

        # Decision tree based on concept type
        if concept_type == "hierarchy":
            # Trees work well in text if simple
            if complexity < 0.7 and content_length <= 6:
                return (True, "hierarchy_text_tree_simple", 0.95)
            elif complexity < 0.6 and content_length <= 8:
                return (True, "hierarchy_text_tree_moderate", 0.80)
            return (False, "hierarchy_complex_use_svg", 0.85)

        elif concept_type == "process_flow":
            # Simple linear flows work in text
            if content_length <= 3 and complexity < 0.6:
                return (True, "process_text_simple_linear", 0.90)
            elif content_length <= 5 and complexity < 0.5:
                return (True, "process_text_simple_sequence", 0.75)
            return (False, "process_complex_use_mermaid", 0.85)

        elif concept_type == "comparison":
            # Comparisons = tables, perfect for ASCII
            if content_length <= 8:
                return (True, "comparison_text_table_ideal", 0.95)
            return (False, "comparison_complex_use_svg", 0.80)

        elif concept_type == "timeline":
            # Simple timelines work in text
            if content_length <= 5 and complexity < 0.6:
                return (True, "timeline_text_simple", 0.90)
            return (False, "timeline_complex_use_mermaid", 0.85)

        elif concept_type == "data_flow":
            # Simple pipelines/flows work, complex ones need mermaid
            if content_length <= 4 and complexity < 0.5:
                return (True, "data_flow_text_simple", 0.85)
            return (False, "data_flow_complex_use_mermaid", 0.90)

        elif concept_type == "data_structure":
            # Simple structures (linked list, stack) work, trees/graphs need svg
            if complexity < 0.6 and content_length <= 5:
                return (True, "data_structure_text_simple", 0.85)
            return (False, "data_structure_complex_use_svg", 0.80)

        elif concept_type == "network_topology":
            # Simple networks (2-4 nodes) can work in text
            if content_length <= 4 and complexity < 0.6:
                return (True, "network_text_simple", 0.80)
            return (False, "network_complex_use_mermaid", 0.90)

        elif concept_type == "scientific_process":
            # Methodologies/procedures can work in text if simple
            if complexity < 0.5 and content_length <= 5:
                return (True, "scientific_text_simple", 0.75)
            return (False, "scientific_complex_use_mermaid", 0.85)

        elif concept_type == "algorithm":
            # Algorithms in text work for simple procedural steps
            if complexity < 0.6 and content_length <= 6:
                return (True, "algorithm_text_simple", 0.80)
            return (False, "algorithm_complex_use_mermaid", 0.90)

        elif concept_type == "system_architecture":
            # Complex architectures need SVG, simple ones can use text
            if complexity < 0.5 and content_length <= 4:
                return (True, "architecture_text_simple", 0.70)
            return (False, "architecture_complex_use_svg", 0.90)

        # Default: uncertain
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
