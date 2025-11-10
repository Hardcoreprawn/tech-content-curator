# Known Issues

**Last Updated:** November 10, 2025

## Active Bugs (Fix Now)

### 1. Exception Handling Crisis 🚨 (CRITICAL)
**Impact**: Silent failures in production GitHub Actions - debugging impossible without logs
**Location**: Throughout codebase, especially:
- `src/illustrations/text_review_refine.py` - Lines 210, 239
- `src/pipeline/deduplication.py` - Multiple locations
- `src/collectors/mastodon.py` - Line 91
- `src/pipeline/file_io.py` - Lines 149, 163

**Issue**: Bare `except Exception:` blocks swallow errors without logging
**Fix**: See `docs/CODE-IMPROVEMENTS.md` Priority 1

### 2. Input Sanitization (HIGH - Security) 🔐
**Impact**: Path traversal vulnerability via article titles
**Location**: `src/pipeline/article_builder.py` - `generate_article_slug()`
**Issue**: Malicious titles like "../../etc/passwd.md" could escape content directory
**Fix**: See `docs/CODE-IMPROVEMENTS.md` Priority 5 (partially implemented)

---

## Resolved Issues ✅

### Previously Fixed (as of Nov 10, 2025)
1. **Cache Deserialization** - Fixed in `src/fallback_content.py:284` using `GeneratedArticle.model_validate()`
2. **Input Sanitization (Partial)** - Implemented via `safe_filename()` and `validate_path()` in `src/pipeline/article_builder.py` and `src/pipeline/file_io.py`
3. **Atomic File Writes** - Implemented in `src/utils/file_io.py` using temp file + atomic rename pattern
4. **Configuration Validation Timing** - Fixed in `src/config.py` by moving validation to import time, catching config errors immediately on module load
5. **Free-Threading now works in GitHub Actions** - Updated workflows to use `python-version: '3.14t'` (free-threaded build) with `allow-prereleases: true` and `PYTHON_GIL=0` environment variable. GitHub Actions now supports free-threaded Python as of March 2025, enabling the documented 3-4x speedup

---

## Medium Priority Issues

### 3. Resource Cleanup Not Guaranteed
**Impact**: Potential memory leaks in long-running processes
**Location**: Various - OpenAI client lifecycle
**Issue**: Not all code paths use context managers for client cleanup
**Fix**: Audit all client usage, ensure context managers used consistently

### 4. Async/Threading Strategy Unclear
**Impact**: Confusing code, no performance benefit
**Location**: `src/pipeline/orchestrator.py` - Line 404
**Issue**: Mixing async/await with ThreadPoolExecutor without clear benefit
**Fix**: Either go full async or full sync+threads, document Python 3.14 nogil requirements

## Tech Debt (Fix When Convenient)

- **Logging Standardization:** Mixed use of `print()` and `logger.*()` - remove all print statements from src/
- **Magic Numbers:** Hardcoded thresholds (0.15, 0.3) should be in config
- **Data Archive Strategy:** 42+ JSON files in data/, no cleanup strategy
- **Generator Abstraction Review:** Evaluate if class hierarchy needed vs function-based approach

---

## How to Report Issues

For new bugs, create a GitHub Issue with:
- File path and line number
- Expected vs actual behavior
- Steps to reproduce
- Impact assessment

**Use GitHub Issues, not this file** - this is just a quick snapshot of known items.
