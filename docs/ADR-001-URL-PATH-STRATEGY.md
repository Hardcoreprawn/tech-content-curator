# ADR-001: URL Path Strategy for GitHub Pages Subdirectory Deployment

**Status:** Accepted  
**Date:** 2025-10-31  
**Context:** Deployment to GitHub Pages under a project subdirectory (`/tech-content-curator/`)

## Problem

The site is deployed to `https://hardcoreprawn.github.io/tech-content-curator/`, a subdirectory of the domain. This creates URL path complexity:

- **baseURL** is `https://hardcoreprawn.github.io/tech-content-curator/`
- All links must work within this subdirectory context
- Menu links, images, and assets all need correct path handling

Initial configuration attempted to use `canonifyURLs = true` with absolute paths like `/tech-content-curator/posts/`, which caused double-path issues: `/tech-content-curator/tech-content-curator/posts/`

## Decision

**Use relative paths in configuration with `canonifyURLs = false`**

### Configuration

- **`canonifyURLs = false`** - Disable automatic URL canonification
- **Menu URLs:** Use simple relative paths (`/posts/`, `/about/`, `/search/`, `/tags/`)
- **Static assets:** Use baseURL-prefixed paths (`/tech-content-curator/images/default-social.png`)
- **RSS/feeds:** Use baseURL-prefixed paths (`/index.xml` for home, will be resolved relative to baseURL)

### Example: hugo.toml

```toml
baseURL = "https://hardcoreprawn.github.io/tech-content-curator/"
canonifyURLs = false

[menu]
  [[menu.main]]
    url = "/posts/"      # Not /tech-content-curator/posts/
    
[params]
  images = ["/tech-content-curator/images/default-social.png"]  # Full path for static files
```

## Rationale

1. **Hugo handles baseURL automatically** - When `canonifyURLs = false`, Hugo preserves relative URLs and the browser resolves them correctly against the baseURL
2. **Prevents double paths** - Simple relative paths avoid concatenation issues
3. **Static assets need full paths** - Images in `site/static/` need the full `/tech-content-curator/` prefix because they're not processed by Hugo's URL handling
4. **Cleaner maintenance** - Simple paths are easier to understand and less error-prone

## Consequences

- ✅ All menu links work correctly
- ✅ Navigation never returns 404
- ✅ Images and assets load properly
- ✅ Easy to migrate to root domain (just change baseURL)
- ⚠️ Must remember to prefix static asset paths with `/tech-content-curator/`
- ⚠️ Cannot use `canonifyURLs = true` without reverting menu URLs

## References

- [Hugo Documentation: baseURL](https://gohugo.io/getting-started/configuration/#baseurl)
- [Hugo Documentation: canonifyURLs](https://gohugo.io/getting-started/configuration/#canonifyurls)
- Related issues resolved:
  - Search page 404
  - About page 404
  - Menu navigation 404 errors

## Migration Path

If moving from GitHub Pages subdirectory to root domain:
1. Change `baseURL = "https://hardcoreprawn.github.io/"`
2. Update static asset paths: `/tech-content-curator/images/` → `/images/`
3. No changes needed to menu URLs (they already use relative paths)

---

**Approved by:** Tech Content Curator Team  
**Last updated:** 2025-10-31
