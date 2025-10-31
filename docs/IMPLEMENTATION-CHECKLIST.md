# Code Implementation Checklist
## Concrete tasks for each sprint

---

## Sprint 1: Multi-Source Image Selection (1 week)

### New Files to Create

#### `src/images/__init__.py`
```python
"""Image selection and generation for articles."""
from .selector import CoverImageSelector

__all__ = ["CoverImageSelector"]
```

#### `src/images/selector.py` (~250 lines)
**What it does**: Main orchestrator for multi-source image selection
**Key insight**: Uses LLM to generate search queries (NOT deterministic rules)
**Pseudocode**:
```python
class CoverImageSelector:
    def select(self, title: str, topics: list[str], is_scientific: bool) -> CoverImage:
        """Try sources in priority order, return first match above threshold."""
        # Step 1: Generate search queries via gpt-3.5-turbo
        queries = self.generate_search_queries(title, topics)
        # Returns: {"wikimedia": "...", "unsplash": "...", "dalle": "..."}
        
        # Step 2: Try each source with generated query
        # 1. Try Wikimedia (free, public domain)
        # 2. Try Unsplash (free)
        # 3. Try Pexels (free)
        # 4. Generate AI image (paid, uses dalle query)
        
    def generate_search_queries(self, title: str, topics: list[str]) -> dict:
        """Use gpt-3.5-turbo to generate platform-specific search queries.
        
        WHY LLM NOT DETERMINISTIC RULES:
        - Deterministic extraction produces generic, poor queries
        - LLM understands context and generates natural, effective searches
        - Platform-aware (different query styles for Wikimedia vs Unsplash)
        - Cost: ~$0.0005 per article (amortized across all image sources)
        """
        
    def _search_unsplash(self, query: str) -> CoverImage | None:
        """Query Unsplash API with LLM-generated query, return best match or None."""
        
    def _generate_ai_image(self, dalle_prompt: str) -> CoverImage:
        """Generate via DALL-E 3 with LLM-generated prompt."""
```

**Dependencies**: httpx, PIL, OpenAI client
**Config keys used**: UNSPLASH_API_KEY, IMAGE_QUALITY_THRESHOLD

#### `src/images/sources/__init__.py`
Empty module init

#### `src/images/sources/unsplash.py` (~50 lines)
**What it does**: Unsplash API wrapper
**Pseudocode**:
```python
class UnsplashSource:
    def search(self, query: str) -> CoverImage | None:
        """GET /search/photos?query=..., return best result."""
```

#### `src/images/sources/ai_generated.py` (~80 lines)
**What it does**: DALL-E prompt generation + image generation
**Pseudocode**:
```python
class AIImageGenerator:
    def generate(self, title: str, topics: list[str], quality: str) -> CoverImage:
        """Generate DALL-E prompt, call API, return image."""
        # 1. Use gpt-3.5-turbo to generate detailed prompt
        # 2. Call DALL-E 3
        # 3. Download and save
        # 4. Return with cost ($0.020)
```

### Files to Modify

#### `src/config.py`
**Changes**:
- Add `ImageSelectionConfig` class or dict to `PipelineConfig`
- New fields:
  - `unsplash_api_key: str`
  - `enable_multimethod_images: bool = True`
  - `image_quality_threshold: float = 0.70`
  - `image_source_timeout: int = 10`

#### `src/models.py`
**Changes**:
- Add `CoverImage` dataclass:
  ```python
  @dataclass
  class CoverImage:
      url: str
      alt_text: str
      source: str  # "unsplash", "dall-e-3", "pexels", etc.
      cost: float
      quality_score: float  # 0-1
  ```

#### `src/generate.py`
**Changes**:
- Import `CoverImageSelector`
- Modify article generation to call selector:
  ```python
  # Around line 811 where images are selected
  if config.enable_multimethod_images:
      selector = CoverImageSelector(config, client)
      image = selector.select(title, tags, is_scientific=should_use_enhanced_images(item))
  else:
      # Use existing select_or_create_cover_image()
  ```

#### `.env.example`
**Add**:
```
# Image Selection
UNSPLASH_API_KEY=your_api_key_here
ENABLE_MULTIMETHOD_IMAGES=true
IMAGE_QUALITY_THRESHOLD=0.70
IMAGE_SOURCE_TIMEOUT=10
```

### Tests to Write

#### `tests/test_image_selector.py`
```python
def test_unsplash_search_returns_image():
    """Mock Unsplash API, verify image selection."""

def test_unsplash_timeout_falls_back_to_ai():
    """If Unsplash times out, should fallback to AI."""

def test_quality_threshold_filters_low_quality():
    """Images below threshold are rejected."""

def test_cost_tracked_in_image_object():
    """Image cost is $0.00 for free sources, $0.020 for AI."""

def test_scientific_article_uses_higher_quality_threshold():
    """Quality threshold higher for scientific content."""
```

### Success Criteria for Sprint 1
- [ ] Unsplash integration working (or gracefully fails with clear error)
- [ ] AI generation works as fallback
- [ ] Cost tracked in `generation_costs` frontmatter
- [ ] Owl article displays real image (from Unsplash or AI)
- [ ] Feature flag works (can disable and fall back to gradient)
- [ ] All tests pass

**Estimated effort**: 3-4 days
**Risk**: Unsplash API key setup, timeouts

---

## Sprint 2: Citation Resolution (1-2 weeks)

### New Files to Create

#### `src/citations/__init__.py`
```python
"""Citation extraction and resolution."""
from .resolver import CitationResolver
from .extractor import extract_citations
from .formatter import format_citations_markdown

__all__ = ["CitationResolver", "extract_citations", "format_citations_markdown"]
```

#### `src/citations/resolver.py` (~150 lines)
**What it does**: Resolve citations via CrossRef/arXiv APIs
**Pseudocode**:
```python
class CitationResolver:
    def resolve(self, author: str, year: int | None, context: str) -> CitationMetadata | None:
        """Search CrossRef, then arXiv, then PubMed."""
        # Check cache first
        # Try CrossRef
        # Try arXiv
        # Try PubMed
        # Cache result
        
    def _crossref_search(self, author: str, year: int) -> CitationMetadata | None:
        """GET https://api.crossref.org/works?query=..."""
        
    def _arxiv_search(self, author: str, year: int) -> CitationMetadata | None:
        """Search arXiv if academic topic."""
        
    def _pubmed_search(self, author: str, year: int) -> CitationMetadata | None:
        """Search PubMed if biomedical topic."""
```

**Dependencies**: httpx, json (for cache)
**No new config needed** (CrossRef is free, no auth)

#### `src/citations/extractor.py` (~80 lines)
**What it does**: Extract citations from text using regex
**Pseudocode**:
```python
def extract_citations(content: str) -> list[Citation]:
    """Find patterns like 'Author et al.' or 'Author (2019)'."""
    patterns = [
        r"(\w+) et al\.?",  # "Author et al."
        r"(\w+)\s+\((\d{4})\)",  # "Author (2019)"
    ]
    # Return list of extracted citations
```

#### `src/citations/formatter.py` (~80 lines)
**What it does**: Format resolved citations as markdown links
**Pseudocode**:
```python
def format_citations_markdown(
    content: str, 
    citations_resolved: list[CitationMetadata]
) -> str:
    """Replace 'Author et al.' with '[Author et al.](doi_url)'."""
    # For each citation, find in text and replace with markdown link
```

#### `src/citations/cache.py` (~60 lines)
**What it does**: Simple JSON cache for citations
**Pseudocode**:
```python
class CitationCache:
    def get(self, key: str) -> CitationMetadata | None:
        """Load from data/citations_cache.json."""
        
    def set(self, key: str, value: CitationMetadata) -> None:
        """Save to data/citations_cache.json."""
```

### Files to Modify

#### `src/config.py`
**Changes**:
- Add to `PipelineConfig`:
  ```python
  enable_citation_resolution: bool = True
  enable_citation_cache: bool = True
  ```

#### `src/models.py`
**Changes**:
- Add `CitationMetadata` dataclass:
  ```python
  @dataclass
  class CitationMetadata:
      authors: list[str]
      title: str
      journal: str
      year: int
      doi: str | None
      url: str | None
      doi_url: str | None = None
  ```

#### `src/generate.py`
**Changes**:
- Import citation modules
- In article generation, after content is generated:
  ```python
  if config.enable_citation_resolution and should_resolve_citations(item):
      citations = extract_citations(content)
      citations_resolved = [resolver.resolve(c) for c in citations]
      content = format_citations_markdown(content, citations_resolved)
  ```

#### `.env.example`
**Add**:
```
# Citation Resolution
ENABLE_CITATION_RESOLUTION=true
ENABLE_CITATION_CACHE=true
```

### Data Files to Create

#### `data/citations_cache.json`
```json
{
  "usherwood:2019": {
    "authors": ["Michael Treep", "Emily Watt", "John Usherwood"],
    "title": "High aerodynamic lift from the tail reduces drag in gliding owls",
    "journal": "Journal of Experimental Biology",
    "year": 2019,
    "doi": "10.1242/jeb.214809",
    "url": "https://journals.biologists.com/jeb/article/223/3/jeb214809/223686/..."
  }
}
```

#### `data/citations_manual.json`
```json
{
  "example_author:2020": {
    "authors": ["Example Author"],
    "title": "Example Paper",
    "journal": "Example Journal",
    "year": 2020,
    "doi": "10.xxxx/example",
    "url": "https://example.com/..."
  }
}
```

### Tests to Write

#### `tests/test_citation_resolver.py`
```python
def test_crossref_lookup_returns_metadata():
    """Mock CrossRef API, verify metadata returned."""

def test_cache_returns_cached_result():
    """First lookup cached, second lookup uses cache."""

def test_resolution_fails_gracefully():
    """If resolution fails, return None, don't crash."""

def test_arxiv_search_called_for_academic_topics():
    """arXiv called if 'arxiv' in context."""

def test_manual_citation_override():
    """Manual citations in data/citations_manual.json used first."""
```

#### `tests/test_citation_extractor.py`
```python
def test_extract_author_et_al():
    """Extract 'Smith et al.' pattern."""

def test_extract_author_year():
    """Extract 'Smith (2019)' pattern."""

def test_no_false_positives():
    """Don't extract non-citation text."""
```

#### `tests/test_citation_formatter.py`
```python
def test_format_citation_as_markdown_link():
    """'Smith et al.' → '[Smith et al.](doi_url)'."""

def test_preserve_text_for_unresolved():
    """If not resolved, keep original text."""
```

### Success Criteria for Sprint 2
- [ ] CrossRef lookup working (example: Usherwood 2019)
- [ ] Citations extracted from text
- [ ] Markdown formatted with DOI links
- [ ] Cache prevents repeated lookups
- [ ] Manual citation database works (edge cases)
- [ ] Graceful fallback if resolution fails
- [ ] Zero cost (CrossRef is free)
- [ ] Owl article has linked citations
- [ ] All tests pass

**Estimated effort**: 5-7 days
**Risk**: CrossRef API response format changes, rate limiting (unlikely, API is stable)

---

## Sprint 3: Concept Illustrations (1-2 weeks)

### New Files to Create

#### `src/illustrations/__init__.py`
```python
"""Concept illustrations for articles."""
from .generator import IllustrationGenerator
```

#### `src/illustrations/generator.py` (~200 lines)
**What it does**: Main orchestrator for illustrations
**Pseudocode**:
```python
class IllustrationGenerator:
    def identify_and_generate_illustrations(
        self,
        content: str,
        topics: list[str],
        quality_score: float
    ) -> list[Illustration]:
        """Detect concepts, generate illustrations."""
        # 1. Identify concepts
        # 2. Try SVG templates
        # 3. Try public domain (Wikimedia)
        # 4. Generate AI if budget allows
        
    def insert_into_content(self, content: str, illustrations: list[Illustration]) -> str:
        """Insert ![alt](url) into markdown at logical points."""
```

#### `src/illustrations/concepts.py` (~100 lines)
**What it does**: Detect concepts in article text
**Pseudocode**:
```python
def identify_concepts(content: str, topics: list[str]) -> list[str]:
    """Extract concepts like 'lift', 'drag', 'vortex' from text."""
    
CONCEPT_KEYWORDS = {
    "lift": ["lift force", "aerodynamic lift", "lifting"],
    "drag": ["drag force", "aerodynamic drag", "air resistance"],
    "vortex": ["vortex", "vortices", "swirl", "eddy"],
    # ... etc
}
```

#### `src/illustrations/svg_templates/` (directory)
**What it does**: Store SVG diagram templates
**Files**:
- `aerodynamic_forces.svg` (~50 lines) - Airfoil with lift/drag vectors
- `vortex_formation.svg` (~50 lines) - Spiral streamlines
- `wing_cross_section.svg` (~50 lines) - Owl wing with serrations
- `pressure_contours.svg` (~50 lines) - Pressure zones (blue/red)
- `generic_flowchart.svg` - For any flowchart use

**Example**: `aerodynamic_forces.svg`
```xml
<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
  <!-- Airfoil shape -->
  <path d="M 50 100 Q 100 50 150 100 L 150 150 Q 100 150 50 150 Z" 
        fill="lightblue" stroke="black" stroke-width="2"/>
  
  <!-- Lift arrow (upward, red) -->
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="5" refY="5" orient="auto">
      <polygon points="0 0, 10 5, 0 10" fill="red" />
    </marker>
  </defs>
  <line x1="100" y1="120" x2="100" y2="50" stroke="red" stroke-width="3" marker-end="url(#arrowhead)" />
  <text x="105" y="80" font-size="14" fill="red">Lift</text>
  
  <!-- Drag arrow (rightward, blue) -->
  <line x1="100" y1="120" x2="180" y2="120" stroke="blue" stroke-width="3" marker-end="url(#arrowhead)" />
  <text x="140" y="135" font-size="14" fill="blue">Drag</text>
</svg>
```

#### `src/illustrations/library.py` (~100 lines)
**What it does**: Index of illustrations and their keywords
**Pseudocode**:
```python
class IllustrationLibrary:
    def get_svg_for_concept(self, concept: str) -> str | None:
        """Return SVG filename for concept, or None."""
        
    def get_mermaid_for_concept(self, concept: str) -> str | None:
        """Return Mermaid diagram code for concept."""

# Map concepts to SVG/Mermaid templates
ILLUSTRATIONS = {
    "lift": {"svg": "aerodynamic_forces.svg", "type": "svg"},
    "drag": {"svg": "aerodynamic_forces.svg", "type": "svg"},
    "vortex": {"svg": "vortex_formation.svg", "type": "svg"},
    "data_flow": {"mermaid": "flowchart LR ...", "type": "mermaid"},
}
```

#### `src/illustrations/public_domain.py` (~80 lines)
**What it does**: Search Wikimedia for scientific diagrams
**Pseudocode**:
```python
class WikimediaDiagramFinder:
    def search(self, concept: str) -> Illustration | None:
        """Search Wikimedia Commons for diagrams matching concept."""
        # GET /w/api.php?action=query&list=search&srsearch=...
        # Return first result if found
```

#### `src/illustrations/ai_generated.py` (~80 lines)
**What it does**: Generate DALL-E diagram (high-quality, expensive)
**Pseudocode**:
```python
class AIIllustrationGenerator:
    def generate(self, concept: str, context: str) -> Illustration | None:
        """Generate scientific diagram via DALL-E, if budget allows."""
        # Check if cost allowed (under max_cost)
        # Generate prompt
        # Call DALL-E
        # Return with cost ($0.020)
```

### Files to Modify

#### `src/config.py`
**Changes**:
- Add to `PipelineConfig`:
  ```python
  enable_concept_illustrations: bool = True
  enable_mermaid_diagrams: bool = True
  enable_svg_templates: bool = True
  enable_illustration_ai_fallback: bool = True
  illustration_ai_max_cost: float = 0.040
  ```

#### `src/models.py`
**Changes**:
- Add `Illustration` dataclass:
  ```python
  @dataclass
  class Illustration:
      concept: str
      title: str
      type: str  # "svg", "mermaid", "ai_image", "public_domain"
      content: str  # SVG XML or URL
      alt_text: str
      caption: str
      cost: float
  ```

#### `src/generate.py`
**Changes**:
- Import illustration modules
- In article generation, after content is generated:
  ```python
  if config.enable_concept_illustrations and should_add_illustrations(item):
      illustrations = generator.identify_and_generate_illustrations(
          content, item.topics, item.quality_score
      )
      content = generator.insert_into_content(content, illustrations)
  ```

#### `.env.example`
**Add**:
```
# Illustrations
ENABLE_CONCEPT_ILLUSTRATIONS=true
ENABLE_MERMAID_DIAGRAMS=true
ENABLE_SVG_TEMPLATES=true
ENABLE_ILLUSTRATION_AI_FALLBACK=true
ILLUSTRATION_AI_MAX_COST=0.040
```

### Tests to Write

#### `tests/test_illustration_generator.py`
```python
def test_identify_concepts_finds_lift_drag_vortex():
    """Detect 'lift', 'drag', 'vortex' in article text."""

def test_svg_template_loaded_for_concept():
    """Get aerodynamic_forces.svg for 'lift' concept."""

def test_mermaid_diagram_returned_for_flowchart():
    """Return Mermaid code for data flow concepts."""

def test_ai_generation_gated_by_budget():
    """If illustration_ai_max_cost=0.0, skip AI diagrams."""

def test_cost_tracked_per_illustration():
    """SVG is $0.00, AI is $0.020."""
```

#### `tests/test_svg_templates.py`
```python
def test_aerodynamic_forces_svg_valid():
    """SVG parses without errors."""

def test_vortex_formation_svg_renders():
    """SVG has expected elements."""
```

### Success Criteria for Sprint 3
- [ ] SVG template library created (5-10 diagrams)
- [ ] Concepts detected in article text (lift, drag, vortex, etc.)
- [ ] SVG diagrams inserted at logical points in content
- [ ] Mermaid diagrams work (if enabled)
- [ ] Public domain diagram search works (Wikimedia)
- [ ] AI fallback respects budget gating
- [ ] All diagrams render correctly in Hugo
- [ ] Cost per illustration tracked ($0.00 for SVG/public domain)
- [ ] Owl article has 2-3 concept diagrams
- [ ] All tests pass

**Estimated effort**: 6-9 days
**Risk**: SVG rendering in Hugo, Wikimedia API response format

---

## Sprint 4: Integration & Polish (1 week)

### Files to Modify

#### `src/generate.py` (main integration)
**Changes**:
- Add lightweight topic detection function:
  ```python
  def should_use_enhanced_images(item: EnrichedItem) -> bool:
      """Check if article would benefit from enhanced image selection."""
      academic_keywords = {
          "research", "study", "paper", "peer review", "journal",
          "experiment", "methodology", "hypothesis", "arxiv", "doi"
      }
      topic_text = " ".join(item.topics).lower()
      return any(k in topic_text for k in academic_keywords)
  
  def should_resolve_citations(item: EnrichedItem) -> bool:
      """Check if article likely has academic citations."""
      return "et al" in item.original.content or should_use_enhanced_images(item)
  
  def should_add_illustrations(item: EnrichedItem) -> bool:
      """Check if article would benefit from concept diagrams."""
      concept_keywords = {
          "architecture", "diagram", "process", "flow", "algorithm",
          "physics", "aerodynamics", "system"
      }
      topic_text = " ".join(item.topics).lower()
      return any(k in topic_text for k in concept_keywords)
  ```

- Modify main generation function:
  ```python
  def generate_article_with_optimizations(item: EnrichedItem) -> GeneratedArticle:
      # Existing content generation
      generator = select_generator(item, generators)
      content, in_tok, out_tok = generator.generate_content(item)
      
      costs = {"content_generation": calculate_text_cost(...)}
      
      # NEW: Conditional enhancements
      if config.enable_multimethod_images:
          if should_use_enhanced_images(item):
              selector = CoverImageSelector(config, client)
              image = selector.select(title, tags)
              costs["image_generation"] = image.cost
              # Store image info in article
          else:
              # Use existing image_library.py
              image = select_or_create_cover_image(tags, slug)
              costs["image_generation"] = 0.0
      
      if config.enable_citation_resolution and should_resolve_citations(item):
          citations = extract_citations(content)
          citations_resolved = [resolver.resolve(c) for c in citations]
          content = format_citations_markdown(content, citations_resolved)
      
      if config.enable_concept_illustrations and should_add_illustrations(item):
          ill_gen = IllustrationGenerator(config, client)
          illustrations = ill_gen.identify_and_generate_illustrations(
              content, item.topics, item.quality_score
          )
          content = ill_gen.insert_into_content(content, illustrations)
          costs["illustrations"] = sum(i.cost for i in illustrations)
      
      return GeneratedArticle(
          title=title,
          content=content,
          generation_costs=costs,
          ...
      )
  ```

#### `docs/` directory
**Create/Update**:
- `IMPLEMENTATION-GUIDE.md` - How to set up and use all features
- `TROUBLESHOOTING.md` - Common issues and fixes
- Update `README.md` with new config keys

#### `.github/workflows/` (if applicable)
**Changes** (optional):
- If using GitHub Actions, ensure new API keys are added as secrets

### Integration Tests

#### `tests/test_end_to_end_scientific_article.py`
```python
def test_scientific_article_generation_complete():
    """Full end-to-end: content + citations + illustrations + images."""
    item = create_scientific_enriched_item()
    article = generate_article_with_optimizations(item)
    
    # Verify all components
    assert article.title
    assert "[" in article.content  # Has links (citations)
    assert "![" in article.content  # Has images
    assert article.generation_costs.get("illustrations", 0.0) >= 0.0
    assert article.generation_costs["content_generation"] > 0.0

def test_feature_flags_disable_enhancements():
    """If features disabled, skip enhancements."""
    config = PipelineConfig(..., enable_multimethod_images=False)
    # Should use gradient images only
```

#### `tests/test_owl_flight_article.py`
```python
def test_owl_article_has_real_image():
    """Sample: Owl article uses Unsplash photo."""

def test_owl_article_has_linked_citations():
    """Sample: Usherwood et al. is linked to DOI."""

def test_owl_article_has_aerodynamic_diagrams():
    """Sample: Article includes lift/drag and vortex diagrams."""
```

### Documentation

#### `docs/SETUP-NEW-FEATURES.md`
```markdown
# Setting Up Scientific Article Features

## Step 1: Get API Keys

### Unsplash
1. Go to https://unsplash.com/developers
2. Sign up / login
3. Create application
4. Copy API key

### CrossRef
No API key needed! API is free and open.

### Mermaid
No API key needed! Diagrams rendered client-side.

## Step 2: Update .env

```bash
UNSPLASH_API_KEY=your_key_here
ENABLE_MULTIMETHOD_IMAGES=true
ENABLE_CITATION_RESOLUTION=true
ENABLE_CONCEPT_ILLUSTRATIONS=true
```

## Step 3: Test

```bash
uv run python -m src.generate --dry-run --max-articles 1
```

Look for log messages about image selection, citation resolution, etc.
```

#### `docs/FEATURE-FLAGS.md`
```markdown
# Feature Flags: Fine-Grained Control

All new features can be enabled/disabled via .env:

### Images
- ENABLE_MULTIMETHOD_IMAGES (default: true)
- ENABLE_PUBLIC_DOMAIN_IMAGES (default: true)
- ENABLE_STOCK_PHOTOS (default: true)
- ENABLE_AI_IMAGE_FALLBACK (default: true)

### Citations
- ENABLE_CITATION_RESOLUTION (default: true)
- ENABLE_CITATION_CACHE (default: true)

### Illustrations
- ENABLE_CONCEPT_ILLUSTRATIONS (default: true)
- ENABLE_MERMAID_DIAGRAMS (default: true)
- ENABLE_SVG_TEMPLATES (default: true)
- ENABLE_ILLUSTRATION_AI_FALLBACK (default: true)

Set to `false` to disable any feature.
```

### Success Criteria for Sprint 4
- [ ] All components integrated and working together
- [ ] Lightweight topic detection functions working
- [ ] Feature flags functional (can disable any component)
- [ ] Full end-to-end test passing (owl article generation)
- [ ] Documentation complete and clear
- [ ] All tests passing
- [ ] No breaking changes to existing pipeline
- [ ] Cost tracking accurate
- [ ] Error handling graceful (timeouts, API failures)

**Estimated effort**: 5 days
**Risk**: Integration issues between components, edge cases in topic detection

---

## Files Summary

### New Directories
```
src/images/                  (Sprint 1)
src/images/sources/         (Sprint 1)
src/citations/              (Sprint 2)
src/illustrations/          (Sprint 3)
src/illustrations/svg_templates/  (Sprint 3)
```

### New Python Modules (~1000 lines total)
```
src/images/selector.py              (~200 lines)
src/images/sources/unsplash.py      (~50 lines)
src/images/sources/ai_generated.py  (~80 lines)
src/citations/resolver.py           (~150 lines)
src/citations/extractor.py          (~80 lines)
src/citations/formatter.py          (~80 lines)
src/citations/cache.py              (~60 lines)
src/illustrations/generator.py      (~200 lines)
src/illustrations/concepts.py       (~100 lines)
src/illustrations/library.py        (~100 lines)
src/illustrations/public_domain.py  (~80 lines)
src/illustrations/ai_generated.py   (~80 lines)
```

### Modified Files (Minimal changes)
```
src/config.py               (~30 new lines)
src/models.py               (~20 new lines)
src/generate.py             (~40 new lines for conditional logic)
.env.example                (~12 new lines)
```

### Test Files (~800 lines total)
```
tests/test_image_selector.py           (~50 lines)
tests/test_citation_resolver.py        (~50 lines)
tests/test_citation_extractor.py       (~30 lines)
tests/test_citation_formatter.py       (~30 lines)
tests/test_illustration_generator.py   (~50 lines)
tests/test_svg_templates.py            (~30 lines)
tests/test_end_to_end_scientific_article.py (~50 lines)
tests/test_owl_flight_article.py       (~40 lines)
```

### Data Files
```
data/citations_cache.json       (auto-generated)
data/citations_manual.json      (template)
```

### SVG Files (~10 total, ~500 lines)
```
src/illustrations/svg_templates/aerodynamic_forces.svg
src/illustrations/svg_templates/vortex_formation.svg
src/illustrations/svg_templates/wing_cross_section.svg
src/illustrations/svg_templates/pressure_contours.svg
... (5-6 more)
```

---

## Code Organization Philosophy

**Guiding principles**:
1. **Modular but not over-engineered**: Each component is independent, testable
2. **Feature flags for safety**: Can disable any component without breaking pipeline
3. **Optional enhancements**: New code never blocks article generation
4. **Zero breaking changes**: Existing pipeline works exactly as before
5. **Clear costs**: Every expensive operation tracked and gated

---

## Ready to Start?

**Next actions**:
1. Review this checklist with team
2. Confirm Sprint 1 priorities
3. Create GitHub issues (one per sprint)
4. Assign developer (or start with Sprint 1 yourself)
5. Set deadline: Sprint 1 complete in 1 week

