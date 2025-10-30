# Visibility & Growth Guide

This guide summarizes how to make the site discoverable and grow organic traffic.

## 1) Make the site indexable

- Robots & sitemap: Enabled in `site/hugo.toml`.
  - robots.txt: https://hardcoreprawn.github.io/tech-content-curator/robots.txt
  - sitemap: https://hardcoreprawn.github.io/tech-content-curator/sitemap.xml
- Post‑deploy sitemap ping: Bing notified automatically by the pipeline.

## 2) Verify ownership (faster indexing & insights)

1. Google Search Console
   - Add property: `https://hardcoreprawn.github.io/tech-content-curator/`
   - Choose HTML tag verification → copy token → set in `site/hugo.toml`:
     - `[params] google_site_verification = "<paste>"`
   - Submit sitemap: `/sitemap.xml`
2. Bing Webmaster Tools
   - Add site and set token:
     - `[params] bing_site_verification = "<paste>"`
   - Submit sitemap: `/sitemap.xml`

## 3) Analytics (measure what works)

- GA4: Add your measurement ID in `site/hugo.toml`:
  - `[services.googleAnalytics] ID = "G-XXXXXXXXXX"`
- Optional: Plausible/Umami for privacy‑friendly analytics (see below).

## 4) Social previews & metadata

- Default share image: add `site/static/images/default-social.png` (1200×630).
- Per‑post images are preferred and will override the default.
- Head tags (OpenGraph, Twitter Cards, JSON‑LD) are added via `site/layouts/partials/extend_head.html`.

## 5) Distribution flywheel

- Cross‑post summaries with canonical link (Dev.to, Medium, Hashnode).
- Share to relevant communities (HN Show/Tell when appropriate, subreddits that allow articles, Mastodon/Bluesky/Twitter with 1–2 key takeaways + link).
- Add site & RSS wherever relevant:
  - Repo About section, GitHub profile, community bios.
  - Submit RSS to aggregators (Feedly, Daily.dev via RSS, Flipboard).

## 6) On‑site signals that help ranking

- Internal links: 2–3 related links near the end of each article.
- Tags/categories: add 3–5 accurate tags per post.
- Consistent cadence: your pipeline already enables this.

## 7) Optional enhancements we can add quickly

- BlogPosting JSON‑LD per post (rich snippets; can be added to head partial).
- Related posts block using Hugo related content.
- Plausible analytics hook (no cookies, fast).
- Add live site/RSS shortcuts to README for quick discovery.

## How to request changes

- Share your Google/Bing verification tokens and GA4 ID and we’ll configure and deploy.
- If you want Plausible, send your domain and I’ll wire it up.
