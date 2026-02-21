# Known Issues

**Last Updated:** February 21, 2026

## Active Bugs

### 1. Broad Exception Handling (~100 `except Exception` in src/)
**Impact**: Reduced debuggability; some handlers catch too broadly
**Status**: The 4 files originally flagged (text_review_refine.py, deduplication.py, mastodon.py, file_io.py) are fixed — they now catch specific exceptions and log with `exc_info=True`. However, ~100 `except Exception as e:` remain across src/, plus 9 bare `except Exception:` without `as e` in clients.py, orchestrator.py, fact_check.py, openai_wrapper.py.
**Tracked**: [#1](https://github.com/Hardcoreprawn/tech-content-curator/issues/1), [#7](https://github.com/Hardcoreprawn/tech-content-curator/issues/7)

### 2. Async/Threading Strategy Unclear
**Impact**: Confusing code mixing asyncio + ThreadPoolExecutor
**Location**: `src/pipeline/orchestrator.py` — `generate_articles_async()`
**Status**: Documented but architecturally unchanged. Works but hard to reason about.
**Tracked**: [#3](https://github.com/Hardcoreprawn/tech-content-curator/issues/3)

---

## Tech Debt

- **Logging**: 14 `print()` calls remain in src/ (semantic_dedup.py, dedup_feedback.py, source_tiers.py). [#4](https://github.com/Hardcoreprawn/tech-content-curator/issues/4)
- **Magic numbers**: Hardcoded thresholds (0.15, 0.3) in enrichment/scorer.py, orchestrator.py, adaptive_scoring.py.
- **Data archive**: 38+ JSON files in data/ with no cleanup strategy. [#28](https://github.com/Hardcoreprawn/tech-content-curator/issues/28)

---

## Resolved Issues ✅

1. **Path Traversal** — Fixed via `safe_filename()` + `validate_path()` in `src/utils/sanitization.py`
2. **Resource Cleanup** — `get_openai_client()` now uses `@contextmanager` with `client.close()` in finally
3. **Cache Deserialization** — Fixed with `GeneratedArticle.model_validate()`
4. **Config Validation Timing** — Moved to import time in `src/config.py`
5. **Free-Threading in CI** — GitHub Actions uses `python-version: '3.14t'` with `PYTHON_GIL=0`
6. **Enrichment Test Failure** — Mock signatures updated to match 4-arg `enrich_single_item`. [#22](https://github.com/Hardcoreprawn/tech-content-curator/issues/22)

---

**Use [GitHub Issues](https://github.com/Hardcoreprawn/tech-content-curator/issues) for new bugs**, not this file.
