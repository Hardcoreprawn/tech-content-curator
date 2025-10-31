# ADR-004: Adaptive Deduplication and Cost Optimization

**Date:** 2024-10-31  
**Status:** ACCEPTED  
**Supersedes:** ADR-002 (Enhanced Deduplication)  
**Relates to:** ADR-003 (Pipeline Integration)

## Context

After implementing post-generation deduplication (ADR-002, ADR-003), we discovered:

1. **Cost Waste**: Generating articles only to reject them as duplicates wastes API credits ($0.001-0.003 per rejected article)
2. **No Learning**: The system doesn't learn from detected duplicates to prevent similar articles in the future
3. **Reactive Only**: Deduplication happens AFTER generation, too late to save costs
4. **No Tracking**: No visibility into how much we're wasting on duplicates
5. **Pattern Blindness**: Similar topics keep getting regenerated (e.g., "Mastodon 4.5 features" × 5 articles)

### Problem Statement

**We need to reject duplicate candidates BEFORE generation, not after, and learn from our mistakes to continuously improve.**

## Decision

Implement a **comprehensive adaptive deduplication system** with four integrated components:

### 1. Recent Content Cache (`src/recent_content_cache.py`)

**Purpose:** Track recently generated articles to catch pre-generation duplicates

**Features:**
- Loads articles from last N days (configurable, default: 14)
- Fast similarity checking against cached metadata
- Title, summary, and tag comparison
- Reports potential duplicates with detailed metrics

**Usage:**
```python
cache = RecentContentCache(content_dir, cache_days=14, similarity_threshold=0.70)
is_dup, match = cache.is_duplicate_candidate(title, summary, tags)
if is_dup:
    # Reject before generation
    cost_tracker.record_pre_gen_rejection(title)
```

**Benefits:**
- Prevents regenerating similar content within 2 weeks
- Saves ~$0.002 per rejected candidate
- Fast (metadata-only, no file parsing)

### 2. Cost Tracker (`src/costs.py`)

**Purpose:** Track all generation costs including waste

**Tracks:**
- **Successful articles**: Full costs (content, title, slug, image)
- **Rejected duplicates**: Wasted costs after generation
- **Pre-gen rejections**: Estimated savings from early rejection

**Features:**
- Persistent JSON storage (`data/generation_costs.json`)
- Summary reports with efficiency metrics
- Waste pattern analysis
- Historical cost data for optimization

**Metrics:**
- Total spent vs. useful articles
- Efficiency rate (% of cost that produced articles)
- Wasted cost on duplicates
- Savings from pre-generation filtering

**Usage:**
```python
cost_tracker = CostTracker()

# On successful save
cost_tracker.record_successful_generation(title, filename, costs)

# On post-gen duplicate
cost_tracker.record_rejected_duplicate(title, costs, duplicate_of)

# On pre-gen rejection
cost_tracker.record_pre_gen_rejection(title, estimated_cost=0.002)

# Print summary
cost_tracker.print_summary(days=30)
```

### 3. Adaptive Feedback (`src/adaptive_dedup.py`)

**Purpose:** Learn from detected duplicates to prevent future similar articles

**How it works:**
1. When duplicate detected post-generation → Extract patterns
2. Patterns stored: common tags, keywords, title phrases
3. Before next generation → Check candidates against learned patterns
4. Matching candidates rejected early

**Pattern Learning:**
- Extracts common keywords from duplicate titles
- Identifies shared tags between duplicates
- Tracks frequency (confidence increases with more detections)
- Stores example titles for reference

**Pattern Matching:**
- Keyword overlap scoring
- Tag overlap scoring
- Confidence weighting (more detections = higher confidence)
- Threshold-based rejection (default: 0.6)

**Data Storage:** `data/adaptive_dedup_patterns.json`

**Example Pattern:**
```json
{
  "topic_keywords": ["mastodon", "features", "release"],
  "common_tags": ["mastodon", "fediverse", "social-media"],
  "detected_count": 5,
  "avg_similarity": 0.87,
  "example_titles": [
    "Mastodon 4.5 New Features",
    "Unlocking Mastodon 4.5 Features",
    "Mastodon 4.5 Developer Tools"
  ]
}
```

### 4. Pipeline Integration

**Pre-Generation Filtering** (in `select_article_candidates()`):
1. Load recent content cache
2. Load adaptive patterns
3. For each candidate:
   - Check against recent articles → Reject if similar
   - Check against learned patterns → Reject if matches
   - Record rejection + estimated savings
4. Only pass unique candidates to generation

**Post-Generation Learning** (in `generate_articles_from_enriched()`):
1. Generate article
2. Check for duplicates (existing logic)
3. If duplicate detected:
   - Record wasted cost
   - Learn pattern from duplicate pair
   - Save pattern for future filtering
4. If unique:
   - Save article
   - Record successful cost

## Implementation Details

### Data Flow

```
┌─────────────────┐
│ Enriched Items  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│ select_article_candidates() │
│  ├─ Recent Content Cache    │──► Reject if similar to recent
│  ├─ Adaptive Patterns       │──► Reject if matches learned pattern
│  └─ Cost Tracker            │──► Record pre-gen rejections
└────────┬────────────────────┘
         │ (Filtered candidates)
         ▼
┌─────────────────────────────┐
│ generate_single_article()   │──► Generate content (API call)
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ Post-Gen Dedup Check        │
│  ├─ find_duplicate_articles │──► Check against existing
│  ├─ Cost Tracker            │──► Record waste if duplicate
│  └─ Adaptive Feedback       │──► Learn pattern if duplicate
└────────┬────────────────────┘
         │
         ▼
    ┌────┴────┐
    │ Unique? │
    └─┬────┬──┘
  Yes │    │ No
      ▼    ▼
   Save  Skip
```

### Configuration

Environment variables (optional):
- `RECENT_CACHE_DAYS` - How many days to cache (default: 14)
- `SIMILARITY_THRESHOLD` - Min similarity for duplicate (default: 0.70)
- `PATTERN_THRESHOLD` - Min pattern match score (default: 0.60)

### File Structure

```
data/
  generation_costs.json         # Cost tracking history
  adaptive_dedup_patterns.json  # Learned patterns
  
src/
  costs.py                      # Cost tracking
  recent_content_cache.py       # Recent article cache
  adaptive_dedup.py             # Pattern learning
  generate.py                   # Integrated pipeline
```

## Benefits

### 1. Cost Savings

**Before (ADR-002):**
- Generate article → $0.002
- Detect duplicate → Waste $0.002
- No learning → Repeat for similar topics

**After (ADR-004):**
- Check cache → Free
- Check patterns → Free
- Reject early → Save $0.002
- Learn pattern → Prevent future waste

**Estimated Savings:**
- Pre-gen cache catches ~30% of potential duplicates
- Pattern learning catches ~20% more over time
- **Total: ~50% reduction in wasted generation costs**
- Example: 10 articles/day × $0.002 × 50% savings = $3.65/year

### 2. Continuous Improvement

- System learns from every duplicate detected
- Patterns improve over time
- More detections = higher confidence = better filtering
- Self-optimizing without manual intervention

### 3. Visibility

- Cost summaries show waste vs. useful spend
- Efficiency metrics track improvement
- Pattern stats show what we're learning
- Historical data enables optimization

### 4. Quality

- Fewer duplicate articles published
- More diverse content (rejects similar topics)
- Better use of generation budget (max_articles limit)

## Trade-offs

### Pros
✅ Significantly reduces wasted API costs  
✅ Self-improving over time  
✅ Full visibility into costs  
✅ Better content diversity  
✅ No manual tuning needed  

### Cons
⚠️ More complex system (4 new modules)  
⚠️ Slightly slower candidate selection (cache/pattern checks)  
⚠️ Requires tuning thresholds for optimal performance  
⚠️ Patterns stored indefinitely (grows over time)  
⚠️ May reject valid articles if patterns too aggressive  

### Mitigation
- Pattern confidence limits false positives
- Thresholds configurable via environment variables
- Cost tracking validates effectiveness
- Patterns can be manually reviewed/edited

## Testing Strategy

### Unit Tests
- `test_recent_content_cache.py` - Cache loading, similarity checks
- `test_costs.py` - Cost recording, summary calculations
- `test_adaptive_dedup.py` - Pattern learning, matching

### Integration Tests
- Generate with known duplicate topics
- Verify pre-gen rejection
- Confirm cost savings tracked
- Validate pattern learning

### Monitoring
```bash
# Check cost efficiency
python -c "from src.costs import CostTracker; CostTracker().print_summary(days=30)"

# View learned patterns
python -c "from src.adaptive_dedup import AdaptiveDedupFeedback; AdaptiveDedupFeedback().print_stats()"

# Test recent cache
python -c "from src.recent_content_cache import RecentContentCache; from src.config import get_content_dir; cache = RecentContentCache(get_content_dir()); print(cache.get_cache_stats())"
```

## Success Metrics

### Immediate (Week 1)
- ✅ Pre-gen rejections recorded
- ✅ Post-gen duplicates trigger learning
- ✅ Cost tracking operational
- ✅ Recent cache functioning

### Short-term (Month 1)
- 🎯 20-30% of potential duplicates caught pre-generation
- 🎯 5-10 learned patterns accumulated
- 🎯 Measurable cost savings ($0.01-0.05)
- 🎯 Efficiency rate > 85%

### Long-term (Quarter 1)
- 🎯 40-50% of potential duplicates caught pre-generation
- 🎯 20-30 learned patterns
- 🎯 Significant cost savings ($0.10-0.30)
- 🎯 Efficiency rate > 90%
- 🎯 Reduced manual duplicate removal

## Migration Path

### Phase 1: Add Infrastructure ✅
- Create `recent_content_cache.py`
- Create `costs.py`
- Create `adaptive_dedup.py`

### Phase 2: Integrate Pre-Gen Filtering ✅
- Update `select_article_candidates()`
- Add cache and pattern checks
- Record pre-gen rejections

### Phase 3: Integrate Post-Gen Learning ✅
- Update `generate_articles_from_enriched()`
- Add cost tracking for all outcomes
- Add pattern learning from duplicates

### Phase 4: Monitoring & Tuning (Ongoing)
- Run generation pipeline
- Review cost summaries
- Adjust thresholds if needed
- Monitor pattern effectiveness

## Examples

### Scenario 1: First Mastodon Article

```
1. Enriched item: "Mastodon 4.5 Features"
2. Pre-gen check: No similar articles in cache → PASS
3. Generate article → $0.002
4. Post-gen check: No duplicates → SAVE
5. Cost tracker: Record successful generation
```

### Scenario 2: Second Similar Mastodon Article (Same Day)

```
1. Enriched item: "Unlocking Mastodon 4.5"
2. Pre-gen check: Similar to recent "Mastodon 4.5 Features" → REJECT
3. Cost tracker: Record pre-gen rejection (+$0.002 saved)
4. No generation → No cost
```

### Scenario 3: Third Mastodon Article (Next Week)

```
1. Enriched item: "Mastodon 4.5 Developer Tools"
2. Pre-gen check:
   - Cache: Outside 14-day window → PASS
   - Patterns: Matches learned pattern (mastodon + features) → REJECT
3. Cost tracker: Record pre-gen rejection (+$0.002 saved)
4. No generation → No cost
```

### Scenario 4: Actually New Topic Gets Through

```
1. Enriched item: "Mastodon 4.5 Security Update"
2. Pre-gen check:
   - Cache: No close match → PASS
   - Patterns: Partial match but below threshold → PASS
3. Generate article → $0.002
4. Post-gen check: Not duplicate (different focus) → SAVE
5. Cost tracker: Record successful generation
```

## Future Enhancements

1. **Semantic Similarity**: Use embeddings instead of keyword matching
2. **Time Decay**: Reduce pattern confidence over time for older patterns
3. **Pattern Pruning**: Remove ineffective patterns automatically
4. **Multi-Level Thresholds**: Strict for same-day, relaxed for older content
5. **Cost Prediction**: Estimate cost before generation based on content length
6. **Budget Limits**: Stop generation if approaching cost limit
7. **Pattern Explanation**: Show WHY a candidate was rejected

## References

- **ADR-002**: Enhanced Deduplication (post-generation strategy)
- **ADR-003**: Pipeline Integration (post-generation implementation)
- **Code**: `src/recent_content_cache.py`, `src/costs.py`, `src/adaptive_dedup.py`
- **Data**: `data/generation_costs.json`, `data/adaptive_dedup_patterns.json`

## Conclusion

This adaptive deduplication system transforms our pipeline from reactive (detect duplicates after generation) to proactive (prevent duplicates before generation). By learning from our mistakes and tracking costs, we continuously improve efficiency and reduce waste.

**Key Innovation:** The feedback loop between post-generation detection and pre-generation filtering creates a self-improving system that gets better over time without manual intervention.
