# Story Clustering - Automatic Cross-Source Deduplication

## What It Does

Automatically detects and filters out **duplicate stories from different sources** before article generation.

### Problem Solved

Your Oct 31, 2025 pipeline run created these duplicate articles:

1. **Affinity Software** (2 articles)
   - HackerNews: "Affinity Studio Goes Free: A Game Changer for Designers"
   - Mastodon: "Affinity Software's Freemium Shift: What Artists Need to..."
   - **Both about the same story** but from different angles

2. **ICC Open Source** (2 articles)
   - Mastodon: "ICC Ditches Microsoft 365 for Open-Source: A Data Privacy..."
   - Mastodon: "ICC's Bold Move: Embracing Open-Source Over Microsoft"
   - **Both about the same story** but different focuses

## How It Works

### Detection Algorithm

Story similarity is calculated using:

| Factor | Weight | What It Detects |
|--------|--------|-----------------|
| **Entity overlap** | 50% | Company/product names: "Affinity", "ICC", "Microsoft" |
| **Topic overlap** | 30% | Shared tags: "open-source", "design", "security" |
| **Title similarity** | 10% | Similar wording in titles |
| **Time proximity** | 10% | Published within 24 hours |

**Bonus:** +10% if strong entity match (>30%) AND good topic overlap (>50%)

**Threshold:** 50% similarity = likely same story

### Integration

Runs automatically in `generate.py` during candidate selection:

```python
# Before generation
candidates = select_article_candidates(
    items,
    deduplicate_stories=True  # Enabled by default
)
```

The system:
1. ✅ Finds story clusters (groups of related items)
2. 📊 Reports findings with confidence scores
3. 🎯 Keeps the **highest quality** item from each cluster
4. 💰 Saves API costs by not generating duplicates

## Usage

### Test It

```bash
python scripts/test_story_clustering.py
```

This runs test cases including your Oct 31 examples.

### In Production

Already integrated! Just run your normal generation:

```bash
python -m src.generate
```

You'll see output like:

```
🔍 Checking for duplicate stories across sources...

📰 Found 1 stories covered by multiple sources:

  Story 1: affinity, canva, freemium, software
  Confidence: 66.7%
  2 sources: hackernews, mastodon
    ⭐ Affinity Studio Goes Free: A Game Changer for Designers...
       Affinity Software's Freemium Shift: What Artists Need to Know...

✓ Filtered out 1 duplicate stories (keeping best source for each)
```

### Disable If Needed

```python
# In your code or config
candidates = select_article_candidates(
    items,
    deduplicate_stories=False  # Disable story clustering
)
```

## Configuration

### Adjust Sensitivity

In `src/story_clustering.py`:

```python
clusters = find_story_clusters(
    items,
    min_similarity=0.50  # Default threshold
)
```

**Threshold values:**
- `0.45` - More aggressive (catches more duplicates, may have false positives)
- `0.50` - **Balanced (default, recommended)**
- `0.55` - Conservative (fewer false positives, may miss some duplicates)

### Customize Detection

In `calculate_story_similarity()`:

```python
score = (
    entity_sim * 0.50 +      # Entity overlap weight
    topic_overlap * 0.30 +   # Topic overlap weight
    title_sim * 0.10 +       # Title similarity weight
    time_proximity * 0.10    # Time proximity weight
)
```

## Output

### What You See

When duplicates are found:

```
📰 Found 2 stories covered by multiple sources:

  Story 1: docker, security, vulnerability
  Confidence: 72.3%
  2 sources: hackernews, reddit
    ⭐ Docker Security Flaw Discovered (quality: 0.90)
       Major Docker Vulnerability Affects Millions (quality: 0.85)

  Story 2: microsoft, icc, open-source
  Confidence: 55.8%
  2 sources: mastodon, mastodon
    ⭐ ICC Ditches Microsoft 365 for Open-Source
       ICC's Bold Move: Embracing Open-Source
```

The ⭐ indicates which item was kept (highest quality score).

### What Gets Saved

Only the best item from each cluster:
- ✅ "Docker Security Flaw Discovered" (quality: 0.90)
- ❌ "Major Docker Vulnerability..." (filtered out)

You save API costs and avoid duplicate content!

## Benefits

### 1. Automatic Detection
No manual review needed - runs on every generation

### 2. Cost Savings
Fewer articles to generate = lower API costs

Example from your Oct 31 run:
- Before: 2 Affinity articles + 2 ICC articles = 4 articles
- After: 1 Affinity article + 1 ICC article = 2 articles
- **Saved: ~$0.02-0.04 in generation costs**

### 3. Quality Focus
Always keeps the highest quality source for each story

### 4. Transparency
Clear reporting of what was filtered and why

### 5. Configurable
Can disable or tune threshold per your needs

## Edge Cases

### Different Angles = Different Stories?

The system uses a **50% threshold** to balance:
- Too low (40%): Might cluster unrelated items
- Too high (60%): Might miss obvious duplicates

**Current behavior:**
- "Docker Security Flaw" + "Docker Vulnerability" → **Clustered** (same story)
- "Rust 1.75 Released" + "Python 3.13 Released" → **Not clustered** (different stories)

If you want to publish different angles on the same story, you can:
1. Lower the quality score of one source (it won't be selected)
2. Disable story clustering temporarily
3. Manually review and publish both (override the filter)

### Single Source, Multiple Posts

If the same source (e.g., Mastodon) has multiple posts about the same story, they'll still be clustered:

```
Story: icc, microsoft, open-source
2 sources: mastodon, mastodon  # Both from same platform, different users
```

This is intentional - it's still duplicate coverage of the same story.

## Future Enhancements

### 1. Source Consolidation

Instead of keeping just one source, **merge perspectives**:

```python
# Combine all sources into one comprehensive article
consolidated_item = consolidate_story_sources(cluster)
# Article generator gets richer context from multiple angles
```

Status: Implemented but not active (see `consolidate_story_sources()`)

### 2. Related Articles Linking

For borderline cases (45-50% similarity), add cross-references instead of filtering:

```yaml
---
title: "ICC Ditches Microsoft 365..."
related_articles:
  - "ICC's Bold Move: Embracing Open-Source..."
---
```

### 3. User Feedback Learning

Track which articles users manually remove and adjust threshold:
- User removes clustered items → threshold too low
- User marks separate items as duplicates → threshold too high

## Troubleshooting

### Too Many False Positives

Unrelated items being clustered together?

**Solution:** Increase threshold:
```python
min_similarity=0.55  # Was 0.50
```

### Missing Obvious Duplicates

Duplicate stories not being caught?

**Solution:** Decrease threshold or check entity extraction:
```python
min_similarity=0.45  # Was 0.50

# Or improve entity extraction for your domain
# Edit extract_entities() in story_clustering.py
```

### Want to See All Items

Disable clustering to see what would have been generated:

```bash
# Edit generate.py temporarily
deduplicate_stories=False
```

Or use dry-run mode:
```bash
python -m src.generate --dry-run
```

## See Also

- `src/story_clustering.py` - Implementation
- `scripts/test_story_clustering.py` - Test cases
- `docs/ADR-006-STORY-DEDUPLICATION.md` - Design decisions
- `docs/RELATED-ARTICLES-CURATION.md` - Original problem
- `docs/ADR-002-ENHANCED-DEDUPLICATION.md` - Post-generation dedup
