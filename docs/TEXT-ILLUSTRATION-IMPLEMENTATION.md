# Text-Based Illustration Implementation Plan

## Overview

Improve Unicode-based text diagrams by enhancing prompts, formatting, quality selection, and swarm routing. Single-specialist tool in larger article-generation swarm.

---

## Phase 1: Foundation (3-4 hours, $0)

**Goal:** 50% quality improvement with better prompts and formatting.

### Task 1.1: Enhance AI Prompt for Text Diagrams

**File:** `src/illustrations/ai_ascii_generator.py`  
**Line:** ~85 (system message in `generate_for_section()`)

**Current:**

```python
"role": "system",
"content": "You are an expert at creating clear ASCII diagrams and tables. "
           "Generate well-formatted ASCII art that visualizes the concept. "
           "Use box drawing characters (─, │, ┌, ┐, └, ┘, ├, ┤, ┬, ┴, ┼) for clarity. "
           "Return ONLY the ASCII art, no explanations or markdown formatting.",
```

**Replace with:**

```python
"role": "system",
"content": """You are a specialist in creating professional Unicode-based diagrams for technical articles.

CONSTRAINTS:
- Width: 50-60 characters maximum (for mobile readability when centered)
- Alignment: All lines perfectly aligned in monospace font
- Return ONLY the diagram, no markdown or explanation

CHARACTER SETS:
- Box drawing: ┌ ┐ └ ┘ ─ │ ├ ┤ ┬ ┴ ┼ 
- Junctions: ├ ┤ ┬ ┴ ┼
- Arrows: → ↓ ← ↑ (for flow)
- Accents: ◆ ★ ✓ ✗ ● (for markers)
- Use appropriate Unicode—not ASCII dashes/pipes

QUALITY CHECKLIST:
✓ Consistent line lengths (within 2 chars)
✓ Proper character pairing (no broken corners/lines)
✓ Clear labels and hierarchy
✓ Minimal clutter—clean and professional
✓ Readable at 50-60 character width

COMMON PATTERNS:
- Trees: Use ├─ for branches, proper indentation
- Flows: Use → and ▼ for direction, box structure
- Tables: Use ┌─┬─┐ for headers, │ for columns
- Networks: Use ┌─┐ boxes with ─ connections""",
```

**Verification:** Test with a tree concept—diagram should be ~50-60 chars wide, center-aligned ready.

---

### Task 1.2: Fix Presentation Formatting

**File:** `src/illustrations/placement.py`  
**Location:** Update the `format_diagram_for_markdown()` function or add if missing

**Add/update function:**

```python
def format_diagram_for_markdown(diagram: str, section_title: str = "") -> str:
    """Wrap diagram with centering and proper spacing."""
    formatted = f"\n<div align=\"center\">\n\n```\n{diagram}\n```\n\n</div>\n"
    if section_title:
        formatted += f"\n*Figure: {section_title}*\n"
    return formatted
```

**Integration point:** In `_find_best_placement_for_concept()` or placement insertion logic, wrap diagrams before returning.

**Verification:** Generated articles should have centered, properly-spaced diagrams.

---

## Phase 2: Smart Selection & Routing (5-7 hours, ~$0.001/article)

**Goal:** 75-80% quality + swarm intelligence routing

### Task 2.1: Multi-Candidate Selection

**File:** `src/illustrations/ai_ascii_generator.py`  
**Action:** Add new class after `AIAsciiGenerator`

```python
class TextIllustrationQualitySelector:
    """Generate multiple candidates and select best."""
    
    def __init__(self, client: OpenAI, model: str = "gpt-3.5-turbo", n_candidates: int = 5):
        self.generator = AIAsciiGenerator(client, model)
        self.n_candidates = n_candidates
    
    def generate_best(self, section_title: str, section_content: str, concept_type: str) -> GeneratedAsciiArt:
        """Generate N candidates, score, return best."""
        candidates = []
        
        for i in range(self.n_candidates):
            art = self.generator.generate_for_section(section_title, section_content, concept_type)
            if art:
                score = self._score(art.content, concept_type)
                candidates.append((score, art))
        
        if not candidates:
            return None
        
        # Sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_art = candidates[0]
        
        # Add metadata
        best_art.quality_score = best_score
        best_art.candidates_tested = len(candidates)
        
        return best_art
    
    def _score(self, content: str, concept_type: str) -> float:
        """Score diagram on alignment, clarity, concept match."""
        score = 0.0
        lines = content.split('\n')
        
        # Alignment (30%) - do lines have consistent length?
        if lines:
            lengths = [len(l) for l in lines if l.strip()]
            if lengths:
                avg_len = sum(lengths) / len(lengths)
                variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
                alignment = 1.0 - min(1.0, variance / 100)
                score += alignment * 0.30
        
        # Character variety (20%) - appropriate chars for concept?
        char_sets = {
            "network_topology": ['─', '│', '┌', '┐', '└', '┘'],
            "data_flow": ['─', '→', '│', '▼'],
            "comparison": ['│', '─', '┼', '┤', '├'],
            "hierarchy": ['├', '─', '│', '└'],
        }
        chars = char_sets.get(concept_type, [])
        if chars:
            matches = sum(1 for c in chars if c in content)
            char_score = min(1.0, matches / max(len(chars), 1))
            score += char_score * 0.20
        
        # Clarity (20%) - proper structure?
        has_structure = '┌' in content or '├' in content or '┬' in content
        structure_score = 1.0 if has_structure else 0.5
        score += structure_score * 0.20
        
        # Content density (15%) - not too sparse/crowded?
        non_ws = sum(1 for c in content if c.strip())
        total = len(content)
        density = min(1.0, non_ws / max(total, 1))
        score += density * 0.15
        
        # Width constraint (15%) - under 60 chars?
        max_width = max(len(l) for l in lines) if lines else 0
        width_score = 1.0 if max_width <= 60 else 0.5
        score += width_score * 0.15
        
        return min(1.0, score)
```

**Integration:** In orchestrator `generate_single_article()`, replace `AIAsciiGenerator` instantiation with `TextIllustrationQualitySelector`.

**Verification:** Generated diagrams should have quality_score metadata; check scores are 0.6-1.0 range.

---

### Task 2.2: Capability Advisor (Smart Tool Routing)

**File:** New file `src/illustrations/capability_advisor.py`

```python
class TextIllustrationCapabilityAdvisor:
    """Tell orchestrator if text-based diagrams are appropriate."""
    
    def should_use_text(
        self,
        concept_type: str,
        complexity: float,  # 0-1 scale
        content_length: int,  # number of items/steps
        requirements: dict = None
    ) -> tuple[bool, str, float]:
        """
        Returns: (should_use, reason, confidence_0_to_1)
        
        Example:
            (True, "hierarchy_simple_tree", 0.95)
            (False, "system_complex_use_svg", 0.85)
        """
        requirements = requirements or {}
        
        # Decision tree via type-safe function dispatch
        def _check_hierarchy(comp: float, len_: int) -> tuple:
            if comp < 0.7:
                return (True, "hierarchy_text_tree_simple", 0.95)
            return (False, "hierarchy_use_svg", 0.85)
        
        def _check_process_flow(comp: float, len_: int) -> tuple:
            if len_ <= 3 and comp < 0.6:
                return (True, "process_text_simple", 0.90)
            elif len_ <= 5 and comp < 0.5:
                return (True, "process_text_moderate", 0.75)
            return (False, "process_use_mermaid", 0.85)
        
        def _check_comparison(comp: float, len_: int) -> tuple:
            if len_ <= 8:
                return (True, "comparison_text_table", 0.95)
            return (False, "comparison_use_svg_matrix", 0.80)
        
        def _check_timeline(comp: float, len_: int) -> tuple:
            if len_ <= 5 and comp < 0.6:
                return (True, "timeline_text_simple", 0.90)
            return (False, "timeline_use_mermaid", 0.85)
        
        def _check_data_structure(comp: float, len_: int) -> tuple:
            if comp < 0.6:
                return (True, "data_structure_text", 0.85)
            return (False, "data_structure_use_svg", 0.80)
        
        def _check_network_topology(comp: float, len_: int) -> tuple:
            if len_ <= 4 and comp < 0.6:
                return (True, "network_text_simple", 0.80)
            return (False, "network_use_mermaid", 0.90)
        
        # Safe dispatch
        checkers = {
            "hierarchy": _check_hierarchy,
            "process_flow": _check_process_flow,
            "comparison": _check_comparison,
            "timeline": _check_timeline,
            "data_structure": _check_data_structure,
            "network_topology": _check_network_topology,
        }
        
        checker = checkers.get(concept_type)
        if checker:
            return checker(complexity, content_length)
        
        # Default: uncertain
        return (False, "uncertain_concept", 0.5)
```

**Integration:** In orchestrator Step 6.5 (illustration routing), call all advisors before generating.

---

### Task 2.3: Update Orchestrator Routing Logic

**File:** `src/pipeline/orchestrator.py`  
**Location:** Step 6.5, around line 120-180 (illustration generation)

**Add routing logic before generator selection:**

```python
# Step 6.5: Smart illustration routing
from ..illustrations.capability_advisor import TextIllustrationCapabilityAdvisor
from ..illustrations.ai_ascii_generator import TextIllustrationQualitySelector

if config.enable_illustrations and should_add_illustrations(generator.name, content):
    concepts_detected = detect_concepts(content)
    
    if concepts_detected:
        text_advisor = TextIllustrationCapabilityAdvisor()
        
        # For each concept, get capability recommendations
        for concept in concepts_detected[:3]:  # Max 3 illustrations
            # Estimate complexity (simple heuristic)
            complexity = len(concept.description or "") / 100.0  # 0-1
            content_len = len(concept.description.split()) if concept.description else 0
            
            # Get text advisor opinion
            text_should_use, text_reason, text_confidence = text_advisor.should_use_text(
                concept.name, 
                complexity, 
                content_len
            )
            
            # If text recommends (high confidence), use it
            if text_should_use and text_confidence > 0.75:
                try:
                    # Use quality selector instead of basic generator
                    selector = TextIllustrationQualitySelector(client)
                    ascii_art = selector.generate_best(
                        section_title=concept.name,
                        section_content=section_content,
                        concept_type=concept.name
                    )
                    
                    if ascii_art and ascii_art.quality_score > 0.6:
                        # Use this illustration
                        console.print(
                            f"[dim]  ✓ {concept.name}: "
                            f"text (score: {ascii_art.quality_score:.2f})[/dim]"
                        )
                        # Format and inject
                        formatted = format_diagram_for_markdown(
                            ascii_art.content, 
                            concept.name
                        )
                        # ... inject into content
                    elif ascii_art:
                        console.print(
                            f"[yellow]  ⚠ {concept.name}: "
                            f"low score ({ascii_art.quality_score:.2f}), skipping[/yellow]"
                        )
                except Exception as e:
                    console.print(f"[yellow]  ⚠ Text diagram failed: {e}[/yellow]")
            else:
                console.print(
                    f"[dim]  → {concept.name}: "
                    f"text not ideal ({text_reason}), "
                    f"routing to other formats[/dim]"
                )
```

**Verification:** Logs should show routing decisions and quality scores.

---

## Phase 3: Polish (Optional - only for high-value diagrams)

**Goal:** 85-90% quality for important illustrations

### Task 3.1: Review & Refinement Loop

**File:** New file `src/illustrations/text_review_refine.py`

```python
class TextIllustrationReviewRefine:
    """Two-stage: generate, review, optionally refine."""
    
    def generate_with_review(
        self,
        section_title: str,
        section_content: str,
        concept_type: str,
        importance: float = 0.5  # 0=low, 1=high
    ) -> GeneratedAsciiArt:
        """Only do review for important diagrams."""
        
        if importance < 0.7:
            # Just use quick generation
            selector = TextIllustrationQualitySelector(self.client)
            return selector.generate_best(section_title, section_content, concept_type)
        
        # Stage 1: Generate
        generator = AIAsciiGenerator(self.client)
        initial = generator.generate_for_section(section_title, section_content, concept_type)
        
        if not initial:
            return None
        
        # Stage 2: Review quality
        review_prompt = f"""
Review this {concept_type} Unicode diagram. Rate quality 0-1.
Identify specific issues (alignment, clarity, complexity).

Diagram:
```

{initial.content}

```

JSON response: {{"score": 0.0-1.0, "issues": ["issue1", ...], "fixes": ["fix1", ...]}}
"""
        
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": review_prompt}],
            temperature=0.3,
            max_tokens=200
        )
        
        try:
            import json
            review = json.loads(response.choices[0].message.content)
            review_score = review.get("score", 0.5)
        except:
            review_score = 0.5
        
        # Stage 3: If score low, refine
        if review_score < 0.7:
            refine_prompt = f"""
Improve this diagram to fix issues: {', '.join(review.get('issues', [])[:2])}

Original:
```

{initial.content}

```

Create improved version addressing: {', '.join(review.get('fixes', [])[:2])}
Width max 60 chars. Return ONLY improved diagram.
"""
            
            refine_response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": refine_prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            refined_content = refine_response.choices[0].message.content.strip()
            
            return GeneratedAsciiArt(
                art_type=initial.art_type,
                content=refined_content,
                alt_text=initial.alt_text,
                prompt_cost=initial.prompt_cost + 0.0005,
                completion_cost=initial.completion_cost + 0.0015,
                quality_score=review_score,
                review_cycles=1
            )
        
        # Score already good
        return GeneratedAsciiArt(
            art_type=initial.art_type,
            content=initial.content,
            alt_text=initial.alt_text,
            prompt_cost=initial.prompt_cost,
            completion_cost=initial.completion_cost,
            quality_score=review_score,
            review_cycles=0
        )
```

**Integration:** Optional—use only when `article_importance > 0.8`.

---

## Testing Checklist

### Phase 1 (After Tasks 1.1 & 1.2)

- [ ] Generated text diagram is 50-60 characters wide
- [ ] Diagram is center-aligned in rendered article
- [ ] Spacing (blank lines) before and after is correct
- [ ] Unicode characters render properly (not ASCII substitutes)
- [ ] Quality feels professional (no jagged edges, aligned boxes)

### Phase 2 (After Tasks 2.1, 2.2, 2.3)

- [ ] `TextIllustrationQualitySelector` generates 5 candidates
- [ ] Quality scores range 0.6-1.0
- [ ] Capability advisor makes routing decisions
- [ ] Logs show routing logic + reason
- [ ] Low-quality diagrams skipped with fallback
- [ ] Correct format chosen for concept type

### Phase 3 (After Task 3.1)

- [ ] Review loop runs only for high-importance articles
- [ ] Quality scores improve after refinement
- [ ] Cost tracking shows review + refinement overhead

---

## Files Summary

**Existing files to modify:**

- `src/illustrations/ai_ascii_generator.py` — Update prompt (1.1), add selector class (2.1)
- `src/illustrations/placement.py` — Add formatting wrapper (1.2)
- `src/pipeline/orchestrator.py` — Add routing logic (2.3)

**New files to create:**

- `src/illustrations/capability_advisor.py` — Swarm routing logic (2.2)
- `src/illustrations/text_review_refine.py` — Optional polish (3.1)

---

## Success Metrics

| Metric | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|
| Quality % good | 70% | 80% | 90% |
| Routing accuracy | N/A | 85% | 95% |
| Cost/article | $0 | +$0.001 | +$0.002 |
| Effort | 3-4h | +5-7h | +10-16h |

---

## Deployment Order

1. **Phase 1** → Deploy immediately, test 5 articles
2. **Phase 2** → After Phase 1 validated, deploy routing + selector
3. **Phase 3** → Optional, only if Phase 2 results warrant polish

All phases backward-compatible. Can stop at any point.
