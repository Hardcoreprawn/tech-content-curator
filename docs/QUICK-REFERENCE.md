# Quick Reference: Code Quality & Testing

## Running Tests

```bash
# All tests (quiet mode)
uv run pytest tests/ -q

# All tests (verbose)
uv run pytest tests/ -v

# Specific test file
uv run pytest tests/test_categorizer.py -v

# Specific test
uv run pytest tests/test_categorizer.py::TestArticleCategorizer::test_detect_content_type -v

# With coverage
uv run pytest tests/ --cov=src --cov-report=html
```

## Code Quality Checks

```bash
# Ruff linting
uv run ruff check src/ tests/

# Ruff formatting check
uv run ruff format --check src/ tests/

# Auto-fix formatting (safe)
uv run ruff format src/ tests/

# Show all issues with statistics
uv run ruff check src/ tests/ --statistics
```

## Combined Pre-Push Check

```bash
# Quick check before pushing
uv run ruff check src/ tests/ && uv run pytest tests/ -q
```

## Fixing Code Issues

```bash
# Auto-fix all fixable Ruff issues
uv run ruff check src/ tests/ --fix

# Format code automatically
uv run ruff format src/ tests/

# Reload in VS Code after auto-fixing
# Ctrl+Shift+P → "Developer: Reload Window"
```

## CI Pipeline Status

**View on GitHub:**
1. Go to repository
2. Click "Actions" tab
3. Find latest "CI - Tests & Code Quality" workflow
4. Click to see details

**Local status:**
- Code Quality: `uv run ruff check src/ tests/`
- Tests: `uv run pytest tests/ -q`

## Test Statistics

| Category | Count |
|----------|-------|
| Total Tests | 479 |
| Test Files | 23 |
| Passing | 479 (100%) |
| Skipped | 2 (async) |
| Failed | 0 |

## Code Quality Standards

| Check | Tool | Command |
|-------|------|---------|
| Linting | Ruff | `ruff check` |
| Formatting | Ruff | `ruff format --check` |
| Type Checking | mypy | `mypy src/ (optional)` |
| Tests | pytest | `pytest tests/` |

## What CI Checks

✅ **On every push to main or pull request:**
- Ruff linting (127 rules)
- Ruff formatting
- pytest (479 tests)
- Project structure validation

**Status required for merge:** Can be configured in GitHub repo settings

## Common Issues & Fixes

### "Test failed: undefined name 'x'"
→ Check if variable is defined and in scope
→ Run: `uv run ruff check tests/ --select=F821`

### "Import not used"
→ Remove unused import
→ Run: `uv run ruff check --fix` to auto-remove

### "Blank line contains whitespace"
→ Remove spaces/tabs from blank lines
→ Run: `uv run ruff format` to auto-fix

### "Ruff check passes but pytest fails"
→ Lint doesn't catch all runtime issues
→ Check test output: `uv run pytest tests/test_file.py -v`

## Performance Tips

```bash
# Fast: Run only quality checks
uv run ruff check src/ tests/  # ~30 seconds

# Moderate: Run linting + quick tests
uv run ruff check src/ tests/ && uv run pytest tests/ -q  # ~65 seconds

# Complete: Full validation with verbose output
uv run ruff check src/ tests/ && uv run pytest tests/ -v  # ~65 seconds

# Coverage: Shows which lines not tested
uv run pytest tests/ --cov=src --cov-report=term-missing  # ~35 seconds
```

## Workflow: Before Committing

```bash
# 1. Make your changes
# ... code code code ...

# 2. Check code quality
uv run ruff check src/ tests/

# 3. Auto-fix what you can
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/

# 4. Run tests
uv run pytest tests/ -q

# 5. If all pass, commit!
git add .
git commit -m "Your message"
git push
```

## Workflow: After Committing

1. Push to GitHub
2. CI pipeline runs automatically (~1 minute)
3. Check GitHub Actions tab for results
4. If failed, review logs and fix locally
5. Push fix (CI runs again)
6. Repeat until all green ✅

## Documentation

- **Full details**: `docs/CODE-QUALITY-REVIEW.md`
- **Setup**: `SETUP.md` (Development environment)
- **CI definition**: `.github/workflows/ci.yml`
- **Ruff config**: `pyproject.toml` → `[tool.ruff]`
- **pytest config**: `pytest.ini`

---

**Last Updated**: November 3, 2025  
**Status**: ✅ Production Ready
