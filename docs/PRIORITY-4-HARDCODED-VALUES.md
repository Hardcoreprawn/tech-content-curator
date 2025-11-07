# Priority 4: Hardcoded Values Audit

## Current Hardcoded Values to Move to Config

### 1. **API Timeouts** (Currently scattered across collectors/generators)
- `src/pipeline/orchestrator.py:238` - OpenAI timeout: **120.0s**
- `src/pipeline/orchestrator.py:407` - OpenAI timeout: **120.0s**
- `src/generate.py:164` - OpenAI timeout: **120.0s**
- `src/enrichment/orchestrator.py:66` - OpenAI timeout: **60.0s**
- `src/images/cover_image.py:95` - httpx timeout: **30.0s**
- `src/collectors/mastodon.py:56,135` - httpx timeout: **30.0s** (2 locations)
- `src/collectors/hackernews.py:38` - httpx timeout: **30.0s**
- `src/collectors/github.py:41` - httpx timeout: **30.0s**
- `src/enrichment/fact_check.py:35` - timeout param default: **10.0s**
- `src/enrichment/fact_check.py:57` - fact check timeout: **5.0s**
- `src/citations/resolver.py:57` - citation resolver timeout: **10**

**Impact:** If timeout needs adjustment, must update 11 locations. If API is slow, can't easily dial up timeouts.

---

### 2. **Retry & Backoff Logic** (Tenacity config hardcoded)
- `src/enrichment/ai_analyzer.py:42` - **stop_after_attempt(3)**, **wait_exponential(multiplier=1, min=2, max=30)**
  - stop_after_attempt: **3 attempts**
  - multiplier: **1**
  - min: **2 seconds**
  - max: **30 seconds**

- `src/config.py:42-44` - Reddit retry config (ALREADY IN CONFIG):
  - max_retries: **3** 
  - backoff_base: **2.0**
  - backoff_max: **60.0**

- `src/collectors/reddit.py:120` - sleep between subreddit requests: **0.5 seconds**
- `src/collectors/hackernews.py:99` - sleep in loop: **0.1 seconds**
- `src/utils/rate_limit.py:67` - min sleep: **0.01 seconds**

**Problem:** Retry logic copied to multiple modules with slightly different values. No way to tune retry behavior centrally.

---

### 3. **Confidence Thresholds** (Scattered across 4+ modules)
- `src/deduplication/semantic_dedup.py:245` - dedup confidence: **0.8**
- `src/citations/resolver.py:119` - citation confidence baseline: **0.0**
- `src/citations/resolver.py:178` - citation year match confidence: **0.9** (exact), **0.6** (off-year)
- `src/citations/resolver.py:245` - citation confidence: **0.85**
- `src/citations/extractor.py:117` - URL citation confidence: **1.0**
- `src/citations/extractor.py:127` - metadata citation confidence: **0.9**
- `src/citations/extractor.py:137` - bibtex citation confidence: **0.85**
- `src/enrichment/fact_check.py:142` - fact check confidence: **1.0** (hardcoded placeholder)

**Problem:** Different modules have inconsistent confidence scoring. Hard to debug quality issues. No validation that thresholds make sense (0.0-1.0 range).

---

### 4. **Content & Length Limits** (Mostly in config, but scattered)

In `src/config.py`:
- `min_content_length`: **100 characters** ✓ (already configured)
- `max_content_length`: **2000 characters** ✓ (already configured)
- `max_illustrations_per_article`: **3** ✓ (already configured)
- `mermaid_candidates`: **3** ✓ (already configured)
- `ascii_candidates`: **3** ✓ (already configured)
- `text_illustration_candidates`: **3** ✓ (already configured)

In `src/models.py`:
- `safe_filename(slug: str, max_length: int = 100)` - filename length: **100 characters** (hardcoded default)

**Status:** Mostly handled but safe_filename has hardcoded default.

---

### 5. **Quality Thresholds** (In config but unvalidated)

In `src/config.py:154-164`:
- `illustration_budget_per_article`: **0.06** ✓
- `illustration_confidence_threshold`: **0.7** ✓
- `illustration_ai_confidence_threshold`: **0.8** ✓
- `diagram_validation_threshold`: **0.7** ✓
- `text_illustration_quality_threshold`: **0.6** ✓

In `src/config.py:140-165` (QUALITY_THRESHOLDS dict):
- beginner: min_flesch_ease=**60.0**, max_grade_level=**10.0**, min_quality_score=**70.0**
- intermediate: min_flesch_ease=**50.0**, max_grade_level=**14.0**, min_quality_score=**75.0**
- advanced: min_flesch_ease=**30.0**, max_grade_level=**18.0**, min_quality_score=**80.0**

**Status:** In config but NO VALIDATION that values make sense (e.g., confidence between 0-1, flesch_ease between 0-100)

---

### 6. **Rate Limiting Params** (Partially in config)

In `src/config.py`:
- `reddit_requests_per_minute`: **30** ✓
- `reddit_burst`: **5** ✓
- `reddit_request_interval_seconds`: **1.0** ✓

In `src/utils/rate_limit.py:66`:
- jitter: hardcoded as **self.jitter** but set via constructor (✓ injectable)

**Status:** Mostly OK but could use more validation.

---

### 7. **Default Image Strategy & Behavior**

In `src/config.py`:
- `image_strategy`: **"reuse"** ✓ (configurable)
- `image_generate_fallback`: **"false"** ✓ (configurable)
- `image_source_timeout`: **30** ✓ (configurable)
- `unsplash_api_key`: defaults to **""** (empty, makes integration optional)
- `pexels_api_key`: defaults to **""** (empty, makes integration optional)

**Status:** Good, but no validation that strategy is valid value.

---

### 8. **Feature Flags** (In config, but scattered as booleans)

In `src/config.py`:
- `allow_tech_content`: **true** ✓
- `allow_science_content`: **true** ✓
- `allow_policy_content`: **true** ✓
- `enable_citations`: **true** ✓
- `enable_illustrations`: **true** ✓
- `skip_list_sections`: **true** ✓

**Status:** In config but could use enum/validation for consistency.

---

### 9. **Cache TTL & Timing**

In `src/config.py`:
- `citations_cache_ttl_days`: **30** ✓

**Status:** Good, one parameter, already in config.

---

## Summary of Changes Needed

### High Priority (Breaking across 10+ locations):
1. **API Timeouts** - Consolidate 11 scattered timeout values
2. **Confidence Thresholds** - Consolidate 8 scattered threshold values
3. **Retry Logic** - Move tenacity config to configurable section

### Medium Priority (Already in config, needs validation):
1. **Add range validators** - Ensure numeric values are sensible
2. **Add dependency validators** - Check related config makes sense
3. **Add enum validators** - Validate strategy/mode choices

### Low Priority (Already well-handled):
1. Content limits - mostly in config
2. Quality thresholds - in config, just needs validation
3. Feature flags - in config, just needs validation

---

## New Config Sections to Add

```python
# src/models.py additions needed

class TimeoutConfig(BaseModel):
    """HTTP and API timeout settings."""
    openai_api_timeout: float = Field(default=120.0, gt=0)
    enrichment_timeout: float = Field(default=60.0, gt=0)
    http_client_timeout: float = Field(default=30.0, gt=0)
    fact_check_timeout: float = Field(default=5.0, gt=0)
    citation_resolver_timeout: int = Field(default=10, gt=0)
    image_source_timeout: int = Field(default=30, gt=0)

class RetryConfig(BaseModel):
    """Retry and backoff configuration."""
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_multiplier: float = Field(default=1.0, gt=0)
    backoff_min: float = Field(default=2.0, gt=0)
    backoff_max: float = Field(default=30.0, ge=2.0)
    jitter: float = Field(default=0.1, ge=0, le=1)

class ConfidenceThresholds(BaseModel):
    """Confidence score thresholds."""
    dedup_confidence: float = Field(default=0.8, ge=0, le=1)
    citation_baseline: float = Field(default=0.0, ge=0, le=1)
    citation_exact_match: float = Field(default=0.9, ge=0, le=1)
    citation_partial_match: float = Field(default=0.6, ge=0, le=1)
    citation_extracted_url: float = Field(default=1.0, ge=0, le=1)
    citation_extracted_metadata: float = Field(default=0.9, ge=0, le=1)
    citation_extracted_bibtex: float = Field(default=0.85, ge=0, le=1)

class SleepIntervals(BaseModel):
    """Inter-request sleep intervals (in seconds)."""
    between_subreddit_requests: float = Field(default=0.5, ge=0)
    between_hackernews_requests: float = Field(default=0.1, ge=0)
    min_interval: float = Field(default=0.01, ge=0)

class PipelineConfig(BaseModel):
    # ... existing fields ...
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)
    retries: RetryConfig = Field(default_factory=RetryConfig)
    confidences: ConfidenceThresholds = Field(default_factory=ConfidenceThresholds)
    sleep_intervals: SleepIntervals = Field(default_factory=SleepIntervals)
```

---

## Implementation Order

1. **Phase 1:** Add new config sections to models.py with validators
2. **Phase 2:** Update get_config() in config.py to populate new sections from env vars
3. **Phase 3:** Update all modules to import and use new config sections
4. **Phase 4:** Remove hardcoded values and replace with config lookups
5. **Phase 5:** Add comprehensive test suite for validation
6. **Phase 6:** Commit with detailed changelog

