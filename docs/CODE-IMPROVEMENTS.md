# Code Improvements - Priority Task List

**Last Updated:** November 5, 2025  
**Status:** Ready for implementation

---

## Priority 0: Configuration Validation at Startup (CRITICAL)

**Problem:** Config validation happens at runtime after work begins, wasting GitHub Actions time and API credits.

**File to fix:**
- `src/config.py` - Lines 100-115

**Task:**
1. Move validation to module import time for CLI scripts
2. Keep deferred validation for library/test usage
3. Add clear error messages for missing API keys
4. Fail immediately before any API calls or data collection

**Implementation:**
```python
# src/pipeline/__main__.py or src/collectors/__main__.py
from src.config import get_config

# Validate at script entry, before any work
config = get_config()  # Raises ValueError if keys missing

if __name__ == "__main__":
    main()
```

**Impact:** Prevents wasting 30+ minutes of GitHub Actions + API credits on missing config.

---

## Priority 1: Exception Handling (HIGH)

**Problem:** Many bare `except Exception:` blocks swallow errors silently, making debugging difficult.

**Files to fix:**
- `src/illustrations/text_review_refine.py` - Lines 210, 239 (confirmed bare except)
- `src/pipeline/deduplication.py` - Multiple locations with bare except
- `src/collectors/mastodon.py` - Line 91
- `src/pipeline/file_io.py` - Lines 149, 163
- `src/enrichment/orchestrator.py` - Throughout

**Note**: This is CRITICAL for production reliability. Silent failures in GitHub Actions make debugging impossible.

**Task:**
1. Replace `except Exception:` with specific exception types
2. Add `logger.exception()` calls to capture stack traces
3. Add context to error messages (what failed, with what data)
4. Re-raise unexpected errors instead of silently continuing

**Example:**
```python
# BAD
except Exception:
    pass

# GOOD
except (URLError, ValueError) as e:
    logger.error(f"URL normalization failed for {url}: {e}", exc_info=True)
    return original_url  # Fallback
```

---

## Priority 2: Logging Standardization (HIGH)

**Problem:** Mixed use of `print()`, `console.print()`, and `logger.*()` - inconsistent and hard to debug.

**Files to fix:**
- `src/illustrations/placement.py` - Lines 301-307 (print statements)
- `src/sources/tiers.py` - Lines 245-262 (print statements)
- All modules missing logger initialization

**Task:**
1. Remove all `print()` statements - replace with `logger.debug()`
2. Keep `console.print()` only for user-facing output
3. Add logger to all modules: `logger = logging.getLogger(__name__)`
4. Use appropriate log levels:
   - `DEBUG`: Internal state
   - `INFO`: Operations (enrich, generate)
   - `WARNING`: Recoverable issues
   - `ERROR`: Operation failures
   - `CRITICAL`: System failures

---

## Priority 3: File I/O Safety (MEDIUM)

**Problem:** JSON writes not atomic - risk of corruption if interrupted.

**Files to fix:**
- `src/pipeline/file_io.py` - `save_article_to_file()`
- `src/collectors/orchestrator.py` - `save_collected_items()`
- `src/deduplication/semantic_dedup.py` - `save_patterns()`
- `src/api_credit_manager.py` - `_save_error_history()`

**Task:**
1. Create helper function `atomic_write_json()` in `src/utils/file_io.py`
2. Replace direct `json.dump()` calls with atomic writes
3. Add disk space checks before large writes
4. Add error handling for disk full scenarios

**Implementation:**
```python
def atomic_write_json(filepath: Path, data: dict) -> None:
    """Write JSON atomically to prevent corruption."""
    temp_file = filepath.with_suffix('.tmp')
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_file.replace(filepath)  # Atomic on POSIX
    except Exception:
        temp_file.unlink(missing_ok=True)
        raise
```

---

## Priority 4: Configuration Validation (MEDIUM)

**Problem:** Config errors discovered at runtime instead of startup.

**File to fix:**
- `src/config.py`

**Task:**
1. Add Pydantic validators for all config fields
2. Add range validation for numeric configs
3. Add dependency validation (e.g., if strategy="generate", require API key)
4. Fail fast at startup with clear error message
5. Add config validation test

**Example:**
```python
from pydantic import Field, field_validator

class PipelineConfig(BaseModel):
    articles_per_run: int = Field(default=3, ge=1, le=20)
    
    @field_validator("image_strategy")
    def validate_image_strategy(cls, v, info):
        if v == "generate" and not info.data.get("unsplash_api_key"):
            raise ValueError("Image generation requires unsplash_api_key")
        return v
```

---

## Priority 5: Input Sanitization (HIGH - Security) 🔐

**Problem:** External content not sanitized before processing. **Path traversal vulnerability exists.**

**Critical Vulnerability:**
```python
# If malicious article title: "../../etc/passwd.md"
slug = generate_article_slug(title)  # → ../../etc/passwd
filepath = content_dir / f"{slug}.md"  # Escapes content directory!
```

**Files to fix:**
- `src/pipeline/article_builder.py` - `generate_article_slug()` (CRITICAL)
- `src/collectors/mastodon.py` - Content processing
- `src/collectors/reddit.py` - Content processing
- `src/pipeline/file_io.py` - Filename validation

**Note:** `src/utils/sanitization.py` exists but not fully applied. Complete the implementation.

**Task:**
1. Create `src/utils/sanitization.py` with sanitization functions
2. Sanitize slugs to prevent directory traversal
3. Escape HTML/markdown in external content
4. Validate file paths before writing
5. Add max length limits

**Implementation:**
```python
def safe_filename(slug: str, max_length: int = 100) -> str:
    """Ensure filename is safe for filesystem."""
    # Remove dangerous characters
    safe = re.sub(r'[<>:"/\\|?*]', '', slug)
    safe = re.sub(r'\.\.+', '', safe)  # No parent directory
    safe = safe[:max_length].strip()
    if not safe:
        raise ValueError(f"Invalid slug: {slug}")
    return safe
```

---

## Priority 6: Resource Management (MEDIUM)

**Problem:** OpenAI client and HTTP connections not properly closed.

**Files to fix:**
- `src/enrichment/orchestrator.py` - OpenAI client lifecycle
- `src/pipeline/orchestrator.py` - Client management
- `src/citations/resolver.py` - HTTP client cleanup

**Task:**
1. Create `src/utils/clients.py` with context managers
2. Replace direct client creation with context managers
3. Add cleanup to signal handlers
4. Audit memory usage in caches

**Implementation:**
```python
from contextlib import contextmanager

@contextmanager
def get_openai_client(config: PipelineConfig):
    client = OpenAI(api_key=config.openai_api_key, timeout=60.0)
    try:
        yield client
    finally:
        client.close()
```

---

## Priority 7: Async/Threading Strategy Clarification (MEDIUM)

**Problem:** Mixing async/await with ThreadPoolExecutor without clear benefit.

**File to fix:**
- `src/pipeline/orchestrator.py` - Lines 404-477
- `src/generate.py` - Lines 74-86

**Task:**
1. Choose ONE approach:
   - **Option A (Recommended):** Remove async, use pure ThreadPoolExecutor
   - **Option B:** Document Python 3.14 nogil requirements (`PYTHON_GIL=0`)
   - **Option C:** True async with `asyncio` (requires rewriting API calls)

2. Update README claims about "3-4x speedup with free-threading":
   - Add environment variable setup: `export PYTHON_GIL=0`
   - Add to GitHub Actions workflows if actually used
   - Or remove claim if not implemented

3. Document performance testing methodology

**Current Issue:** ThreadPoolExecutor wrapped in async adds complexity without benefit unless running with GIL disabled.

---

## Priority 8: Type Safety (LOW-MEDIUM)

**Problem:** Some `# type: ignore` without explanation, `Any` types lose safety.

**Files to fix:**
- `src/collectors/orchestrator.py` - Lines 124, 131
- `src/models.py` - `metadata: dict[str, Any]`

**Task:**
1. Document all `# type: ignore` comments with reason
2. Replace `dict[str, Any]` with TypedDict where possible
3. Add missing return type hints
4. Run mypy with stricter settings

---

## Priority 8: Test Coverage (MEDIUM)

**Problem:** Missing tests for error paths and edge cases.

**Task:**
1. Add tests for exception handling in each module
2. Add integration test for full pipeline
3. Test rate limiter under load
4. Test empty/malformed input handling
5. Add test for atomic file writes

**New test files needed:**
- `tests/test_error_handling.py`
- `tests/test_file_io_safety.py`
- `tests/test_input_sanitization.py`

---

## Quick Wins (Low effort, high impact)

These can be done in 1-2 hours each:

1. **Remove print statements** - Replace with logger calls
2. **Document type ignores** - Add comments explaining why
3. **Add atomic write helper** - Single utility function
4. **Add logger to all modules** - One line per file
5. **Fix bare except blocks** - Be specific about exceptions

---

## Implementation Order

**Week 1 (Critical Reliability):**
- Priority 0: Configuration Validation (2 hours) ⚠️
- Priority 1: Exception Handling (4-6 hours) 🚨
- Priority 5: Input Sanitization (3-4 hours) 🔐

**Week 2 (Maintainability):**
- Priority 2: Logging Standardization (2-3 hours)
- Priority 7: Async/Threading Strategy (2 hours to decide + document)
- Priority 6: Resource Management (2 hours audit)

**Week 3 (Quality):**
- Priority 3: File I/O Safety
- Priority 4: Configuration Validation (additional)
- Priority 8: Type Safety improvements
- Add error path tests

---

## Success Criteria

### Critical (Week 1)
- [ ] Config validation at startup (fails before any API calls)
- [ ] No bare `except:` or `except Exception:` without logging
- [ ] All external input sanitized (path traversal fixed)
- [ ] GitHub Actions logs show clear error messages

### Important (Week 2)
- [ ] No `print()` statements in src/ (only logger and console)
- [ ] Async/threading strategy documented and consistent
- [ ] All clients properly closed (context managers)
- [ ] Free-threading setup documented or claims removed

### Quality (Week 3)
- [ ] All JSON writes use atomic operations
- [ ] All `# type: ignore` have explanations
- [ ] Test coverage >85% including error paths
- [ ] Magic numbers moved to config

---

## Notes for Implementation

- Focus on **one priority at a time**
- Run tests after each change: `uv run pytest tests/ -v`
- Run linter: `uv run ruff check src/`
- Check types: `uv run mypy src/`
- Commit small, logical changes
- Update tests alongside code changes
