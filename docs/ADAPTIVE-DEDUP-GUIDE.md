# Adaptive Deduplication User Guide

## Quick Start

The adaptive deduplication system is **now automatic** - it runs whenever you generate articles. No configuration needed!

```bash
# Generate articles as normal
python -m src.generate

# The system will now:
# 1. Check candidates against recent articles (last 14 days)
# 2. Check against learned duplicate patterns
# 3. Reject likely duplicates BEFORE generation
# 4. Track costs (successful, wasted, saved)
# 5. Learn from any post-generation duplicates detected
```

## What You'll See

### Pre-Generation Rejections

When a candidate is rejected before generation:

```
⚠ Potential duplicate detected (pre-generation)
  Candidate: Mastodon 4.5 Developer Tools...
  Similar to: Mastodon 4.5 New Features... (from 2024-10-29)
  Overall similarity: 85.3%
  Title: 78%, Summary: 92%, Tags: 100%

⏭ Rejected pre-generation (likely duplicate)
```

Or when matching a learned pattern:

```
⚠ Matches learned duplicate pattern: ['mastodon', 'fediverse', 'social-media']...
⏭ Rejected pre-generation (pattern match)
```

### Post-Generation Learning

When a duplicate slips through and is caught after generation:

```
⚠ Duplicate detected - skipping article
[Table showing similarity metrics]

💸 Wasted $0.0021 on duplicate article
🧠 Learned pattern from duplicate (will help reject similar in future)
```

### End-of-Run Summaries

After generation, you'll see cost and learning stats:

```
💰 Generation Cost Summary (Last 7 Days)

┌─────────────────────────┬───────┬──────────────┐
│ Metric                  │ Count │ Cost (USD)   │
├─────────────────────────┼───────┼──────────────┤
│ Successful Articles     │ 12    │ $0.0234      │
│ Wasted on Duplicates    │ 2     │ $0.0042      │
│ Pre-Gen Rejections      │ 8     │ $0.0160 saved│
│ Total Spent             │ 14    │ $0.0276      │
└─────────────────────────┴───────┴──────────────┘

Efficiency Rate: 84.8%
⚠ Waste: $0.0042 (15.2% of total)
✓ Savings from pre-gen filtering: $0.0160

🧠 Adaptive Dedup Learning Stats

Total patterns learned: 6
Total duplicates detected: 18
Average similarity: 82.5%

Most common duplicate tags:
  • mastodon: 8 occurrences
  • fediverse: 6 occurrences
  • postgresql: 4 occurrences
```

## Manual Checks

### View Cost Summary

```bash
python -c "from src.costs import CostTracker; CostTracker().print_summary(days=30)"
```

### View Learned Patterns

```bash
python -c "from src.adaptive_dedup import AdaptiveDedupFeedback; AdaptiveDedupFeedback().print_stats()"
```

### Check Recent Cache Stats

```bash
python -c "
from src.recent_content_cache import RecentContentCache
from src.config import get_content_dir
cache = RecentContentCache(get_content_dir())
print(cache.get_cache_stats())
"
```

### Test Candidate Against Cache

```bash
python -c "
from src.recent_content_cache import RecentContentCache
from src.config import get_content_dir

cache = RecentContentCache(get_content_dir())
title = 'Your Test Title'
summary = 'Your test summary'
tags = ['test', 'tags']

is_dup, match = cache.is_duplicate_candidate(title, summary, tags)
if is_dup:
    print(f'DUPLICATE! Similar to: {match.cached_article.title}')
    print(f'Similarity: {match.overall_score:.1%}')
else:
    print('UNIQUE - would be generated')
"
```

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Recent content cache
RECENT_CACHE_DAYS=14          # How many days to cache (default: 14)
SIMILARITY_THRESHOLD=0.70     # Min similarity to flag duplicate (default: 0.70)

# Pattern matching
PATTERN_THRESHOLD=0.60        # Min pattern match score (default: 0.60)
```

### Thresholds Explained

**Similarity Threshold (0.70 = 70%)**
- Higher = More strict (fewer false positives, might miss some duplicates)
- Lower = More lenient (catches more duplicates, might reject unique articles)
- Recommended: 0.65-0.75

**Pattern Threshold (0.60 = 60%)**
- How closely candidate must match learned pattern
- Higher = Only reject very similar to past duplicates
- Lower = Reject more aggressively based on patterns
- Recommended: 0.55-0.65

## Data Files

### `data/generation_costs.json`

Tracks all generation attempts:

```json
[
  {
    "timestamp": "2024-10-31T12:34:56.789",
    "article_title": "Mastodon 4.5 Features",
    "article_filename": "2024-10-31-mastodon-4-5-features.md",
    "content_cost": 0.0018,
    "title_cost": 0.0002,
    "slug_cost": 0.0001,
    "image_cost": 0.0000,
    "total_cost": 0.0021,
    "status": "saved"
  },
  {
    "timestamp": "2024-10-31T12:35:23.456",
    "article_title": "Unlocking Mastodon 4.5",
    "article_filename": "",
    "content_cost": 0.0019,
    "title_cost": 0.0002,
    "slug_cost": 0.0001,
    "image_cost": 0.0000,
    "total_cost": 0.0022,
    "status": "rejected_duplicate",
    "duplicate_of": "2024-10-31-mastodon-4-5-features.md"
  }
]
```

**Status Values:**
- `saved` - Article successfully generated and saved
- `rejected_duplicate` - Detected as duplicate after generation (wasted cost)
- `rejected_pre_gen` - Rejected before generation (saved cost)

### `data/adaptive_dedup_patterns.json`

Learned patterns from duplicates:

```json
[
  {
    "topic_keywords": ["mastodon", "features", "release"],
    "common_tags": ["mastodon", "fediverse", "social-media"],
    "title_patterns": [],
    "detected_count": 5,
    "first_seen": "2024-10-29T...",
    "last_seen": "2024-10-31T...",
    "example_titles": [
      "Mastodon 4.5 New Features",
      "Unlocking Mastodon 4.5 Features",
      "Mastodon 4.5 Developer Tools"
    ],
    "avg_similarity": 0.873
  }
]
```

**Fields:**
- `topic_keywords` - Common words in duplicate titles
- `common_tags` - Tags shared by duplicates
- `detected_count` - How many times pattern seen (confidence)
- `avg_similarity` - Average similarity of duplicates

## Monitoring & Optimization

### Check Efficiency

Run generation and look for:

```
Efficiency Rate: > 85%  ✅ Good
                 < 75%  ⚠️  Too much waste, consider tuning thresholds
```

### Review Waste Patterns

If efficiency is low, check what's being wasted:

```python
from src.costs import CostTracker
tracker = CostTracker()

# Get patterns of waste
patterns = tracker.get_waste_patterns()
for source, count, cost in patterns[:5]:
    print(f"{source}: {count} duplicates, ${cost:.4f} wasted")
```

This shows which articles are causing the most duplicate generation.

### Adjust Thresholds

If too many unique articles are being rejected:
- **Lower** `SIMILARITY_THRESHOLD` (e.g., from 0.70 to 0.65)
- **Lower** `PATTERN_THRESHOLD` (e.g., from 0.60 to 0.55)

If too many duplicates are getting through:
- **Raise** `SIMILARITY_THRESHOLD` (e.g., from 0.70 to 0.75)
- **Raise** `PATTERN_THRESHOLD` (e.g., from 0.60 to 0.65)

### Manual Pattern Review

If patterns seem too aggressive:

```python
from src.adaptive_dedup import AdaptiveDedupFeedback
feedback = AdaptiveDedupFeedback()

# Review patterns
for i, pattern in enumerate(feedback.patterns):
    print(f"\nPattern {i+1}:")
    print(f"  Tags: {list(pattern.common_tags)}")
    print(f"  Keywords: {list(pattern.topic_keywords)[:5]}")
    print(f"  Detections: {pattern.detected_count}")
    print(f"  Examples: {pattern.example_titles[:2]}")
```

You can manually edit `data/adaptive_dedup_patterns.json` to remove or adjust patterns.

## Troubleshooting

### "All candidates rejected!"

Check if thresholds are too strict:
1. Review cache stats - how many articles are cached?
2. Check learned patterns - are they too broad?
3. Try lowering thresholds temporarily
4. Check if recent cache days is too high (14 days might be too long)

### "Still generating duplicates"

Check if thresholds are too lenient:
1. Review post-gen duplicate reports
2. Check what similarity scores duplicates have
3. Raise thresholds to match those scores
4. Verify patterns are being learned (check `adaptive_dedup_patterns.json`)

### "Patterns not learning"

Verify:
1. `data/adaptive_dedup_patterns.json` exists and is writable
2. Post-generation duplicates are being detected
3. Check console output for "🧠 Learned pattern..." message
4. Manually inspect file to see if patterns are being added

### "Cost tracking not working"

Verify:
1. `data/generation_costs.json` exists and is writable
2. Check file permissions
3. Look for error messages during generation
4. Manually call `CostTracker().print_summary()` to test

## Best Practices

1. **Let it learn** - First few runs will have more waste as patterns are learned
2. **Monitor efficiency** - Check summary after each run
3. **Don't over-tune** - Start with defaults, only adjust if problems
4. **Review patterns weekly** - Check what's being learned
5. **Clean old patterns** - Remove patterns for outdated topics (manual edit)
6. **Track savings** - Use cost summaries to justify system

## Expected Results

### Week 1
- Some duplicates still get through (learning phase)
- 10-20% pre-gen rejections
- Efficiency ~80-85%

### Month 1
- Fewer post-gen duplicates
- 20-30% pre-gen rejections
- Efficiency ~85-90%
- 5-10 learned patterns

### Quarter 1
- Rare post-gen duplicates
- 30-50% pre-gen rejections
- Efficiency >90%
- 20-30 learned patterns
- Measurable cost savings

## Example Session

```bash
$ python -m src.generate

Loading enriched items...
✓ Loaded 45 enriched items

Loaded 64 articles from last 14 days into cache
Loaded 8 learned dedup patterns

✓ Selected 18 candidates from 45 enriched items
Recent cache: 64 articles, 47 unique tags

⚠ Potential duplicate detected (pre-generation)
  Candidate: PostgreSQL Performance Tips...
  Similar to: Boost PostgreSQL Performance... (from 2024-10-29)
  Overall similarity: 78.2%
⏭ Rejected pre-generation (likely duplicate)

⚠ Matches learned duplicate pattern: ['postgresql', 'performance', 'database']...
⏭ Rejected pre-generation (pattern match)

Generating 3 articles...

Progress: 1/3
  Using: GeneralArticleGenerator
  Content: 842 words
  Title: Securing NPM: Fighting Malicious Packages
  Slug: securing-npm-malicious-packages
✓ Generated: Securing NPM: Fighting Malicious Packages

[... 2 more articles ...]

✓ Article generation complete: 3 articles created

💰 Generation Cost Summary (Last 7 Days)
[table showing costs]

🧠 Adaptive Dedup Learning Stats
Total patterns learned: 8
Total duplicates detected: 12
[pattern stats]
```

## Success!

You now have a self-improving duplicate detection system that:
- ✅ Saves money by rejecting duplicates early
- ✅ Learns from mistakes automatically
- ✅ Gets better over time
- ✅ Provides full visibility into costs
- ✅ Requires minimal configuration

The more you use it, the better it gets! 🚀
