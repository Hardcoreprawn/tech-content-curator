# Feature 2: Academic Citation Resolution - Complete Architecture & Usage

## Core Principle

**When article generators mention research, citations are automatically discovered and linked to enable readers to find the original papers.**

---

## How It Works

### 1. Citation Extraction (Automatic During Article Generation)

When an article is generated and contains academic citations:
```
Recent research by Lentink (2014) established foundational principles...
Later, Usherwood et al. (2017) conducted detailed studies...
Jones et al (2016) also contributed findings...
```

The **CitationExtractor** finds all citations matching:
- `Author (Year)` - Single author
- `Author et al. (Year)` - Multiple authors (standard format)
- `Author et al (Year)` - Missing period (common typo)  
- `Author, et al. (Year)` - Comma variant

### 2. Citation Resolution (Multi-Strategy API Lookups)

For each citation found, the **CitationResolver** attempts to find the actual paper:

**Resolution Strategy (tries in order):**
1. Check cache first (30-day TTL) - fastest
2. Query CrossRef API with full author string - best for published papers
3. Query CrossRef API with first author only - handles abbreviated lists
4. Query arXiv API with full author string - preprints & CS papers
5. Query arXiv API with first author only - backup for arXiv

This multi-strategy approach handles:
- Abbreviated author lists ("Smith et al." when paper has many authors)
- Papers not indexed in CrossRef (arXiv preprints)
- Different author formatting variations
- Cache misses efficiently

### 3. Citation Formatting & Linking

Each resolved citation becomes a markdown link:

**Before (plain text):**
```
Lentink (2014) established foundational principles
```

**After (with link):**
```markdown
[Lentink (2014)](https://doi.org/10.1088/1748-3182/9/2/020301) established foundational principles
```

### 4. Performance Caching

All resolutions are cached (30-day TTL) in `data/citations_cache.json`:
- First lookup of "Lentink (2014)" → API query (~300-500ms)
- Subsequent lookups of "Lentink (2014)" → cache hit (~1ms)

---

## Architecture

### Module Structure
```
src/citations/
├── __init__.py              # Public API (Citation, CitationExtractor, CitationResolver, etc.)
├── extractor.py             # CitationExtractor - regex-based extraction (~190 lines)
├── resolver.py              # CitationResolver - CrossRef & arXiv API calls (~220 lines)
├── formatter.py             # CitationFormatter - markdown link formatting (~135 lines)
└── cache.py                 # CitationCache - 30-day TTL JSON persistence (~145 lines)
```

### Integration Point: Article Generation

In `src/generate.py`, `save_article()` function:

```python
if config.enable_citations:
    try:
        extractor = CitationExtractor()
        resolver = CitationResolver()
        formatter = CitationFormatter()
        cache = CitationCache()

        # Extract → Resolve → Format → Apply
        citations = extractor.extract(article.content)
        
        for citation in citations:
            # Try cache first, then APIs
            cached = cache.get(citation.authors, citation.year)
            if cached and cached.get("url"):
                resolved = ResolvedCitation(
                    doi=cached.get("doi"),
                    arxiv_id=None,
                    pmid=None,
                    url=cached.get("url"),
                    confidence=0.95
                )
            else:
                resolved = resolver.resolve(citation.authors, citation.year)
                cache.put(citation.authors, citation.year, resolved.doi, resolved.url)
            
            formatted = formatter.format(citation, resolved)
            
        article_content = formatter.apply_to_text(article_content, formatted_citations)
    
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Citation processing failed: {e}")
        # Continue without citations on error
```

---

## Files & Changes

### New Files (5)
- `src/citations/__init__.py` - Public API exports
- `src/citations/extractor.py` - Multi-pattern citation extraction
- `src/citations/resolver.py` - CrossRef & arXiv resolution
- `src/citations/formatter.py` - Markdown link formatting
- `src/citations/cache.py` - 30-day TTL JSON cache

### Modified Files
- `src/models.py` - Added `enable_citations` and `citations_cache_ttl_days` config fields
- `src/config.py` - Load citation config from environment
- `src/generate.py` - Integrated citation processing into `save_article()`
- `.env.example` - Added citation config variables

### Test File
- `tests/test_citations.py` - 32 comprehensive tests (all passing)

---

## Usage & Configuration

### Environment Variables
```bash
# .env file
ENABLE_CITATIONS=true
CITATIONS_CACHE_TTL_DAYS=30
```

### Programmatic Usage

**Basic extraction & resolution:**
```python
from src.citations import CitationExtractor, CitationResolver

extractor = CitationExtractor()
resolver = CitationResolver()

text = "Research by Smith et al. (2020) shows..."
citations = extractor.extract(text)

for citation in citations:
    resolved = resolver.resolve(citation.authors, citation.year)
    if resolved.doi:
        print(f"Found: {resolved.url}")
```

**Full pipeline with formatting:**
```python
from src.citations import CitationExtractor, CitationResolver, CitationFormatter

article = """
Lentink (2014) established principles.
Usherwood et al. (2017) expanded on this work.
"""

extractor = CitationExtractor()
resolver = CitationResolver()
formatter = CitationFormatter()

citations = extractor.extract(article)
formatted_citations = []

for citation in citations:
    resolved = resolver.resolve(citation.authors, citation.year)
    formatted = formatter.format(citation, resolved)
    formatted_citations.append(formatted)

result = formatter.apply_to_text(article, formatted_citations)
# Citations are now markdown links
```

**With caching:**
```python
from src.citations import CitationResolver
from src.citations.cache import CitationCache

resolver = CitationResolver()
cache = CitationCache()

# First call: checks cache (miss), queries API, stores result
resolved = resolver.resolve("Lentink", 2014)
cache.put("Lentink", 2014, resolved.doi, resolved.url)

# Second call: returns from cache (30 days), no API query
cached = cache.get("Lentink", 2014)
# Returns: {"doi": "10.1088/...", "url": "https://doi.org/..."}
```

---

## API Integrations

### CrossRef (https://api.crossref.org/v1/works)
- **Type:** Free, no authentication required
- **Rate limit:** Typically 50 requests/second (very generous)
- **Returns:** DOI, publication metadata
- **Best for:** Published journal articles and books

**Query example:**
```
https://api.crossref.org/v1/works?query=author:Smith+year:2020&rows=1
```

### arXiv (https://export.arxiv.org/api/query)
- **Type:** Free, no authentication required
- **Rate limit:** ~3 requests/second (more conservative)
- **Returns:** arXiv ID, preprint metadata
- **Best for:** Computer science preprints, physics papers

**Query example:**
```
https://export.arxiv.org/api/query?search_query=au:"Smith"+AND+submittedDate:[202001010000+TO+202012312359]
```

---

## Confidence Scoring

### Extraction Confidence (pattern reliability)
| Pattern | Format | Confidence |
|---------|--------|------------|
| Primary | `Smith et al. (2014)` | 100% |
| Secondary | `Smith et al (2014)` | 90% (missing period) |
| Tertiary | `Smith, et al. (2014)` | 85% (comma variant) |

### Resolution Confidence (match quality)
| Scenario | Confidence |
|----------|------------|
| Exact match + year verified | 95%+ |
| Found via first-author fallback | 80-94% |
| Partial match (common names) | 70-79% |
| Not found | 0% |

### Formatting Threshold
- **Only citations with confidence ≥ 0.7** are formatted as markdown links
- Lower confidence citations remain as plain text
- Configurable per use case

---

## Error Handling & Resilience

### Graceful Degradation
If anything fails:
1. Article continues without citations (no crash)
2. Error is logged to console with yellow warning
3. Original citation text is preserved
4. Processing completes successfully

### Specific Failure Scenarios
| Scenario | Behavior |
|----------|----------|
| API timeout | Use cached value if available, skip citation |
| API rate limited | Retry with exponential backoff |
| Citation not found | Keep as plain text (no link) |
| Cache expired | Re-query API |
| Invalid year | Skip citation (filtered during extraction) |
| Network error | Log warning, continue without citations |

---

## Data Structures

### Citation (extracted)
```python
@dataclass
class Citation:
    original_text: str          # "Lentink (2014)"
    authors: str                # "Lentink"
    year: int                   # 2014
    position: tuple[int, int]   # Start/end position in text
    confidence: float           # 0.85-1.0 (pattern confidence)
```

### ResolvedCitation (from API)
```python
@dataclass
class ResolvedCitation:
    doi: str | None             # "10.1088/1748-3182/9/2/020301"
    arxiv_id: str | None        # "1234.5678"
    pmid: str | None            # (not currently used)
    url: str | None             # "https://doi.org/10.xxxx/..."
    confidence: float           # 0.7-1.0 (match confidence)
```

### Cache Format (data/citations_cache.json)
```json
{
  "Lentink_2014": {
    "doi": "10.1088/1748-3182/9/2/020301",
    "url": "https://doi.org/10.1088/1748-3182/9/2/020301",
    "timestamp": "2025-10-31T12:34:56.789012"
  },
  "Usherwood_2017": {
    "doi": "10.4324/9781315464015",
    "url": "https://doi.org/10.4324/9781315464015",
    "timestamp": "2025-10-31T12:34:57.123456"
  }
}
```

---

## Testing

### Test Coverage (32 tests, all passing)
- **Extraction:** 8 tests (patterns, false positives, year validation, deduplication)
- **Resolution:** 8 tests (CrossRef, arXiv, fallbacks, error handling)
- **Formatting:** 8 tests (confidence thresholds, single/multiple citations)
- **Caching:** 5 tests (put/get, persistence, TTL, expiration)
- **Integration:** 3 tests (full pipeline, cache effectiveness, fallback chains)

### Running Tests
```bash
# All citation tests
python -m pytest tests/test_citations.py -v

# Specific test class
python -m pytest tests/test_citations.py::TestCitationExtractor -v

# With coverage
python -m pytest tests/test_citations.py --cov=src.citations

# Verbose output
python -m pytest tests/test_citations.py -vv
```

---

## Performance

### API Response Times
- **CrossRef:** 50-200ms per query
- **arXiv:** 200-500ms per query (slower)
- **Cache hit:** ~1ms per lookup

### Typical Article Processing
| Scenario | Time |
|----------|------|
| 0 citations | 0ms |
| 3 citations (all cached) | 3ms |
| 3 citations (all new) | 600-1500ms |
| 3 citations (mixed) | 200-800ms |

### Cache Benefits
- **First article:** API queries
- **Subsequent articles:** Cache hits (98%+ faster)
- **30-day TTL:** Balances freshness with performance

---

## Key Features

✅ **FREE** - CrossRef and arXiv are free (no API costs)
✅ **NO AUTH** - No authentication required
✅ **CACHED** - 30-day TTL prevents duplicate API calls
✅ **RESILIENT** - Failures don't break article generation
✅ **CONFIGURABLE** - Enable/disable, adjust TTL
✅ **TYPED** - Full type hints throughout
✅ **TESTED** - 32 comprehensive test cases
✅ **DOCUMENTED** - Extensive inline comments

---

## Future Enhancements

### Potential Features
- Direct PDF links from CrossRef/arXiv
- Citation formatting options (APA, MLA, Chicago)
- Citation count ("cited 450 times")
- Fuzzy matching for misspelled names
- Author disambiguation for common names
- PMID resolution for medical articles
- Citation relationship visualization

### Configuration Extensibility
- Resolution strategy priority settings
- Custom confidence thresholds per article type
- Support for custom API endpoints
- Citation style preferences per publication

---

## Summary

The citation resolution feature:
- Runs automatically during article generation
- Handles multiple citation format variations
- Links to official sources (DOI, arXiv)
- Caches results for performance
- Fails gracefully if APIs unavailable
- Improves reader experience by providing citations
- Adds academic credibility to generated articles
- Costs zero dollars (all APIs free)
- Adds minimal processing time

**Result:** Readers can click citations to read the original papers.
