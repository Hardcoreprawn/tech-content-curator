# Code Improvements - Priority Task List

**Last Updated:** November 5, 2025  
**Status:** Ready for implementation

---

## Priority 1: Exception Handling (HIGH)

**Problem:** Many bare `except Exception:` blocks swallow errors silently, making debugging difficult.

**Files to fix:**
- `src/pipeline/deduplication.py` - Lines 53, 87, 153, 187
- `src/collectors/mastodon.py` - Line 91
- `src/pipeline/file_io.py` - Lines 149, 163
- `src/enrichment/orchestrator.py` - Throughout

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

## Priority 5: Input Sanitization (HIGH - Security)

**Problem:** External content not sanitized before processing.

**Files to fix:**
- `src/pipeline/article_builder.py` - `generate_article_slug()`
- `src/collectors/mastodon.py` - Content processing
- `src/collectors/reddit.py` - Content processing
- `src/pipeline/file_io.py` - Filename validation

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

## Priority 7: Type Safety (LOW-MEDIUM)

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

**Week 1:**
- Priority 1: Exception Handling
- Priority 2: Logging Standardization
- Quick Win: Remove print statements

**Week 2:**
- Priority 3: File I/O Safety  
- Priority 5: Input Sanitization
- Priority 8: Add error path tests

**Week 3:**
- Priority 4: Configuration Validation
- Priority 6: Resource Management
- Priority 7: Type Safety improvements

---

## Success Criteria

- [ ] No bare `except:` or `except Exception:` without logging
- [ ] No `print()` statements in src/ (only logger and console)
- [ ] All JSON writes use atomic operations
- [ ] All config validated at startup with clear errors
- [ ] All external input sanitized
- [ ] All clients properly closed (context managers)
- [ ] All `# type: ignore` have explanations
- [ ] Test coverage >85% including error paths

---

## Notes for Implementation

- Focus on **one priority at a time**
- Run tests after each change: `uv run pytest tests/ -v`
- Run linter: `uv run ruff check src/`
- Check types: `uv run mypy src/`
- Commit small, logical changes
- Update tests alongside code changes
