# Agent Instructions (Reliability + Type Hygiene)

This project treats **types as executable expectations**: they encode correctness, edge-cases, and reduce AI-induced drift.

## Default Workflow (Required)

When a user points at a file or reports a type/IDE diagnostic:

1. **Check diagnostics first**
   - Run workspace diagnostics (e.g. VS Code “Problems” / static type warnings) for the file(s) you touched.
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

## Notes

- Type cleanliness is not “extra polish”; it is part of correctness for this repo.
- Keep fixes minimal and local: prefer adjusting test helpers and call sites rather than weakening core model types.
- Avoid adding broad `Any` types unless the upstream library truly forces it.
