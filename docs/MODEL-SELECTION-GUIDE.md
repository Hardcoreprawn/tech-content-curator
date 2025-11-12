# AI Model Selection Guide

**Last Updated:** November 12, 2025

---

## Recommended Model Configuration

### Default (Balanced Cost & Quality) ⭐ RECOMMENDED

```bash
CONTENT_MODEL=gpt-5-nano           # $0.05/$0.40 per 1M tokens (cheapest)
TITLE_MODEL=gpt-5-nano             # $0.05/$0.40 per 1M tokens
REVIEW_MODEL=gpt-5-mini            # $0.25/$2.00 per 1M tokens (balanced)
ENRICHMENT_MODEL=gpt-5-mini        # $0.25/$2.00 per 1M tokens
```

**Cost per article:** ~$0.003-0.008  
**Quality:** Excellent for most content  
**Best for:** Regular production use, high volume

**Note:** GPT-4.1 series is still available but GPT-5 series offers better performance and similar/better pricing.

---

## Model Purpose & Recommendations

### 1. Content Generation Model

**Purpose:** Generate main article body (1200-2000 words)

**Options:**

| Model | Cost (Input/Output) | Quality | Use Case |
|-------|---------------------|---------|----------|
| **gpt-5-nano** ⭐ | $0.05/$0.40 | Excellent | Default - cheapest, great for summaries |
| **gpt-5-mini** | $0.25/$2.00 | Superior | Balanced - best for most articles |
| **gpt-5** | $1.25/$10.00 | Premium | Complex technical/scientific content |
| **gpt-5-pro** | $15.00/$120.00 | Ultimate | Only for flagship articles (very expensive!) |
| **gpt-4.1-mini** (legacy) | ~$0.30/$1.20 | Good | Older model, use GPT-5 instead |

**Recommendation:** 
- **Budget option:** `gpt-5-nano` - amazing value at $0.05/$0.40, perfect for straightforward articles
- **Default:** `gpt-5-mini` - best balance of quality and cost for most content
- **Upgrade to gpt-5 if:** Complex technical topics, scientific research, consistently low quality scores
- **Avoid gpt-5-pro:** Costs 12x more than gpt-5, only for critical flagship content

**Input/Output:** ~1500 in / ~1500 out tokens per article

---

### 2. Title Generation Model

**Purpose:** Generate catchy, SEO-friendly titles (10-80 characters)

**Options:**

| Model | Cost (Input/Output) | Quality | Use Case |
|-------|---------------------|---------|----------|
| **gpt-5-nano** ⭐ | $0.05/$0.40 | Excellent | Default - perfect for titles |
| **gpt-5-mini** | $0.25/$2.00 | Overkill | Unnecessary for simple titles |

**Recommendation:** 
- **Always use:** `gpt-5-nano` - titles are tiny, cost is ~$0.00001/title
- **Never upgrade:** Even gpt-5-nano is overkill; titles are simple tasks
- **Cost impact:** ~$0.001 per 100 titles

**Input/Output:** ~200 in / ~20 out tokens per title

---

### 3. Review Model

**Purpose:** Evaluate article quality across 6 dimensions, provide feedback

**Options:**

| Model | Cost (Input/Output) | Quality | Use Case |
|-------|---------------------|---------|----------|
| **gpt-5-nano** | $0.05/$0.40 | Good | Budget reviews |
| **gpt-5-mini** ⭐ | $0.25/$2.00 | Excellent | Default - reliable reviews |
| **gpt-5** | $1.25/$10.00 | Superior | Stricter evaluation, nuanced feedback |
| **o4-mini** | $4.00/$16.00 | Best reasoning | Deep quality analysis (RL-based) |

**Recommendation:** 
- **Default:** `gpt-5-mini` - consistent, reliable evaluation at great price
- **Budget option:** `gpt-5-nano` - adequate for basic quality checks
- **Upgrade to gpt-5 if:** 
  - Review inconsistency detected
  - Need stricter quality standards
  - Budget allows (adds $0.03-0.05/review)
- **Use o4-mini only if:** Experimental - testing reasoning models for review (expensive)

**Input/Output:** ~2000 in / ~500 out tokens per review

**Cost Impact:**
- gpt-5-nano: $0.003-0.005/review
- gpt-5-mini: $0.005-0.015/review
- gpt-5: $0.025-0.075/review
- o4-mini: $0.080-0.240/review (expensive!)

---

### 4. Enrichment Model

**Purpose:** Research topics, extract key points, generate summaries

**Options:**

| Model | Cost (Input/Output) | Quality | Use Case |
|-------|---------------------|---------|----------|
| **gpt-5-nano** ⭐ | $0.05/$0.40 | Excellent | Default - perfect for summarization |
| **gpt-5-mini** | $0.25/$2.00 | Superior | Complex research synthesis |
| **gpt-5** | $1.25/$10.00 | Premium | Academic/scientific deep analysis |

**Recommendation:** 
- **Default:** `gpt-5-nano` - specifically designed for summarization and classification, perfect fit
- **Upgrade to gpt-5-mini if:** 
  - Complex multi-source synthesis
  - Need deeper analysis than simple extraction
- **Upgrade to gpt-5 if:**
  - Scientific papers requiring nuanced understanding
  - Academic content enrichment

**Input/Output:** ~1000 in / ~300 out tokens per enrichment

---

## Cost Comparison Table

### Per Article (Full Pipeline)

| Configuration | Content | Title | Review | Enrichment | Total/Article | Use Case |
|---------------|---------|-------|--------|------------|---------------|----------|
| **Ultra Budget** | nano | nano | nano | nano | $0.003 | Maximum cost savings |
| **Budget** | nano | nano | mini | nano | $0.005 | High volume, good quality |
| **Balanced** ⭐ | mini | nano | mini | nano | $0.008 | Recommended default |
| **Quality** | mini | nano | gpt-5 | mini | $0.025 | Stricter standards |
| **Premium** | gpt-5 | nano | gpt-5 | gpt-5 | $0.080 | Complex/flagship content |
| **Experimental** | gpt-5 | nano | o4-mini | gpt-5 | $0.200 | Testing reasoning models |

**Monthly Cost Estimates (270 articles/month):**
- Ultra Budget: $0.81/month
- Budget: $1.35/month
- Balanced: $2.16/month ⭐
- Quality: $6.75/month
- Premium: $21.60/month
- Experimental: $54.00/month

**Note:** These costs are MUCH lower than previous generations! GPT-5 nano/mini offer exceptional value.

---

## Quality Gate Strategy

### Recommended Approach: Two-Tier Quality Gate

#### Tier 1: Automatic Quality Scoring (No Cost)

Use existing `QualityScorer` (free, deterministic):

```bash
# Current implementation - already in place
MIN_QUALITY_SCORE=70.0           # Overall quality threshold (0-100)
MIN_READABILITY_SCORE=50.0       # Flesch Reading Ease
```

**Action:** Articles below threshold trigger review

#### Tier 2: AI Review (Costs $0.02-0.12 per review)

Only review articles that fail Tier 1:

```bash
# New quality gate settings
ENABLE_QUALITY_GATE=true                    # Enable two-tier gate
QUALITY_GATE_THRESHOLD=70.0                 # Tier 1 threshold
ENABLE_AUTO_REVIEW_ON_FAILURE=true          # Auto-review if Tier 1 fails
ENABLE_AUTO_REGENERATION=true               # Auto-fix if review fails
MAX_REGENERATION_ATTEMPTS=2                 # Limit regeneration loops
REVIEW_SCORE_THRESHOLD=6.5                  # Tier 2 threshold (0-10)
```

### Quality Gate Flow

```
Article Generated
      ↓
[Tier 1: Quality Scorer]
   (Free, instant)
      ↓
Score >= 70? ──Yes──> ✅ Publish
      ↓ No
[Tier 2: AI Review]
   ($0.02-0.12)
      ↓
Review >= 6.5? ──Yes──> ✅ Publish with notes
      ↓ No
[Regenerate with Feedback]
   ($0.15-0.30)
      ↓
[Re-review]
      ↓
Publish or flag for manual review
```

### Cost Impact Analysis

**Scenario: 270 articles/month, Balanced config**

| Metric | Value | Cost |
|--------|-------|------|
| Total articles | 270 | - |
| Pass Tier 1 (80%) | 216 | $0 review cost |
| Fail Tier 1 (20%) | 54 | 54 × $0.03 = $1.62 |
| Need regeneration (5%) | 14 | 14 × $0.20 = $2.80 |
| **Total quality gate cost** | - | **$4.42/month** |
| **Total pipeline cost** | - | **$13.87/month** |

**Benefit:** Catches 20% of low-quality articles, improves 5%, costs only $4.42/month

---

## Optimal Configuration by Use Case

### 1. Personal Blog (Low Volume, Quality Focus)

```bash
CONTENT_MODEL=gpt-5               # Premium content
TITLE_MODEL=gpt-5-nano            # Titles are cheap
REVIEW_MODEL=gpt-5                # Strict quality
ENRICHMENT_MODEL=gpt-5            # Deep research

ENABLE_QUALITY_GATE=true
QUALITY_GATE_THRESHOLD=75.0       # Higher bar
ENABLE_AUTO_REVIEW_ON_FAILURE=true
ENABLE_AUTO_REGENERATION=true
REVIEW_SCORE_THRESHOLD=7.0        # Stricter
```

**Cost:** ~$0.08/article (~30 articles/month = $2.40/month)

---

### 2. High-Volume News Aggregator

```bash
CONTENT_MODEL=gpt-5-nano          # Fastest & cheapest
TITLE_MODEL=gpt-5-nano            # Cheap
REVIEW_MODEL=gpt-5-nano           # Quick checks
ENRICHMENT_MODEL=gpt-5-nano       # Fast research

ENABLE_QUALITY_GATE=true
QUALITY_GATE_THRESHOLD=65.0       # Lower bar
ENABLE_AUTO_REVIEW_ON_FAILURE=true
ENABLE_AUTO_REGENERATION=false    # Speed over perfection
```

**Cost:** ~$0.003/article (500 articles/month = $1.50/month)

---

### 3. Technical Research Blog (Current Setup) ⭐

```bash
CONTENT_MODEL=gpt-5-mini          # Great quality/cost
TITLE_MODEL=gpt-5-nano            # Cheap
REVIEW_MODEL=gpt-5-mini           # Good evaluation
ENRICHMENT_MODEL=gpt-5-nano       # Excellent for summaries

ENABLE_QUALITY_GATE=true
QUALITY_GATE_THRESHOLD=70.0       # Balanced
ENABLE_AUTO_REVIEW_ON_FAILURE=true
ENABLE_AUTO_REGENERATION=true
REVIEW_SCORE_THRESHOLD=6.5        # Reasonable
MAX_REGENERATION_ATTEMPTS=2       # Prevent loops
```

**Cost:** ~$0.008/article (270 articles/month = $2.16/month)

---

### 4. Premium Long-Form Content

```bash
CONTENT_MODEL=gpt-5               # Best writing
TITLE_MODEL=gpt-5-nano            # Still overkill
REVIEW_MODEL=gpt-5                # Strict evaluation
ENRICHMENT_MODEL=gpt-5            # Deep research

ENABLE_QUALITY_GATE=true
QUALITY_GATE_THRESHOLD=80.0       # High bar
ENABLE_AUTO_REVIEW_ON_FAILURE=true
ENABLE_AUTO_REGENERATION=true
REVIEW_SCORE_THRESHOLD=7.5        # Very strict
MAX_REGENERATION_ATTEMPTS=3       # Worth the effort
```

**Cost:** ~$0.08/article (50 articles/month = $4.00/month)

---

## Decision Matrix

### When to Upgrade Content Model to gpt-4o

✅ **Upgrade if:**
- Average quality scores < 70 consistently
- Complex scientific/academic content
- Voice consistency issues
- Budget allows 10x cost increase
- Content is flagship/premium

❌ **Don't upgrade if:**
- Quality scores > 75 (already good)
- News/short-form content
- High volume requirements
- Budget constrained

### When to Upgrade Review Model to gpt-4o

✅ **Upgrade if:**
- Review scores don't correlate with actual quality
- Need more nuanced feedback
- Generating premium content
- Willing to spend $0.08/review

❌ **Don't upgrade if:**
- gpt-4o-mini reviews are consistent
- Budget tight
- High volume (reviews add up fast)

### Quality Gate: On or Off?

✅ **Enable quality gate if:**
- Quality matters more than speed
- Can afford $0.02-0.05/article review cost
- Willing to regenerate poor articles
- Want data on quality trends

❌ **Disable if:**
- Need maximum speed
- Very tight budget
- Trust content model completely
- Manual review process exists

---

## Recommended Settings for Your Project

Based on your current setup (tech research blog, 270 articles/month):

```bash
# Optimal model configuration - NEW GPT-5 SERIES
CONTENT_MODEL=gpt-5-mini           # Perfect balance
TITLE_MODEL=gpt-5-nano             # Negligible cost, perfect for titles
REVIEW_MODEL=gpt-5-mini            # Reliable evaluation
ENRICHMENT_MODEL=gpt-5-nano        # Designed for summarization

# Quality gate - two-tier approach
ENABLE_QUALITY_GATE=true
QUALITY_GATE_THRESHOLD=70.0        # Reasonable bar
ENABLE_AUTO_REVIEW_ON_FAILURE=true # Catch failures
ENABLE_AUTO_REGENERATION=true      # Auto-fix
REVIEW_SCORE_THRESHOLD=6.5         # Balanced
MAX_REGENERATION_ATTEMPTS=2        # Prevent runaway costs

# Voice metrics (free)
ENABLE_VOICE_METRICS=true

# Secondary sources (minimal cost)
ENABLE_SECONDARY_SOURCES=true
MAX_SECONDARY_REFERENCES=3
```

**Expected monthly cost:** $2-3/month (amazing value!)  
**Quality improvement:** 15-20% fewer low-quality articles  
**ROI:** Better reader experience, less manual review needed

**Migration Note:** If currently using gpt-4o-mini, GPT-5 nano/mini are cheaper and perform better!

---

## Testing Strategy

### Phase 1: Baseline (Current State)
- Run 30 articles with all gpt-4o-mini, no review
- Track quality scores and manual review time

### Phase 2: Add Quality Gate
- Enable two-tier gate
- Track review trigger rate
- Measure improvement in published quality

### Phase 3: Optimize Thresholds
- Adjust QUALITY_GATE_THRESHOLD based on trigger rate
- Tune REVIEW_SCORE_THRESHOLD based on regeneration effectiveness
- Find sweet spot for cost vs quality

### Phase 4: Consider Upgrades
- If review scores suggest model limits, test gpt-4o for reviews
- If content consistently fails review, test gpt-4o for content
- Always A/B test before committing to upgrades

---

## Summary

**Best Overall Configuration (GPT-5 Series):**
- Mix of gpt-5-nano (titles, enrichment) and gpt-5-mini (content, review)
- Cost: ~$0.008/article
- Catches 20% of quality issues
- Auto-fixes 5% via regeneration
- Total: **$2.16/month for 270 articles** (incredible value!)

**When to Spend More:**
- Only upgrade to gpt-5 if quality scores consistently show mini is insufficient
- Review model can stay on gpt-5-mini unless you need stricter evaluation
- Always test before committing to higher-cost models
- Avoid gpt-5-pro unless absolutely critical (12x cost of gpt-5)

**Key Insights:** 
- GPT-5 nano is **specifically designed** for summarization/classification - perfect for enrichment!
- GPT-5 mini offers excellent quality at ~60% cheaper than old gpt-4o-mini
- The quality gate (free tier 1 + cheap tier 2) is still more cost-effective than upgrading models
- GPT-5 series made high-quality AI content generation incredibly affordable
