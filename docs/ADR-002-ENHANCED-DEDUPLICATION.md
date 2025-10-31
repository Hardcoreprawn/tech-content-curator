# ADR-002: Enhanced Deduplication Strategy for Same-Day Content

**Status:** Proposed  
**Date:** 2025-10-31  
**Context:** Found duplicate "Affinity Software" articles published on same day from different sources

## Problem

The current deduplication system (`semantic_dedup.py`) catches many duplicates but misses some same-day duplicates:
- **Threshold:** 0.6 similarity (60%) - allows moderately different phrasings to pass
- **Scope:** Only compares content at collection time, not post-generation
- **Late Discovery:** Duplicates only caught if they pass semantic check; manually found after publication

Example: Two articles about Affinity Software going freemium:
- Source 1: Mastodon (@Haste) - quality_score: 0.59
- Source 2: HackerNews (@dagmx) - quality_score: 0.50
- Both published same day, different sources, similar titles/content
- Only caught manually after publication

## Proposed Solutions

### 1. **Stricter Same-Day Deduplication** ⭐ PRIORITY
After enrichment (before generation), check generated articles:
- **Title similarity:** Use `difflib.SequenceMatcher` for title matching (threshold: 0.75)
- **Summary similarity:** Check generated summaries (threshold: 0.65)
- **Tag overlap:** If 80%+ tags match, flag as likely duplicate
- **Theme matching:** If 3+ entities overlap + high keyword overlap, flag duplicate

Implementation in `src/generate.py`:
```python
def check_article_duplicates(enriched_items, existing_articles):
    """Check if new articles duplicate existing ones."""
    for item in enriched_items:
        for existing in existing_articles:
            # Compare titles
            title_sim = SequenceMatcher(None, item.title, existing.title).ratio()
            # Compare summaries
            summary_sim = SequenceMatcher(None, item.summary, existing.summary).ratio()
            # Compare tags
            tag_overlap = len(set(item.tags) & set(existing.tags)) / max(len(item.tags), len(existing.tags))
            
            if title_sim > 0.75 or (summary_sim > 0.65 and tag_overlap > 0.5):
                yield (item, existing, {
                    'title_similarity': title_sim,
                    'summary_similarity': summary_sim,
                    'tag_overlap': tag_overlap
                })
```

### 2. **Daily Duplicate Report**
Add logging/reporting of near-duplicates:
- Create `data/duplicate_candidates.json` tracking close matches
- Alert when same-day articles are >75% similar
- Include quality scores to keep higher-quality version
- Log user actions for feedback system

### 3. **Feedback Loop Integration**
Feed manual deduplication into learning system:
- When user removes a duplicate, record it in `dedup_feedback.json`
- Analyze patterns (both from same source, different sources, etc.)
- Adjust thresholds based on false negatives

### 4. **Temporal Deduplication**
Consider publication date in duplicate detection:
- Same day + same topic = higher suspicion
- Different dates + same content = RSS loop or repost
- Articles within 12 hours of same topic/entities = high-risk duplicates

## Implementation Priority

1. **Phase 1 (Immediate):** Add `check_article_duplicates()` in `src/generate.py` 
2. **Phase 2 (Week 1):** Integrate with feedback system
3. **Phase 3 (Week 2):** Add temporal analysis and reporting

## Expected Improvements

- ✅ Catch same-day duplicates before publication
- ✅ Higher precision (reduce false positives)
- ✅ Learn from user corrections
- ✅ Clear audit trail of deduplication decisions

## Consequences

- Slightly slower generation (extra comparison pass)
- Must maintain duplicate candidates file
- Need UI/command to review flagged duplicates

## Related Code

- `src/semantic_dedup.py` - Current semantic deduplication
- `src/dedup_feedback.py` - Feedback system
- `src/generate.py` - Article generation (where enhancement should go)
- `src/collect.py` - Collection (current dedup location)
- `data/dedup_patterns.json` - Learned patterns
- `data/dedup_feedback.json` - Feedback history

---

**Next Steps:**
1. Implement `check_article_duplicates()` helper function
2. Integrate into generation pipeline
3. Create duplicate candidates reporting
4. Test with past duplicates to validate thresholds
