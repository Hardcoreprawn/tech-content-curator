# Roadmap: Sustainable Cash Flow (AI-First, Ethical)

**Date:** 2026-01-15  
**Goal:** Reach sustainable cost recovery without compromising ethics or usability.

---

## Executive Summary (Critical View)

Traffic is constrained more by **content trust + distribution** than hosting. GitHub Pages is not a blocker for SEO or traction. The highest-impact fixes are:
1) **Trust signals:** grounded sources, stable references, no unverifiable claims.
2) **Distribution:** consistent digest + social posting + backlinks.
3) **Quality over volume:** fewer, stronger posts.

---

## Prioritized Next Steps (Cost Recovery Focus)

1) **Trust + tone first**
   - Grounding-first citations ([#9](https://github.com/Hardcoreprawn/tech-content-curator/issues/9))
   - Remove source-post referential language ([#19](https://github.com/Hardcoreprawn/tech-content-curator/issues/19))
   - Enforce “no unverifiable claims” in prompts

2) **Image stability + social previews**
   - Persist cover images locally ([#14](https://github.com/Hardcoreprawn/tech-content-curator/issues/14))
   - Avoid unstable/animated hotlinks ([#20](https://github.com/Hardcoreprawn/tech-content-curator/issues/20))
   - Ensure frontmatter includes `images` for social cards

3) **Distribution engine**
   - Weekly digest + social summaries (Phase 2)
   - Targeted backlink attempts for highest-quality posts

4) **Quality gating**
   - Skip items without resolvable source URLs
   - Lower throughput, higher average quality

5) **Cost/throughput optimization (from OPTIMIZATION.md)**
   - Concurrent collection + enrichment with rate-limit safe backoff
   - Progressive image generation (top-N only)
   - Cache Hugo build + uv deps
   - Batch API option for 50% cost savings (longer latency)
   - Smarter scheduling based on trend activity

6) **Measurement loop**
   - Track CTR and time-on-page by post
   - Track runtime + cost per article
   - Publish 5–10 improved posts before re-evaluating

7) **Monetization (lightweight)**
   - Add one clearly labeled sponsor slot
   - Add support CTA in nav/footer

---

## Current Risks & Constraints

### Known GitHub Issues (recent)
- Branch protection blocked pushes → **resolved by removing required PR reviews** (personal repo limitation).
- CI failure: cover fallback changed → **tests updated**.
- Broken images risk → **image guard now clears external/broken covers** before commit.

### Artifact Quality
- External covers dominate (Unsplash), which is fragile.
- References often lack URLs (weak E-E-A-T, poor trust).
- Some content contains “I did X” claims without evidence (credibility risk).

### Performance/Cost Considerations (from OPTIMIZATION.md)
- Parallel generation is already in place.
- Additional speed gains exist, but content quality is the bigger ROI right now.

---

## Strategy: Ethical Monetization Without UX Harm

**Primary (low-risk):**
- 1 **sponsor slot** per week (clearly labeled, fixed placement).
- “**Support this project**” (GitHub Sponsors / Buy Me a Coffee).
- Small **newsletter sponsor** placement.

**Secondary (opt-in):**
- Affiliate links only for tools used by the project (explicit disclosure).
- Optional paid “**Weekly Research Digest**” (curated, grounded, minimal AI fluff).

**Avoid:** intrusive ads, autoplay, popups, tracking-heavy networks.

---

## Roadmap Phases

### Phase 0 — Stabilize Output (1–3 days)
**Goal:** Stop trust leaks and broken previews.
- ✅ Image guard clears external/broken covers before commit.
- ✅ **Add frontmatter `images`** using `cover.image` to fix social previews.
- ✅ **Remove unverifiable “I did X” language** from prompts.
- ✅ Enforce references with URLs or remove the References section.
- ✅ Cache uv dependencies in CI to cut pipeline time.

**Deliverables**
- ✅ Metadata parity: `images`, `description`, `summary`.
- ✅ Template change: avoid pseudo-lab claims.
- ✅ CI cache for uv deps.

---

### Phase 1 — Raise Content Trust (1 week)
**Goal:** Make posts defensible, citable, and shareable.
- ✅ Ground sources: require URLs + quotes or snippets.
- ✅ Add editorial policy + methodology page (E-E-A-T).
- ⏳ Reduce volume: fewer posts, higher quality threshold.
- ✅ Add concurrent collection (async) to reduce collection time.

**Deliverables**
- ✅ New “Methodology” page.
- ✅ Quality gate: reject items without usable source URLs.
- ✅ Parallel collection across sources.

---

### Phase 2 — Distribution Engine (1–2 weeks)
**Goal:** Make good content discoverable.
- ✅ Weekly digest (email + RSS summary).
- ✅ Social posting automation with short summaries.
- Backlink strategy: targeted HN/Reddit posts for strongest pieces.
- ✅ Incremental Hugo builds (cache `site/resources/_gen`).

**Deliverables**
- ✅ Digest generator from last 7 days.
- ✅ Posting cadence + summary templates.
- ✅ Cached Hugo build artifacts.

---

### Phase 3 — Monetization (2–4 weeks)
**Goal:** Cover costs ethically with minimal disruption.
- Add sponsor slot in homepage + post footer (one slot only).
- Add support CTA in nav.
- Optional: “Research Digest” paid tier.
- Parallel enrichment with rate limiting.
- Progressive image generation for top-N articles.
- Smart scheduling based on trending activity.
- Batch API option for 50% cost savings (long-latency runs).

**Deliverables**
- Sponsor component (clearly labeled).
- Support page (transparent costs + mission).
- Enrichment parallelism + rate-limit controls.
- Progressive image generation gate.
- Schedule tuning + optional batch pipeline.

---

## Prompt Overhaul (Extreme Suggestions)

### 1) Dynamic Structure
- Replace fixed templates with **structure pools** (5–8 variants per content type).
- Randomized section ordering within safety rules.

### 2) Grounded Evidence Mode
- Require **2–4 concrete quotes/snippets** from source URLs.
- If not available, **downgrade or skip** the article.

### 3) Tone Modulation
- Add “voice constraints” per topic (e.g., technical vs narrative).
- Mix long-form, short “Field Notes,” and “Explainer” formats.

### 4) Stance & Value
- Force a clear takeaway: “what to do next.”
- Add **“Why this matters to working devs”** section for practical value.

### 5) Clarity Filter
- Ban phrases like “I inspected” / “I benchmarked” unless actual logs exist.

---

## What to Build Next (Concrete Tasks)

1) **Frontmatter enrichment**
   - Set `images` to `cover.image` and `description` from summary.

2) **Prompt rewrite**
   - Remove unverifiable claims.
   - Add evidence requirements.

3) **Quality gating**
   - Skip items lacking resolvable source URLs.

4) **Digest generator**
   - Weekly summary + links.

---

## Success Metrics

- CTR improvement from social previews (target +25%).
- Lower bounce rate (target -20%).
- 2–3 sponsor inquiries/month within 60 days.
- Cost recovery by month 2–3.

---

## Decision Log

- Hosting: **stay on GitHub Pages** for now; SEO not blocked.
- Focus: **content trust + distribution** over site migration.

---

## Next Action (Proposed)

Implement frontmatter `images` + prompt updates first, then validate by publishing 5–10 improved posts and tracking CTR and time on page.
