# PaperMod Theme Customization Guide

This document explains the proper way to customize the PaperMod theme in this Hugo project.

## Understanding the Hugo Asset Pipeline

PaperMod uses Hugo's asset pipeline to load CSS in a specific order:

1. **Theme variables** (`theme-vars.css`) - CSS custom properties (--main-width, --nav-width, etc.)
2. **Reset and core styles** (`reset.css`, common CSS)
3. **Component styles** (post-single, post-entry, header, footer, etc.)
4. **Extended overrides** - Your custom CSS files from `assets/css/extended/`

See: `site/themes/PaperMod/layouts/partials/head.html` line 64

## Directory Structure

```
site/
├── assets/
│   └── css/
│       └── extended/              ← Place custom CSS here
│           ├── theme-overrides.css    (theme variables)
│           └── post-entry-override.css (component overrides)
├── themes/
│   └── PaperMod/
│       ├── assets/css/
│       │   └── core/
│       │       ├── theme-vars.css     (DEFAULT variables)
│       │       └── zmedia.css         (responsive breakpoints)
│       └── layouts/partials/
│           └── head.html              (CSS loading order)
└── hugo.toml
```

## How to Override PaperMod

### 1. Override Theme Variables

Create or edit `assets/css/extended/theme-overrides.css`:

```css
/* PaperMod Theme Variable Overrides */
:root {
    --main-width: 1024px;      /* Article content width */
    --nav-width: 1024px;       /* Header navigation width */
    --gap: 24px;               /* Spacing/padding */
}
```

**Why this works:**
- Files in `assets/css/extended/` are loaded AFTER PaperMod's core CSS
- The `:root` selector overrides the CSS custom properties globally
- All components that use these variables automatically adopt the new values

### 2. Override Component Styles

Create or edit `assets/css/extended/post-entry-override.css`:

```css
/* Component-specific overrides */
.first-entry {
    min-height: auto !important;
    justify-content: flex-start !important;
}

@media screen and (max-width: 768px) {
    .first-entry {
        min-height: auto !important;
    }
}
```

**Why use `!important`:**
- PaperMod's component CSS has high specificity
- `!important` ensures your overrides take precedence
- Use sparingly and only when necessary

## Available PaperMod Theme Variables

See `site/themes/PaperMod/assets/css/core/theme-vars.css` for the complete list:

| Variable | Default | Purpose |
|----------|---------|---------|
| `--gap` | 24px | General spacing and padding |
| `--content-gap` | 20px | Spacing between content elements |
| `--nav-width` | 1024px | Header navigation width |
| `--main-width` | 720px | Article content max-width |
| `--header-height` | 60px | Header bar height |
| `--footer-height` | 60px | Footer bar height |
| `--radius` | 8px | Border radius |

### Colors (Light Mode)
- `--theme` - Page background
- `--entry` - Post/entry card background
- `--primary` - Main text color
- `--secondary` - Secondary text color
- `--tertiary` - Tertiary elements
- `--content` - Content text color
- `--code-block-bg` - Code block background
- `--code-bg` - Inline code background
- `--border` - Border color

### Dark Mode
The same variables are redefined in `:root[data-theme="dark"]` for dark mode colors.

## Common Customizations

### Align Content Width with Header

**Problem:** Articles are narrower than the header/navigation

**Solution:** In `assets/css/extended/theme-overrides.css`:
```css
:root {
    --main-width: 1024px;  /* Match --nav-width */
}
```

### Increase Article Width

**Solution:** In `assets/css/extended/theme-overrides.css`:
```css
:root {
    --main-width: 900px;   /* Default is 720px */
}
```

### Adjust Overall Spacing

**Solution:** In `assets/css/extended/theme-overrides.css`:
```css
:root {
    --gap: 32px;           /* Default is 24px */
}
```

### Change Code Block Colors

**Solution:** In `assets/css/extended/theme-overrides.css`:
```css
:root {
    --code-block-bg: rgb(40, 44, 52);
    --code-bg: rgb(250, 250, 250);
}

:root[data-theme="dark"] {
    --code-block-bg: rgb(50, 55, 65);
    --code-bg: rgb(60, 65, 75);
}
```

## Responsive Breakpoints

PaperMod defines breakpoints in `site/themes/PaperMod/assets/css/core/zmedia.css`:

```css
@media screen and (max-width: 768px) {
    /* Tablet/mobile styles */
}

@media screen and (max-width: 900px) {
    /* Medium screens */
}

@media screen and (max-width: 340px) {
    /* Very small screens */
}
```

When overriding component styles, match these breakpoints for consistency.

## Best Practices

1. **Use theme variables first** - Override `--main-width` instead of rewriting `.main` styles
2. **Keep overrides in `assets/css/extended/`** - Never modify theme files directly
3. **Use separate files by purpose** - `theme-overrides.css` for variables, `post-entry-override.css` for components
4. **Document why you're overriding** - Add comments explaining the customization
5. **Use `!important` sparingly** - Only when PaperMod's specificity prevents your override
6. **Test in both light and dark modes** - PaperMod has separate color variables for each
7. **Check responsive behavior** - Test at 768px, 900px, and mobile breakpoints

## Debugging

### Check loaded CSS

In browser DevTools:
1. Open Inspector
2. Go to "Computed" tab for an element
3. Look for `var(--main-width)` or other variables
4. Click to see which file set the value

### Verify files are loading

Check Hugo's build output:
```bash
cd site
hugo --verbose
```

Look for lines like:
```
Total in 1234 ms
css/extended/theme-overrides.css: 456 bytes
```

### Force rebuild

```bash
cd site
rm -rf resources/
hugo
```

## File Naming Convention

- `theme-overrides.css` - CSS custom properties (variables)
- `*-override.css` - Component-specific styles
- Keep filenames clear about what they customize

## References

- **PaperMod Documentation:** https://adityatelange.github.io/hugo-PaperMod/
- **Hugo Asset Pipeline:** https://gohugo.io/hugo-pipes/
- **CSS Custom Properties:** https://developer.mozilla.org/en-US/docs/Web/CSS/--*

---

**Last Updated:** November 6, 2025  
**For:** PaperMod Theme Customization  
**Hugo Version:** Latest (with asset pipeline support)
