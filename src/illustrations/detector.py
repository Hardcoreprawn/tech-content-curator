"""Concept detection engine for identifying illustration opportunities.

Detects high-value concepts in article content that would benefit from visual aids.
Performs keyword analysis, structural pattern detection, and content density analysis.
"""

from dataclasses import dataclass


@dataclass
class Concept:
    """A detected concept that would benefit from visualization."""

    name: str
    """Name of the concept (e.g., 'network_topology', 'data_flow')"""

    keywords: list[str]
    """Keywords that triggered detection"""

    confidence: float
    """Confidence score from 0.0 to 1.0"""

    visual_types: list[str]
    """Suggested visual types: 'svg', 'mermaid', 'ascii', 'code_block'"""

    description: str = ""
    """Optional description of what to visualize"""


class ConceptDetector:
    """Detects concepts in article content that would benefit from illustrations."""

    # Concept patterns with detection keywords and metadata
    CONCEPT_PATTERNS = {
        "network_topology": {
            "keywords": [
                "nat",
                "router",
                "ip address",
                "packet",
                "routing",
                "network",
                "gateway",
                "firewall",
                "vpn",
                "protocol",
            ],
            "visual_types": ["svg", "mermaid"],
            "confidence_base": 0.75,
            "description": "Network architecture and data flow diagrams",
        },
        "system_architecture": {
            "keywords": [
                "architecture",
                "components",
                "microservices",
                "layers",
                "modules",
                "service",
                "cluster",
                "infrastructure",
            ],
            "visual_types": ["svg", "mermaid"],
            "confidence_base": 0.70,
            "description": "System component relationships and interactions",
        },
        "data_flow": {
            "keywords": [
                "pipeline",
                "processing",
                "transform",
                "workflow",
                "data flow",
                "input",
                "output",
                "stage",
                "step",
            ],
            "visual_types": ["mermaid", "ascii"],
            "confidence_base": 0.65,
            "description": "Data transformation and workflow sequences",
        },
        "scientific_process": {
            "keywords": [
                "methodology",
                "experiment",
                "analysis",
                "lifecycle",
                "research",
                "procedure",
                "method",
                "hypothesis",
            ],
            "visual_types": ["svg", "mermaid"],
            "confidence_base": 0.75,
            "description": "Scientific methods and experimental workflows",
        },
        "comparison": {
            "keywords": [
                "versus",
                "comparison",
                "differences",
                "pros and cons",
                "vs",
                "advantage",
                "disadvantage",
                "tradeoff",
            ],
            "visual_types": ["ascii", "svg"],
            "confidence_base": 0.60,
            "description": "Comparative analysis and feature matrices",
        },
        "algorithm": {
            "keywords": [
                "algorithm",
                "steps",
                "procedure",
                "optimization",
                "search",
                "sort",
                "logic",
            ],
            "visual_types": ["mermaid", "code_block"],
            "confidence_base": 0.65,
            "description": "Algorithm flows and logical sequences",
        },
    }

    def detect(self, content: str) -> list[Concept]:
        """Detect concepts in article content.

        Args:
            content: Article markdown content to analyze

        Returns:
            List of detected concepts, sorted by confidence (highest first)
        """
        concepts: dict[str, Concept] = {}
        content_lower = content.lower()

        # Detect each concept pattern
        for concept_name, pattern in self.CONCEPT_PATTERNS.items():
            keywords = pattern["keywords"]
            matches = sum(1 for kw in keywords if kw in content_lower)

            if matches > 0:
                # Calculate confidence based on keyword density
                confidence = min(
                    0.95,
                    pattern["confidence_base"] + (matches * 0.05),
                )

                concepts[concept_name] = Concept(
                    name=concept_name,
                    keywords=[kw for kw in keywords if kw in content_lower],
                    confidence=confidence,
                    visual_types=pattern["visual_types"],
                    description=pattern["description"],
                )

        # Sort by confidence, highest first
        sorted_concepts = sorted(
            concepts.values(), key=lambda c: c.confidence, reverse=True
        )

        return sorted_concepts

    def filter_by_confidence(
        self, concepts: list[Concept], min_confidence: float
    ) -> list[Concept]:
        """Filter concepts by confidence threshold.

        Args:
            concepts: List of concepts to filter
            min_confidence: Minimum confidence score (0.0 to 1.0)

        Returns:
            Filtered list of concepts meeting confidence threshold
        """
        return [c for c in concepts if c.confidence >= min_confidence]

    def limit_by_type(
        self, concepts: list[Concept], visual_type: str | None = None
    ) -> list[Concept]:
        """Filter concepts by supported visual type.
        Args:
            concepts: List of concepts to filter
            visual_type: If specified, only return concepts supporting this type

        Returns:
            Filtered list of concepts (or all if visual_type is None)
        """
        if visual_type is None:
            return concepts

        return [c for c in concepts if visual_type in c.visual_types]


def detect_concepts(content: str, min_confidence: float = 0.7) -> list[Concept]:
    """Convenience function to detect concepts in article content.

    Args:
        content: Article markdown content to analyze
        min_confidence: Minimum confidence threshold (default 0.7)

    Returns:
        List of detected concepts meeting confidence threshold, sorted by confidence
    """
    detector = ConceptDetector()
    concepts = detector.detect(content)
    return detector.filter_by_confidence(concepts, min_confidence)
