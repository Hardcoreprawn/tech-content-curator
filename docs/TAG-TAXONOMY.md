# AI-Managed Tag Taxonomy

The tag normalization system now includes **AI-managed evolution** that learns from actual content usage and adapts over time.

## Overview

Instead of manually managing hundreds of tag variations, the system:

1. ✅ **Normalizes tags** - Maps variations to canonical forms (e.g., "AI" → "artificial-intelligence")
2. ✅ **Learns from usage** - Promotes frequently used tags to canonical status
3. ✅ **Prunes unused tags** - Removes canonical tags that aren't being used
4. ✅ **Auto-discovers mappings** - Finds new variations and adds mappings
5. ✅ **Validates with AI** - Uses GPT-4o-mini to validate all changes

## Current State

**Before normalization:**
- 601 unique tags across 160 articles
- 4.3 tags per article average
- Massive duplication (e.g., "ai", "AI", "artificial intelligence", "GenAI")

**After normalization:**
- 35 canonical tags
- 94.2% reduction in unique tags
- Consistent naming across all articles

## Components

### 1. Tag Normalizer (`src/content/tag_normalizer.py`)

Core normalization system with:
- **Canonical taxonomy** (~100 curated tags)
- **Tag mappings** (500+ variations → canonical)
- **Fuzzy matching** (catches typos)
- **Max 5 tags** per article

**Automatically applied** to all new articles via:
- `src/enrichment/ai_analyzer.py` - During topic extraction
- `src/pipeline/article_builder.py` - During metadata creation
- `src/fallback_content.py` - During fallback generation

### 2. Tag Analyzer (`scripts/analyze_tags.py`)

Shows current tag statistics:
```bash
uv run python scripts/analyze_tags.py
```

Displays:
- Current vs normalized tag counts
- Example normalizations
- Top 20 most used canonical tags
- Projected improvements

### 3. Taxonomy Evolution (`scripts/evolve_taxonomy.py`)

AI-managed taxonomy updates:
```bash
uv run python scripts/evolve_taxonomy.py
```

**What it does:**
1. Analyzes all existing articles
2. Finds frequently used tags not in canonical list (used 5+ times)
3. Finds canonical tags barely used (used <2 times)
4. Asks GPT-4o-mini to validate proposed changes
5. Updates `tag_normalizer.py` with new taxonomy
6. Creates backup before changes

**When to run:**
- Monthly (or when you notice tag drift)
- After generating 50+ new articles
- When analysis shows many discarded tags

**Safety:**
- ✅ Creates backup before changes
- ✅ Asks for confirmation before writing
- ✅ AI validates all changes
- ✅ Conservative by default

## Usage

### For New Articles

**Nothing to do!** Tag normalization happens automatically:

```python
# In enrichment phase
topics = extract_topics_and_themes(item, client)
# → Returns normalized canonical tags

# In article generation
metadata = create_article_metadata(item, title, content)
# → metadata["tags"] contains max 5 canonical tags
```

### Monthly Maintenance

1. **Check tag statistics:**
   ```bash
   uv run python scripts/analyze_tags.py
   ```

2. **If many tags are being discarded (20%+), evolve taxonomy:**
   ```bash
   uv run python scripts/evolve_taxonomy.py
   ```

3. **Review and approve AI recommendations**

4. **Run tests to verify:**
   ```bash
   uv run pytest tests/test_tag_normalizer.py
   ```

## Taxonomy Philosophy

### What Makes a Good Canonical Tag?

✅ **DO include:**
- Programming languages: `python`, `rust`, `javascript`
- Core technologies: `kubernetes`, `docker`, `postgresql`
- Broad topics: `machine-learning`, `cybersecurity`, `web-development`
- Common patterns: `devops`, `cloud-computing`, `open-source`

❌ **DON'T include:**
- Too specific: `python-3.14-free-threading`
- Too generic: `programming`, `technology`
- One-off topics: `specific-company-product-v2`
- Temporary trends: `hot-framework-of-the-month`

### Drift Management

The system allows **controlled drift**:

- **Promote** tags when they're used 5+ times (shows sustained interest)
- **Remove** tags when they're used <2 times (not resonating)
- **AI validates** to prevent bad additions
- **Backup** lets you revert if needed

This lets the taxonomy **evolve with your content** rather than fighting it.

## Examples

### AI Validation in Action

**Input to AI:**
```
TAGS TO PROMOTE (frequently used but not canonical):
- wasm (raw: WebAssembly, used 12x)
- edge-computing (raw: edge computing, used 8x)
- mlops (raw: MLOps, used 6x)

TAGS TO REMOVE (canonical but underused):
- quantum-computing (used 0x)
- blockchain (used 1x)
```

**AI Response:**
```json
{
  "promote": ["wasm", "edge-computing"],
  "remove": ["quantum-computing"],
  "mappings": {
    "webassembly": "wasm",
    "edge computing": "edge-computing",
    "mlops": "machine-learning"
  },
  "reasoning": "WebAssembly and edge computing show strong usage. Quantum computing is too specialized for current content. MLOps is better mapped to existing machine-learning tag. Kept blockchain as it may be used in future articles."
}
```

### Tag Normalization Examples

| Raw Tag | Normalized | Reason |
|---------|-----------|--------|
| `ai` | `artificial-intelligence` | Direct mapping |
| `AI adoption` | `artificial-intelligence` | Mapped via pattern |
| `machine learning models` | `machine-learning` | Mapped via pattern |
| `k8s` | `kubernetes` | Common abbreviation |
| `python programming` | `python` | Redundant word removed |
| `some random topic` | ❌ discarded | Not in taxonomy |

## Configuration

### Adjust Thresholds

In `scripts/evolve_taxonomy.py`:

```python
# Minimum usage to promote a tag
promote_candidates = identify_candidates_for_promotion(stats, min_usage=5)

# Minimum usage to keep a canonical tag
remove_candidates = identify_underused_tags(stats, min_usage=2)
```

**Recommendations:**
- **Promote threshold (5)**: Higher = more conservative, only well-established tags
- **Remove threshold (2)**: Lower = more aggressive pruning of unused tags

### Expand Initial Taxonomy

To add tags manually to `src/content/tag_normalizer.py`:

```python
CANONICAL_TAGS = {
    # ... existing tags ...
    "new-technology",
    "emerging-concept",
}

TAG_MAPPINGS = {
    # ... existing mappings ...
    "new tech": "new-technology",
    "new-tech": "new-technology",
}
```

## Testing

Comprehensive test suite in `tests/test_tag_normalizer.py`:

```bash
# Run all normalization tests
uv run pytest tests/test_tag_normalizer.py -v

# Test specific functionality
uv run pytest tests/test_tag_normalizer.py::TestNormalizeTag -v
```

**Tests cover:**
- Direct mappings (AI → artificial-intelligence)
- Fuzzy matching (typos)
- Batch normalization
- Tag limits (max 5)
- Deduplication
- Edge cases

## Benefits

### For Content Quality
- ✅ **Consistent tags** across all articles
- ✅ **Better discoverability** - readers find related content
- ✅ **SEO improvements** - canonical terms rank better
- ✅ **Reduced clutter** - 35 tags instead of 601

### For Maintenance
- ✅ **Self-managing** - AI evolves taxonomy based on usage
- ✅ **Low overhead** - monthly 5-minute review
- ✅ **Data-driven** - changes based on actual patterns
- ✅ **Reversible** - backups before every change

### For Analytics
- ✅ **Track trends** - see which topics are popular
- ✅ **Identify gaps** - find underserved areas
- ✅ **Content planning** - make data-driven decisions

## Troubleshooting

### Too Many Tags Still Discarded

If >30% of tags are discarded after normalization:

1. Run `scripts/evolve_taxonomy.py` to promote common tags
2. Or manually add to taxonomy if AI doesn't recommend
3. Review AI prompt - may need to be more specific

### Taxonomy Growing Too Large

If canonical tags exceed 150:

1. Review underused tags - remove those <2 uses
2. Merge similar tags (e.g., `frontend` + `front-end` → `frontend`)
3. Increase promotion threshold to be more selective

### AI Makes Bad Recommendations

1. Don't approve the changes (say 'N' when prompted)
2. Adjust thresholds to be more conservative
3. Review AI prompt in `ask_ai_to_validate_changes()`

## Future Enhancements

Potential improvements:

- **Hierarchical tags** - Parent/child relationships (e.g., `python` → `programming-languages`)
- **Semantic similarity** - Use embeddings to find related tags
- **Auto-consolidation** - AI suggests merging similar tags
- **Tag statistics dashboard** - Web UI for tracking trends
- **A/B testing** - Track which tags drive engagement

---

**Last Updated:** November 6, 2025  
**Status:** ✅ Implemented and tested  
**Next Review:** Monthly or after 50+ new articles
