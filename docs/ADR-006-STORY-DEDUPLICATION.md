# ADR-006: Automated Story Deduplication

**Status:** Implemented  
**Date:** 2025-10-31  
**Context:** October 31 pipeline run published multiple articles from different sources about the same news stories

## Problem

During content generation, the pipeline collected multiple items from different sources (HackerNews, Mastodon, Reddit) that were about the **same underlying news story** but from different angles or perspectives.

### Examples from Oct 31, 2025 run:

**Case 1: Affinity Software**
- Source 1 (HackerNews): "Affinity Studio Goes Free: A Game Changer for Designers"
- Source 2 (Mastodon): "Affinity Software's Freemium Shift: What Artists Need to..."
- **Issue:** Both cover Affinity's business model change, but from different angles

**Case 2: ICC Open Source**
- Source 1 (Mastodon): "ICC Ditches Microsoft 365 for Open-Source: A Data Privacy..."
- Source 2 (Mastodon): "ICC's Bold Move: Embracing Open-Source Over Microsoft"
- **Issue:** Both cover ICC's cloud transition with different focuses

### Why Existing Dedup Didn't Catch This

The existing deduplication systems (`post_gen_dedup.py`, `semantic_dedup.py`, `adaptive_dedup.py`) focus on:
- **Near-identical content** - Same title, same summary
- **Published articles** - Post-generation checks
- **Exact duplicates** - >90% text similarity

They **correctly don't flag** these as duplicates because:
1. Different titles (not >75% similar)
2. Different angles/perspectives in content
3. Different sources (each from unique URL)
4. Intentional content variations from enrichment

## Decision

Implement **story clustering** that detects when multiple enriched items are about the same underlying news story **before generation**, using:

### Detection Criteria

Story similarity calculated from:
1. **Entity overlap** (50% weight) - Key indicator
   - Company names: "Affinity", "ICC", "Microsoft"
   - Technology terms: "freemium", "open-source", "Docker"
   - Extracted from title + summary + topics
   
2. **Topic overlap** (25% weight)
   - Shared tags indicate similar subject matter
   
3. **Title similarity** (15% weight)
   - Less important but still a signal
   
4. **Time proximity** (10% weight)
   - Published within 24 hours = more likely same story

**Threshold:** 0.55 similarity score = likely same story

### Implementation Approach

```python
# Before generation in select_article_candidates()
if deduplicate_stories:
    # 1. Find story clusters
    clusters = find_story_clusters(candidates, min_similarity=0.55)
    
    # 2. Report findings to user
    report_story_clusters(clusters, verbose=True)
    
    # 3. Filter: keep best item from each cluster
    candidates = filter_duplicate_stories(candidates, keep_best=True)
```

### Clustering Algorithm

Greedy clustering approach:
1. Sort items by quality score (best first)
2. For each item:
   - Check similarity against primary item in each existing cluster
   - If similarity ≥ 0.55, add to that cluster
   - Otherwise, create new cluster
3. Each cluster has:
   - Primary item (highest quality)
   - Story signature (top 5 entities)
   - Consolidation score (similarity confidence)

### Selection Strategy

**Current:** Keep best source from each story cluster
- Prioritizes quality over coverage
- Saves API costs by not generating duplicate stories
- User sees clear report of what was filtered

**Future Option:** Consolidate sources
- Merge perspectives from multiple sources into single article
- Richer context for article generator
- More comprehensive coverage
- Implemented in `consolidate_story_sources()` but not active yet

## Consequences

### Positive

1. **Automatic deduplication** of cross-source stories
2. **Cost savings** - Fewer articles to generate
3. **Better user experience** - No duplicate stories in feed
4. **Transparent** - Reports what was clustered and why
5. **Quality-first** - Always keeps the best source

### Negative

1. **Potential false positives** - Might cluster unrelated items
   - Mitigated by 0.55 threshold (tunable)
   - User can disable with `deduplicate_stories=False`

2. **Loses alternative perspectives** - Only keeps one source
   - Acceptable tradeoff for automatic pipeline
   - Can be addressed with consolidation in future

### Neutral

1. **Changes candidate selection** - Fewer items selected
   - This is the goal - better quality over quantity
   
2. **Adds processing time** - O(n²) clustering
   - Negligible for typical batch sizes (< 50 items)

## Testing

Test script: `scripts/test_story_clustering.py`

Covers:
- Affinity case (HackerNews + Mastodon)
- ICC case (Mastodon + Mastodon)
- Unrelated items (should NOT cluster)
- Mixed batch (realistic scenario)

Run: `python scripts/test_story_clustering.py`

## Configuration

### Enable/Disable

```python
# In generate.py
candidates = select_article_candidates(
    items,
    deduplicate_stories=True  # Set to False to disable
)
```

### Tune Threshold

```python
# In story_clustering.py
clusters = find_story_clusters(
    items,
    min_similarity=0.55  # Lower = more clustering, Higher = less
)
```

**Recommended values:**
- `0.50` - Aggressive (more clustering, some false positives)
- `0.55` - Balanced (current default)
- `0.60` - Conservative (fewer clusters, high confidence)

## Alternatives Considered

### 1. Editorial Review (Original Approach)

**Pros:** Human judgment, no false positives  
**Cons:** Manual work, not scalable, requires human in loop

**Decision:** Not chosen for automated pipeline, but still valid for manual review

### 2. Merge Articles Post-Generation

**Pros:** Can combine perspectives after generation  
**Cons:** Wastes API costs, more complex

**Decision:** Not chosen - prevention is better than cure

### 3. Block Specific Sources

**Pros:** Simple configuration  
**Cons:** Inflexible, doesn't adapt to story overlap

**Decision:** Not chosen - story clustering is more intelligent

## Future Enhancements

### 1. Source Consolidation Mode

Currently implemented but not active:

```python
# Instead of filtering, consolidate
for cluster in clusters:
    if cluster.should_consolidate:
        consolidated_item = consolidate_story_sources(cluster)
        # Pass to generator with multiple sources
```

This would create single articles that incorporate perspectives from all sources.

### 2. Related Articles Linking

For clusters that shouldn't be consolidated, add cross-references:

```yaml
---
title: "Affinity Studio Goes Free..."
related_articles:
  - 2025-10-31-affinity-software-freemium-shift.md
---
```

### 3. Adaptive Threshold Learning

Track user feedback on clustering decisions:
- If user manually removes clustered items → increase threshold
- If user manually marks items as duplicates → decrease threshold

### 4. Entity Ranking

Weight entities by importance:
- Company names: higher weight
- Generic terms ("software", "update"): lower weight

## See Also

- `src/story_clustering.py` - Implementation
- `scripts/test_story_clustering.py` - Test suite
- `docs/RELATED-ARTICLES-CURATION.md` - Original problem documentation
- `docs/ADR-002-ENHANCED-DEDUPLICATION.md` - Post-generation dedup
- `docs/ADR-004-ADAPTIVE-DEDUPLICATION.md` - Learning from duplicates
