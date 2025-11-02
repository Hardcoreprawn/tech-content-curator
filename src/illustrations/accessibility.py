"""Accessibility module for WCAG compliance and alt-text generation.

Ensures all illustrations meet accessibility standards including alt-text generation,
SVG accessibility wrapping, and WCAG 2.1 AA compliance checking.
"""

import re
from dataclasses import dataclass


@dataclass
class AccessibilityReport:
    """Report on accessibility compliance of an illustration."""

    wcag_level: str
    """WCAG level achieved: 'A', 'AA', or 'AAA'"""

    is_compliant: bool
    """Whether illustration meets specified WCAG level"""

    issues: list[str]
    """List of identified accessibility issues"""

    warnings: list[str]
    """Non-critical accessibility warnings"""

    alt_text: str
    """Generated alt-text for the illustration"""

    long_description: str | None = None
    """Optional long description for complex diagrams"""

class AccessibilityChecker:
    """Validates and enhances illustrations for accessibility compliance."""

    def __init__(self, target_wcag_level: str = "AA"):
        """Initialize accessibility checker.

        Args:
            target_wcag_level: Target WCAG level ('A', 'AA', or 'AAA')
        """
        self.target_wcag_level = target_wcag_level

    def generate_alt_text(
        self, illustration_name: str, concept_name: str, context: str = ""
    ) -> str:
        """Generate WCAG-compliant alt-text for an illustration.

        Args:
            illustration_name: Name/type of illustration
            concept_name: Primary concept being illustrated
            context: Optional context from article content

        Returns:
            Alt-text suitable for screen readers (max 125 chars for optimization)
        """
        # Map concept names to descriptions
        concept_descriptions = {
            "network_topology": "network diagram showing devices and connections",
            "system_architecture": "system architecture diagram showing layered components",
            "data_flow": "data flow diagram showing processing pipeline stages",
            "scientific_process": "scientific process diagram showing methodology steps",
            "comparison": "comparison diagram showing differences and similarities",
            "algorithm": "algorithm flowchart showing decision points and processes",
        }

        base_description = concept_descriptions.get(concept_name, "technical diagram")

        # Map illustration names to specifics
        if illustration_name == "nat_translation":
            return "NAT translation diagram: private IPs translate to public IP through router"
        elif illustration_name == "packet_flow":
            return "Packet flow diagram: shows data route through network devices"
        elif illustration_name == "network_topology":
            return "Network topology diagram: displays interconnected devices and routing"
        elif illustration_name == "system_architecture":
            return "System architecture: clients, API layer, services, and data layer"
        elif illustration_name == "data_pipeline":
            return "Data pipeline: input → extract → transform → load → output stages"
        elif illustration_name == "simple_flow":
            return "Process flow diagram showing input, processing, and output stages"
        elif illustration_name == "decision_tree":
            return "Decision tree diagram with branching logic paths"
        elif illustration_name == "system_components":
            return "System components diagram showing client, API, services, and database"
        elif illustration_name == "network_flow":
            return "Network flow showing packet routing through routers"
        elif illustration_name == "algorithm_flow":
            return "Algorithm flowchart showing loops and conditional logic"
        else:
            return f"Diagram illustrating {base_description}"

    def generate_long_description(
        self, illustration_name: str, concept_name: str
    ) -> str:
        """Generate detailed description for complex diagrams.

        Provides comprehensive description for screen reader users to understand
        complex visual relationships and data flows.

        Args:
            illustration_name: Name/type of illustration
            concept_name: Primary concept being illustrated

        Returns:
            Long-form description (200-300 characters)
        """
        descriptions = {
            "nat_translation": (
                "This diagram illustrates Network Address Translation. Private IP addresses "
                "from the left (192.168.x.x range) pass through a NAT router in the center, which "
                "maintains a translation table mapping private addresses to public addresses "
                "(203.0.113.x range). Arrows show the translation direction."
            ),
            "packet_flow": (
                "This diagram shows how a network packet travels through a series of routers. "
                "Starting from the source, the packet is forwarded through Router 1, then Router 2, "
                "then through a gateway, before reaching the destination. Each hop is labeled with "
                "timing information (t=1, t=2, etc)."
            ),
            "network_topology": (
                "This network topology diagram shows several device types connected to a central "
                "router. At the top is the Internet connection. Below are workstations (left), a "
                "server (center), and a printer (right), all connected to the router via network "
                "lines representing physical or logical connections."
            ),
            "system_architecture": (
                "This layered system architecture shows four levels: Client Applications at the "
                "top, API Gateway below it, Service A and Service B in the middle layer, and Database "
                "and Cache in the data layer at the bottom. Arrows show data flow between layers."
            ),
            "data_pipeline": (
                "This data pipeline diagram shows five sequential stages: Input data enters the "
                "pipeline, goes through Extract, Transform, Load, and finally Output. Each stage is "
                "represented as a box with arrows showing the flow direction from left to right."
            ),
        }

        return descriptions.get(
            illustration_name,
            f"Detailed diagram related to {concept_name.replace('_', ' ')} concepts",
        )

    def wrap_svg_accessibility(self, svg_content: str, alt_text: str, title: str = "") -> str:
        """Add accessibility elements to SVG markup.

        Adds <title>, <desc>, role attributes, and aria-labels to make SVG
        accessible to screen readers.

        Args:
            svg_content: Original SVG markup
            alt_text: Short alt-text for the diagram
            title: Optional diagram title

        Returns:
            Enhanced SVG with accessibility elements
        """
        # Check if SVG already has accessibility elements
        if "<title>" in svg_content and "<desc>" in svg_content:
            return svg_content

        # Extract viewBox and attributes from opening <svg tag
        svg_match = re.match(r"(<svg[^>]*>)", svg_content)
        if not svg_match:
            return svg_content

        svg_opening = svg_match.group(1)

        # Ensure role is set
        if 'role="' not in svg_opening:
            svg_opening = svg_opening.replace("<svg", '<svg role="img"', 1)

        # Build accessibility section
        accessibility_section = f'  <title>{title or "Diagram"}</title>\n  <desc>{alt_text}</desc>'

        # Insert after opening <svg tag
        enhanced_svg = svg_content.replace(
            svg_match.group(1), svg_opening.rstrip(">") + ">\n" + accessibility_section
        )

        return enhanced_svg

    def validate_wcag_compliance(
        self, illustration_content: str, illustration_type: str = "mermaid"
    ) -> AccessibilityReport:
        """Validate illustration for WCAG compliance.

        Args:
            illustration_content: Illustration markup or code
            illustration_type: Type of illustration ('svg', 'mermaid', 'ascii')

        Returns:
            AccessibilityReport with compliance status and issues
        """
        issues = []
        warnings = []
        alt_text = ""

        if illustration_type == "svg":
            # Check SVG accessibility
            if "<title>" not in illustration_content:
                issues.append("SVG missing <title> element")
            if "<desc>" not in illustration_content:
                issues.append("SVG missing <desc> element")
            if 'role="img"' not in illustration_content:
                warnings.append("SVG missing role='img' attribute")

            # Check for text contrast (basic check)
            if re.search(r"fill=['\"]#fff['\"]|fill=['\"]white['\"]", illustration_content):
                if not re.search(r"fill=['\"]#000['\"]|fill=['\"]black['\"]", illustration_content):
                    warnings.append("Potential low contrast: white fill without dark background")

            alt_text = self._extract_svg_alt_text(illustration_content)

        elif illustration_type == "mermaid":
            # Mermaid accessibility check
            if not illustration_content.strip():
                issues.append("Mermaid diagram is empty")

            # Ensure it has readable structure
            if len(illustration_content) < 20:
                issues.append("Mermaid diagram too simple for accessibility")

            alt_text = f"Mermaid diagram: {illustration_content[:50]}..."

        elif illustration_type == "ascii":
            # ASCII art accessibility
            if len(illustration_content.split("\n")) < 3:
                warnings.append("ASCII diagram very simple, verify it conveys intended meaning")

            alt_text = f"ASCII diagram with {len(illustration_content.split(chr(10)))} lines"

        # Determine compliance level
        is_compliant = len(issues) == 0
        wcag_level = "AA" if is_compliant else "A"

        if not is_compliant and self.target_wcag_level == "AAA":
            wcag_level = "A"

        return AccessibilityReport(
            wcag_level=wcag_level,
            is_compliant=is_compliant and wcag_level == self.target_wcag_level,
            issues=issues,
            warnings=warnings,
            alt_text=alt_text,
            long_description=self.generate_long_description("", ""),
        )

    def _extract_svg_alt_text(self, svg_content: str) -> str:
        """Extract or generate alt-text from SVG content.

        Args:
            svg_content: SVG markup

        Returns:
            Alt-text extracted from SVG or generated from content
        """
        # Try to extract from <desc> tag
        desc_match = re.search(r"<desc[^>]*>([^<]+)</desc>", svg_content)
        if desc_match:
            return desc_match.group(1)

        # Try to extract from <title> tag
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", svg_content)
        if title_match:
            return title_match.group(1)

        # Generate from text content
        text_elements = re.findall(r"<text[^>]*>([^<]+)</text>", svg_content)
        if text_elements:
            return "Diagram showing: " + ", ".join(text_elements[:3])

        return "SVG Diagram"

    def add_markdown_accessibility(
        self, illustration: str, alt_text: str, title: str = ""
    ) -> str:
        """Format illustration for accessible markdown display.

        Args:
            illustration: Illustration content (SVG, code fence, etc)
            alt_text: Alt-text for the illustration
            title: Optional title for the illustration

        Returns:
            Markdown-formatted illustration with accessibility elements
        """
        title_line = f"**Figure**: {title}\n" if title else ""
        alt_text_line = f"*{alt_text}*\n\n"

        return f"{title_line}{alt_text_line}{illustration}"
