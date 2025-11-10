# TODO - Priority Actions

**Last Updated:** November 10, 2025

## Week 1: Critical Reliability 🚨

- [ ] **Config Validation at Startup** (2 hours) - Priority 0
  - Move validation to CLI entry points
  - Fail fast before API calls
  - Test in GitHub Actions
  
- [ ] **Fix Exception Handling** (4-6 hours) - Priority 1
  - Replace bare `except Exception:` with specific types
  - Add `logger.exception()` calls
  - Focus on: `text_review_refine.py`, `deduplication.py`, `file_io.py`
  
- [ ] **Fix Path Traversal Vulnerability** (3-4 hours) - Priority 5
  - Complete sanitization in `generate_article_slug()`
  - Validate all file paths before writing
  - Add tests for malicious inputs

## Week 2: Maintainability 🔧

- [ ] **Standardize Logging** (2-3 hours) - Priority 2
  - Remove all `print()` from `src/`
  - Use `logger.debug/info/error` consistently
  - Keep `console.print()` only for user-facing output

- [ ] **Clarify Async Strategy** (2 hours) - Priority 7
  - Document Python 3.14 nogil requirements OR
  - Remove async wrapper, use pure threads
  - Update README performance claims

- [ ] **Audit Resource Cleanup** (2 hours) - Priority 6
  - Ensure all OpenAI clients use context managers
  - Check HTTP client lifecycle
  - Test for memory leaks

## Week 3: Quality & Polish ✨

- [ ] **Move Magic Numbers to Config** (1 hour)
  - Extract 0.15, 0.3 thresholds
  - Document what each threshold means
  
- [ ] **Add Error Path Tests** (3-4 hours)
  - Test API failures gracefully handled
  - Test malformed input handling
  - Test config validation

- [ ] **Data Archive Strategy** (2 hours)
  - Document cleanup for old `collected_*.json`
  - Consider moving to `data/archive/YYYY-MM/`

## Long-Term Evaluation 🔮

- [ ] **Generator Abstraction Review** (research task)
  - Measure if classes share significant code
  - Consider function-based approach if minimal sharing
  
- [ ] **Voice System Metrics** (research task)
  - Add analytics to measure voice effectiveness
  - A/B test if possible
  - Simplify or remove if no proven benefit

- [ ] **Adaptive Learning Dashboard** (future)
  - Visualize pattern effectiveness over time
  - Show cost trends
  - Quality score distribution

---

## Quick Reference

**For detailed implementation:** See `docs/CODE-IMPROVEMENTS.md`  
**For active bugs:** See `BUGS.md`  
**For architecture context:** See `PROJECT-STATUS.md`

**Completion Goal:** Critical items (Week 1) done by November 17, 2025
