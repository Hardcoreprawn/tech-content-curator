# Quick Start: 3 Scientific Article Enhancements

You asked for **3 improvements to scientific articles** (like the owl flight piece). I've created **3 focused implementation guides** to replace the 9-document mess.

---

## The 3 Features

| # | Feature | Effort | Cost | Guide |
|---|---------|--------|------|-------|
| 1 | **Multi-source images** | 3-4 hrs | $0 (free stock photos) | `FEATURE-1-IMAGES.md` |
| 2 | **Academic citations** | 2-3 hrs | $0 (free CrossRef API) | `FEATURE-2-CITATIONS.md` |
| 3 | **Concept illustrations** | 4-5 hrs | $0-0.06 (SVGs + optional AI) | `FEATURE-3-ILLUSTRATIONS.md` |

**Total effort**: ~9-12 hours  
**Total cost**: $0-0.06 per article (currently you're paying $0.020 for AI images)  
**Result**: Better-looking, more credible scientific articles

---

## How to Use These Guides

Each file has the same structure:

1. **What to Build** - Quick overview
2. **Files to Create** - Code templates (mostly pseudocode, ready to customize)
3. **Files to Modify** - Integration points in existing code
4. **API Keys** - How to get them (5-10 min per API)
5. **Tests** - What to verify
6. **Time Breakdown** - Realistic hours per task

---

## Recommended Implementation Order

### Week 1: Images (Highest ROI)
- Unsplash + Pexels + Wikimedia for free photos
- Graceful fallback to DALL-E
- **Impact**: Owl article gets real wing photos instead of gradient

### Week 2: Citations (Easiest)
- CrossRef API looks up DOIs
- Auto-link citations to papers
- **Impact**: Academic credibility boost

### Week 3-4: Illustrations (Most Creative)
- SVG templates for common concepts
- Mermaid diagrams for flows
- **Impact**: Complex concepts become visual

---

## Before You Start

### Decisions I Made (So You Don't Have To)

❌ **NOT** creating new generator route  
✅ Using conditional logic in existing `generate.py` instead (simpler, easier to test)

❌ **NOT** using deterministic rules for image queries  
✅ Using **gpt-3.5-turbo** to generate platform-specific search queries ($0.0005 per article)

❌ **NOT** requiring authentication for APIs  
✅ All APIs are free or free-tier (Wikimedia, CrossRef, Unsplash all require no auth)

✅ **Feature flags** for all components (graceful degradation if APIs fail)

✅ **Caching** for citations (30-day TTL, prevents duplicate lookups)

✅ **Budget gating** for illustrations (won't generate DALL-E unless budget allows)

---

## Files You'll Be Creating

### New Directories
```
src/images/
  __init__.py
  selector.py
  sources/
    unsplash.py
    public_domain.py
    ai_generated.py

src/citations/
  __init__.py
  extractor.py
  resolver.py
  formatter.py
  cache.py

src/illustrations/
  __init__.py
  concepts.py
  library.py
  generator.py
  svg_templates/
    aerodynamics_diagram.svg
    lifecycle_cycle.svg
    [3 more SVG files]
```

### Files You'll Modify
```
src/config.py               (add ~30 lines)
src/generate.py             (add ~50 lines)
src/models.py               (add ~10 lines)
.env.example                (add ~12 lines)
```

### New Data Files
```
data/citations_cache.json   (auto-generated)
```

---

## Quick Reference: APIs

| API | Cost | Auth | Rate Limit | Use |
|-----|------|------|-----------|-----|
| Unsplash | Free | API key | 50/hr | Stock photos |
| Pexels | Free | API key | Unlimited | Stock photos |
| Wikimedia | Free | None | 200/sec | Public domain |
| CrossRef | Free | None | Unlimited | Citation lookup |
| arXiv | Free | None | Unlimited | Preprint lookup |
| DALL-E 3 | $0.020/img | OpenAI key | 100/min | Fallback images |

---

## Development Checklist

**Setup** (30 min)
- [ ] Get Unsplash API key: https://unsplash.com/developers
- [ ] Get Pexels API key: https://www.pexels.com/api
- [ ] Add to `.env.example` and `.env.development`

**Feature 1: Images** (3-4 hrs)
- [ ] Create `src/images/` directory and files
- [ ] Write tests for multi-source fallback
- [ ] Integrate into `generate.py`
- [ ] Test with owl article

**Feature 2: Citations** (2-3 hrs)
- [ ] Create `src/citations/` directory and files
- [ ] Write tests for citation extraction
- [ ] Test CrossRef lookup
- [ ] Verify caching works

**Feature 3: Illustrations** (4-5 hrs)
- [ ] Create 5 SVG templates (or use existing free SVGs)
- [ ] Create `src/illustrations/` directory and files
- [ ] Write concept detection tests
- [ ] Integrate into `generate.py`

**Integration & Testing** (2-3 hrs)
- [ ] Run full test suite
- [ ] Verify all costs are tracked
- [ ] Test graceful fallbacks when APIs fail
- [ ] Document in README

---

## Cost Comparison

### Current Approach
- All images via DALL-E: **$0.020 per article**
- No citations: $0.00
- No illustrations: $0.00
- **Total: $0.020/article**

### After Implementation
- Images: Free (Unsplash) + $0.020 fallback (rare) = **~$0.001/article**
- Citations: Free (CrossRef) = **$0.00**
- Illustrations: Free (SVG) + $0.020 fallback (optional, gated) = **~$0.005/article**
- **Total: $0.006/article (70% savings)**

---

## Getting Help

Each feature guide includes:
- ✅ Complete code templates
- ✅ File paths and structure
- ✅ Integration points
- ✅ Test cases
- ✅ Realistic time estimates

Read them in order:
1. `FEATURE-1-IMAGES.md` - Start here, highest impact
2. `FEATURE-2-CITATIONS.md` - Quick win
3. `FEATURE-3-ILLUSTRATIONS.md` - Most fun/creative

Questions? Refer to:
- `IMPLEMENTATION-STRATEGY-SCIENTIFIC-ARTICLES.md` - Detailed design decisions
- `ADR-005-SCIENTIFIC-ARTICLE-IMPROVEMENTS.md` - Original proposals (archived)

---

## Next Steps

**Read This First**: `FEATURE-1-IMAGES.md`  
It has everything you need to get started: code templates, API setup, tests, and integration points.

**Estimated Timeline**:
- Days 1-2: Images (highest ROI, visible impact)
- Days 3-4: Citations (quick, builds credibility)
- Days 5-8: Illustrations (creative, most code)
- Day 9: Testing & documentation

**Ready?** Open `FEATURE-1-IMAGES.md` →

