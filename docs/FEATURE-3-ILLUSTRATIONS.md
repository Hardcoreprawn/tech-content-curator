# Feature 3: Concept Illustrations

**Goal**: Add SVG diagrams for key concepts  
**Effort**: 4-5 days (includes SVG creation)  
**Cost Impact**: $0.00-0.060 per article (free SVGs + optional AI fallback)

---

## What to Build

1. Create a library of reusable SVG diagrams (5-10 templates)
2. Detect key concepts in articles
3. Embed SVGs inline in markdown
4. Fallback to Mermaid diagrams or DALL-E if no matching template

**Example**: Owl flight article → auto-insert SVG of wing mechanics + Mermaid diagram of flight phases

---

## Files to Create

### `src/illustrations/__init__.py`
```python
from .generator import IllustrationGenerator
from .concepts import ConceptDetector
__all__ = ["IllustrationGenerator", "ConceptDetector"]
```

### `src/illustrations/concepts.py` (~100 lines)

```python
"""Detect key concepts for illustration."""
from dataclasses import dataclass

@dataclass
class Concept:
    name: str                    # "wing mechanics"
    svg_template: str | None     # "wing_mechanics.svg"
    mermaid_diagram: str | None  # Mermaid syntax
    confidence: float            # 0-1
    position: int                # Where to insert in article

class ConceptDetector:
    """Identify concepts suitable for illustration."""
    
    # Map keywords → concept definitions
    CONCEPT_MAP = {
        "aerodynamics": {
            "keywords": ["lift", "drag", "wing", "airflow", "vortex"],
            "svg_template": "aerodynamics_diagram.svg",
            "mermaid": "graph TD\n    A[Air Flow] --> B[Pressure Difference]\n    B --> C[Lift]"
        },
        "lifecycle": {
            "keywords": ["metamorphosis", "pupae", "larvae", "emerge", "development", "cycle"],
            "svg_template": "lifecycle_cycle.svg",
            "mermaid": None  # SVG only
        },
        "neural_network": {
            "keywords": ["neural", "neurons", "layer", "activation", "weights"],
            "svg_template": "neural_network.svg",
            "mermaid": None
        },
        "algorithm": {
            "keywords": ["algorithm", "steps", "input", "output", "flow"],
            "svg_template": None,  # Mermaid is better
            "mermaid": "graph TD\n    A[Input] --> B[Process]\n    B --> C[Output]"
        },
        "molecular_structure": {
            "keywords": ["molecule", "atom", "bond", "structure", "element"],
            "svg_template": "molecular_structure.svg",
            "mermaid": None
        }
    }
    
    def detect(self, title: str, content: str) -> list[Concept]:
        """Find concepts in article."""
        concepts = []
        content_lower = content.lower()
        
        for concept_name, config in self.CONCEPT_MAP.items():
            # Count keyword matches
            matches = sum(
                content_lower.count(keyword)
                for keyword in config["keywords"]
            )
            
            if matches >= 2:  # Need at least 2 keyword matches
                confidence = min(matches / 5, 1.0)  # Cap at 1.0
                
                concepts.append(Concept(
                    name=concept_name,
                    svg_template=config.get("svg_template"),
                    mermaid_diagram=config.get("mermaid"),
                    confidence=confidence,
                    position=self._find_best_position(content, config["keywords"])
                ))
        
        return sorted(concepts, key=lambda c: c.confidence, reverse=True)[:2]  # Max 2
    
    def _find_best_position(self, content: str, keywords: list[str]) -> int:
        """Find best place to insert illustration."""
        # Insert after first paragraph (usually intro)
        first_newline = content.find("\n\n")
        return first_newline if first_newline > 0 else len(content) // 3
```

### `src/illustrations/library.py` (~100 lines)

```python
"""SVG template library."""
from pathlib import Path
from dataclasses import dataclass

@dataclass
class SVGTemplate:
    name: str
    content: str  # SVG XML
    keywords: list[str]
    credits: str  # Attribution

class SVGLibrary:
    """Load and manage SVG templates."""
    
    def __init__(self, templates_dir: str = "src/illustrations/svg_templates"):
        self.templates_dir = Path(templates_dir)
        self.templates = self._load_templates()
    
    def _load_templates(self) -> dict[str, SVGTemplate]:
        """Load all SVG files from directory."""
        templates = {}
        
        for svg_file in self.templates_dir.glob("*.svg"):
            with open(svg_file) as f:
                content = f.read()
            
            templates[svg_file.stem] = SVGTemplate(
                name=svg_file.stem,
                content=content,
                keywords=self._extract_keywords(svg_file.stem),
                credits=self._extract_credits(content)
            )
        
        return templates
    
    def get(self, name: str) -> SVGTemplate | None:
        """Get template by name."""
        return self.templates.get(name)
    
    def _extract_keywords(self, filename: str) -> list[str]:
        """Convert filename to keywords."""
        return filename.replace("_", " ").split()
    
    def _extract_credits(self, svg_content: str) -> str:
        """Extract credits from SVG comment."""
        # Look for <!-- credits: ... --> comment
        import re
        match = re.search(r'<!-- credits: (.*?) -->', svg_content)
        return match.group(1) if match else "Unknown"
```

### `src/illustrations/generator.py` (~200 lines)

```python
"""Generate illustrations for articles."""
from dataclasses import dataclass
import httpx
from openai import OpenAI
from rich.console import Console

from .concepts import ConceptDetector, Concept
from .library import SVGLibrary
from src.config import PipelineConfig

console = Console()

@dataclass
class Illustration:
    markdown: str  # Ready to embed
    type: str  # "svg", "mermaid", "dalle"
    concept: str  # e.g., "wing mechanics"
    cost: float

class IllustrationGenerator:
    """Generate concept illustrations."""
    
    def __init__(self, openai_client: OpenAI, config: PipelineConfig):
        self.client = openai_client
        self.config = config
        self.detector = ConceptDetector()
        self.svg_library = SVGLibrary()
    
    def generate(self, title: str, content: str) -> list[Illustration]:
        """Generate illustrations for article."""
        concepts = self.detector.detect(title, content)
        illustrations = []
        
        total_cost = 0
        
        for concept in concepts:
            # Try each tier in order
            
            # Tier 1: SVG template (FREE)
            if concept.svg_template:
                ill = self._use_svg_template(concept)
                if ill:
                    illustrations.append(ill)
                    continue
            
            # Tier 2: Mermaid diagram (FREE)
            if concept.mermaid_diagram:
                ill = self._use_mermaid(concept)
                if ill:
                    illustrations.append(ill)
                    continue
            
            # Tier 3: AI-generated (PAID, gated by budget/quality)
            if (total_cost < self.config.illustration_budget and 
                concept.confidence >= 0.8):
                ill = self._generate_dalle(concept)
                if ill:
                    illustrations.append(ill)
                    total_cost += ill.cost
        
        return illustrations
    
    def _use_svg_template(self, concept: Concept) -> Illustration | None:
        """Use existing SVG from library."""
        template = self.svg_library.get(concept.svg_template)
        
        if not template:
            return None
        
        # Embed as base64 data URI
        import base64
        b64 = base64.b64encode(template.content.encode()).decode()
        
        markdown = f"""
![{concept.name}](data:image/svg+xml;base64,{b64})

> SVG illustration of {concept.name}. Credit: {template.credits}
"""
        
        return Illustration(
            markdown=markdown,
            type="svg",
            concept=concept.name,
            cost=0.0
        )
    
    def _use_mermaid(self, concept: Concept) -> Illustration | None:
        """Render Mermaid diagram (Hugo supports this)."""
        
        markdown = f"""
```mermaid
{concept.mermaid_diagram}
```

Diagram showing {concept.name} flow.
"""
        
        return Illustration(
            markdown=markdown,
            type="mermaid",
            concept=concept.name,
            cost=0.0
        )
    
    def _generate_dalle(self, concept: Concept) -> Illustration | None:
        """Generate diagram via DALL-E (last resort, $0.020)."""
        
        # Only if budget allows and confidence is high
        if self.config.illustration_budget < 0.02:
            return None
        
        prompt = f"""Create a scientific diagram showing {concept.name}.
        
Make it:
- Clean and minimalist
- Educational (suitable for blog article)
- Black and white or muted colors
- Professional appearance

This is for a technical blog post."""
        
        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1
            )
            
            url = response.data[0].url
            
            markdown = f"""
![{concept.name}]({url})

> AI-generated diagram of {concept.name}
"""
            
            return Illustration(
                markdown=markdown,
                type="dalle",
                concept=concept.name,
                cost=0.020
            )
        except Exception as e:
            console.print(f"[yellow]DALL-E generation failed: {e}[/yellow]")
        
        return None
    
    def inject_into_content(self, content: str, illustrations: list[Illustration]) -> str:
        """Insert illustrations at best positions in markdown."""
        
        # Insert after first section header
        lines = content.split("\n")
        
        for i, line in enumerate(lines):
            if line.startswith("##"):  # First h2
                # Insert after this section
                insert_pos = i + 2  # After blank line
                for illustration in illustrations:
                    lines.insert(insert_pos, illustration.markdown)
                    insert_pos += 2
                break
        
        return "\n".join(lines)
```

---

## SVG Templates to Create

Create these 5 templates in `src/illustrations/svg_templates/`:

### `aerodynamics_diagram.svg`
```xml
<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">
  <!-- Wing cross-section -->
  <path d="M 50 150 Q 150 50 250 150" stroke="black" fill="lightblue" stroke-width="2"/>
  
  <!-- Pressure lines (upper) -->
  <line x1="100" y1="100" x2="80" y2="80" stroke="red" stroke-width="2" marker-end="url(#arrowred)"/>
  <line x1="150" y1="60" x2="150" y2="20" stroke="red" stroke-width="2"/>
  <line x1="200" y1="100" x2="220" y2="80" stroke="red" stroke-width="2"/>
  
  <!-- Pressure lines (lower) -->
  <line x1="100" y1="200" x2="80" y2="220" stroke="blue" stroke-width="2"/>
  <line x1="150" y1="240" x2="150" y2="280" stroke="blue" stroke-width="2"/>
  <line x1="200" y1="200" x2="220" y2="220" stroke="blue" stroke-width="2"/>
  
  <!-- Labels -->
  <text x="150" y="40" text-anchor="middle" font-size="14">Lower Pressure</text>
  <text x="150" y="290" text-anchor="middle" font-size="14">Higher Pressure</text>
  <text x="300" y="150" font-size="14">Lift ↑</text>
  
  <!-- Arrow definitions -->
  <defs>
    <marker id="arrowred" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <polygon points="0 0, 10 3, 0 6" fill="red"/>
    </marker>
  </defs>
  
  <!-- credits: Aerodynamics tutorial, CC0 -->
</svg>
```

### `lifecycle_cycle.svg`
```xml
<svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg">
  <!-- Circular stages -->
  <circle cx="200" cy="100" r="40" fill="lightblue" stroke="black" stroke-width="2"/>
  <circle cx="300" cy="200" r="40" fill="lightgreen" stroke="black" stroke-width="2"/>
  <circle cx="200" cy="300" r="40" fill="lightyellow" stroke="black" stroke-width="2"/>
  <circle cx="100" cy="200" r="40" fill="lightcoral" stroke="black" stroke-width="2"/>
  
  <!-- Arrows connecting -->
  <path d="M 240 130 L 270 170" stroke="black" stroke-width="2" marker-end="url(#arrow)"/>
  <path d="M 270 240 L 230 270" stroke="black" stroke-width="2" marker-end="url(#arrow)"/>
  <path d="M 160 270 L 130 240" stroke="black" stroke-width="2" marker-end="url(#arrow)"/>
  <path d="M 130 160 L 170 130" stroke="black" stroke-width="2" marker-end="url(#arrow)"/>
  
  <!-- Labels -->
  <text x="200" y="105" text-anchor="middle" font-weight="bold" font-size="12">Egg</text>
  <text x="300" y="205" text-anchor="middle" font-weight="bold" font-size="12">Larva</text>
  <text x="200" y="305" text-anchor="middle" font-weight="bold" font-size="12">Pupa</text>
  <text x="100" y="205" text-anchor="middle" font-weight="bold" font-size="12">Adult</text>
  
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <polygon points="0 0, 10 3, 0 6" fill="black"/>
    </marker>
  </defs>
  
  <!-- credits: Lifecycle diagram, public domain -->
</svg>
```

(Create 3 more: `neural_network.svg`, `molecular_structure.svg`, `algorithm_flow.svg`)

---

## Files to Modify

### `src/config.py`

Add to `PipelineConfig`:
```python
illustration_budget: float = 0.06  # $0.06/article max
enable_illustrations: bool = True
```

### `src/generate.py`

Around line 815 (content finalization):
```python
from src.illustrations import IllustrationGenerator

# In generate_article():
if config.enable_illustrations:
    ill_gen = IllustrationGenerator(client, config)
    illustrations = ill_gen.generate(article.title, article.content)
    
    if illustrations:
        article.content = ill_gen.inject_into_content(
            article.content,
            illustrations
        )
        
        for ill in illustrations:
            costs["illustrations"] = costs.get("illustrations", 0) + ill.cost
```

### `.env.example`

```bash
# Illustrations
ENABLE_ILLUSTRATIONS=true
ILLUSTRATION_BUDGET=0.06
```

---

## Tests to Write

```python
# tests/test_illustrations.py

def test_detect_aerodynamics_concept():
    """Identify 'lift' + 'drag' keywords → aerodynamics."""
    
def test_detect_lifecycle_concept():
    """Identify 'metamorphosis' + 'larvae' → lifecycle."""
    
def test_svg_template_loaded():
    """SVG library loads templates from disk."""
    
def test_prefer_svg_over_dalle():
    """Use free SVG if available, skip $0.020 AI."""
    
def test_mermaid_fallback():
    """If no SVG, use Mermaid diagram."""
    
def test_dalle_gated_by_budget():
    """Don't generate DALL-E if budget exhausted."""
    
def test_dalle_gated_by_confidence():
    """Don't generate DALL-E unless concept confidence >= 0.8."""
    
def test_inject_illustration_after_first_section():
    """Insert illustration after first h2 header."""
```

---

## Success Criteria

- ✅ Owl article includes 1-2 relevant SVG diagrams
- ✅ SVGs are free (no cost increase)
- ✅ Diagrams appear after intro section
- ✅ Gracefully skips if no matching concept
- ✅ DALL-E only used if budget available + confidence high

---

## Time Breakdown

- Design 5 SVG templates: 90 min
- Write concept detector: 45 min
- Write SVG library: 30 min
- Write generator: 60 min
- Integration in generate.py: 15 min
- Tests: 40 min
- **Total: 4-5 hours**

---

## SVG Resources

- **Create free SVGs**:
  - Inkscape (free desktop tool): https://inkscape.org
  - Excalidraw (free online): https://excalidraw.com
  - Draw.io (free online): https://draw.io

- **Find public domain diagrams**:
  - Wikimedia Commons: https://commons.wikimedia.org
  - OpenClipart: https://openclipart.org
  - Biodiversity Heritage Library: https://www.biodiversitylibrary.org

