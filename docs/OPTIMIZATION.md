# Pipeline Performance Optimizations

## Current Implementation: Parallel Article Generation ✅

**Strategy**: Matrix strategy with 5 parallel jobs generating 2 articles each
- **Total**: 10 articles
- **Time savings**: ~5x faster for generation phase
- **Cost**: Same ($0.22 per run)

## Future Optimization Opportunities

### 1. **Batch API for OpenAI**
OpenAI provides a Batch API with 50% cost savings for async workloads:
```python
# Instead of sequential API calls
batch_requests = [
    {"model": "gpt-4o-mini", "messages": [...]},
    {"model": "gpt-4o-mini", "messages": [...]},
]
batch_id = client.batches.create(requests=batch_requests)
# Wait 24 hours, get results at 50% cost
```
**Impact**: $0.11 per run instead of $0.22 (50% savings)
**Trade-off**: 24-hour delay (okay for scheduled runs)

### 2. **Concurrent Collection with asyncio**
```python
# In src/collectors/orchestrator.py
import asyncio

async def collect_all():
    tasks = [
        collect_hackernews(),
        collect_github(),
        collect_mastodon(),
    ]
    results = await asyncio.gather(*tasks)
```
**Impact**: 3x faster collection (run sources in parallel)
**Time savings**: ~2-3 minutes per run

### 3. **Parallel Enrichment**
```python
# In src/enrichment/orchestrator.py
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=5) as executor:
    enriched = list(executor.map(enrich_item, items))
```
**Impact**: 5x faster enrichment
**Time savings**: ~5-10 minutes per run
**Note**: Rate limit handling needed

### 4. **Incremental Hugo Builds**
```yaml
# Cache Hugo build artifacts
- name: Cache Hugo resources
  uses: actions/cache@v4
  with:
    path: site/resources/_gen
    key: hugo-${{ hashFiles('content/**') }}
```
**Impact**: Faster Hugo builds (only rebuild changed pages)
**Time savings**: ~30 seconds per run

### 5. **Artifact Caching**
```yaml
# Cache Python dependencies
- name: Cache uv
  uses: actions/cache@v4
  with:
    path: ~/.cache/uv
    key: uv-${{ hashFiles('uv.lock') }}
```
**Impact**: Faster dependency installation
**Time savings**: ~1 minute per run

### 6. **Smarter Scheduling**
Instead of fixed schedules, trigger based on trending activity:
```python
# Monitor HackerNews front page change rate
# Trigger collection when >50% churn detected
# Skip runs when trending is stale
```
**Impact**: Better content freshness, fewer wasted runs
**Cost savings**: ~20-30% (skip low-activity periods)

### 7. **Progressive Image Generation**
```python
# Generate images only for top 5 articles (by quality score)
# Defer images for others to next run if they gain traction
```
**Impact**: 50% faster, 50% cheaper per run
**Trade-off**: Some articles initially without hero images

### 8. **Streaming Generation**
```python
# Use OpenAI streaming for real-time progress
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    stream=True,
)
```
**Impact**: Better UX (see progress), no time savings
**Benefit**: Can cancel slow generations early

## Recommended Implementation Order

### Phase 1 (Immediate) ✅
- [x] Matrix strategy for parallel article generation
- [ ] Concurrent collection with asyncio
- [ ] Hugo/uv caching

**Impact**: ~8-10 minute time savings
**Effort**: Low (2-3 hours)

### Phase 2 (Short-term)
- [ ] Parallel enrichment with rate limiting
- [ ] Progressive image generation
- [ ] Incremental Hugo builds

**Impact**: ~10-15 minute time savings + 50% cost savings on images
**Effort**: Medium (1-2 days)

### Phase 3 (Long-term)
- [ ] OpenAI Batch API integration (when available)
- [ ] Smart scheduling based on trending activity
- [ ] Streaming generation for better UX

**Impact**: 50% cost savings + better content freshness
**Effort**: High (1 week)

## Current Pipeline Timing

**Before optimization**:
- Collection: ~3 minutes
- Enrichment: ~10 minutes (51 items)
- Generation: ~10 minutes (10 articles sequentially)
- Hugo build: ~1 minute
- Deploy: ~30 seconds
- **Total**: ~25 minutes

**After Phase 1 (current)**:
- Collection: ~3 minutes
- Enrichment: ~10 minutes
- Generation: ~2 minutes (5 parallel batches)
- Hugo build: ~1 minute
- Deploy: ~30 seconds
- **Total**: ~17 minutes (32% faster)

**After Phase 2**:
- Collection: ~1 minute (concurrent)
- Enrichment: ~2 minutes (parallel)
- Generation: ~2 minutes
- Hugo build: ~30 seconds (cached)
- Deploy: ~30 seconds
- **Total**: ~6 minutes (76% faster)

## Cost Analysis

| Approach | Time | Cost per Run | Articles/Day | Daily Cost |
|----------|------|--------------|--------------|------------|
| Sequential | 25m | $0.22 | 30 | $0.66 |
| Parallel (current) | 17m | $0.22 | 30 | $0.66 |
| Parallel + Progressive Images | 17m | $0.11 | 30 | $0.33 |
| Batch API | 24h | $0.11 | 30 | $0.33 |
| Full optimization | 6m | $0.08 | 30 | $0.24 |

## Monitoring & Alerting

Add workflow timing metrics:
```yaml
- name: Record timing
  run: |
    echo "collection_duration_seconds=$SECONDS" >> $GITHUB_OUTPUT
```

Track in GitHub Actions insights:
- Average pipeline duration
- Success rate
- Cost per article
- Articles per run

Alert when:
- Pipeline takes >30 minutes
- Success rate drops below 90%
- Cost per article exceeds $0.03
