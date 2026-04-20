# TODO - Priority Actions

**Last Updated:** February 21, 2026

All items are tracked as [GitHub Issues](https://github.com/Hardcoreprawn/tech-content-curator/issues). This file is a quick-reference snapshot.

## Immediate (High Priority)

- [ ] **Investigate pipeline automation downtime** — no content generated since Jan 14 ([#23](https://github.com/Hardcoreprawn/tech-content-curator/issues/23))
- [ ] **Set default cost caps** — safety net for runaway API costs ([#29](https://github.com/Hardcoreprawn/tech-content-curator/issues/29))

## Short-Term (Medium Priority)

- [ ] **Fix empty cover images** — recent articles have `cover.image: ''` ([#31](https://github.com/Hardcoreprawn/tech-content-curator/issues/31))
- [ ] **Fix incorrect DOI citations** — resolver produces wrong DOIs for non-academic sources ([#32](https://github.com/Hardcoreprawn/tech-content-curator/issues/32))

## Ongoing (Code Quality)

- [ ] **Fix broad exception handling** — ~100 `except Exception` across src/ ([#1](https://github.com/Hardcoreprawn/tech-content-curator/issues/1), [#7](https://github.com/Hardcoreprawn/tech-content-curator/issues/7))
- [ ] **Standardize logging** — replace remaining `print()` with `logger` ([#4](https://github.com/Hardcoreprawn/tech-content-curator/issues/4))
- [ ] **Harden input sanitization** consistently ([#5](https://github.com/Hardcoreprawn/tech-content-curator/issues/5))
- [ ] **Add pre-commit + task runner** ([#18](https://github.com/Hardcoreprawn/tech-content-curator/issues/18))

## Content Quality

- [ ] **Grounding-first citations** — stop relying on invented author/year ([#9](https://github.com/Hardcoreprawn/tech-content-curator/issues/9))
- [ ] **Reduce source-referential language** in prompts ([#19](https://github.com/Hardcoreprawn/tech-content-curator/issues/19))
- [ ] **Persist cover images locally** + normalize paths ([#14](https://github.com/Hardcoreprawn/tech-content-curator/issues/14))
- [ ] **Fix unstable/animated image hotlinks** ([#20](https://github.com/Hardcoreprawn/tech-content-curator/issues/20))

## Completed ✅

- [x] Fix enrichment test mock signatures ([#22](https://github.com/Hardcoreprawn/tech-content-curator/issues/22))
- [x] Remove test-slug articles from content/posts/ ([#21](https://github.com/Hardcoreprawn/tech-content-curator/issues/21))
- [x] Consolidate duplicate pipeline workflows ([#30](https://github.com/Hardcoreprawn/tech-content-curator/issues/30))
- [x] Remove `src/**` push trigger — consolidated into content-pipeline.yml ([#24](https://github.com/Hardcoreprawn/tech-content-curator/issues/24))
- [x] Fix quarterly-model-evaluation.yml — migrated to uv ([#25](https://github.com/Hardcoreprawn/tech-content-curator/issues/25))
- [x] Path traversal vulnerability (fixed via `safe_filename()`)
- [x] Config validation at startup
- [x] Free-threading in CI
- [x] Resource cleanup (context managers)

---

**For implementation details:** See `docs/CODE-IMPROVEMENTS.md`
**For active bugs:** See `BUGS.md`
**For roadmap:** See `docs/roadmap.md`
