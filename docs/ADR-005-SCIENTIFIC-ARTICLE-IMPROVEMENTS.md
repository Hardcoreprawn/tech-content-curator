# ADR-005: Scientific Article Improvements
## Enhanced Images, Citations, and Concept Illustrations

**Status**: Proposed  
**Date**: 2025-10-31  
**Context**: The owl flight article (2025-10-31) demonstrates strong content but needs:
1. Context-aware featured images (owl photo vs gradient)
2. Academic citation handling and DOI linking
3. Inline concept illustrations (aerodynamic diagrams, vortex visualization)

---

## Problem Statement

The current pipeline treats all articles uniformly:
- **Images**: Generated abstract visuals via DALL-E 3 gradient (appropriate for general tech, poor for scientific topics)
- **Citations**: Referenced by author name ("Usherwood et al.") but no DOI, journal link, or automated lookup
- **Concepts**: Long text explanations of complex ideas (lift, drag, vortices) that would benefit from visual aids

Scientific articles need specialized handling to be more authoritative and visually effective.

---

## Proposed Solution

### Overview

Create a **`scientific_article` generator route** that extends the general pipeline with:
1. **Smart cover image selection** - use stock photos or AI-generated domain-specific images
2. **Academic citation pipeline** - extract, validate, and format citations with DOI/journal links
3. **Concept illustration framework** - generate or select inline diagrams for technical concepts

### 1. Context-Aware Cover Image Selection

#### Current State
- Always uses DALL-E 3 abstract images
- Cost: $0.020 per article
- Limited relevance to scientific content

#### Proposed Approach

**Strategy 1: Stock Photo Integration** (Recommended for MVP)
```
Owl flight article:
  Topic: aerodynamics, biomechanics, owl flight
  → Search Unsplash/Pexels for "owl flying night"
  → Select high-quality match (free tier, open license)
  → Resize locally (1792x1024 hero + 512x512 icon)
  → Cost: $0.00 (bandwidth only, cached)
  → Quality: High (real photograph)
```

**Strategy 2: AI-Generated Domain-Specific Images** (Fallback)
```
If no good stock match:
  → Use detailed DALL-E prompt with reference style
  → Example: "Realistic owl mid-flight, wings outstretched, 
             night sky, scientific photography style"
  → Cost: $0.040 (HD quality for science)
  → Quality: Professional, on-brand
```

**Implementation Plan**

1. **New module**: `src/cover_image_selector.py`
   ```python
   class CoverImageSelector:
       def select_for_article(
           self, 
           title: str, 
           topics: list[str], 
           article_type: str
       ) -> CoverImage:
           """Select or generate cover image based on article metadata."""
           
           if article_type == "scientific_article":
               # Step 1: Extract key concepts (owl, flight, night)
               concepts = self.extract_visual_concepts(title, topics)
               
               # Step 2: Try stock photo first
               stock_result = self.search_unsplash(concepts)
               if stock_result and stock_result.quality_score > 0.7:
                   return stock_result  # Free, high quality
               
               # Step 3: Fallback to AI generation
               return self.generate_scientific_image(
                   title, concepts, quality="hd"
               )
           else:
               # Existing pipeline: generic DALL-E gradient
               return self.generate_generic_image(title)
   ```

2. **Stock photo APIs to consider** (free tier):
   - **Unsplash** - 1500 req/hr, free download, open license
   - **Pexels** - Unlimited downloads, free
   - **Pixabay** - Simple API, free
   - **API key**: Minimal setup, no auth on free plans

3. **Configuration**:
   ```yaml
   # config.py
   COVER_IMAGE_STRATEGY:
     scientific_article:
       - strategy: "stock_photo"
         sources: ["unsplash", "pexels"]
         quality_threshold: 0.7
         timeout: 10s
       - strategy: "ai_generated"
         model: "dall-e-3"
         quality: "hd"
         cost_max: 0.040
       - strategy: "fallback"
         model: "dall-e-3"
         quality: "standard"
         cost_max: 0.020
     
     general_article:
       - strategy: "ai_generated"
         model: "dall-e-3"
         quality: "standard"
   ```

4. **Data to track**:
   ```python
   # In frontmatter
   cover:
     alt: "..."
     image: "..."
     source: "unsplash"  # or "dall-e-3" or "pexels"
     search_query: "owl flying night"
   ```

---

### 2. Academic Citation Pipeline

#### Current State
- Text reference: "Usherwood et al." with mastodon link
- No DOI, journal, or direct access to paper
- Citation format not standardized

#### Proposed Approach

**Citation Extraction & Validation**

```
Input article text:
  "Recent research by Usherwood et al. has unveiled..."
  
→ NLP extract: author_name="Usherwood", 
                approximate_year=2023 (from research summary context),
                topic="owl flight aerodynamics"

→ Search academic APIs:
  - CrossRef API (free, 50M articles) for DOI lookup
  - PubMed (if life sciences)
  - arXiv (if physics/CS preprints)
  
→ Return metadata:
  - DOI: 10.1242/jeb.214809
  - Journal: Journal of Experimental Biology
  - Title: "High aerodynamic lift from the tail reduces drag in gliding owls"
  - URL: https://journals.biologists.com/jeb/article/223/3/jeb214809/223686/High-aerodynamic-lift-from-the-tail-reduces-drag
  - Authors: ["Michael Treep", "Emily Watt", "John Usherwood"]
  - Published: 2019-12-27

→ Format citations in article markdown with links
```

**Implementation Plan**

1. **New module**: `src/citations.py`
   ```python
   from dataclasses import dataclass
   from typing import Optional
   import httpx
   
   @dataclass
   class CitationMetadata:
       """Academic citation with resolved metadata."""
       authors: list[str]
       title: str
       journal: str
       year: int
       doi: Optional[str]
       url: Optional[str]
       doi_url: Optional[str] = None
       
       def __post_init__(self):
           if self.doi:
               self.doi_url = f"https://doi.org/{self.doi}"
   
   class CitationResolver:
       """Resolve academic citations to full metadata."""
       
       def resolve(
           self, 
           author_name: str, 
           topic: str, 
           context: str
       ) -> CitationMetadata | None:
           """
           Attempt to resolve citation via CrossRef/arXiv APIs.
           
           Returns CitationMetadata if found, None if not resolvable.
           """
           # 1. Try CrossRef (largest academic index)
           result = self._crossref_search(author_name, topic)
           if result:
               return result
           
           # 2. Try arXiv (if preprint)
           result = self._arxiv_search(author_name, topic)
           if result:
               return result
           
           # 3. Try PubMed (if biomedical)
           result = self._pubmed_search(author_name, topic)
           return result
       
       def _crossref_search(self, author: str, topic: str) -> CitationMetadata | None:
           """Search CrossRef API (free, no auth required)."""
           # Example: GET https://api.crossref.org/works?query=Usherwood%20owl%20aerodynamics
           # Returns: JSON with DOI, title, authors, journal, publication date
           pass
   ```

2. **Integration with generator**:
   ```python
   # In scientific_article generator
   
   def extract_and_resolve_citations(content: str) -> list[Citation]:
       """Extract citations from generated content and resolve metadata."""
       
       # Step 1: Use regex/NLP to find citation patterns
       patterns = [
           r"(\w+) et al\.",  # "Author et al."
           r"(?P<author>\w+)\s+\((?P<year>\d{4})\)",  # Author (2023)
       ]
       
       citations = extract_citations(content, patterns)
       
       # Step 2: Resolve each citation
       resolved = []
       for citation in citations:
           metadata = citation_resolver.resolve(
               citation.author,
               topics=self.topics,
               context=content
           )
           if metadata:
               resolved.append(metadata)
       
       return resolved
   
   def format_citations_in_markdown(
       content: str, 
       citations: list[CitationMetadata]
   ) -> str:
       """Replace citation references with markdown links."""
       
       # Input: "Recent research by Usherwood et al. unveiled..."
       # Output: "Recent research by [Usherwood et al.](https://doi.org/...) 
       #          (Journal of Experimental Biology, 2019) unveiled..."
       
       for citation in citations:
           # Replace "Usherwood et al." with "[Usherwood et al.](doi_url)"
           pattern = f"{citation.authors[0]}.* et al\."
           replacement = (
               f"[{citation.authors[0]} et al.]"
               f"({citation.doi_url or citation.url}) "
               f"({citation.journal}, {citation.year})"
           )
           content = re.sub(pattern, replacement, content)
       
       return content
   ```

3. **Frontmatter enhancement**:
   ```yaml
   ---
   title: "Unlocking Owl Flight: Nature's Blueprint for Quieter Drones"
   sources:
     - url: https://mastodon.social/@wonderofscience/115465184154273561
       platform: mastodon
   
   # NEW: Academic citations resolved in article
   citations:
     - key: "usherwood2019"
       authors: ["Michael Treep", "Emily Watt", "John Usherwood"]
       title: "High aerodynamic lift from the tail reduces drag in gliding owls"
       journal: "Journal of Experimental Biology"
       year: 2019
       doi: "10.1242/jeb.214809"
       doi_url: "https://doi.org/10.1242/jeb.214809"
       journal_url: "https://journals.biologists.com/jeb/article/223/3/jeb214809/223686/..."
   ---
   ```

4. **Error handling**:
   - If CrossRef lookup fails → keep original text reference (graceful degradation)
   - Log unresolved citations for manual follow-up
   - Add manual citation database (JSON) for edge cases

---

### 3. Concept Illustrations

#### Current State
- Complex concepts (lift, drag, vortices) explained in prose only
- No visual aids or diagrams
- Dense paragraphs that could be broken up with illustrations

#### Proposed Approach

**Two-Tier Strategy**

**Tier 1: AI-Generated Diagrams** (Technical, clean)
```
Concept: "Vortex formation at owl wingtip"

Prompt:
  "Create a scientific diagram showing vortex formation at an owl's 
   wingtip. Include: wing cross-section, pressure zones (red/blue),
   streamlines showing air flow, vortex core spiral. White background,
   professional scientific style, black and colored lines only.
   No text labels."

Generated via: DALL-E 3 or specialized diagram API (e.g., Graphviz, PlantUML)
Cost: $0.020 per diagram (use DALL-E) or $0.00 (programmatic)
Placement: Inline in markdown with figure captions
```

**Tier 2: SVG/Programmatic Diagrams** (Cheap, scalable)
```
Concept: "Lift vs Drag forces"

Approach:
  - Use SVG templates (airfoil shape, force vectors, labels)
  - Parameterize with concept data (force magnitudes, angles)
  - No API calls needed
  - Cost: $0.00
  - Time: ~50ms per diagram
  
Example SVG:
  <svg width="400" height="300">
    <!-- Airfoil shape -->
    <path d="M 50 100 Q 100 50 150 100 L 150 150 Q 100 150 50 150 Z" 
          fill="lightblue" stroke="black"/>
    
    <!-- Lift arrow (upward) -->
    <arrow x1="100" y1="120" x2="100" y2="50" color="red" label="Lift"/>
    
    <!-- Drag arrow (rightward) -->
    <arrow x1="100" y1="120" x2="180" y2="120" color="blue" label="Drag"/>
  </svg>
```

**Implementation Plan**

1. **New module**: `src/concept_illustrations.py`
   ```python
   from enum import Enum
   from dataclasses import dataclass
   
   class IllustrationType(str, Enum):
       AIFOIL_FORCES = "airfoil_forces"      # Lift/Drag diagram
       VORTEX_FORMATION = "vortex_formation"  # Swirling flow
       WING_STRUCTURE = "wing_structure"      # Cross-section
       PRESSURE_MAP = "pressure_map"          # Pressure zones
   
   @dataclass
   class ConceptIllustration:
       """Inline illustration for a concept."""
       concept: str          # "lift", "drag", "vortex"
       title: str
       type: IllustrationType
       description: str      # Alt text
       image_url: str
       alt_text: str
       caption: str
       cost: float
   
   class IllustrationGenerator:
       """Generate or select illustrations for concepts."""
       
       def generate_for_concept(
           self,
           concept: str,
           context: str,
           preferred_type: str = "auto"
       ) -> ConceptIllustration | None:
           """Generate illustration for concept (lift, drag, etc.)."""
           
           # Step 1: Determine illustration type
           ill_type = self._determine_type(concept, preferred_type)
           
           # Step 2: Use appropriate method
           if ill_type == IllustrationType.AIRFOIL_FORCES:
               return self._generate_airfoil_diagram(concept)
           elif ill_type == IllustrationType.VORTEX_FORMATION:
               return self._generate_vortex_ai(concept, context)
           # ... etc
       
       def _generate_airfoil_diagram(self, concept: str) -> ConceptIllustration:
           """Programmatic SVG for airfoil + force vectors."""
           svg_content = self._render_airfoil_svg(
               concept=concept,
               wing_angle=5,  # degrees AoA
               forces={"lift": 100, "drag": 20}  # relative units
           )
           
           # Save to file
           filename = f"concept-airfoil-{slugify(concept)}.svg"
           filepath = self._save_svg(svg_content, filename)
           
           return ConceptIllustration(
               concept=concept,
               title=f"Aerodynamic Forces: {concept.title()}",
               type=IllustrationType.AIRFOIL_FORCES,
               description="Diagram showing lift and drag forces on an airfoil",
               image_url=f"/images/{filename}",
               alt_text="Airfoil with force vectors",
               caption=f"The {concept} force acts on an airfoil as air flows around it.",
               cost=0.0
           )
       
       def _generate_vortex_ai(self, concept: str, context: str) -> ConceptIllustration:
           """AI-generated vortex diagram (DALL-E)."""
           prompt = (
               f"Create a scientific diagram of {concept} in fluid dynamics. "
               f"Show streamlines, vortex cores, and pressure zones. "
               f"Context: {context[:200]}"
           )
           
           image_url = self.openai_client.images.generate(
               model="dall-e-3",
               prompt=prompt,
               size="1024x1024",
               quality="standard"
           )
           
           return ConceptIllustration(
               concept=concept,
               title=f"Visualization: {concept.title()}",
               type=IllustrationType.VORTEX_FORMATION,
               image_url=image_url,
               cost=0.020
           )
   ```

2. **Integration with scientific_article generator**:
   ```python
   class ScientificArticleGenerator(BaseGenerator):
       """Generate articles with academic rigor and visual aids."""
       
       CONCEPT_KEYWORDS = {
           "lift": IllustrationType.AIRFOIL_FORCES,
           "drag": IllustrationType.AIRFOIL_FORCES,
           "vortex": IllustrationType.VORTEX_FORMATION,
           "turbulence": IllustrationType.VORTEX_FORMATION,
           "aerodynamic": IllustrationType.WING_STRUCTURE,
       }
       
       def generate_content(self, item: EnrichedItem) -> str:
           """Generate scientific article with concept illustrations."""
           
           # ... base content generation ...
           
           # Step: Identify concepts that need illustrations
           concepts = self._identify_concepts(content, item.topics)
           
           # Step: Generate/fetch illustrations
           illustrations = []
           for concept in concepts:
               ill_type = self.CONCEPT_KEYWORDS.get(concept)
               if ill_type:
                   ill = self.illustration_generator.generate_for_concept(
                       concept=concept,
                       context=content,
                       preferred_type=ill_type
                   )
                   if ill:
                       illustrations.append(ill)
           
           # Step: Insert illustrations into content at logical points
           content = self._insert_illustrations(content, illustrations)
           
           # Step: Add cost to generation_costs
           for ill in illustrations:
               self.generation_costs["illustrations"] = sum(
                   i.cost for i in illustrations
               )
           
           return content
       
       def _insert_illustrations(
           self, 
           content: str, 
           illustrations: list[ConceptIllustration]
       ) -> str:
           """Insert illustrations at relevant points in markdown."""
           
           for ill in illustrations:
               # Find section discussing the concept
               section_pattern = rf"## .*{ill.concept}.*"
               
               if match := re.search(section_pattern, content, re.IGNORECASE):
                   # Insert after first paragraph in that section
                   insertion_point = match.end()
                   insert_text = (
                       f"\n\n![{ill.alt_text}]({ill.image_url})\n"
                       f"*{ill.caption}*\n"
                   )
                   content = content[:insertion_point] + insert_text + content[insertion_point:]
           
           return content
   ```

3. **SVG Template Library** (Pre-built, zero-cost):
   ```
   src/svg_templates/
   ├── airfoil_forces.svg        # Lift/Drag vectors
   ├── wing_structure.svg         # Cross-section with serrations
   ├── vortex_simple.svg          # Spiral streamlines
   └── pressure_contours.svg      # Pressure zones (blue/red)
   ```

4. **Frontmatter tracking**:
   ```yaml
   ---
   title: "Unlocking Owl Flight..."
   
   # Track images and illustrations
   images:
     cover:
       source: "unsplash"
       url: "https://unsplash.com/..."
       cost: 0.0
     
     illustrations:
       - concept: "vortex"
         source: "svg_template"
         url: "/images/vortex-formation.svg"
         cost: 0.0
       
       - concept: "lift_drag"
         source: "svg_template"
         url: "/images/airfoil-forces.svg"
         cost: 0.0
   
   generation_costs:
     content_generation: 0.00095685
     illustrations: 0.0
     cover_image: 0.0
     total: 0.00095685
   ---
   ```

---

## Implementation Roadmap

### Phase 1: Stock Photo Integration (MVP - 1 week)
- [ ] Create `cover_image_selector.py` with Unsplash integration
- [ ] Add `scientific_article` article_type detection
- [ ] Update `GeneratedArticle` model to track image source/cost
- [ ] Test with owl flight article
- **Outcome**: Real images for scientific articles, $0 cost

### Phase 2: Academic Citations (2 weeks)
- [ ] Create `citations.py` with CrossRef/arXiv resolvers
- [ ] Integrate citation extraction into `scientific_article` generator
- [ ] Format citations with DOI links in markdown
- [ ] Add manual citation database (JSON) for edge cases
- [ ] Update frontmatter schema to include `citations`
- **Outcome**: Authoritative links to academic papers

### Phase 3: Concept Illustrations (2 weeks)
- [ ] Create `concept_illustrations.py` with SVG template system
- [ ] Build SVG template library (5-10 base templates)
- [ ] Integrate DALL-E diagram generation as tier 2 (paid)
- [ ] Implement concept detection in article content
- [ ] Test insertion logic and markdown formatting
- **Outcome**: Visual explanations of complex concepts

### Phase 4: Scientific Article Route (1 week)
- [ ] Create `generators/specialized/scientific_article.py`
- [ ] Wire all three components together
- [ ] Route detection: "scientific_article" when topics include research/academic keywords
- [ ] Cost tracking and reporting
- **Outcome**: End-to-end scientific article generation with images + citations + diagrams

---

## Cost Analysis

### Current (Generic DALL-E)
```
Per article: $0.020 (image only)
Type: Abstract gradient
```

### Proposed (Scientific Article)
```
Scenario 1 - All free (stock photo + SVG diagrams):
  Cover image:         $0.00 (Unsplash stock photo)
  Illustrations:       $0.00 (SVG templates)
  Citations:           $0.00 (CrossRef API free)
  Content:             $0.0015 (existing)
  Total:               $0.0015 ✓ 93% cheaper

Scenario 2 - Stock + AI diagrams (if needed):
  Cover image:         $0.00 (Unsplash)
  Illustrations:       $0.040 (2x DALL-E diagrams)
  Citations:           $0.00 (CrossRef)
  Content:             $0.0015
  Total:               $0.0415 ✓ Still good ROI for academic rigor

Scenario 3 - All AI (fallback):
  Cover image:         $0.040 (DALL-E HD if no stock match)
  Illustrations:       $0.040 (DALL-E diagram)
  Citations:           $0.00
  Content:             $0.0015
  Total:               $0.0815 (but rarely needed)
```

---

## Technical Dependencies

### APIs & Services
- **CrossRef** - Free DOI lookup (no auth)
- **Unsplash API** - Free tier: 50 req/hour (one key per app_id)
- **arXiv** - Free preprint search
- **PubMed** - Free biomedical search (optional)
- **DALL-E 3** - Already in use

### Libraries (No new requirements)
- `requests` / `httpx` - Already in use
- `Pillow` - Already in use for image processing
- `lxml` - For XML/SVG templating

---

## Trade-offs & Risks

### Trade-offs
| Aspect | Option A (MVP) | Option B (Rich) |
|--------|---|---|
| **Cover Images** | Stock photos only | Stock + AI fallback |
| **Cost** | $0.00 | Up to $0.04 |
| **Coverage** | ~80% of topics have good stock | ~99% coverage |
| **Speed** | Faster (API lookup cached) | Slower (AI generation) |
| **Recommendation** | Start here | Add after MVP |

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Citation API downtime** | Article generates but cites incomplete | Graceful fallback: keep original text reference |
| **No matching stock photo** | Fallback to AI (adds cost) | Set quality threshold, allow graceful degradation |
| **API rate limits** | Collection throttling | Cache results, implement backoff (existing pattern) |
| **Concept detection misses concepts** | Illustrations not inserted | Manual review phase, add keywords over time |
| **SVG rendering issues** | Broken diagram display | Fallback to text description in alt text |

---

## Configuration Changes Needed

```python
# config.py additions

# Enable scientific article route
ARTICLE_TYPES = ["general", "integrative", "scientific_article"]

# Cover image strategy per type
COVER_IMAGE_CONFIG = {
    "scientific_article": {
        "primary_strategy": "stock_photo",
        "fallback_strategy": "ai_generated",
        "stock_photo_sources": ["unsplash", "pexels"],
        "ai_model": "dall-e-3",
        "ai_quality": "hd",
    },
    "general": {
        "primary_strategy": "ai_generated",
        "ai_model": "dall-e-3",
        "ai_quality": "standard",
    },
}

# Stock photo API keys
UNSPLASH_API_KEY = os.getenv("UNSPLASH_API_KEY", "")

# Citation resolution
CITATION_CONFIG = {
    "resolvers": ["crossref", "arxiv", "pubmed"],  # In order of preference
    "cache_citations": True,  # Cache results
    "cache_ttl_days": 30,
}

# Concept illustrations
ILLUSTRATION_CONFIG = {
    "svg_template_dir": "src/svg_templates",
    "prefer_svg": True,  # Prefer programmatic SVG over AI
    "ai_fallback_enabled": True,
    "ai_model": "dall-e-3",
    "ai_quality": "standard",
}
```

---

## Success Metrics

### Phase 1 (Stock Photos)
- [ ] ≥80% of scientific articles use real images
- [ ] Cost reduced to $0.0015/article
- [ ] Image quality rated 4.5+/5 by editor

### Phase 2 (Citations)
- [ ] ≥70% of academic references resolve to DOI
- [ ] 0 broken links in citations
- [ ] Citation format consistent across articles

### Phase 3 (Illustrations)
- [ ] ≥2 illustrations per scientific article
- [ ] 90%+ of concept illustrations render correctly
- [ ] Editor rates diagram clarity 4+/5

### Phase 4 (Full Pipeline)
- [ ] Scientific articles visually distinct from general articles
- [ ] Example: Owl flight article with:
  - Real owl photo (or high-quality AI)
  - Linked "Usherwood et al. (2019)" → DOI
  - 2-3 concept diagrams (vortex, lift/drag, wing structure)

---

## References

- **CrossRef API**: https://www.crossref.org/documentation/apis/
- **Unsplash API**: https://unsplash.com/developers
- **arXiv API**: https://arxiv.org/help/api/
- **DALL-E 3 Docs**: https://platform.openai.com/docs/guides/images/

---

## Next Steps

1. **Review & feedback** on this plan
2. **Prioritize** which phases to tackle first
3. **Create tickets** for each phase
4. **Prototype** Phase 1 (stock photo integration) with owl article
5. **Measure** impact (image quality, costs, time)
6. **Iterate** before moving to Phase 2

