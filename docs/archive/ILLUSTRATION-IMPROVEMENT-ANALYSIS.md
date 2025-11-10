# Illustration System Improvement Analysis

**Date:** November 3, 2025
**Problem:** Mermaid diagrams replacing lists with nonsensical visualizations

## Problem Analysis

### Example from Lisp Article

The article has TWO flowchart diagrams inserted in the "Rise of Modern Lisp Dialects" section that appear to be random/generic:

1. A flowchart about "Check_Clojure" that doesn't match the prose
2. A generic "Data Collection → Data Cleaning → Data Transformation" pipeline that has nothing to do with Clojure or Lisp

The actual content in that section is a BULLETED LIST about Clojure's features:

- Simplicity and Power
- Concurrency
- Interoperability

**The system replaced a perfectly good list with random diagrams.**

### Root Causes

#### 1. **Weak Content-to-Diagram Validation**

- Prompts in `AIMermaidGenerator._build_prompt()` only use first 500 chars of section
- No validation that the diagram actually reflects the section content
- Temperature=0.7 allows creativity but introduces randomness
- System message is too generic: "Generate valid Mermaid syntax that visualizes the concept"

#### 2. **Over-Scoring List Sections**

- Lists with keywords like "simplicity", "concurrency" score high for concepts
- Section parser doesn't distinguish between "list section" vs "narrative section"
- 75-word threshold catches short list sections

#### 3. **No Diagram Relevance Check**

- Generated diagrams are never validated against source content
- No semantic similarity check between diagram and section
- Trust AI output blindly without quality gates

#### 4. **Wrong Concept Detection**

- "Clojure features" section detected as "system_architecture" or "data_flow"
- List-based sections shouldn't trigger visual concepts
- Concept detector over-matches on technical keywords

## Proposed Solutions

### Option 1: Add Post-Generation Validation (RECOMMENDED)

**Cost:** Low (1 extra API call per diagram)
**Impact:** High (catches nonsensical diagrams)

After generating a diagram, use an LLM to score:

1. Does this diagram accurately represent the section content? (0-1)
2. Does it add explanatory value beyond reading the text? (0-1)

Reject diagrams scoring < 0.7 on either metric.

**Implementation:**

```python
def validate_diagram_relevance(
    section_content: str,
    diagram_description: str,
    threshold: float = 0.7
) -> tuple[bool, float, str]:
    """Validate diagram matches content."""
    prompt = f"""Rate this diagram's relevance to the source content on 0-1 scale.

Section content:
{section_content[:800]}

Diagram description:
{diagram_description}

Reply with JSON:
{{
  "accuracy": 0.0-1.0,  // Does diagram match content?
  "value_add": 0.0-1.0, // Does it explain better than text?
  "reason": "brief explanation"
}}
"""
    # Score and validate
    # Return (is_valid, score, reason)
```

### Option 2: Improve List Detection & Exclusion

**Cost:** None (deterministic)
**Impact:** Medium (prevents some bad cases)

Enhance section parser to:

- Detect list-heavy sections (>50% lines starting with `-`, `*`, `•`, digits)
- Mark sections as `section_type: "list"` vs `"narrative"`
- Skip illustration for list sections OR only allow ASCII tables

**Implementation:**

```python
def _analyze_section_type(self, content: str) -> str:
    """Determine section structure type."""
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    list_lines = sum(1 for l in lines if re.match(r'^[-*•\d]+\.\s', l))
    
    if list_lines / len(lines) > 0.5:
        return "list"
    return "narrative"
```

### Option 3: Strengthen AI Prompts

**Cost:** None (prompt engineering)
**Impact:** Medium (reduces but doesn't eliminate bad outputs)

Improve system prompt:

```
"You are an expert at creating ACCURATE Mermaid diagrams.
The diagram MUST directly visualize concepts from the provided content.
If the content is a list of features, DO NOT create a generic flowchart.
If you cannot create an accurate diagram, return 'SKIP' instead.
Generate ONLY valid Mermaid syntax or 'SKIP'."
```

Add examples to prompt showing when to skip.

### Option 4: Multi-Candidate Generation with Selection

**Cost:** High (3-5x API calls)
**Impact:** High (pick best of N)

Similar to existing `TextIllustrationQualitySelector`:

- Generate 3 candidate diagrams
- Use LLM to score each against content
- Select highest-scoring candidate
- Reject if all score < threshold

**Already exists for ASCII, extend to Mermaid.**

### Option 5: Concept-Content Semantic Matching

**Cost:** Medium (embeddings)
**Impact:** High (catches mismatches early)

Before generating diagrams:

- Embed section content
- Embed concept description
- Compute cosine similarity
- Skip if similarity < 0.6

Prevents "data_flow" concept from matching "Clojure features list".

## Recommendations

### Tier 1 (Immediate, High Impact)

1. **Implement Option 1**: Post-generation validation (~50 lines)
2. **Implement Option 2**: List section detection (~30 lines)

**Combined benefit:** Catches 80%+ of bad diagrams at minimal cost

### Tier 2 (Quick Win)

3. **Implement Option 3**: Better prompts (just edit strings)

### Tier 3 (If Budget Allows)

4. **Implement Option 4**: Multi-candidate Mermaid generation (like ASCII)

## Cost Analysis

Current cost per diagram: ~$0.0005 - $0.002

- Option 1 validation: +$0.0005 per diagram (100 tokens)
- Option 2: Free (deterministic)
- Option 3: Free (prompt change)
- Option 4: +$0.002 - $0.006 (3x generation)

For 3 diagrams/article × 50 articles:

- Current: $0.15 - $0.30
- With validation (Opt 1+2+3): $0.225 - $0.375 (+50%)
- With multi-candidate (Opt 4): $0.45 - $0.90 (+200%)

## Success Metrics

After implementation, measure:

- **Rejection rate**: % diagrams rejected by validation
- **Manual review**: % diagrams rated "helpful" by humans
- **Section type accuracy**: % list sections correctly identified
- **Cost per quality diagram**: Total cost / accepted diagrams

Target: <10% rejection rate, >80% "helpful" rating

## Implementation Priority

1. **Phase 1 (This week):**
   - Add list section detection
   - Add post-generation validation
   - Update prompts with "SKIP" capability

2. **Phase 2 (Next sprint):**
   - Extend QualitySelector to Mermaid
   - Add semantic similarity pre-filtering

3. **Phase 3 (Future):**
   - Machine learning classifier for "should illustrate?"
   - Fine-tuned model for diagram generation
