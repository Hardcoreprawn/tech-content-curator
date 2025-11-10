# Illustration Quality Improvement Implementation Plan

**Date:** November 3, 2025  
**Goal:** Eliminate nonsensical diagrams by adding validation and filtering  
**Target:** 80%+ reduction in bad diagrams with minimal cost increase

---

## Problem Statement

Current system generates Mermaid diagrams that:

- Replace useful bullet lists with random flowcharts
- Don't match section content (e.g., generic "data pipeline" for Clojure features)
- Add visual noise instead of explanatory value

**Root cause:** No validation that generated diagrams actually represent the content.

---

## Architecture Overview

### Current Flow

```
Content → Detect Concepts → Score Sections → Generate Diagram → Inject
                                                    ↑
                                              (blind trust)
```

### New Flow

```
Content → Pre-filter → Detect Concepts → Score Sections → Multi-candidate Generation → Validation → Inject
            ↓                                                        ↓                      ↓
      Skip lists                                              3 diagrams              Pick best / reject all
```

---

## Implementation Plan

### Phase 1: Foundation (Priority 1 - This Week)

**Goal:** Add filtering and single-candidate validation  
**Effort:** ~2-3 hours  
**Cost Impact:** +$0.0005 per diagram (~50% increase, but prevents waste)

#### Task 1.1: List Section Detection

**File:** `src/illustrations/placement.py`  
**Function:** Add `_analyze_section_type()` to `PlacementAnalyzer`

**Implementation:**

```python
def _analyze_section_type(self, content: str) -> str:
    """Determine if section is list-based or narrative.
    
    Args:
        content: Section content to analyze
        
    Returns:
        "list" if >50% lines are list items, else "narrative"
    """
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    
    if not lines:
        return "narrative"
    
    # Count lines starting with list markers
    list_pattern = re.compile(r'^[-*•\d]+\.?\s')
    list_lines = sum(1 for line in lines if list_pattern.match(line))
    
    list_ratio = list_lines / len(lines)
    return "list" if list_ratio > 0.5 else "narrative"
```

**Integration Point:** In `parse_structure()`, add `section_type` field to `Section` dataclass:

```python
@dataclass
class Section:
    # ... existing fields ...
    section_type: str = "narrative"
    """Section type: 'list' or 'narrative'"""
```

Update section creation:

```python
section = Section(
    # ... existing fields ...
    section_type=self._analyze_section_type(section_content),
)
```

**Filter in IllustrationService:** In `generate_illustrations()`, skip list sections:

```python
# Filter suitable sections (>75 words, no existing visuals, not list-based)
suitable_sections = [
    (idx, sec)
    for idx, sec in enumerate(sections)
    if sec.word_count >= 75 
    and not sec.has_visuals
    and sec.section_type == "narrative"  # NEW
]
```

**Tests:** Add to `tests/test_illustrations.py`:

```python
def test_detect_list_section():
    """Detects sections with >50% list items."""
    analyzer = PlacementAnalyzer()
    
    list_content = """
    ## Features
    
    - Feature A
    - Feature B
    - Feature C
    - Feature D
    """
    
    assert analyzer._analyze_section_type(list_content) == "list"

def test_detect_narrative_section():
    """Detects narrative sections."""
    analyzer = PlacementAnalyzer()
    
    narrative = """
    ## How It Works
    
    The system processes data through several stages.
    First, it collects input from various sources.
    Then it validates and transforms the data.
    """
    
    assert analyzer._analyze_section_type(narrative) == "narrative"
```

---

#### Task 1.2: Diagram Validation Service

**File:** `src/illustrations/diagram_validator.py` (NEW)

**Implementation:**

```python
"""Validation service for generated diagrams.

Scores diagrams on content accuracy and explanatory value to prevent
nonsensical or low-quality visualizations from being injected.
"""

import json
from dataclasses import dataclass

from openai import OpenAI


@dataclass
class ValidationResult:
    """Result of diagram validation."""
    
    is_valid: bool
    """Whether diagram passes validation threshold"""
    
    accuracy_score: float
    """How well diagram matches content (0.0-1.0)"""
    
    value_score: float
    """How much value it adds over text (0.0-1.0)"""
    
    combined_score: float
    """Combined validation score (0.0-1.0)"""
    
    reason: str
    """Explanation of validation decision"""
    
    cost: float
    """Cost of validation API call"""


class DiagramValidator:
    """Validates generated diagrams against source content."""
    
    PRICING = {
        "gpt-3.5-turbo": {
            "prompt": 0.0005,
            "completion": 0.0015,
        }
    }
    
    def __init__(
        self,
        client: OpenAI,
        model: str = "gpt-3.5-turbo",
        threshold: float = 0.7,
    ):
        """Initialize validator.
        
        Args:
            client: OpenAI client for API calls
            model: Model to use for validation
            threshold: Minimum combined score to pass (0.0-1.0)
        """
        self.client = client
        self.model = model
        self.threshold = threshold
    
    def validate_diagram(
        self,
        section_title: str,
        section_content: str,
        diagram_content: str,
        diagram_type: str,
    ) -> ValidationResult:
        """Validate a generated diagram against source content.
        
        Args:
            section_title: Title of the section
            section_content: Full section content
            diagram_content: Generated diagram (Mermaid syntax or ASCII)
            diagram_type: Type of diagram ("mermaid" or "ascii")
            
        Returns:
            ValidationResult with scores and pass/fail decision
        """
        prompt = self._build_validation_prompt(
            section_title,
            section_content,
            diagram_content,
            diagram_type,
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert at evaluating diagram quality and relevance. "
                            "Score diagrams objectively on accuracy and explanatory value."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # Low temperature for consistent scoring
                max_tokens=150,
            )
            
            content = response.choices[0].message.content
            if not content:
                return self._create_failed_result("No response from validator")
            
            # Parse JSON response
            result = json.loads(content.strip())
            
            accuracy = float(result.get("accuracy", 0.0))
            value = float(result.get("value_add", 0.0))
            reason = result.get("reason", "No reason provided")
            
            # Combined score (weighted average)
            combined = (accuracy * 0.6) + (value * 0.4)
            
            # Calculate cost
            usage = response.usage
            if usage:
                cost = (
                    (usage.prompt_tokens / 1000) * self.PRICING[self.model]["prompt"]
                    + (usage.completion_tokens / 1000) * self.PRICING[self.model]["completion"]
                )
            else:
                cost = 0.0
            
            return ValidationResult(
                is_valid=combined >= self.threshold,
                accuracy_score=accuracy,
                value_score=value,
                combined_score=combined,
                reason=reason,
                cost=cost,
            )
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            return self._create_failed_result(f"Parse error: {e}")
        except Exception as e:
            return self._create_failed_result(f"Validation error: {e}")
    
    def _build_validation_prompt(
        self,
        section_title: str,
        section_content: str,
        diagram_content: str,
        diagram_type: str,
    ) -> str:
        """Build validation prompt."""
        # Truncate content for cost efficiency
        content_preview = section_content[:800]
        diagram_preview = diagram_content[:500]
        
        return f"""Evaluate this {diagram_type} diagram's quality for a technical article.

SECTION: "{section_title}"
CONTENT:
{content_preview}
{"..." if len(section_content) > 800 else ""}

GENERATED DIAGRAM:
{diagram_preview}
{"..." if len(diagram_content) > 500 else ""}

Rate on two dimensions (0.0 to 1.0):

1. ACCURACY: Does the diagram accurately represent concepts from the section content?
   - 1.0 = Perfect match, visualizes actual content
   - 0.5 = Generic/vague, could apply to anything
   - 0.0 = Completely wrong or unrelated

2. VALUE_ADD: Does the diagram explain concepts better than just reading the text?
   - 1.0 = Significantly clarifies complex relationships
   - 0.5 = Marginal value, just restates text
   - 0.0 = Adds confusion or clutter

Reply with ONLY this JSON:
{{
  "accuracy": 0.0-1.0,
  "value_add": 0.0-1.0,
  "reason": "brief explanation (20 words max)"
}}"""
    
    def _create_failed_result(self, reason: str) -> ValidationResult:
        """Create a failed validation result."""
        return ValidationResult(
            is_valid=False,
            accuracy_score=0.0,
            value_score=0.0,
            combined_score=0.0,
            reason=reason,
            cost=0.0,
        )
```

**Tests:** Add to `tests/test_diagram_validator.py` (NEW):

```python
"""Tests for diagram validation."""

import pytest
from unittest.mock import Mock, MagicMock
from openai import OpenAI

from src.illustrations.diagram_validator import DiagramValidator, ValidationResult


class TestDiagramValidator:
    """Tests for DiagramValidator."""
    
    def test_validate_good_diagram(self):
        """Accepts diagrams with high scores."""
        client = Mock(spec=OpenAI)
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"accuracy": 0.9, "value_add": 0.8, "reason": "Clear and accurate"}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        client.chat.completions.create.return_value = mock_response
        
        validator = DiagramValidator(client, threshold=0.7)
        result = validator.validate_diagram(
            section_title="How REPL Works",
            section_content="The Read-Eval-Print Loop executes code...",
            diagram_content="flowchart TD\n  Read --> Eval --> Print",
            diagram_type="mermaid",
        )
        
        assert result.is_valid is True
        assert result.accuracy_score == 0.9
        assert result.value_score == 0.8
        assert result.combined_score >= 0.7
    
    def test_validate_bad_diagram(self):
        """Rejects diagrams with low scores."""
        client = Mock(spec=OpenAI)
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"accuracy": 0.3, "value_add": 0.2, "reason": "Generic, doesn\'t match content"}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        client.chat.completions.create.return_value = mock_response
        
        validator = DiagramValidator(client, threshold=0.7)
        result = validator.validate_diagram(
            section_title="Clojure Features",
            section_content="- Simplicity\n- Concurrency\n- Interoperability",
            diagram_content="flowchart TD\n  A --> B --> C",
            diagram_type="mermaid",
        )
        
        assert result.is_valid is False
        assert result.combined_score < 0.7
```

---

#### Task 1.3: Integrate Validation into IllustrationService

**File:** `src/pipeline/illustration_service.py`

**Changes:**

1. Import validator:

```python
from ..illustrations.diagram_validator import DiagramValidator
```

2. Initialize in `__init__`:

```python
def __init__(self, client: OpenAI, config: PipelineConfig) -> None:
    # ... existing code ...
    self.diagram_validator = DiagramValidator(
        client,
        threshold=getattr(config, "diagram_validation_threshold", 0.7),
    )
```

3. Update `_select_format_for_match()` to validate after generation:

```python
def _select_format_for_match(
    self, match: ConceptSectionMatch
) -> tuple[str, GeneratedAsciiArt | GeneratedMermaidDiagram | None, ValidationResult | None]:
    """Select best format and generate diagram for a concept-section match.
    
    Returns:
        Tuple of (selected_format, generated_diagram, validation_result)
    """
    # ... existing format selection code ...
    
    # Generate diagram (existing code)
    if selected_format == "ascii":
        # ... existing ASCII generation ...
        pass
    elif diagram is None and selected_format != "ascii":
        # ... existing Mermaid generation ...
        pass
    
    # NEW: Validate diagram
    validation = None
    if diagram:
        validation = self.diagram_validator.validate_diagram(
            section_title=match.section.title,
            section_content=match.section.content,
            diagram_content=diagram.content,
            diagram_type=selected_format,
        )
        
        if not validation.is_valid:
            console.print(
                f"  [yellow]    ✗ Diagram rejected "
                f"(score: {validation.combined_score:.2f}): {validation.reason}[/yellow]"
            )
            diagram = None  # Reject diagram
        else:
            console.print(
                f"  [dim]    ✓ Diagram validated "
                f"(accuracy: {validation.accuracy_score:.2f}, "
                f"value: {validation.value_score:.2f})[/dim]"
            )
    
    return selected_format, diagram, validation
```

4. Update `generate_illustrations()` to handle validation:

```python
for match in top_matches:
    try:
        selected_format, diagram, validation = self._select_format_for_match(match)
        
        if diagram and validation and validation.is_valid:
            injected_content = self._inject_diagram(
                injected_content,
                match.section.title,
                diagram,
                selected_format,
            )
            
            illustrations_added += 1
            
            # Track costs including validation
            total_cost = diagram.total_cost
            if validation:
                total_cost += validation.cost
            
            illustration_costs[f"diagram_{illustrations_added}"] = total_cost
            # ... rest of existing code ...
```

---

### Phase 2: Multi-Candidate Generation (Priority 2 - Next Week)

**Goal:** Generate 3 candidates, validate all, pick best  
**Effort:** ~2-3 hours  
**Cost Impact:** 3x generation cost (~$0.006/diagram total)

#### Task 2.1: Mermaid Quality Selector

**File:** `src/illustrations/mermaid_quality_selector.py` (NEW)

**Implementation:**

```python
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
        for i in range(self.n_candidates):
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
```

**Tests:** Add to `tests/test_mermaid_quality_selector.py` (NEW):

```python
"""Tests for MermaidQualitySelector."""

import pytest
from unittest.mock import Mock, MagicMock
from openai import OpenAI

from src.illustrations.mermaid_quality_selector import MermaidQualitySelector
from src.illustrations.ai_mermaid_generator import GeneratedMermaidDiagram


class TestMermaidQualitySelector:
    """Tests for multi-candidate Mermaid generation."""
    
    def test_selects_best_candidate(self):
        """Selects highest-scoring valid candidate."""
        client = Mock(spec=OpenAI)
        
        # Mock 3 generations with different quality
        diagrams = [
            "flowchart TD\n  A --> B --> C",  # Generic
            "flowchart TD\n  Read --> Eval --> Print --> Loop",  # Good
            "flowchart LR\n  X --> Y",  # Poor
        ]
        
        validation_scores = [0.5, 0.85, 0.3]
        
        # Setup mocks (simplified - actual test would be more detailed)
        # ...
        
        selector = MermaidQualitySelector(client, n_candidates=3)
        result = selector.generate_best(
            section_title="REPL Process",
            section_content="The Read-Eval-Print Loop...",
            concept_type="scientific_process",
        )
        
        assert result.diagram is not None
        assert result.best_score >= 0.7
        assert result.candidates_tested == 3
        assert not result.all_rejected
```

---

#### Task 2.2: Integrate Multi-Candidate into IllustrationService

**File:** `src/pipeline/illustration_service.py`

**Changes:**

1. Import:

```python
from ..illustrations.mermaid_quality_selector import MermaidQualitySelector
```

2. Initialize in `__init__`:

```python
def __init__(self, client: OpenAI, config: PipelineConfig) -> None:
    # ... existing code ...
    self.mermaid_selector = MermaidQualitySelector(
        client,
        n_candidates=getattr(config, "mermaid_candidates", 3),
        validation_threshold=getattr(config, "diagram_validation_threshold", 0.7),
    )
```

3. Update `_select_format_for_match()`:

```python
# Replace single Mermaid generation with multi-candidate
if diagram is None and selected_format != "ascii":
    console.print(f"  [dim]    Generating {self.mermaid_selector.n_candidates} Mermaid candidates...[/dim]")
    
    result = self.mermaid_selector.generate_best(
        section_title=match.section.title,
        section_content=match.section.content,
        concept_type=match.concept,
    )
    
    if result.diagram:
        diagram = result.diagram
        console.print(
            f"  [dim]    ✓ Best of {result.candidates_tested} "
            f"(score: {result.best_score:.2f})[/dim]"
        )
    else:
        console.print(
            f"  [yellow]    ✗ All {result.candidates_tested} candidates rejected "
            f"(best score: {result.best_score:.2f})[/yellow]"
        )
```

---

### Phase 3: Configuration & Monitoring (Priority 3)

**Goal:** Make system configurable and observable  
**Effort:** ~1 hour

#### Task 3.1: Add Configuration Options

**File:** `src/config.py`

Add fields to `PipelineConfig`:

```python
@dataclass
class PipelineConfig:
    # ... existing fields ...
    
    # Illustration quality settings
    diagram_validation_threshold: float = 0.7
    """Minimum validation score to accept diagrams (0.0-1.0)"""
    
    mermaid_candidates: int = 3
    """Number of Mermaid candidates to generate for selection"""
    
    ascii_candidates: int = 3
    """Number of ASCII candidates to generate for selection"""
    
    text_illustration_quality_threshold: float = 0.6
    """Minimum quality score for ASCII diagrams"""
    
    skip_list_sections: bool = True
    """Skip illustration generation for list-heavy sections"""
```

---

#### Task 3.2: Add Metrics Tracking

**File:** `src/pipeline/illustration_service.py`

Add tracking to `IllustrationResult`:

```python
@dataclass
class IllustrationResult:
    content: str
    count: int
    costs: dict[str, float]
    format_distribution: dict[str, int]
    
    # NEW metrics
    rejected_count: int = 0
    """Number of diagrams rejected by validation"""
    
    list_sections_skipped: int = 0
    """Number of list sections skipped"""
    
    validation_scores: list[float] = field(default_factory=list)
    """Validation scores for accepted diagrams"""
    
    @property
    def acceptance_rate(self) -> float:
        """Percentage of generated diagrams that passed validation."""
        total_generated = self.count + self.rejected_count
        return (self.count / total_generated * 100) if total_generated > 0 else 0.0
```

Update `generate_illustrations()` to populate these metrics.

---

## Testing Strategy

### Unit Tests

1. **List detection** (Task 1.1)
   - Test >50% list lines → "list"
   - Test <50% list lines → "narrative"
   - Test edge cases (empty, all code)

2. **Validation** (Task 1.2)
   - Test high scores → is_valid=True
   - Test low scores → is_valid=False
   - Test parsing errors → graceful failure

3. **Multi-candidate** (Task 2.1)
   - Test selects highest score
   - Test rejects all if below threshold
   - Test handles generation failures

### Integration Tests

4. **End-to-end flow**
   - Generate article with list section → verify skipped
   - Generate with narrative section → verify validated
   - Mock low validation scores → verify rejection

### Manual Testing

5. **Real articles**
   - Run on the Lisp article → verify no list replacement
   - Check validation logs for score distribution
   - Verify cost tracking accuracy

---

## Rollout Plan

### Week 1: Phase 1 (Foundation)

**Monday-Tuesday:**
- Implement Task 1.1 (list detection)
- Implement Task 1.2 (validation service)
- Write unit tests

**Wednesday:**
- Implement Task 1.3 (integration)
- Test on sample articles

**Thursday:**
- Deploy to staging
- Monitor rejection rates

**Friday:**
- Production deployment
- Collect metrics for 2-3 days

### Week 2: Phase 2 (Multi-Candidate)

**Monday-Tuesday:**
- Implement Task 2.1 (Mermaid selector)
- Write tests

**Wednesday:**
- Implement Task 2.2 (integration)
- Compare single vs multi-candidate quality

**Thursday-Friday:**
- A/B test (50% single, 50% multi)
- Analyze quality improvements vs cost

### Week 3: Phase 3 (Polish)

**Monday:**
- Implement Task 3.1 (configuration)
- Implement Task 3.2 (metrics)

**Tuesday-Friday:**
- Documentation updates
- Performance optimization
- Final production rollout

---

## Success Metrics

Track these after each phase:

| Metric | Phase 1 Target | Phase 2 Target |
|--------|---------------|----------------|
| **Rejection rate** | 15-25% | 10-15% |
| **Manual "helpful" rating** | >70% | >85% |
| **List sections skipped** | ~30% of sections | ~30% |
| **Cost per accepted diagram** | <$0.003 | <$0.008 |
| **Acceptance rate** | >75% | >85% |

---

## Cost Analysis

### Current State

- 3 diagrams/article × 50 articles = 150 diagrams/month
- Cost: ~$0.0015/diagram = **$0.225/month**

### Phase 1 (Foundation)

- List filtering: -30% attempts = 105 diagrams
- Validation: +$0.0005/diagram
- Cost: 105 × $0.002 = **$0.21/month** (slight savings!)

### Phase 2 (Multi-Candidate)

- 3 candidates + validation = 4x cost/attempt
- But 85% acceptance vs 75% = fewer retries
- Cost: 105 × $0.006 = **$0.63/month** (+200%)

### Budget Recommendation

- **Phase 1:** Deploy immediately (cost-neutral or saving)
- **Phase 2:** Deploy if budget allows **OR** reduce to 2 candidates (2x cost)
- **Alternative:** Use multi-candidate only for high-value articles

---

## File Checklist

### New Files

- [ ] `src/illustrations/diagram_validator.py`
- [ ] `src/illustrations/mermaid_quality_selector.py`
- [ ] `tests/test_diagram_validator.py`
- [ ] `tests/test_mermaid_quality_selector.py`

### Modified Files

- [ ] `src/illustrations/placement.py` (list detection)
- [ ] `src/pipeline/illustration_service.py` (integration)
- [ ] `src/config.py` (configuration)
- [ ] `tests/test_illustrations.py` (list detection tests)

### Documentation

- [ ] Update `docs/START-HERE.md` with validation info
- [ ] Update `README.md` with new configuration options
- [ ] Add validation examples to `docs/QUICK-START.md`

---

## Troubleshooting

### High Rejection Rates (>40%)

**Cause:** Validation threshold too strict  
**Fix:** Lower `diagram_validation_threshold` from 0.7 to 0.6

### Low Quality Despite Validation

**Cause:** Validation prompt not specific enough  
**Fix:** Add domain-specific validation criteria in prompt

### Excessive Costs

**Cause:** Too many candidates or sections  
**Fix:** 
- Reduce `mermaid_candidates` to 2
- Increase section word threshold to 100+
- Enable `skip_list_sections`

### Slow Generation

**Cause:** Sequential candidate generation  
**Fix:** Parallelize generation using `asyncio` (future enhancement)

---

## Future Enhancements

### Phase 4 (Optional)

1. **Semantic pre-filtering:** Use embeddings to match concepts to sections before generation
2. **Adversarial refinement:** Generator → Critic → Refine for high-value content
3. **Diagram caching:** Cache validated diagrams for similar sections
4. **Fine-tuned model:** Train custom model on accepted/rejected pairs
5. **User feedback loop:** Allow users to rate diagrams, feed back into validation

---

## Implementation Commands

### For Claude/Haiku to Execute

Each phase can be implemented with:

```
Phase 1, Task 1.1:
"Implement list section detection in placement.py as specified in the plan. 
Add _analyze_section_type() method and integrate with Section dataclass. 
Write the tests in test_illustrations.py."

Phase 1, Task 1.2:
"Create diagram_validator.py with DiagramValidator class as specified. 
Include ValidationResult dataclass and all methods. 
Create test_diagram_validator.py with the specified tests."

Phase 1, Task 1.3:
"Integrate DiagramValidator into illustration_service.py. 
Update _select_format_for_match() and generate_illustrations() 
as specified in the plan."

Phase 2, Task 2.1:
"Create mermaid_quality_selector.py with MermaidQualitySelector class. 
Include multi-candidate generation and validation. 
Create test_mermaid_quality_selector.py."

Phase 2, Task 2.2:
"Integrate MermaidQualitySelector into illustration_service.py. 
Replace single-candidate generation with multi-candidate selection."

Phase 3:
"Add configuration options to config.py and metrics tracking 
to IllustrationResult as specified in the plan."
```

---

## Summary

This plan addresses the nonsensical diagram problem through **layered defense:**

1. **Pre-filter** list sections (free)
2. **Validate** generated diagrams (cheap)
3. **Multi-candidate** selection (optional, higher quality)

**Phase 1** is the highest priority and **cost-neutral** due to reduced waste. **Phase 2** improves quality significantly but increases costs—deploy based on budget and quality requirements.

The plan is modular: each phase delivers value independently, and you can stop after Phase 1 if quality is sufficient.
