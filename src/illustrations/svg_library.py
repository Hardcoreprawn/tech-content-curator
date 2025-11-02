"""SVG template library for hand-crafted educational diagrams.

Provides a collection of pre-designed SVG templates that can be used directly
or as a basis for generating custom diagrams.
"""

from dataclasses import dataclass


@dataclass
class SVGTemplate:
    """A hand-crafted SVG diagram template."""

    name: str
    """Unique identifier for the template"""

    title: str
    """Human-readable title"""

    description: str
    """What the template visualizes"""

    concepts: list[str]
    """Concept types this template addresses (e.g., ['network_topology', 'data_flow'])"""

    alt_text: str
    """Accessibility alt-text for the diagram"""

    svg_content: str
    """The SVG markup"""

    tags: list[str] = None
    """Optional tags for categorization (e.g., ['networking', 'architecture'])"""

    def __post_init__(self):
        """Initialize default values."""
        if self.tags is None:
            self.tags = []


class SVGTemplateLibrary:
    """Manager for the SVG template collection."""

    def __init__(self):
        """Initialize the template library."""
        self._templates: dict[str, SVGTemplate] = {}
        self._load_templates()

    def _load_templates(self):
        """Load all SVG templates into memory."""
        # Initialize templates programmatically
        # In Phase 1, templates are created inline. Phase 3 can load from disk.

        # NAT Translation Diagram - Priority template for networking articles
        self._templates["nat_translation"] = SVGTemplate(
            name="nat_translation",
            title="NAT Translation Process",
            description="Shows how Network Address Translation translates private IPs to public IPs",
            concepts=["network_topology"],
            alt_text="Diagram showing NAT translation: private IP addresses on the left going through a NAT router in the center, emerging as public IP addresses on the right, with a translation table in the middle",
            svg_content=self._create_nat_translation_svg(),
            tags=["networking", "NAT", "IP-addressing"],
        )

        # Packet Flow Diagram
        self._templates["packet_flow"] = SVGTemplate(
            name="packet_flow",
            title="Network Packet Flow",
            description="Illustrates how data packets flow through a network",
            concepts=["network_topology", "data_flow"],
            alt_text="Diagram showing a packet journey through network devices: source, router, gateway, destination",
            svg_content=self._create_packet_flow_svg(),
            tags=["networking", "data-flow"],
        )

        # Network Topology
        self._templates["network_topology"] = SVGTemplate(
            name="network_topology",
            title="Generic Network Topology",
            description="Basic network topology showing connected devices and segments",
            concepts=["network_topology", "system_architecture"],
            alt_text="Network diagram showing interconnected devices including workstations, servers, routers, and the internet",
            svg_content=self._create_network_topology_svg(),
            tags=["networking", "architecture"],
        )

        # System Architecture
        self._templates["system_architecture"] = SVGTemplate(
            name="system_architecture",
            title="System Architecture Components",
            description="Generic system architecture showing layered components",
            concepts=["system_architecture"],
            alt_text="Layered system architecture diagram: clients, API layer, service layer, data layer",
            svg_content=self._create_system_architecture_svg(),
            tags=["architecture", "systems"],
        )

        # Data Pipeline
        self._templates["data_pipeline"] = SVGTemplate(
            name="data_pipeline",
            title="Data Processing Pipeline",
            description="Shows stages of data processing and transformation",
            concepts=["data_flow"],
            alt_text="Pipeline diagram: Input data → Extraction → Transformation → Loading → Output",
            svg_content=self._create_data_pipeline_svg(),
            tags=["data", "pipeline", "ETL"],
        )

    def _create_nat_translation_svg(self) -> str:
        """Create NAT translation diagram SVG."""
        return """<svg viewBox="0 0 800 300" xmlns="http://www.w3.org/2000/svg" class="illustration">
  <style>
    .net-box { fill: #e8f4f8; stroke: #0066cc; stroke-width: 2; }
    .label { font-family: Arial, sans-serif; font-size: 14px; fill: #333; }
    .title { font-family: Arial, sans-serif; font-size: 16px; font-weight: bold; fill: #000; }
    .arrow { stroke: #666; stroke-width: 2; fill: none; marker-end: url(#arrowhead); }
    .device { fill: #fff; stroke: #333; stroke-width: 2; }
  </style>
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <polygon points="0 0, 10 3, 0 6" fill="#666" />
    </marker>
  </defs>

  <text x="400" y="25" text-anchor="middle" class="title">Network Address Translation (NAT)</text>

  <!-- Private network -->
  <rect x="20" y="60" width="150" height="220" class="net-box" rx="5"/>
  <text x="95" y="85" text-anchor="middle" class="label" font-weight="bold">Private Network</text>

  <rect x="35" y="110" width="120" height="40" class="device" rx="3"/>
  <text x="95" y="135" text-anchor="middle" class="label">192.168.1.10</text>

  <rect x="35" y="165" width="120" height="40" class="device" rx="3"/>
  <text x="95" y="190" text-anchor="middle" class="label">192.168.1.20</text>

  <!-- NAT Router -->
  <rect x="330" y="100" width="140" height="140" class="device" rx="5"/>
  <text x="400" y="130" text-anchor="middle" class="label" font-weight="bold">NAT Router</text>
  <text x="400" y="155" text-anchor="middle" class="label" font-size="12">Translation</text>
  <text x="400" y="175" text-anchor="middle" class="label" font-size="12">Table</text>
  <text x="400" y="195" text-anchor="middle" class="label" font-size="11">192.168.1.10</text>
  <text x="400" y="210" text-anchor="middle" class="label" font-size="11">→ 203.0.113.1</text>

  <!-- Public network -->
  <rect x="630" y="60" width="150" height="220" class="net-box" rx="5"/>
  <text x="705" y="85" text-anchor="middle" class="label" font-weight="bold">Public Internet</text>

  <rect x="645" y="110" width="120" height="40" class="device" rx="3"/>
  <text x="705" y="135" text-anchor="middle" class="label">203.0.113.1</text>

  <!-- Arrows -->
  <path d="M 170 130 Q 290 130 330 140" class="arrow"/>
  <path d="M 170 190 Q 290 170 330 180" class="arrow"/>
  <path d="M 470 160 Q 550 160 630 130" class="arrow"/>
</svg>"""

    def _create_packet_flow_svg(self) -> str:
        """Create packet flow diagram SVG."""
        return """<svg viewBox="0 0 800 200" xmlns="http://www.w3.org/2000/svg" class="illustration">
  <style>
    .device { fill: #e8f4f8; stroke: #0066cc; stroke-width: 2; }
    .label { font-family: Arial, sans-serif; font-size: 12px; fill: #333; }
    .title { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; fill: #000; }
    .arrow { stroke: #ff6b6b; stroke-width: 3; fill: none; marker-end: url(#arrowhead); }
  </style>
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <polygon points="0 0, 10 3, 0 6" fill="#ff6b6b" />
    </marker>
  </defs>

  <text x="400" y="25" text-anchor="middle" class="title">Packet Flow Through Network</text>

  <circle cx="60" cy="100" r="30" class="device"/>
  <text x="60" y="105" text-anchor="middle" class="label">Source</text>

  <rect x="140" y="70" width="60" height="60" class="device" rx="5"/>
  <text x="170" y="105" text-anchor="middle" class="label">Router 1</text>

  <rect x="280" y="70" width="60" height="60" class="device" rx="5"/>
  <text x="310" y="105" text-anchor="middle" class="label">Router 2</text>

  <rect x="420" y="70" width="60" height="60" class="device" rx="5"/>
  <text x="450" y="105" text-anchor="middle" class="label">Gateway</text>

  <circle cx="580" cy="100" r="30" class="device"/>
  <text x="580" y="105" text-anchor="middle" class="label">Dest</text>

  <!-- Arrows -->
  <path d="M 90 100 L 140 100" class="arrow"/>
  <path d="M 200 100 L 280 100" class="arrow"/>
  <path d="M 340 100 L 420 100" class="arrow"/>
  <path d="M 480 100 L 550 100" class="arrow"/>

  <!-- Time labels -->
  <text x="115" y="135" text-anchor="middle" class="label" font-size="10">t=1</text>
  <text x="255" y="135" text-anchor="middle" class="label" font-size="10">t=2</text>
  <text x="395" y="135" text-anchor="middle" class="label" font-size="10">t=3</text>
  <text x="535" y="135" text-anchor="middle" class="label" font-size="10">t=4</text>
</svg>"""

    def _create_network_topology_svg(self) -> str:
        """Create network topology diagram SVG."""
        return """<svg viewBox="0 0 700 300" xmlns="http://www.w3.org/2000/svg" class="illustration">
  <style>
    .device { fill: #e8f4f8; stroke: #0066cc; stroke-width: 2; }
    .label { font-family: Arial, sans-serif; font-size: 11px; fill: #333; text-anchor: middle; }
    .title { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; fill: #000; }
    .line { stroke: #0066cc; stroke-width: 1.5; }
  </style>

  <text x="350" y="20" text-anchor="middle" class="title">Network Topology</text>

  <!-- Internet -->
  <rect x="300" y="30" width="100" height="40" class="device" rx="3"/>
  <text x="350" y="57" class="label">Internet</text>

  <!-- Router -->
  <rect x="300" y="110" width="100" height="40" class="device" rx="3"/>
  <text x="350" y="137" class="label">Router</text>

  <!-- Workstations -->
  <rect x="50" y="210" width="80" height="40" class="device" rx="3"/>
  <text x="90" y="237" class="label">Workstation 1</text>

  <rect x="180" y="210" width="80" height="40" class="device" rx="3"/>
  <text x="220" y="237" class="label">Workstation 2</text>

  <!-- Server -->
  <rect x="310" y="210" width="80" height="40" class="device" rx="3"/>
  <text x="350" y="237" class="label">Server</text>

  <!-- Printer -->
  <rect x="440" y="210" width="80" height="40" class="device" rx="3"/>
  <text x="480" y="237" class="label">Printer</text>

  <!-- Connections -->
  <line x1="350" y1="70" x2="350" y2="110" class="line"/>
  <line x1="350" y1="150" x2="90" y2="210" class="line"/>
  <line x1="350" y1="150" x2="220" y2="210" class="line"/>
  <line x1="350" y1="150" x2="350" y2="210" class="line"/>
  <line x1="350" y1="150" x2="480" y2="210" class="line"/>
</svg>"""

    def _create_system_architecture_svg(self) -> str:
        """Create system architecture diagram SVG."""
        return """<svg viewBox="0 0 600 350" xmlns="http://www.w3.org/2000/svg" class="illustration">
  <style>
    .layer { fill: #e8f4f8; stroke: #0066cc; stroke-width: 2; }
    .label { font-family: Arial, sans-serif; font-size: 12px; fill: #333; }
    .title { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; fill: #000; }
  </style>

  <text x="300" y="20" text-anchor="middle" class="title">System Architecture</text>

  <!-- Client Layer -->
  <rect x="50" y="50" width="500" height="50" class="layer" rx="3"/>
  <text x="300" y="82" text-anchor="middle" class="label">Client Applications</text>

  <!-- API Layer -->
  <rect x="50" y="120" width="500" height="50" class="layer" rx="3"/>
  <text x="300" y="152" text-anchor="middle" class="label">API Gateway</text>

  <!-- Service Layer -->
  <rect x="50" y="190" width="200" height="50" class="layer" rx="3"/>
  <text x="150" y="222" text-anchor="middle" class="label">Service A</text>

  <rect x="300" y="190" width="200" height="50" class="layer" rx="3"/>
  <text x="400" y="222" text-anchor="middle" class="label">Service B</text>

  <!-- Data Layer -->
  <rect x="50" y="260" width="200" height="50" class="layer" rx="3"/>
  <text x="150" y="292" text-anchor="middle" class="label">Database</text>

  <rect x="300" y="260" width="200" height="50" class="layer" rx="3"/>
  <text x="400" y="292" text-anchor="middle" class="label">Cache</text>

  <!-- Arrows -->
  <line x1="300" y1="100" x2="300" y2="120" stroke="#666" stroke-width="2"/>
  <line x1="200" y1="170" x2="150" y2="190" stroke="#666" stroke-width="2"/>
  <line x1="400" y1="170" x2="400" y2="190" stroke="#666" stroke-width="2"/>
  <line x1="150" y1="240" x2="150" y2="260" stroke="#666" stroke-width="2"/>
  <line x1="400" y1="240" x2="400" y2="260" stroke="#666" stroke-width="2"/>
</svg>"""

    def _create_data_pipeline_svg(self) -> str:
        """Create data pipeline diagram SVG."""
        return """<svg viewBox="0 0 800 150" xmlns="http://www.w3.org/2000/svg" class="illustration">
  <style>
    .stage { fill: #e8f4f8; stroke: #0066cc; stroke-width: 2; }
    .label { font-family: Arial, sans-serif; font-size: 12px; fill: #333; }
    .title { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; fill: #000; }
    .arrow { stroke: #666; stroke-width: 2; fill: none; marker-end: url(#arrowhead); }
  </style>
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <polygon points="0 0, 10 3, 0 6" fill="#666" />
    </marker>
  </defs>

  <text x="400" y="20" text-anchor="middle" class="title">Data Processing Pipeline</text>

  <rect x="20" y="40" width="90" height="50" class="stage" rx="3"/>
  <text x="65" y="70" text-anchor="middle" class="label">Input</text>

  <rect x="150" y="40" width="90" height="50" class="stage" rx="3"/>
  <text x="195" y="70" text-anchor="middle" class="label">Extract</text>

  <rect x="280" y="40" width="90" height="50" class="stage" rx="3"/>
  <text x="325" y="70" text-anchor="middle" class="label">Transform</text>

  <rect x="410" y="40" width="90" height="50" class="stage" rx="3"/>
  <text x="455" y="70" text-anchor="middle" class="label">Load</text>

  <rect x="540" y="40" width="90" height="50" class="stage" rx="3"/>
  <text x="585" y="70" text-anchor="middle" class="label">Output</text>

  <!-- Arrows -->
  <path d="M 110 65 L 150 65" class="arrow"/>
  <path d="M 240 65 L 280 65" class="arrow"/>
  <path d="M 370 65 L 410 65" class="arrow"/>
  <path d="M 500 65 L 540 65" class="arrow"/>
</svg>"""

    def get(self, template_name: str) -> SVGTemplate | None:
        """Get a template by name.

        Args:
            template_name: The name/id of the template

        Returns:
            SVGTemplate if found, None otherwise
        """
        return self._templates.get(template_name)

    def list_templates(self) -> list[SVGTemplate]:
        """Get all templates in the library.

        Returns:
            List of all available SVGTemplate objects
        """
        return list(self._templates.values())

    def find_by_concept(self, concept: str) -> list[SVGTemplate]:
        """Find templates suitable for a specific concept.

        Args:
            concept: Concept name (e.g., 'network_topology', 'data_flow')

        Returns:
            List of templates that address this concept
        """
        return [t for t in self._templates.values() if concept in t.concepts]

    def find_by_tag(self, tag: str) -> list[SVGTemplate]:
        """Find templates by tag.

        Args:
            tag: Tag to search for (e.g., 'networking', 'architecture')

        Returns:
            List of templates with matching tag
        """
        return [t for t in self._templates.values() if tag in t.tags]
