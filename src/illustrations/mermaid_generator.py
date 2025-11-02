"""Programmatic Mermaid diagram generation for free visual content.

Generates Mermaid diagrams that can be rendered by Hugo/markdown for
flowcharts, graphs, and other visual representations.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MermaidDiagram:
    """A generated Mermaid diagram."""

    name: str
    """Unique identifier for the diagram"""

    diagram_type: str
    """Type of Mermaid diagram: 'graph', 'flowchart', 'sequence', 'pie', etc."""

    content: str
    """The Mermaid diagram syntax"""

    alt_text: str = ""
    """Accessibility description of the diagram"""

    title: str = ""
    """Optional diagram title"""


class MermaidDiagramGenerator:
    """Generates Mermaid diagrams for various concept types."""

    # Mermaid diagram patterns for different concepts
    DIAGRAM_PATTERNS = {
        "simple_flow": {
            "type": "flowchart",
            "template": """flowchart TD
    A[Input] --> B[Process]
    B --> C[Validation]
    C --> D[Output]""",
            "description": "Simple linear data flow",
        },
        "decision_tree": {
            "type": "flowchart",
            "template": """flowchart TD
    A{{Decision?}} -->|Yes| B[Action A]
    A -->|No| C[Action B]
    B --> D[Result]
    C --> D""",
            "description": "Decision point with branching paths",
        },
        "system_components": {
            "type": "graph",
            "template": """graph LR
    Client[Client] --> API[API Layer]
    API --> ServiceA[Service A]
    API --> ServiceB[Service B]
    ServiceA --> DB[(Database)]
    ServiceB --> Cache[(Cache)]
    Cache --> DB""",
            "description": "System architecture showing component relationships",
        },
        "data_pipeline": {
            "type": "flowchart",
            "template": """flowchart LR
    Input[Raw Data] --> Extract[Extract]
    Extract --> Transform[Transform]
    Transform --> Load[Load]
    Load --> Output[Output]""",
            "description": "ETL/ELT data pipeline stages",
        },
        "network_flow": {
            "type": "flowchart",
            "template": """flowchart TD
    Src[Source] --> Router1[Router 1]
    Router1 --> Router2[Router 2]
    Router2 --> Dest[Destination]
    Src -->|Packet| Router1
    Router1 -->|Forward| Router2
    Router2 -->|Deliver| Dest""",
            "description": "Network packet flow through devices",
        },
        "algorithm_flow": {
            "type": "flowchart",
            "template": """flowchart TD
    Start([Start]) --> Init[Initialize]
    Init --> Loop{Loop Condition}
    Loop -->|Continue| Process[Process Item]
    Process --> Check{Check Result}
    Check -->|Valid| Loop
    Check -->|Invalid| End([End])
    Loop -->|Exit| End""",
            "description": "Generic algorithm flow with loops",
        },
    }

    def generate(
        self, pattern_name: str, custom_title: Optional[str] = None
    ) -> MermaidDiagram:
        """Generate a Mermaid diagram from a pattern.

        Args:
            pattern_name: Name of the pattern to use
            custom_title: Optional custom title for the diagram

        Returns:
            MermaidDiagram with generated content

        Raises:
            ValueError: If pattern_name is not found
        """
        if pattern_name not in self.DIAGRAM_PATTERNS:
            raise ValueError(f"Unknown Mermaid pattern: {pattern_name}")

        pattern = self.DIAGRAM_PATTERNS[pattern_name]

        return MermaidDiagram(
            name=pattern_name,
            diagram_type=pattern["type"],
            content=pattern["template"],
            alt_text=pattern["description"],
            title=custom_title or pattern_name.replace("_", " ").title(),
        )

    def generate_for_concept(self, concept_name: str) -> Optional[MermaidDiagram]:
        """Generate an appropriate Mermaid diagram for a detected concept.

        Args:
            concept_name: Name of the concept (e.g., 'network_topology', 'data_flow')

        Returns:
            MermaidDiagram if a suitable pattern exists, None otherwise
        """
        # Map concepts to best-fit diagram patterns
        concept_patterns = {
            "network_topology": "network_flow",
            "system_architecture": "system_components",
            "data_flow": "data_pipeline",
            "algorithm": "algorithm_flow",
            "comparison": "decision_tree",
            "scientific_process": "simple_flow",
        }

        pattern_name = concept_patterns.get(concept_name)
        if not pattern_name:
            return None

        return self.generate(pattern_name)

    def format_for_markdown(self, diagram: MermaidDiagram) -> str:
        """Format a diagram for inclusion in markdown.

        Wraps the diagram content in markdown code fence with mermaid language tag.

        Args:
            diagram: The MermaidDiagram to format

        Returns:
            Markdown-formatted diagram ready for insertion
        """
        title_line = f"**{diagram.title}**\n\n" if diagram.title else ""
        alt_text_line = f"*{diagram.alt_text}*\n\n" if diagram.alt_text else ""

        return f"{title_line}{alt_text_line}```mermaid\n{diagram.content}\n```"

    def create_custom_flow(
        self, nodes: list[str], edges: list[tuple[str, str]], title: str = ""
    ) -> MermaidDiagram:
        """Create a custom flowchart from nodes and edges.

        This allows dynamic generation of flowcharts for specific article content.

        Args:
            nodes: List of node labels
            edges: List of (source, target) tuples representing connections
            title: Optional diagram title

        Returns:
            Custom MermaidDiagram

        Raises:
            ValueError: If nodes or edges are invalid
        """
        if not nodes:
            raise ValueError("At least one node is required")

        if len(nodes) > 20:
            raise ValueError("Maximum 20 nodes for custom flowcharts")

        # Create flowchart syntax
        lines = ["flowchart TD"]

        # Add nodes
        node_ids = {}
        for i, node_label in enumerate(nodes):
            node_id = f"N{i}"
            node_ids[node_label] = node_id
            # Use box for regular nodes, circles for start/end
            if node_label.lower() in ("start", "begin"):
                lines.append(f"    {node_id}([{node_label}])")
            elif node_label.lower() in ("end", "finish"):
                lines.append(f"    {node_id}([{node_label}])")
            else:
                lines.append(f"    {node_id}[{node_label}]")

        # Add edges
        for source, target in edges:
            source_id = node_ids.get(source)
            target_id = node_ids.get(target)

            if source_id and target_id:
                lines.append(f"    {source_id} --> {target_id}")

        content = "\n".join(lines)

        return MermaidDiagram(
            name="custom_flow",
            diagram_type="flowchart",
            content=content,
            alt_text="Custom process flow diagram",
            title=title or "Process Flow",
        )

    def list_patterns(self) -> list[str]:
        """Get names of all available patterns.

        Returns:
            List of pattern names
        """
        return list(self.DIAGRAM_PATTERNS.keys())

    def get_pattern_info(self, pattern_name: str) -> Optional[dict]:
        """Get information about a specific pattern.

        Args:
            pattern_name: Name of the pattern

        Returns:
            Pattern information dict, or None if not found
        """
        return self.DIAGRAM_PATTERNS.get(pattern_name)
