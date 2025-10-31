# ADR-003: Post-Generation Deduplication Pipeline Integration

**Date:** 2024-10-30  
**Status:** ACCEPTED  
**Relates to:** ADR-002 (Enhanced Deduplication)

## Context

Following the discovery of duplicate articles (e.g., multiple "Affinity Software" articles published the same day from different sources), we implemented an enhanced deduplication strategy (ADR-002). This ADR documents the integration of that strategy into the main article generation pipeline.

## Decision

We have integrated post-generation deduplication checks into `src/generate.py` so that:

1. **All newly generated articles are automatically checked** against existing articles in the content directory
2. **Duplicates are flagged and skipped** before being saved to disk
3. **Detailed duplicate reports** are printed to console for visibility

This ensures the deduplication logic runs automatically every time articles are generated, preventing duplicate articles from ever being published.

## Implementation Details

### Pipeline Integration Point

The deduplication check occurs in `generate_articles_from_enriched()` after an article is generated but **before it's saved to file**:

```python
# Step 1: Generate article from enriched item
article = generate_single_article(item, config, generators, force_regenerate)

if article:
    # Step 2: CRITICAL - Check for duplicates before saving
    existing_articles = _load_article_metadata_for_dedup(get_content_dir())
    
    duplicates = find_duplicate_articles([new_article_data] + existing_articles)
    flagged = [d for d in duplicates if d matches new article]
    
    if flagged:
        console.print("[yellow]⚠ Duplicate detected - skipping article[/yellow]")
        report_duplicate_candidates(flagged, verbose=True)
    else:
        # Step 3: Only save if no duplicates found
        save_article_to_file(article, config, generate_images)
        articles.append(article)
```

### Helper Functions Added

#### `_load_article_metadata_for_dedup(content_dir: Path) -> list[dict]`

Loads metadata from existing articles for efficient deduplication checks:

- Reads all `.md` files in content directory
- Extracts: `title`, `summary`, `tags`, `path`
- Returns list of metadata dicts for comparison

**Usage:**
```python
existing_articles = _load_article_metadata_for_dedup(get_content_dir())
```

### Deduplication Thresholds

Applied via `check_articles_for_duplicates()` from `post_gen_dedup.py`:

| Condition | Threshold | Logic |
|-----------|-----------|-------|
| **Title Match** | Title similarity > 75% + Tag overlap > 60% | Flag as duplicate |
| **Summary Match** | Summary similarity > 70% + Tag overlap > 60% | Flag as duplicate |
| **Overall Score** | Combined score > 65% | Flag as duplicate |

### Output Reporting

When a duplicate is detected, users see:

```
⚠ Duplicate detected - skipping article

Pair 1:
  Article 1: [new-generated-article-slug].md
  Article 2: 2025-10-30-existing-similar-article.md
  Overall similarity: 82.5%
  
[Rich table with detailed metrics]
```

## Benefits

1. **Automatic Protection:** No manual intervention needed - duplicates are caught at generation time
2. **Visibility:** Detailed reports show why articles were flagged
3. **Efficiency:** Metadata loading is fast (no full file parsing)
4. **Consistency:** Uses same thresholds as test script (`scripts/test_dedup.py`)
5. **Non-Intrusive:** Doesn't affect other generation steps (title, slug, image generation)

## Testing

### Local Testing

Test the script independently:
```bash
# Find all duplicates in existing articles
python scripts/test_dedup.py --verbose

# Preview what would be removed (dry-run)
python scripts/test_dedup.py --dry-run --remove

# Actually remove high-confidence duplicates (>75% similar)
python scripts/test_dedup.py --remove
```

### Pipeline Testing

When `generate.py` is run, it will:
1. Load enriched items
2. Generate candidate articles
3. For each newly generated article:
   - Check against existing articles
   - Skip if duplicate found
   - Save only if unique
4. Report all skipped duplicates

## Monitoring

To verify the integration is working:

1. **Check console output** during generation for "Duplicate detected" warnings
2. **Review generation logs** to see which articles were skipped
3. **Compare counts:** Articles generated vs. articles saved to disk

If `generated_count > saved_count`, duplicates were caught.

## Future Enhancements

1. **Configurable thresholds:** Allow `--dedup-threshold` CLI flag
2. **Dedup statistics:** Track and report duplicate prevention metrics
3. **Archive skipped:** Save skipped duplicates to `content/archive/dedup-skipped/`
4. **Weekly reports:** Generate summary of duplicates caught

## References

- `docs/ADR-002-ENHANCED-DEDUPLICATION.md` - Strategy and thresholds
- `src/post_gen_dedup.py` - Deduplication implementation
- `scripts/test_dedup.py` - Testing script
- `src/generate.py` - Main generation pipeline
