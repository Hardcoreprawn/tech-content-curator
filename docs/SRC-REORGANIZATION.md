# Source Reorganization Migration Guide

**Status**: Phase 1 Complete ✅  
**Started**: October 31, 2025  
**Target Completion**: TBD

## Overview

This document tracks the reorganization of the `src/` folder to improve code organization, maintainability, and scalability.

## Motivation

### Problems Identified
- ❌ **Large monolithic files**: `generate.py` (50KB), `collect.py` (48KB), `enrich.py` (31KB)
- ❌ **Flat structure**: 22 Python files in root with no clear organization
- ❌ **Mixed concerns**: Deduplication logic scattered across 5+ files
- ❌ **Inconsistent patterns**: Some features have packages, others don't

### Benefits Expected
- ✅ **Better organization**: Clear domain boundaries
- ✅ **Easier debugging**: Find code faster
- ✅ **Testability**: Smaller, focused modules
- ✅ **Scalability**: Easy to add new collectors/generators
- ✅ **Team collaboration**: Reduced merge conflicts
- ✅ **Documentation**: Package-level documentation

## Migration Phases

### ✅ Phase 1: Create New Structure (COMPLETE)

**Goal**: Set up new directory structure with comprehensive documentation

**Actions Completed**:
- [x] Created `src/pipeline/` package
- [x] Created `src/collectors/` package
- [x] Created `src/enrichment/` package
- [x] Created `src/deduplication/` package
- [x] Created `src/content/` package
- [x] Created `src/sources/` package
- [x] Created `src/api/` package
- [x] Enhanced `src/utils/` documentation
- [x] Enhanced `src/images/` documentation
- [x] Updated `src/__init__.py` with roadmap
- [x] Created this migration guide

**Files Created**:
- `src/pipeline/__init__.py` - Pipeline orchestration docs
- `src/collectors/__init__.py` - Collector interface docs
- `src/enrichment/__init__.py` - Enrichment pipeline docs
- `src/deduplication/__init__.py` - Dedup strategies docs
- `src/content/__init__.py` - Content management docs
- `src/sources/__init__.py` - Source tier docs
- `src/api/__init__.py` - API client docs
- `src/utils/__init__.py` - Utility functions docs
- `docs/SRC-REORGANIZATION.md` - This file

**Impact**: ✅ No breaking changes, purely additive

---

### ⏳ Phase 2: Move Complete Modules (NEXT)

**Goal**: Move intact files to new locations without breaking them apart

**Files to Move**:
```
src/adaptive_scoring.py      → src/enrichment/adaptive_scoring.py
src/fact_check.py             → src/enrichment/fact_check.py
src/semantic_dedup.py         → src/deduplication/semantic_dedup.py
src/adaptive_dedup.py         → src/deduplication/adaptive_dedup.py
src/post_gen_dedup.py         → src/deduplication/post_gen_dedup.py
src/story_clustering.py       → src/deduplication/story_clustering.py
src/dedup_feedback.py         → src/deduplication/dedup_feedback.py
src/recent_content_cache.py   → src/deduplication/recent_content_cache.py
src/source_tiers.py           → src/sources/tiers.py
src/rate_limit.py             → src/utils/rate_limit.py
src/image_catalog.py          → src/images/catalog.py
src/image_library.py          → src/images/library.py
src/images.py                 → src/images/cover_image.py
```

**Actions Required**:
1. Move each file to new location
2. Update imports in the moved file (internal references)
3. Update imports in files that use the moved module
4. Update package `__init__.py` to export moved items
5. Run tests after each batch of moves
6. Update this document with progress

**Impact**: 🟡 Import changes required, but logic unchanged

**Testing Strategy**:
- Run `pytest tests/` after each batch
- Verify imports with `python -m src.deduplication.semantic_dedup`
- Check that scripts still work

---

### ⏳ Phase 3: Refactor collect.py

**Goal**: Break `collect.py` into individual collector modules

**Structure**:
```
src/collectors/
├── __init__.py
├── base.py              # Base collector interface (NEW)
├── mastodon.py          # Extract from collect.py
├── bluesky.py           # Extract from collect.py
├── reddit.py            # Extract from collect.py
└── hackernews.py        # Extract from collect.py
```

**Steps**:
1. Create `base.py` with `BaseCollector` interface
2. Extract Mastodon functions to `mastodon.py`
3. Extract Bluesky functions to `bluesky.py`
4. Extract Reddit functions to `reddit.py`
5. Extract Hacker News functions to `hackernews.py`
6. Update `collectors/__init__.py` exports
7. Keep `src/collect.py` as facade for backward compatibility
8. Update scripts to use new imports
9. Eventually deprecate `src/collect.py`

**Functions to Extract**:
- `collect_from_mastodon()` → `collectors/mastodon.py`
- `collect_from_mastodon_trending()` → `collectors/mastodon.py`
- `collect_from_bluesky()` → `collectors/bluesky.py`
- `collect_from_reddit()` → `collectors/reddit.py`
- `collect_from_hackernews()` → `collectors/hackernews.py`

**Impact**: 🟡 Import changes, backward compatible facade maintained

---

### ⏳ Phase 4: Refactor enrich.py

**Goal**: Split `enrich.py` into focused enrichment modules

**Structure**:
```
src/enrichment/
├── __init__.py
├── scorer.py            # Quality scoring (NEW)
├── researcher.py        # AI research (NEW)
├── analyzer.py          # Topic/entity extraction (NEW)
├── adaptive_scoring.py  # Already moved in Phase 2
└── fact_check.py        # Already moved in Phase 2
```

**Steps**:
1. Create `scorer.py` with scoring functions
2. Create `researcher.py` with research functions
3. Create `analyzer.py` with analysis functions
4. Extract shared OpenAI logic to `src/api/openai_client.py`
5. Update `enrichment/__init__.py` exports
6. Keep `src/enrich.py` as facade
7. Update scripts to use new imports

**Functions to Extract**:
- Scoring logic → `scorer.py`
- Research logic → `researcher.py`
- Topic/entity extraction → `analyzer.py`

**Impact**: 🟡 Import changes, facade maintained

---

### ⏳ Phase 5: Refactor generate.py

**Goal**: Break `generate.py` into manageable components

**Structure**:
```
src/pipeline/
├── __init__.py
└── generate.py          # Orchestration only

src/generators/
├── article_writer.py    # Core writing logic (NEW)
└── metadata_generator.py # Frontmatter/metadata (NEW)

src/content/
├── __init__.py
├── article_manager.py   # CRUD operations (NEW)
├── frontmatter.py       # Frontmatter handling (NEW)
└── publisher.py         # Publishing logic (NEW)
```

**Steps**:
1. Extract article writing to `generators/article_writer.py`
2. Extract metadata generation to `generators/metadata_generator.py`
3. Extract file operations to `content/article_manager.py`
4. Extract frontmatter logic to `content/frontmatter.py`
5. Extract publishing to `content/publisher.py`
6. Keep orchestration in `pipeline/generate.py`
7. Update all imports

**Impact**: 🟠 Significant refactoring, careful testing needed

---

### ⏳ Phase 6: Move Utility Files

**Goal**: Consolidate remaining utility files

**Files to Move**:
```
src/rate_limit.py → src/utils/rate_limit.py (if not done in Phase 2)
```

**New Files to Create**:
```
src/utils/text_processing.py  # Extract text utils from various files
src/utils/date_utils.py        # Extract date utils if needed
```

**Impact**: ✅ Low risk, utility consolidation

---

### ⏳ Phase 7: Testing and Validation

**Goal**: Comprehensive testing of reorganized codebase

**Actions**:
1. Run full test suite (`pytest tests/`)
2. Run all demo scripts
3. Test collection pipeline end-to-end
4. Test enrichment pipeline end-to-end
5. Test generation pipeline end-to-end
6. Verify cost tracking still works
7. Check all imports resolve correctly
8. Update any remaining documentation
9. Clean up any deprecated facades
10. Final code review

**Success Criteria**:
- ✅ All tests pass
- ✅ All scripts run successfully
- ✅ No import errors
- ✅ Documentation is complete
- ✅ Code is cleaner and more maintainable

**Impact**: ✅ Validation only, no code changes

---

## Rollback Plan

If issues arise during migration:

1. **Phase 1**: Just delete new directories (no code changes made)
2. **Phase 2**: Revert file moves, restore old imports
3. **Phase 3+**: Git revert to last known good state
4. **Always**: Keep backups before major refactoring

## Import Migration Examples

### Before (Old Imports)
```python
from src.collect import collect_from_mastodon
from src.enrich import enrich_items
from src.generate import generate_articles
from src.semantic_dedup import deduplicate_semantic
from src.adaptive_scoring import ScoringAdapter
```

### After (New Imports)
```python
from src.collectors import collect_from_mastodon
from src.enrichment import enrich_items
from src.pipeline.generate import generate_articles
from src.deduplication import deduplicate_semantic
from src.enrichment import ScoringAdapter
```

## Package Dependencies

```
models.py, config.py (core, no dependencies)
    ↓
utils/ (minimal dependencies)
    ↓
collectors/ (depends on: models, config, utils)
    ↓
enrichment/ (depends on: models, config, utils, api)
    ↓
deduplication/ (depends on: models, enrichment)
    ↓
generators/ (depends on: models, config, utils, citations, images)
    ↓
content/ (depends on: models, generators)
```

## Documentation Updates Needed

- [ ] Update README.md with new structure
- [ ] Update IMPLEMENTATION-STRATEGY-*.md docs
- [ ] Update demo scripts
- [ ] Update test imports
- [x] Create this migration guide

## Notes

- Each phase should be a separate git commit
- Run tests after each phase
- Update this document as we progress
- Document any unexpected issues or decisions
- Keep backward compatibility where possible during transition
