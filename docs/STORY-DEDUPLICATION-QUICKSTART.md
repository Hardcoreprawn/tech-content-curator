# Quick Start: Story Deduplication

## Problem
Multiple articles being generated from different sources about the same news story (e.g., "Affinity goes free" from HackerNews + Mastodon).

## Solution ✅
**Automatic story clustering** now detects and filters duplicate stories **before generation**.

## What Changed

### New File
- `src/story_clustering.py` - Core deduplication logic

### Modified Files
- `src/generate.py` - Integrated story clustering into candidate selection

### Test & Docs
- `scripts/test_story_clustering.py` - Test with your Oct 31 examples
- `docs/STORY-CLUSTERING-GUIDE.md` - Full usage guide
- `docs/ADR-006-STORY-DEDUPLICATION.md` - Design decisions

## How to Use

### 1. Test It
```bash
python scripts/test_story_clustering.py
```

### 2. Run Generation (Already Integrated!)
```bash
python -m src.generate
```

You'll see output like:
```
📰 Found 1 stories covered by multiple sources:
  Story 1: affinity, canva, freemium
  Confidence: 66.7%
  2 sources: hackernews, mastodon
    ⭐ Affinity Studio Goes Free...  (kept)
       Affinity Software's Freemium Shift... (filtered)

✓ Filtered out 1 duplicate stories
```

### 3. Disable If Needed
In `generate.py`:
```python
candidates = select_article_candidates(
    items,
    deduplicate_stories=False  # Disable clustering
)
```

## How It Works

Detects duplicate stories using:
- **Entity overlap** (50%) - Company/product names
- **Topic overlap** (30%) - Shared tags
- **Title similarity** (10%)
- **Time proximity** (10%) - Published within 24h

**Threshold:** 50% similarity = same story

**Action:** Keeps highest quality source, filters others

## Benefits

✅ **Automatic** - No manual review needed  
✅ **Cost savings** - Fewer articles to generate  
✅ **Quality first** - Always keeps best source  
✅ **Transparent** - Shows what was filtered and why  
✅ **Configurable** - Can tune threshold or disable

## Configuration

### Adjust Threshold
```python
# In story_clustering.py
clusters = find_story_clusters(
    items,
    min_similarity=0.50  # Default (balanced)
    # 0.45 = more aggressive
    # 0.55 = more conservative
)
```

## Examples

### ✅ Will Be Clustered (Same Story)
- "Affinity Studio Goes Free" + "Affinity Software's Freemium Shift"
- "Docker Security Flaw" + "Docker Vulnerability Affects Millions"
- "ICC Ditches Microsoft" + "ICC's Open-Source Move"

### ✅ Will NOT Be Clustered (Different Stories)
- "Rust 1.75 Released" + "Python 3.13 Released"
- "GitHub Copilot Update" + "Docker Security Flaw"

## Troubleshooting

**Too many false positives?**
→ Increase threshold to 0.55

**Missing obvious duplicates?**
→ Decrease threshold to 0.45

**Want to see all items?**
→ Set `deduplicate_stories=False`

## More Info

- Full guide: `docs/STORY-CLUSTERING-GUIDE.md`
- Design doc: `docs/ADR-006-STORY-DEDUPLICATION.md`
- Test cases: `scripts/test_story_clustering.py`
