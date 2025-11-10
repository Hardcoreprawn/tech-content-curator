# Article Lifecycle Management - Design Document

## Executive Summary

This document outlines a scalable article lifecycle management system for the Tech Content Curator. The system addresses growth concerns by implementing intelligent archival, quality-based retention, and automated cleanup strategies while maintaining site performance and SEO value.

**Key Goals:**
- Scale to thousands of articles without performance degradation
- Automatically archive low-value content
- Maintain high-quality evergreen content
- Preserve SEO juice for valuable articles
- Reduce storage and maintenance overhead

---

## Current State Analysis

### What We Have
- **168+ articles** in `content/posts/` (as of Nov 2025)
- **6 archived articles** in `content/archive/` (deduplication)
- **Automated generation**: 3x daily (20-30 articles/day)
- **Quality metrics**: Built-in scoring (readability, structure, citations, etc.)
- **Hugo static site**: Fast but scales linearly with article count
- **No lifecycle rules**: Articles live forever in posts/

### Growth Projections

| Timeline | Articles | Site Size | Build Time | Issues |
|----------|----------|-----------|------------|--------|
| Current | 168 | ~5MB | ~3s | None |
| 1 month | 800 | ~24MB | ~8s | Manageable |
| 3 months | 2400 | ~72MB | ~20s | Slow builds |
| 6 months | 4800 | ~144MB | ~40s | Performance issues |
| 1 year | 9600 | ~288MB | ~80s | Unmanageable |

**Without lifecycle management:**
- ❌ Slow Hugo builds (>1 minute at 10K articles)
- ❌ Large Git repo (hundreds of MB)
- ❌ RSS feed bloat
- ❌ Difficult to find quality content
- ❌ High maintenance burden

---

## Article Lifecycle States

### State Diagram

```
[New] → [Active] → [Aging] → [Archived] → [Deleted]
                      ↓
                  [Evergreen] (promoted)
```

### State Definitions

#### 1. **New** (0-7 days)
- **Location**: `content/posts/`
- **Purpose**: Fresh content for discovery and indexing
- **SEO**: Full indexing, sitemap priority 0.8
- **RSS**: Included in main feed
- **Visibility**: Homepage, search, tags

#### 2. **Active** (7-90 days)
- **Location**: `content/posts/`
- **Purpose**: Proven content building engagement
- **SEO**: Full indexing, sitemap priority 0.7
- **RSS**: Included in main feed
- **Visibility**: Full site

#### 3. **Aging** (90-180 days)
- **Location**: `content/posts/`
- **Purpose**: Evaluation period for retention
- **SEO**: Full indexing, sitemap priority 0.5
- **RSS**: Excluded from main feed (archive feed only)
- **Visibility**: Search and direct links only

#### 4. **Evergreen** (promoted from Aging)
- **Location**: `content/posts/` or `content/evergreen/`
- **Purpose**: High-value timeless content
- **SEO**: Full indexing, sitemap priority 1.0
- **RSS**: Featured feed
- **Visibility**: Promoted on homepage, curated lists
- **Criteria**: High quality score, sustained traffic, valuable reference

#### 5. **Archived** (>180 days, low value)
- **Location**: `content/archive/{year}/`
- **Purpose**: Historical record, reduced maintenance
- **SEO**: Noindex, but preserved URLs (301 redirects)
- **RSS**: Archive-only feed
- **Visibility**: Archive section only

#### 6. **Deleted** (optional, extreme cases)
- **Location**: Removed from site
- **Purpose**: Remove harmful/outdated/low-quality content
- **SEO**: 410 Gone status
- **Criteria**: Factually incorrect, harmful, or zero value

---

## Retention Policies

### Policy 1: Quality-Based Retention

**Keep articles that:**
- Quality score ≥ 80/100
- Sustained traffic (>10 views/month after 90 days)
- External backlinks (SEO value)
- Technical depth (tutorial, guide, analysis)
- Evergreen topics (not time-sensitive news)

**Archive articles that:**
- Quality score < 70/100
- Zero traffic after 90 days
- News-only content (time-sensitive)
- Duplicate coverage of topics
- No external engagement

**Formula for retention score:**
```python
retention_score = (
    quality_score * 0.4 +
    traffic_score * 0.3 +
    engagement_score * 0.2 +
    evergreen_score * 0.1
)

# Keep if retention_score > 60
```

### Policy 2: Age-Based Archival

| Age | Quality | Action |
|-----|---------|--------|
| 0-90 days | Any | Keep active |
| 90-180 days | ≥80 | Evaluate for evergreen |
| 90-180 days | 70-79 | Monitor traffic |
| 90-180 days | <70 | Archive |
| 180+ days | ≥85 | Promote to evergreen |
| 180+ days | 70-84 | Archive (keep indexed) |
| 180+ days | <70 | Archive (noindex) |

### Policy 3: Storage Limits

**Target metrics:**
- **Active posts**: 500-800 articles (last 3 months)
- **Evergreen**: 200-300 articles (best content)
- **Archive**: Unlimited (compressed, noindex)
- **Git repo**: <100MB (excluding large binaries)

**When limits exceeded:**
- Archive oldest 10% of low-quality articles
- Compress archived article images
- Remove duplicate/low-value content

---

## Implementation Strategy

### Phase 1: Foundation (Week 1-2)

**Deliverables:**
1. ✅ Article metadata extensions
2. ✅ Lifecycle state tracking
3. ✅ Retention score calculation
4. ✅ Manual archival script

**Files to create/modify:**

```python
# src/models.py - Add lifecycle metadata
class GeneratedArticle(BaseModel):
    # ... existing fields ...
    
    # Lifecycle metadata
    lifecycle_state: str = "new"  # new, active, aging, evergreen, archived
    published_date: datetime
    last_updated: datetime | None = None
    last_traffic_check: datetime | None = None
    retention_score: float | None = None
    archive_reason: str | None = None
    
    # Analytics metadata (populated by external script)
    page_views_30d: int = 0
    page_views_90d: int = 0
    external_links: int = 0
    avg_time_on_page: float = 0.0
```

```python
# src/lifecycle/scorer.py - Retention scoring
class RetentionScorer:
    """Calculate article retention score."""
    
    def score(self, article: GeneratedArticle, analytics: dict) -> float:
        """Calculate retention score (0-100).
        
        Components:
        - Quality score (40%): From existing quality metrics
        - Traffic score (30%): Page views over time
        - Engagement score (20%): Time on page, bounce rate
        - Evergreen score (10%): Topic timelessness
        """
        quality = article.quality_score or 70.0
        traffic = self._score_traffic(analytics)
        engagement = self._score_engagement(analytics)
        evergreen = self._score_evergreen(article)
        
        return (
            quality * 0.4 +
            traffic * 0.3 +
            engagement * 0.2 +
            evergreen * 0.1
        )
```

```python
# scripts/archive_articles.py - Manual archival tool
"""Archive old articles based on retention policies."""

def archive_article(filepath: Path, reason: str):
    """Move article to archive with proper metadata."""
    # Load article
    post = frontmatter.load(filepath)
    
    # Update metadata
    post.metadata['lifecycle_state'] = 'archived'
    post.metadata['archive_reason'] = reason
    post.metadata['archived_date'] = datetime.now(UTC).isoformat()
    
    # Move to archive
    year = post.metadata['date'].year
    archive_dir = Path(f"content/archive/{year}")
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    new_path = archive_dir / filepath.name
    with open(new_path, 'w') as f:
        frontmatter.dump(post, f)
    
    filepath.unlink()
    console.print(f"[green]✓[/green] Archived: {filepath.name} → {new_path}")

# Usage: python scripts/archive_articles.py --age 180 --quality-max 70
```

### Phase 2: Automation (Week 3-4)

**Deliverables:**
1. ✅ Automated archival workflow (GitHub Actions)
2. ✅ Analytics integration (Google Analytics API)
3. ✅ Archive section on site
4. ✅ RSS feed splitting

**GitHub Actions Workflow:**

```yaml
# .github/workflows/lifecycle-management.yml
name: Article Lifecycle Management

on:
  schedule:
    - cron: '0 6 * * 0'  # Weekly on Sunday 6am UTC
  workflow_dispatch:

jobs:
  manage-lifecycle:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'
      
      - name: Install dependencies
        run: |
          pip install -e .
          pip install google-analytics-data
      
      - name: Update article analytics
        env:
          GA_PROPERTY_ID: ${{ secrets.GA_PROPERTY_ID }}
          GA_CREDENTIALS: ${{ secrets.GA_CREDENTIALS }}
        run: python scripts/update_article_analytics.py
      
      - name: Calculate retention scores
        run: python scripts/calculate_retention_scores.py
      
      - name: Archive old articles
        run: |
          python scripts/archive_articles.py \
            --age 180 \
            --retention-threshold 60 \
            --dry-run false
      
      - name: Promote evergreen content
        run: python scripts/promote_evergreen.py --threshold 85
      
      - name: Commit changes
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add -A
          git commit -m "🗄️ Lifecycle: Archive old articles, promote evergreen" || echo "No changes"
          git push
      
      - name: Rebuild site
        run: hugo -s site/
```

### Phase 3: Archive Section (Week 5)

**Site changes:**

```toml
# site/hugo.toml - Add archive section
[params]
  mainSections = ["posts", "evergreen"]  # Exclude archive from homepage
  
[[menu.main]]
  name = "Archive"
  url = "/archive/"
  weight = 40
```

```html
<!-- site/layouts/archive/list.html - Archive page -->
{{ define "main" }}
<header class="page-header">
  <h1>Article Archive</h1>
  <p>Historical articles preserved for reference. May contain outdated information.</p>
</header>

{{ range (.Pages.GroupByDate "2006") }}
  <h2>{{ .Key }}</h2>
  <ul class="archive-list">
    {{ range .Pages }}
      <li>
        <time>{{ .Date.Format "Jan 2" }}</time>
        <a href="{{ .Permalink }}">{{ .Title }}</a>
        {{ with .Params.archive_reason }}
          <span class="archive-reason">{{ . }}</span>
        {{ end }}
      </li>
    {{ end }}
  </ul>
{{ end }}
{{ end }}
```

```yaml
# content/archive/_index.md - Archive section metadata
---
title: "Article Archive"
description: "Historical tech articles from our automated content curator"
robots: noindex  # Don't index archive pages
sitemap_exclude: true
---

This archive contains older articles that are no longer actively maintained.
```

### Phase 4: Advanced Features (Week 6+)

**Optional enhancements:**

1. **Evergreen Hub** - Curated collection of best articles
   - `content/evergreen/_index.md` with featured content
   - Auto-updated based on retention scores

2. **Topic Consolidation** - Merge similar articles
   - Detect overlapping topics with semantic similarity
   - Create comprehensive guides from multiple articles

3. **Content Refresh** - Auto-update aging articles
   - Regenerate articles with updated information
   - Add "Last updated" timestamps

4. **Smart Redirects** - 301 redirects for archived content
   - Point archived articles to newer related content
   - Preserve SEO value

5. **Archive Compression** - Reduce storage
   - Compress images in archived articles
   - Remove unnecessary frontmatter

---

## Site Structure After Implementation

```
content/
├── posts/                    # Active articles (last 90 days)
│   ├── 2025-11-06-...md     # ~800 articles max
│   └── ...
├── evergreen/                # Promoted high-value content
│   ├── _index.md            # Evergreen hub page
│   ├── mastering-docker.md
│   └── ...                  # ~200-300 articles
├── archive/                  # Historical content
│   ├── _index.md            # Archive listing
│   ├── 2025/                # Archived by year
│   │   ├── 01/              # Month subdirs (optional)
│   │   └── ...
│   ├── 2026/
│   └── ...
└── about/
    └── lifecycle.md          # Explain lifecycle policy
```

**Benefits:**
- ✅ Fast builds (500-1000 active articles vs 10K+)
- ✅ Focused content discovery
- ✅ Preserved SEO for valuable content
- ✅ Clean RSS feeds
- ✅ Scalable to years of operation

---

## Analytics Integration

### Google Analytics 4 API

**Setup:**
1. Enable GA4 Data API in Google Cloud Console
2. Create service account with "Viewer" role
3. Download credentials JSON
4. Add to GitHub Secrets: `GA_CREDENTIALS`

**Script: `scripts/update_article_analytics.py`**

```python
"""Fetch analytics data and update article metadata."""

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)

def fetch_article_analytics(property_id: str) -> dict[str, dict]:
    """Fetch page views and engagement metrics for all articles.
    
    Returns:
        Dict mapping article path to analytics data:
        {
            '/posts/article-slug/': {
                'views_30d': 123,
                'views_90d': 456,
                'avg_time': 180.5,
                'bounce_rate': 0.45,
            }
        }
    """
    client = BetaAnalyticsDataClient()
    
    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date="90daysAgo", end_date="today")],
        dimensions=[Dimension(name="pagePath")],
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="averageSessionDuration"),
            Metric(name="bounceRate"),
        ],
    )
    
    response = client.run_report(request)
    
    analytics_data = {}
    for row in response.rows:
        path = row.dimension_values[0].value
        if '/posts/' in path:
            analytics_data[path] = {
                'views_90d': int(row.metric_values[0].value),
                'avg_time': float(row.metric_values[1].value),
                'bounce_rate': float(row.metric_values[2].value),
            }
    
    return analytics_data

def update_article_metadata(article_path: Path, analytics: dict):
    """Update article frontmatter with analytics data."""
    post = frontmatter.load(article_path)
    
    # Extract article URL from frontmatter or filename
    article_url = post.metadata.get('url', f"/posts/{article_path.stem}/")
    
    if article_url in analytics:
        data = analytics[article_url]
        post.metadata['page_views_90d'] = data['views_90d']
        post.metadata['avg_time_on_page'] = data['avg_time']
        post.metadata['last_traffic_check'] = datetime.now(UTC).isoformat()
        
        with open(article_path, 'w') as f:
            frontmatter.dump(post, f)

# Usage in workflow
if __name__ == "__main__":
    property_id = os.getenv("GA_PROPERTY_ID")
    analytics = fetch_article_analytics(property_id)
    
    for article in Path("content/posts").glob("*.md"):
        update_article_metadata(article, analytics)
```

### Alternative: Simple File-Based Tracking

**Without GA4 API (simpler):**

Track basic metrics in a JSON file:

```python
# data/article_analytics.json
{
  "2025-11-06-docker-guide.md": {
    "created": "2025-11-06T10:00:00Z",
    "days_live": 45,
    "quality_score": 85.5,
    "retention_score": 78.2,
    "last_updated": "2025-12-20T06:00:00Z"
  }
}
```

Calculate retention based purely on quality + age:
- **High quality (>80) + <90 days**: Keep active
- **High quality (>80) + >180 days**: Promote to evergreen
- **Low quality (<70) + >180 days**: Archive

---

## Rollout Plan

### Week 1: Setup & Testing
- [ ] Add lifecycle fields to `src/models.py`
- [ ] Create `src/lifecycle/scorer.py`
- [ ] Test retention scoring on existing articles
- [ ] Manually archive 10 low-quality articles
- [ ] Verify archive section renders correctly

### Week 2: Automation
- [ ] Create `scripts/archive_articles.py`
- [ ] Create `scripts/calculate_retention_scores.py`
- [ ] Test automation on sample articles
- [ ] Set up GitHub Actions workflow (dry-run mode)

### Week 3: Integration
- [ ] Enable GA4 API (or use file-based tracking)
- [ ] Update article frontmatter with analytics
- [ ] Run first automated archival (50-100 articles)
- [ ] Verify no broken links or SEO issues

### Week 4: Polish
- [ ] Create archive page design
- [ ] Add lifecycle explanation to About page
- [ ] Set up RSS feed splitting
- [ ] Monitor build times and site performance

### Week 5: Evergreen Promotion
- [ ] Create evergreen section
- [ ] Promote top 20-30 articles
- [ ] Feature evergreen on homepage
- [ ] Update navigation

### Ongoing: Monitoring
- [ ] Weekly lifecycle runs (automated)
- [ ] Monthly review of retention scores
- [ ] Quarterly content audits
- [ ] Annual archival deep-clean

---

## Success Metrics

### Performance Targets
- **Build time**: <10 seconds (vs. 40s+ without lifecycle)
- **Active articles**: 500-800 (vs. unlimited growth)
- **Archive ratio**: 60-70% archived after 1 year
- **Git repo size**: <100MB (vs. 300MB+)

### Quality Targets
- **Evergreen articles**: 200-300 high-value pieces
- **Retention rate**: 30-40% of articles stay active
- **SEO preservation**: No loss of Google rankings for valuable content
- **User experience**: Faster site, easier content discovery

### Operational Targets
- **Manual intervention**: <30 min/month
- **Automation success**: 95%+ of archival decisions correct
- **Zero downtime**: No broken links or 404s from archival
- **Reversibility**: Easy to un-archive if needed

---

## Edge Cases & Considerations

### 1. Viral Articles
**Problem**: Article gets sudden traffic spike after 180 days

**Solution**: 
- Monitor traffic trends (last 7 days vs. previous 30 days)
- Don't archive if recent spike detected
- Promotion threshold: 10x traffic increase → move to evergreen

### 2. Seasonal Content
**Problem**: Holiday or event-based articles are low-traffic 11 months/year

**Solution**:
- Add `seasonal: true` frontmatter flag
- Extended retention (keep for 2+ years)
- Re-promote before relevant season

### 3. Evergreen Drift
**Problem**: "Evergreen" article becomes outdated (framework version change)

**Solution**:
- Annual evergreen audit
- Flag outdated articles for refresh or demotion
- Add "Last verified" timestamp

### 4. External Backlinks
**Problem**: Archived article has valuable backlinks

**Solution**:
- Keep article indexed (noarchive) even if aged
- Or create 301 redirect to newer related content
- Track backlinks via Google Search Console

### 5. User Feedback
**Problem**: Users complain about missing articles

**Solution**:
- Keep archive searchable
- Clear messaging about lifecycle policy
- Easy un-archive request process (GitHub issue)

---

## Configuration

### Environment Variables

```bash
# .env additions for lifecycle management

# Lifecycle thresholds
LIFECYCLE_AGING_DAYS=90
LIFECYCLE_ARCHIVE_DAYS=180
LIFECYCLE_RETENTION_THRESHOLD=60.0
LIFECYCLE_EVERGREEN_THRESHOLD=85.0

# Analytics integration
GA_PROPERTY_ID=123456789
GA_CREDENTIALS_PATH=/path/to/credentials.json

# Archive behavior
ARCHIVE_NOINDEX=true
ARCHIVE_COMPRESS_IMAGES=false
ARCHIVE_PRESERVE_URLS=true

# Limits
MAX_ACTIVE_ARTICLES=800
MAX_EVERGREEN_ARTICLES=300
```

### Hugo Configuration

```toml
# site/hugo.toml additions

[params]
  mainSections = ["posts", "evergreen"]  # Exclude archive
  
  [params.lifecycle]
    enable = true
    archive_message = "This article is archived and may contain outdated information."
    evergreen_badge = true

[[menu.main]]
  name = "Archive"
  url = "/archive/"
  weight = 40
```

---

## Migration Path

### Option A: Gradual Migration (Recommended)
1. **Month 1**: Test lifecycle on 10-20 articles manually
2. **Month 2**: Archive 50-100 low-quality articles (>180 days old)
3. **Month 3**: Enable automated weekly archival
4. **Month 4**: Promote evergreen content
5. **Month 5**: Full automation, monitor and adjust

**Pros**: Low risk, can adjust policies based on feedback  
**Cons**: Takes longer to see benefits

### Option B: Big Bang Migration
1. **Week 1**: Archive all articles >180 days with quality <70
2. **Week 2**: Promote all articles with retention score >85
3. **Week 3**: Enable full automation

**Pros**: Immediate benefits (faster builds, cleaner site)  
**Cons**: Higher risk, might archive valuable content

**Recommendation**: Start with Option A, transition to Option B after validation.

---

## Questions & Decisions Needed

### Before Implementation
1. **Analytics integration**: Use GA4 API or simple file-based tracking?
   - GA4 API: More accurate, requires setup
   - File-based: Simpler, quality + age only

2. **Archival aggressiveness**: Conservative or aggressive?
   - Conservative: Keep more articles, slower growth control
   - Aggressive: Archive more, faster performance gains

3. **Evergreen criteria**: Manual curation or fully automated?
   - Manual: Better quality control, more work
   - Automated: Scalable, might miss context

4. **Archive visibility**: Fully indexed or noindex?
   - Indexed: Preserves SEO, clutters search
   - Noindex: Clean search results, loses SEO value

5. **Redirect strategy**: Keep old URLs or redirect?
   - Keep URLs: No SEO loss, more files
   - Redirect: Cleaner, requires redirect logic

### Recommended Defaults
- ✅ **Start with file-based tracking** (simpler, no API setup)
- ✅ **Conservative archival** (retention threshold 60, not 70)
- ✅ **Manual evergreen curation** (first 50-100 articles)
- ✅ **Archive with noindex** (reduce clutter, preserve files)
- ✅ **Keep old URLs** (no redirects initially, simpler)

---

## Next Steps

To get started:

1. **Review this document** and provide feedback on:
   - Retention policies (too aggressive/conservative?)
   - State transitions (make sense?)
   - Automation timeline (too fast/slow?)

2. **Choose integration approach**:
   - Simple file-based (easier, start here)
   - GA4 API (more accurate, more setup)

3. **Set priorities**:
   - Phase 1 only (manual archival for now)
   - Phase 1-3 (full automation within 1 month)
   - Full implementation (all 4 phases)

4. **Test on sample**:
   - Manually archive 10 articles
   - Create archive section
   - Verify site still works

Would you like me to implement any specific phase, or would you prefer to discuss the strategy first?
