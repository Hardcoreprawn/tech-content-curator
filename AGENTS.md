# Agent Instructions

This project treats **types as executable expectations**: they encode correctness, edge-cases, and reduce AI-induced drift.

For full commands, patterns, and OpenAI integration details see [AI-DEVELOPMENT-GUIDE.md](AI-DEVELOPMENT-GUIDE.md).

## Project Philosophy

- **Simple > complex.** Functions over classes. JSON files over databases. Standard library over new dependencies.
- **No enterprise patterns.** No factories, singletons, DI frameworks, message queues, or microservices.
- **Abstractions only at 3+** similar implementations. Never for a single use case.
- **No async/await** unless you are doing concurrent I/O and have measured the benefit.
- Push back on complexity: "Can this be simpler? Can we use the standard library?"

## Environment (Required)

- **Package manager:** `uv` — never `pip`. Use `uv run <cmd>`, `uv add <pkg>`, `uv sync`.
- **Python:** 3.14+ (free-threading via `PYTHON_GIL=0`).
- **Shell:** bash on WSL — never PowerShell.

## Default Workflow (Required)

When modifying any file:

1. **Check diagnostics first**
   - Run workspace diagnostics (e.g. VS Code "Problems" / static type warnings) for the file(s) you touched.
   - Fix all actionable diagnostics caused by your changes.

2. **Prefer canonical types in tests**
   - Use `SourceType` (enum) instead of strings.
   - Use `pydantic.HttpUrl` for URL fields where models require it.
   - If a third-party library has weak or missing type stubs (e.g. `frontmatter`), use a **small, consistent** shim:
     - `cast(frontmatter.Post, frontmatter.load(...))` when loading.
     - Cast `post["..."]` / `post.metadata` to concrete `dict` / `list` shapes before indexing.
     - For Pydantic URLs, use `TypeAdapter(HttpUrl).validate_python("https://...")` in tests.

3. **Run tests in a tight loop**
   - Run the smallest relevant tests first.
   - Before finishing a batch of changes, run the full suite.

4. **Lint and format**
   - `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/` must pass.

5. **Type checks**
   - Pyright is in `basic` mode. `uv run mypy src/` must pass.
   - Don't weaken types to silence errors.

## OpenAI Usage

Two layers — never merge them:

- **`src/utils/openai_wrapper.py`** — use in pipeline/product code. Handles cost tracking, budget caps, telemetry.
- **`src/utils/openai_client.py`** — use in low-level helpers and tests only when telemetry is explicitly unwanted.

## Error Handling

- No bare `except Exception: pass`. Catch specific exceptions.
- Use `logger.exception(...)` or `logger.error(..., exc_info=True)` — never swallow tracebacks.
- Validate inputs early; fail fast with clear messages.

## Code Style

- Type hints on all functions (`def f(x: int) -> str:`).
- Functions under 50 lines.
- Docstrings with examples where non-obvious.
- Return typed results, not raw dicts.
- Add logging for visibility; no bare `print()` in production code.

## Notes

- Type cleanliness is not "extra polish"; it is part of correctness for this repo.
- Keep fixes minimal and local: prefer adjusting test helpers and call sites rather than weakening core model types.
- Avoid adding broad `Any` types unless the upstream library truly forces it.
