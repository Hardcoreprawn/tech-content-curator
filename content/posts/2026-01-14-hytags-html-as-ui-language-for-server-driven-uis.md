---
action_run_id: '21004859336'
article_quality:
  dimensions:
    citations: 75.0
    code_examples: 100.0
    length: 100.0
    readability: 59.9
    source_citation: 100.0
    structure: 80.0
    tone: 100.0
  overall_score: 82.2
  passed_threshold: true
cover:
  alt: ''
  image: ''
  image_source: unsplash
  photographer: Ferenc Almasi
  photographer_url: https://unsplash.com/@flowforfrank
date: 2026-01-14T18:16:44+0000
generation_costs:
  content_generation:
  - 0.0022725
  image_generation:
  - 0.0
  title_generation:
  - 0.00077264
generator: General Article Generator
icon: ''
illustrations_count: 0
models_used:
  content: gpt-5-mini
  enrichment: gpt-5-nano
  title: gpt-5-nano
reading_time: 7 min read
sources:
- author: lassejansen
  platform: hackernews
  quality_score: 0.65
  url: https://hytags.org/
summary: That is the premise behind HyTags, a compact language that embeds control
  flow, functions, and asynchronous handling directly into HTML via custom tags.
tags:
- swift
- html
- web development
- asynchronous programming
- templating
title: 'HyTags: HTML-as-UI-Language for Server-Driven UIs'
word_count: 1464
---

> **Attribution:** This article was based on content by **@lassejansen** on **hackernews**.  
> Original: https://hytags.org/

## Introduction

What if HTML itself could be a programming language for building interactive web UIs? That is the premise behind HyTags, a compact language that embeds control flow, functions, and asynchronous handling directly into HTML via custom tags. Originally conceived as a way to write full‑stack apps in Swift without a separate frontend, HyTags has evolved into a backend‑agnostic approach: servers that can emit HTML—via templates or domain‑specific languages (DSLs)—can produce HyTags pages that run in the browser or in a hybrid runtime (source: Hacker News post by @lassejansen; https://hytags.org/).

This article explains the idea, situates it among server‑driven UI and templating patterns, shows practical use cases, and outlines tradeoffs and migration paths for teams considering HyTags or similar HTML‑centric DSLs.

Key Takeaways

- HyTags treats HTML as a host for programming constructs, embedding logic in custom tags to express control flow, functions, and async behavior.
- It follows a server‑generated UI / server‑driven UI philosophy: any backend that can output HTML can produce HyTags pages, reducing the need for a separate JavaScript frontend.
- Major tradeoffs include tooling and type support, debugging ergonomics, and careful attention to performance, security (XSS), accessibility, and SEO.
- HyTags is most compelling for teams that prefer server templating workflows, want minimal client JavaScript, or are adopting server‑centric full‑stack languages (e.g., Swift on the backend).
- Before adopting, evaluate state management, testing and observability, integration with existing frameworks, and the community/tooling maturity.

> Background: Server‑side rendering (SSR) is the practice of producing HTML on the server and sending it to the client; client‑side rendering (CSR) runs UI logic in the browser.

## Background

HTML (HyperText Markup Language) is a markup language used to structure web pages. Traditionally, markup describes structure and presentation, while imperative or declarative UI logic lives in other layers: server templates (e.g., Jinja2, ERB) for SSR or JavaScript/TypeScript frameworks (React, Vue, Svelte) for CSR and interactive behavior. A long‑standing design split exists between view templates and application logic; architectural patterns like Model‑View‑Controller (MVC) codified this separation (Reenskaug, 1979).

Embedding domain logic in markup is not new. Templating engines and embedded DSLs have allowed mixing simple control structures and variable interpolation in HTML for decades. HyTags pushes that idea further by making HTML a richer language surface: control flow, function definitions, and async operations are expressed via tags, enabling a minimal runtime that interprets those tags either client‑side, server‑side, or both. The DSL approach follows ideas explored in the DSL literature (Hudak, 1996): small, domain‑specific notations can make expression concise and align with developer intent.

## Main Content

What does "HTML as a programming language" mean in practice? HyTags introduces a set of custom tags—think `<if>`, `<for>`, `<fn>`, `<await>`—that encode program structure into the HTML DOM. The runtime interprets these tags to produce DOM updates, make asynchronous calls, or invoke functions. Crucially, because the syntax is valid HTML, any server that can emit HTML templates can generate HyTags pages without special compilation.

Execution models

- Client‑side runtime: The browser loads a small JavaScript engine that parses HyTags tags and executes logic in the client. This gives interactivity without a large framework and keeps logic decoupled from backend language.
- Server‑side rendering + client activation: The server renders initial HTML (possibly including resolved hyTags constructs) and the client runtime "activates" remaining interactive parts, similar to hydration in React.
- Server‑only execution (progressive enhancement): The server executes HyTags to produce plain HTML and handles interactions via full page reloads or XHR endpoints—no client runtime needed for basic functionality.

State and async handling
HyTags must reconcile mutable UI state with stateless HTTP and asynchronous calls (fetching data, awaiting long operations). Common patterns include:

- Local UI state tracked in the client runtime (small in‑memory store).
- Server roundtrips to persist or compute state, often via fetch/XHR triggered by hyTags event handlers.
- Declarative async tags (e.g., `<await>`) that show loading states and result templates without explicit imperative callbacks.

How HyTags compares to other approaches

- Unlike heavyweight CSR frameworks, HyTags minimizes the client bundle and keeps markup readable and server‑friendly.
- vs classic templates (Handlebars, Jinja2): HyTags adds richer control structures and client side behavior encoded uniformly in HTML rather than splitting template and script files.
- vs Web Components: Web Components define encapsulated UI primitives; HyTags defines a language for flow and behavior, which can complement components.

The theoretical roots of embedding behavior in a host syntax are well studied: DSL design shows that small, focused languages can dramatically improve expressiveness for a domain (Hudak, 1996). And placing logic closer to markup echoes server‑driven UI philosophies, which align the backend’s view over state with the delivered UI (Fielding, 2000).

## Examples/Applications

Example 1 — Interactive counter (conceptual HyTags)

```html
<div>
  <fn name="increment">
    <set state="count" expr="state.count + 1" />
  </fn>

  <button onclick="increment()">Clicked <span>{{ state.count }}</span> times</button>
</div>
```

Use case: Small widgets and admin tools where the UI logic is simple and directly tied to server templates.

Example 2 — Fetching data with a declarative await

```html
<await src="/api/items">
  <loading>Loading items…</loading>
  <then>
    <ul>
      <for each="item in result">
        <li>{{ item.name }}</li>
      </for>
    </ul>
  </then>
  <catch>
    <div class="error">Failed to load</div>
  </catch>
</await>
```

Use case: Dashboards or CMS previews where the server can embed `await` markers and the client runtime handles fetching and showing fallback states.

Example 3 — Server‑generated forms with validation
Generate HyTags markup from a backend (Swift, Ruby, Python) to render forms that perform client validation and submit to server endpoints. This reduces duplication between server validation logic and client UI.

> Background: Hydration refers to the process of attaching client-side behavior to server-rendered HTML, enabling interactivity without re-rendering the entire UI.

## Best Practices

- Keep core business logic on the backend. Use hyTags for UI orchestration and state that lives in the client session.
- Favor declarative constructs for async flows (loading/error states), which improves readability and aligns with progressive enhancement.
- Sanitize any interpolated data on the server to avoid cross‑site scripting (XSS). When the runtime executes expressions, make escaping explicit.
- Modularize: combine HyTags with Web Components or server templates to scope UI pieces and improve reusability.
- Instrument and test: add logging hooks for hyTags runtime events and develop unit tests for server‑generated templates.

## Implications

Performance

- Smaller client bundles can reduce time‑to‑interactive for simple apps. However, a poorly optimized runtime or heavy use of client‑side evaluation can negate gains.
- SSR + progressive activation can preserve SEO and initial render speed while enabling interactivity as needed.

Security

- Any system that evaluates templates or expressions needs strict escaping and content security policies. HyTags increases the surface area for expression evaluation, so standard server‑side protections remain critical.

Tooling and developer ergonomics

- Tooling maturity is a primary constraint. IDE integration, static analysis, type checking, and debuggers are far more advanced in mainstream JS frameworks. Teams should expect to invest in linters, language servers, or compile‑time checks if they rely heavily on hyTags for complex logic.
- Type systems: If your backend is strongly typed (Swift, Rust, TypeScript), map data contracts clearly into the hyTags templates and consider code generation to reduce runtime mismatches.

Accessibility and SEO

- Since HyTags outputs real HTML, it can remain accessible and crawlable if semantic markup and ARIA practices are used. Server rendering of critical content preserves SEO.

Ecosystem maturity

- HyTags is promising for server‑centric workflows, but community size, libraries, and production polish matter. Evaluate the roadmap, maintenance commitment, and whether third‑party integrations are available.

## Conclusion

HyTags is an intriguing take on server‑driven UIs and embedded DSLs: it makes HTML a first‑class surface for expressing control flow, functions, and asynchronous behavior. For teams that prefer server templating, want minimal client JavaScript, or are already invested in languages like Swift on the backend, HyTags offers a succinct way to unify templates and UI logic without a separate frontend stack.

However, adoption requires careful tradeoff analysis: tooling, type safety, debugging, and security must be addressed. For teams evaluating HyTags, start with small widgets or admin UIs, instrument interactions, and iterate on integration with existing backends and CI pipelines.

Credit: This article is based on the Hacker News post by @lassejansen and the HyTags project (https://hytags.org/).

Citations

- [Hudak (1996)](https://doi.org/10.3998/mpub.22829) — foundational discussion of domain‑specific embedded languages and their design.
- Reenskaug (1979) — original articulation of the Model‑View‑Controller (MVC) pattern and separation of concerns in UI design.
- Fielding (2000) — discussion of web architectural constraints and the role of server‑driven representations in web systems.

Further reading and resources

- HyTags project: https://hytags.org/
- For DSL design: Hudak, P. (1996). Building domain-specific embedded languages.
- For web architecture and server-driven approaches: Fielding, R. T. (2000). Architectural Styles and the Design of Network-based Software Architectures.
- For UI architecture history: Reenskaug, T. (1979). The original MVC notes.


## References

- [Show HN: HyTags – HTML as a Programming Language](https://hytags.org/) — @lassejansen on hackernews

- [Hudak (1996)](https://doi.org/10.3998/mpub.22829)