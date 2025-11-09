# ADR-007: Primary Source Integration for Meta-Content

**Status:** Accepted  
**Date:** 2025-11-09

## Problem
Articles about other articles lack specificity. Generic meta-discussion
replaces engagement with actual content.

## Decision
1. Detect meta-content during enrichment
2. Extract and fetch primary source URLs
3. Add "commentary" content type
4. Score source citation quality

## Rationale
- Better articles with actual quotes/specifics
- Follows existing patterns (retry, error handling)
- Backward compatible with feature flag
- Cost-controlled (~$0.01-0.03/article)

## Consequences
✅ Improved article quality for meta-content
✅ Maintainable (existing patterns)
⚠️ Small cost increase
⚠️ Requires monitoring fetch failures

## References
- ARTICLE-QUALITY-IMPROVEMENT-PLAN.md
- src/enrichment/source_fetcher.py
- Tests: test_source_fetcher.py