# Related Articles & Editorial Curation

## Problem

During the October 31, 2025 pipeline run, we published two sets of articles that covered the same underlying news story but from different angles and sources:

### Example 1: Affinity Software
- **"Affinity Studio Goes Free: A Game Changer for Designers"** (from hackernews)
- **"Affinity Software's Freemium Shift: What Artists Need to..."** (from mastodon)

**Issue**: Both articles cover Affinity's business model change, but:
- Article 1 focuses on the **free release announcement**
- Article 2 focuses on the **freemium model + Canva acquisition implications**
- They came from **different sources** (HackerNews vs Mastodon)
- Published **same day** (2025-10-31)

### Example 2: ICC Open Source
- **"ICC Ditches Microsoft 365 for Open-Source: A Data Privacy..."** (from mastodon)
- **"ICC's Bold Move: Embracing Open-Source Over Microsoft"** (from mastodon)

**Issue**: Both cover ICC's cloud transition, but:
- Article 1 focuses on **data privacy & sovereignty concerns**
- Article 2 focuses on **industry adoption trends & European tech development**
- Both from **different mastodon posts** by different users
- Published **same day** (2025-10-31)

## Why This Isn't a Deduplication Problem

The current deduplication logic (combining title similarity, summary similarity, tag overlap, entity matching, and content similarity) correctly **doesn't flag these as duplicates** because:

1. **Different titles** - Not >75% similar
2. **Different angles/perspectives** - Content talks about different aspects
3. **Different sources** - Each article traces back to a specific source
4. **Intentional variations** - Our enrichment/generation pipeline creates unique content for each angle

## This Is an Editorial/Curation Problem

These are **legitimate, distinct articles** that could all be published:
- ✅ **Publish both**: Different perspectives enrich coverage
- ✅ **Publish both with linking**: Cross-reference them
- ❌ **Publish one only**: Miss one angle of the story  
- ❌ **Merge them**: Dilute either perspective

The right choice depends on **editorial policy**, not algorithmic similarity.

## Solution: Action Run Tracking + Editorial Review

### 1. Track Article Generation Source

Each article now includes `action_run_id` in frontmatter:

```yaml
---
title: "Affinity Studio Goes Free..."
date: '2025-10-31'
action_run_id: "123456789"  # GitHub Actions run that generated this
---
```

This allows you to:
- Query all articles from a specific run
- Revert a full run if needed
- Audit which run created each article

### 2. Editorial Workflow

After generation, editors should:

1. **Review articles grouped by date**
   ```bash
   # See all articles from today
   ls -lt content/posts/ | head -20
   ```

2. **Identify related articles**
   - Same topic area?
   - Same underlying news story?
   - Different angles/sources?

3. **Make editorial decision**
   - **Same angle, different words?** → Remove duplicate, keep best
   - **Same story, different angles?** → Keep both, add "Related: ..." links
   - **Different stories, coincidentally similar?** → Keep all

### 3. Marking Related Articles (Future)

Consider adding a `related_articles` field to frontmatter:

```yaml
---
title: "Affinity Studio Goes Free..."
related_articles:
  - 2025-10-31-affinity-software-freemium-shift.md
---
```

## Technical Implementation

### What Changed

1. **models.py**: Added `action_run_id` field to `GeneratedArticle`
2. **generate.py**: 
   - Captures `GITHUB_RUN_ID` from GitHub Actions environment
   - Passes it through pipeline
   - Includes it in frontmatter

3. **dedup logic**: Simplified
   - Removed overly aggressive entity/keyword matching
   - Kept entity similarity, but with reasonable thresholds
   - Focus remains on "exact/near-exact duplicates", not "related articles"

### GitHub Actions Integration

The workflow already sets `GITHUB_RUN_ID` automatically:

```yaml
env:
  GITHUB_RUN_ID: ${{ github.run_id }}
```

Every generated article will have this tracking value.

## Recommended Rules of Thumb

| Situation | Action |
|-----------|--------|
| Exact duplicate (>90% similar) | Remove one |
| Same topic, same source, <24h apart | Review closely |
| Same topic, different sources, <24h apart | Keep both with context |
| Different topics, coincidentally similar | Keep all |
| Related articles (same story, different angles) | Link them |

## Future Enhancements

1. **Related Articles Index**
   - Build graph of related articles post-generation
   - Add "See also" links automatically

2. **Editorial Dashboard**
   - Show articles by date
   - Highlight potential related sets
   - Track editorial decisions

3. **Content Merging Tool**
   - Semi-automated merging of related perspectives
   - Combine complementary information
   - Preserve attribution

4. **Learner Feedback**
   - When editors remove related articles, log decision
   - Improve future filtering based on feedback
   - Adjust thresholds over time

## See Also

- `docs/DEDUPLICATION-IMPLEMENTATION.md` - Technical dedup docs
- `docs/ADR-002-ENHANCED-DEDUPLICATION.md` - Dedup strategy
- `src/post_gen_dedup.py` - Dedup implementation
