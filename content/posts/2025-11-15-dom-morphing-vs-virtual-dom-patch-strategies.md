---
action_run_id: '19396630207'
article_quality:
  dimensions:
    citations: 0.0
    code_examples: 0.0
    length: 100.0
    readability: 77.9
    source_citation: 100.0
    structure: 80.0
    tone: 100.0
  overall_score: 60.5
  passed_threshold: false
cover:
  alt: ''
  image: ''
  image_source: pexels
  photographer: Markus Spiske
  photographer_url: https://www.pexels.com/@markusspiske
date: 2025-11-15T22:47:33+0000
generation_costs:
  content_generation:
  - 0.0022248
  image_generation:
  - 0.0
  title_generation:
  - 0.00090765
generator: General Article Generator
icon: ''
illustrations_count: 0
models_used:
  content: gpt-5-mini
  enrichment: gpt-5-nano
  title: gpt-5-nano
reading_time: 7 min read
sources:
- author: joeldrapper
  platform: hackernews
  quality_score: 0.65
  url: https://joel.drapper.me/p/morphlex/
summary: Joel Draper recently shared a Show HN post announcing "a better DOM morphing
  algorithm" (Draper, 2025).
tags:
- javascript
- web development
- dom manipulation
- diffing algorithm
- ui rendering
title: 'DOM Morphing vs Virtual DOM: Patch Strategies'
word_count: 1449
---

> **Attribution:** This article was based on content by **@joeldrapper** on **hackernews**.  
> Original: https://joel.drapper.me/p/morphlex/

## Introduction

A compact JavaScript function that updates the browser DOM with the minimum possible work sounds like developer candy. Joel Draper recently shared a Show HN post announcing "a better DOM morphing algorithm" (Draper, 2025). That claim raises practical questions for anyone building interactive web UIs: how do new morphing strategies compare to virtual-DOM reconciliation or established morphers? What invariants must a correct patcher preserve? And when is it worth swapping your renderer?

This article unpacks DOM morphing ideas, explains why they matter for performance and correctness, and walks through concrete use cases, benchmarking advice, and integration notes. I credit Joel Draper’s post for prompting this exploration — see his write-up at https://joel.drapper.me/p/morphlex/ for the original implementation and tests.

> Background: The DOM (Document Object Model) is a live tree of browser objects; virtual DOMs are in-memory representations used to compute changes before applying them to the live DOM.

Key Takeaways

- DOM morphing aims to reduce actual DOM mutations, preserving state like focus and event handlers while minimizing reflows and paints.
- Keyed diffing and edit-distance approaches shape correctness and move-minimization. The longest-increasing-subsequence (LIS) trick is a common optimization for reorders.
- Preserve inputs, focus, and event bindings; benchmark using realistic workloads and frame-time metrics rather than microbenchmarks alone.
- Choose morphing when you need low-overhead updates to existing DOM (e.g., form-heavy apps, incremental hydration). Virtual-DOM still wins for complex component graphs and predictable abstractions.

## Background

Browsers expose a live DOM tree via APIs like `document.createElement`, `node.appendChild`, `node.replaceChild`, and `element.setAttribute`. Mutating the DOM can trigger layout (reflow) and paint phases. These phases are expensive: frequent or poorly ordered DOM writes cause layout thrashing and drop frame rates.

Virtual DOMs (used by React and others) keep an in-memory tree and generate a diff (patch set) between renders; the runtime applies the minimal set of mutations the reconcilation algorithm computes (React, 2013). Direct DOM morphers skip the immutable virtual tree and instead compute and apply updates by walking both old and new DOM fragments. Incremental approaches like Google’s Incremental DOM generate updates by running template functions that call DOM APIs directly (Google, 2016). Compile-time frameworks such as Svelte produce update code at build time to avoid per-frame diffing (Harris, 2019).

A core question is trade-offs: virtual-DOM provides a clear mental model and predictable lifecycle, while direct morphers can avoid extra allocations and sometimes fewer DOM operations. Both face the same correctness constraints: inputs must keep their values, focus and selection must not be lost needlessly, and event handlers should remain attached unless an element is intentionally replaced.

## Main Content

What does a "better" morph algorithm aim to improve?

1. Fewer DOM mutations

   - Each `appendChild`, `removeChild`, `setAttribute`, or text replacement can cause layout/paint work.
   - A morphing algorithm seeks to reuse existing nodes when possible and only apply necessary attribute/text changes.

1. Correctness invariants

   - Preserve input `value`, caret position, selection, and focus.
   - Keep attached event listeners when nodes are conceptually the same.
   - Avoid breaking external references (libraries that hold DOM handles).

1. Efficient reordering and keyed updates

   - Keyed children let the algorithm identify the same logical items across updates.
   - For many frameworks, the standard trick is to map keys to indices, detect moved items, and minimize node moves via Longest Increasing Subsequence (LIS) on indices (this avoids unnecessary DOM insertions).

1. Low memory and CPU overhead

   - Virtual DOMs allocate data structures each render. Morphers aim to avoid extra allocations while still being fast enough in JS.

Algorithmic building blocks

- Sequence diffing: Myers’ diff algorithm (Myers, 1986) finds a minimal edit script between sequences. It’s robust but O(ND) in complexity, and heavier than heuristics used in practice.
- Heuristic two-pointer scans: Many morphers walk start and end pointers and only do expensive checks when keys or tags mismatch.
- Key maps + LIS: Map keys from new list to their positions in old list, then compute LIS to find elements that can stay put. Non-LIS nodes are moved.

Handling attributes and text

- Compare attributes and text node values directly and only call `setAttribute` or replace text when the value differs.
- For boolean attributes, follow DOM semantics (`checked`, `selected`).

Preserving focus and inputs

- Before replacing an element, check if it is the document.activeElement (i.e., focused). If so, either reuse the node or restore focus and caret after the replacement.
- For `<input>` and `<textarea>`, copy `value` to the new node if replacing is unavoidable.

Event listener considerations

- If you attach listeners via DOM methods (`addEventListener`), keeping the same node preserves handlers. If you use delegation, handlers remain unaffected by node replacements.
- Some morphers use a policy: "reuse when tagName and key match" — events persist in that case.

Edge cases

- Shadow DOM and slots: Morphers must respect shadow boundaries; patching across a shadow root is not allowed.
- Dynamic attributes with side effects (like `autofocus`) need careful handling.
- Detached nodes (elements held by other code) can lead to conflicts; a safe morpher should avoid mutating nodes it doesn’t own.

## Examples/Applications

1. Live chat feed (keyed list)

   - Problem: Frequent appends and occasional reorders when messages are edited.
   - Approach: Use unique message IDs as keys. The morpher maps old-to-new indices and uses LIS to keep most nodes in place. This minimizes DOM insert/remove operations and maintains scroll position and event bindings.

1. Complex forms with user focus

   - Problem: An autosave or partial re-render replaces form markup, losing cursor position.
   - Approach: Morph rather than replace form fields. If replacement is needed, copy `value`, `selectionStart`, and `selectionEnd`, and restore focus with `element.focus()` and caret offsets.

1. Dashboard with many widgets (large trees)

   - Problem: Updates touch isolated subtrees; full re-render causes expensive repaints.
   - Approach: Scope morphing to changed subtrees. Use shallow checks on high-level nodes and full morphs only where necessary. Combine with requestAnimationFrame batching to avoid jank.

Small illustrative snippet (conceptual)
`// conceptual morph: preserve keyed elements by reusing matching nodes`
`morph(oldParent, newFragment) {`
`  // map keys from oldChildren -> index`
`  // map keys from newChildren -> index`
`  // compute LIS to identify nodes to keep in place`
`  // move or insert nodes as needed`
`  // diff attributes and text for reused nodes`
`}`

## Best Practices

- Use stable keys for list items. Keys are the single most important factor for efficient diffs.
- Prefer delegation for event handlers when possible; it reduces reliance on node reuse for listener preservation.
- Avoid innerHTML for incremental updates; it usually replaces subtrees wholesale and loses state.
- Benchmark with realistic scenarios: user interactions, frequent small updates, and large-tree updates. Measure frame times (FPS), main-thread time, layout counts, and total DOM mutations.
- Use requestAnimationFrame and microtask batching to group DOM writes and avoid layout thrashing.

Benchmarking advice

- Synthetic tests help isolate algorithmic behavior, but real-app traces show actual bottlenecks.
- Track not just operation counts but layout and paint costs in DevTools Performance tab.
- Compare memory pressure across runs to check for GC spikes.

## Implications

If Joel Draper’s algorithm indeed reduces unnecessary moves and avoids breaking invariants, it could be a practical win for apps that need low-overhead, state-preserving updates. Direct morphers are particularly attractive for progressive enhancement, hydration after server-rendering, and legacy apps where migrating to a component framework is impractical.

Yet there are trade-offs. Virtual-DOM solutions often give predictable lifecycle hooks and a developer ergonomics advantage. Compile-time approaches (Svelte) remove this runtime cost but impose compile constraints. The best choice depends on your app shape: interactive forms and in-place updates favor morphers, while complex component graphs still map well to virtual-DOM patterns.

## Conclusion

DOM morphing is a mature space with many sensible design points: minimize DOM mutations, preserve user state, and use keys to detect sameness. New algorithms — like the one Joel Draper shared — push the envelope on reducing moves and preserving correctness. If you maintain a high-interaction UI (forms, chats, dashboards), experimenting with a lightweight morpher can produce meaningful frame-time wins.

When evaluating any new morphing library:

- Check how it handles keys, focus, and inputs.
- Run both synthetic and real-world benchmarks.
- Verify behavior with Shadow DOM, server-side hydration, and event handling strategies.

References and further reading

- Myers, E. W. (1986). An O(ND) Difference Algorithm and Its Variations.
- React documentation (Facebook, 2013) — reconciliation and virtual DOM concepts.
- Incremental DOM (Google, 2016) — direct DOM update approach.
- Harris, R. (Svelte, 2019) — compile-time UI approach.
- MDN Web Docs — DOM APIs and rendering lifecycle.

Original source: Joel Draper, "Show HN: I made a better DOM morphing algorithm" — https://joel.drapper.me/p/morphlex/ (Show HN post).


## References

- [Show HN: I made a better DOM morphing algorithm](https://joel.drapper.me/p/morphlex/) — @joeldrapper on hackernews