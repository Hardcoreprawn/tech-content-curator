"""Analyze why the duplicate detection missed the recent duplicates."""

from pathlib import Path

import frontmatter

from src.deduplication.post_gen_dedup import (
    calculate_content_similarity,
    calculate_entity_similarity,
    calculate_tag_overlap,
    calculate_text_similarity,
    check_articles_for_duplicates,
    extract_entities,
)

# Load full articles from files to test with content
affinity1_path = Path("content/posts/2025-10-31-affinity-studio-goes-free.md")
affinity2_path = Path("content/posts/2025-10-31-affinity-software-freemium-shift.md")
icc1_path = Path("content/posts/2025-10-31-icc-ditches-microsoft-365.md")
icc2_path = Path("content/posts/2025-10-31-icc-open-source-move.md")

def load_article(path):
    """Load article and extract metadata."""
    post = frontmatter.load(str(path))
    meta = post.metadata or {}
    return {
        "title": meta.get("title", ""),
        "summary": meta.get("summary", ""),
        "tags": meta.get("tags", []),
        "content": post.content,
        "path": str(path)
    }

affinity1 = load_article(affinity1_path)
affinity2 = load_article(affinity2_path)
icc1 = load_article(icc1_path)
icc2 = load_article(icc2_path)

print("=" * 80)
print("AFFINITY DUPLICATES ANALYSIS (WITH CONTENT)")
print("=" * 80)

print("\nArticle 1:", affinity1["title"])
print("Article 2:", affinity2["title"])

title_sim = calculate_text_similarity(affinity1["title"], affinity2["title"])
summary_sim = calculate_text_similarity(affinity1["summary"], affinity2["summary"])
tag_overlap = calculate_tag_overlap(affinity1["tags"], affinity2["tags"])
content_sim = calculate_content_similarity(affinity1["content"], affinity2["content"])

# Extract and compare entities
entities1 = extract_entities(affinity1["title"] + " " + affinity1["summary"])
entities2 = extract_entities(affinity2["title"] + " " + affinity2["summary"])
entity_sim = calculate_entity_similarity(entities1, entities2)

print(f"\nTitle similarity:   {title_sim:.3f} (threshold: > 0.75)")
print(f"Summary similarity: {summary_sim:.3f} (threshold: > 0.70)")
print(f"Tag overlap:        {tag_overlap:.3f} (threshold: > 0.20 or 0.60)")
print(f"Entity similarity:  {entity_sim:.3f} (NEW - threshold: > 0.50)")
print(f"Content similarity: {content_sim:.3f} (NEW - threshold: > 0.60)")

print(f"\nEntities Article 1: {entities1}")
print(f"Entities Article 2: {entities2}")

overall_score = (
    (title_sim * 0.30) +
    (summary_sim * 0.20) +
    (tag_overlap * 0.10) +
    (entity_sim * 0.40)
)
print(f"\nOverall score (without content): {overall_score:.3f}")

overall_score_with_content = (
    (title_sim * 0.25) +
    (summary_sim * 0.15) +
    (tag_overlap * 0.10) +
    (entity_sim * 0.25) +
    (content_sim * 0.25)
)
print(f"Overall score (with content):    {overall_score_with_content:.3f} (threshold: > 0.55)")

dup = check_articles_for_duplicates(affinity1, affinity2)
print(f"\nDuplicate detected: {dup is not None}")
if dup:
    print(f"  Overall score: {dup.overall_score:.3f}")
    print(f"  Entity similarity: {dup.entity_similarity:.3f}")
    print(f"  Content similarity: {dup.content_similarity:.3f}")

print("\n" + "=" * 80)
print("ICC DUPLICATES ANALYSIS (WITH CONTENT)")
print("=" * 80)

print("\nArticle 1:", icc1["title"])
print("Article 2:", icc2["title"])

title_sim = calculate_text_similarity(icc1["title"], icc2["title"])
summary_sim = calculate_text_similarity(icc1["summary"], icc2["summary"])
tag_overlap = calculate_tag_overlap(icc1["tags"], icc2["tags"])
content_sim = calculate_content_similarity(icc1["content"], icc2["content"])

# Extract and compare entities
entities1 = extract_entities(icc1["title"] + " " + icc1["summary"])
entities2 = extract_entities(icc2["title"] + " " + icc2["summary"])
entity_sim = calculate_entity_similarity(entities1, entities2)

print(f"\nTitle similarity:   {title_sim:.3f} (threshold: > 0.75)")
print(f"Summary similarity: {summary_sim:.3f} (threshold: > 0.70)")
print(f"Tag overlap:        {tag_overlap:.3f} (threshold: > 0.20 or 0.60)")
print(f"Entity similarity:  {entity_sim:.3f} (NEW - threshold: > 0.50)")
print(f"Content similarity: {content_sim:.3f} (NEW - threshold: > 0.60)")

print(f"\nEntities Article 1: {entities1}")
print(f"Entities Article 2: {entities2}")

overall_score = (
    (title_sim * 0.30) +
    (summary_sim * 0.20) +
    (tag_overlap * 0.10) +
    (entity_sim * 0.40)
)
print(f"\nOverall score (without content): {overall_score:.3f}")

overall_score_with_content = (
    (title_sim * 0.25) +
    (summary_sim * 0.15) +
    (tag_overlap * 0.10) +
    (entity_sim * 0.25) +
    (content_sim * 0.25)
)
print(f"Overall score (with content):    {overall_score_with_content:.3f} (threshold: > 0.55)")

dup = check_articles_for_duplicates(icc1, icc2)
print(f"\nDuplicate detected: {dup is not None}")
if dup:
    print(f"  Overall score: {dup.overall_score:.3f}")
    print(f"  Entity similarity: {dup.entity_similarity:.3f}")
    print(f"  Content similarity: {dup.content_similarity:.3f}")

