# Documentation Guide

**Essential documentation for the Tech Content Curator project.**

---

## Start Here

| Document | Purpose |
|----------|---------|
| `../README.md` | Project overview, quick start, technology stack |
| `../SETUP.md` | Development environment setup |
| `../PROJECT-STATUS.md` | Current status, architecture, completed features |
| `../BUGS.md` | Known bugs and tech debt (use GitHub Issues for new ones) |

---

## Operational Guides

### Code Quality
- **`CODE-IMPROVEMENTS.md`** - Prioritized list of code quality improvements (exception handling, logging, file I/O safety)

### Development
- **`AI-DEVELOPMENT-GUIDE.md`** - Guidelines for AI-assisted development
- **`QUICK-REFERENCE.md`** - Common commands and workflows
- **`FREE-THREADING-SETUP.md`** - Python 3.14 free-threading optimization

### Content Systems
- **`VOICE-QUICK-REFERENCE.md`** - Writing voice profiles and selection
- **`TEXT-ILLUSTRATION-IMPLEMENTATION.md`** - Visual generation system (Mermaid, ASCII, SVG)
- **`ADAPTIVE-DEDUP-GUIDE.md`** - Deduplication with pattern learning
- **`TAG-TAXONOMY.md`** - Content categorization system

### Operations
- **`CREDIT-MANAGEMENT-QUICKSTART.md`** - API cost management
- **`VISIBILITY.md`** - SEO and discoverability

---

## Architecture Decision Records (ADRs)

Decision history with rationale and trade-offs:

1. **`ADR-001-URL-PATH-STRATEGY.md`** - URL normalization approach
2. **`ADR-002-ENHANCED-DEDUPLICATION.md`** - Semantic similarity detection
3. **`ADR-003-DEDUP-PIPELINE-INTEGRATION.md`** - Pipeline integration strategy
4. **`ADR-004-ADAPTIVE-DEDUPLICATION.md`** - Learning from patterns
5. **`ADR-005-SCIENTIFIC-ARTICLE-IMPROVEMENTS.md`** - Quality enhancements
6. **`ADR-006-STORY-DEDUPLICATION.md`** - Story clustering approach
7. **`ADR-007-primary-source-integration.md`** - Primary source handling

---

## Archive

Historical documents moved to `archive/` directory:
- Implementation summaries (phases, features)
- Refactoring logs (orchestrator, Python 3.14 migration)
- Planning documents (completed initiatives)

**These are for reference only** - the system has evolved since they were written.

---

## Documentation Philosophy

**Keep docs:**
- Essential for current operations
- Answer "how do I..." questions
- Explain architectural decisions
- Provide reference for future contributors

**Archive docs:**
- Historical summaries of completed work
- Implementation logs (useful context but not current)
- Refactoring plans (done, but might inform future work)

**Delete docs:**
- Duplicates (same info in multiple places)
- Stale planning (contradicts current reality)
- "Documentation theater" (looks comprehensive, adds no value)

---

## Contributing to Docs

- **Update existing docs** when you change behavior
- **Use GitHub Issues** for bugs/features, not markdown files
- **Create ADRs** for significant architectural decisions
- **Delete stale docs** instead of marking them outdated
- **One canonical source** for each topic

**Quality > Quantity** - Would rather have 10 accurate docs than 50 outdated ones.
