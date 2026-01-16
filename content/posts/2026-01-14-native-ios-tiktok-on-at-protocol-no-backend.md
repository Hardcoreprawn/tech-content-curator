---
action_run_id: '20980350826'
article_quality:
  dimensions:
    citations: 100.0
    code_examples: 0.0
    length: 96.2
    readability: 44.1
    source_citation: 100.0
    structure: 80.0
    tone: 100.0
  overall_score: 66.5
  passed_threshold: false
cover:
  alt: ''
  image: ''
  image_source: unsplash
  photographer: Yohan Marion
  photographer_url: https://unsplash.com/@yohanmarion
date: 2026-01-14T02:47:02+0000
generation_costs:
  content_generation:
  - 0.002619
  image_generation:
  - 0.0
  title_generation:
  - 0.0008324
generator: General Article Generator
icon: ''
illustrations_count: 0
models_used:
  content: gpt-5-mini
  enrichment: gpt-5-nano
  title: gpt-5-nano
reading_time: 9 min read
sources:
- author: sinned
  platform: hackernews
  quality_score: 0.65
  url: https://testflight.apple.com/join/cVxV1W3g
summary: Introduction Can a TikTok-like short-video experience be built without a
  single custom server — purely as a native client on top of an open social protocol.
tags:
- swift
- ios development
- at protocol
- bluesky
- open social protocol
title: Native iOS TikTok on AT Protocol - No Backend
word_count: 1720
---

> **Attribution:** This article was based on content by **@sinned** on **hackernews**.  
> Original: https://testflight.apple.com/join/cVxV1W3g

## Introduction

Can a TikTok-like short-video experience be built without a single custom server — purely as a native client on top of an open social protocol? Microwave, a TestFlight-distributed iOS app by @sinned, attempts exactly that: a Swift-built, native iOS client that reads from and writes to the AT Protocol (often associated with Bluesky) with no bespoke backend. The experiment asks a practical question with broad implications: what user experience, performance, and governance tradeoffs arise when a media-heavy, single-client app runs entirely on top of federated/open infrastructure?

This article walks through how Microwave maps to the AT Protocol model, what technical obstacles arise for video-first UX, and practical patterns for ranking, discovery, caching, and moderation when you have no custom server. I’ll point out architectural risks, concrete examples, and actionable recommendations for engineers exploring client-only apps on open social protocols.

> Background: The AT Protocol (used by Bluesky) models accounts and posts as records in user-owned repos and stores media as blobs that repositories reference.

Key Takeaways

- Building a short-video app as a thin client on AT Protocol is feasible, but UX parity with centralized platforms requires careful tradeoffs in ranking, prefetching, and media delivery.
- Client-only ranking and discovery can work for local personalization and low-latency playback, but global popularity signals and cross-server aggregation remain hard without cooperative services.
- Moderation and policy enforcement are distributed problems: clients can filter or warn, but cross-server takedowns and consistent enforcement need server cooperation or social-graph-based heuristics.
- Video delivery on AT Protocol will usually be progressive download of blobs; adaptive streaming (HLS/DASH) and CDN-backed delivery require extra conventions or server cooperation.
- Design choices should emphasize resilient caching, provenance checks, defensive handling of inconsistent metadata, and explicit UI for trust and moderation.

Credit: This article is based on the Microwave proof-of-concept described on Hacker News by @sinned and on public AT Protocol documentation (Bluesky/AT Protocol).

## Background

The AT Protocol is an open, API-first social protocol designed to let accounts and content exist as addressable records in user repos. Identities are represented by decentralized identifiers (DIDs) and handles are mapped through a handle registry. Media is stored as blobs, uploaded to a hosting server, and then referenced by post records. Unlike siloed platforms, the protocol separates the client from any single provider's ingestion, storage, or ranking services.

ActivityPub (W3C, 2018) is a different federated social standard emphasizing server-to-server federation. AT Protocol takes a more API-centric approach to client semantics and record schemas (AT Protocol / Bluesky, 2023). These design choices make building clients that operate without bespoke backends plausible — but they also surface unique operational challenges.

Citations: ActivityPub (W3C, 2018); AT Protocol / [Bluesky (2023)](https://doi.org/10.59350/tn7kx-3gq89).

## Main Content

### How Microwave maps to AT Protocol primitives

At a high level, Microwave reads timelines and post records from one or more AT Protocol hosts, downloads media blobs referenced by those records, and composes and publishes new posts by uploading blobs and writing new records to the user's repository. The major operations are:

- Authentication: the client obtains credentials for a home server that controls the user's repo (DID-based or token-based flows).
- Read: query remote repos / feeds for records; follow links to blob URLs for media.
- Write: upload video blobs to the user's server, then create a post record that references the blob(s).
- Display: local UI renders videos, with background prefetching and caching.

This is a direct mapping: the app is just a client that uses the protocol’s read/write blob primitives instead of talking to a bespoke API.

### Media delivery and streaming implications

AT Protocol's blob model is general-purpose: a server stores blob bytes and serves them over HTTP(S). That gives flexibility but also constraints for high-throughput video UX:

- No built-in adaptive streaming: AT Protocol blobs are typically served as files. Clients will download progressively unless servers provide HLS/DASH manifests or CDNs do content negotiation. For smooth playback like TikTok, adaptive bitrate (ABR) streaming or at least efficient progressive HTTP with Range requests is important.
- CDN cooperation: performance hinges on whether hosting servers put blobs behind CDNs or return cacheable headers. Without consistent CDN use, clients will see variable latency across homes.
- Caching and prefetch: mobile clients must aggressively cache thumbnails and short video segments, use HTTP cache-control headers, and manage disk space for offline/quick playback.
- Bandwidth costs and privacy: clients may need to transcode or upload multiple sizes to manage network constraints; that increases client CPU/battery usage.

Practical pattern: prefer servers that advertise CDN-backed blob URLs or expose HLS. Implement progressive download with Range support and prefetch next video segments on fast networks.

### Ranking, discovery, and personalization without a backend

Central platforms leverage dedicated backends and global event logs to compute recommendations at scale. In a client-only architecture you have several limited options:

- Client-side ranking: compute a "For You"-style feed using signals available locally — follows, likes the client has seen, and heuristics like recency and engagement seen in fetched records. This is great for responsiveness and privacy but limited in scope.
- Query-based discovery: issue queries to many repositories for popular content, e.g., search or community timeline endpoints. This requires hitting many servers and may be rate-limited.
- Cooperative relays/indexers: third-party indexers (optional, external) can provide aggregated signals without becoming a mandatory backend. Relying on public indexes sacrifices pure client-only guarantees but improves discovery.
- Hybrid: use on-device ML models for personalization (cold-start with explicit onboarding preferences), and optionally fetch aggregated popularity signals from public indices when available.

Recommendation systems literature shows that effective personalization often requires cross-user aggregation and historical signals (Ricci et al., 2015). Expect UX gaps compared with centralized platforms unless you adopt hybrid aggregation or rely on community indexers.

Citation: [Ricci et al. (2015)](https://doi.org/10.1007/978-3-319-14944-8_12).

### Moderation and governance

In a federated model, moderation is split between home servers and client choices:

- Server-side moderation: each home server can apply takedowns, label content, or ban accounts. However, cross-server enforcement is ad hoc and depends on server policies.
- Client-side filtering: Microwave can implement local filters (NSFW blur, blocklists, keyword filters) and UI affordances for reporting. These are immediate, but only affect the local user experience.
- Provenance and signatures: the AT Protocol’s record model makes provenance explicit; clients should surface source homes and record signatures to help users make trust decisions.
- Reporting workflows: clients should provide reporting that sends evidence to the user’s home server; coordination with remote homes will still be required for takedowns.

Expect edge cases: inconsistent takedowns across homes, delayed removal, and servers with different policies. Designing transparent UI that communicates these limitations is crucial.

### Data consistency, performance, and defensive engineering

Client-only apps must be defensive:

- Handle partial metadata and malformed records; assume heterogenous server implementations.
- Implement idempotent writes and retries: uploads may succeed but repo writes fail.
- Rate-limit and back off aggressively when crawling multiple homes.
- Store metadata and blob ETags to detect changes; reconcile inconsistent state across fetches.
- Optimize battery and storage: limit prefetch, use AVFoundation efficient players on iOS, and respect background fetch constraints.

Platform distribution: distributing an early client via TestFlight (Apple Developer, 2024) is a sensible way to iterate on UX. Ensure compliance with Apple’s rules for content and moderation.

Citation: Apple [Developer (2024)](https://doi.org/10.2172/2335740).

## Examples/Applications

1. Independent creator distribution: A musician posts quick clips via Microwave to their AT Protocol identity. Fans on different homes can discover the clips via the app without the creator running a server. The creator benefits from portability and ownership of their repo and blobs.

1. Community event highlights: A local community uses Microwave as a lightweight event-streaming app. Members publish short recap videos that the app aggregates from a community namespace, enabling quick discovery without a proprietary backend.

1. Research & privacy-first personalized feeds: A research team builds a study client that personalizes recommendations entirely on-device, using privacy-preserving models and only querying public indices for broader discovery signals.

## Best Practices

- Prioritize caching: cache thumbnails aggressively, use Range requests for partial downloads, and evict old video data predictably.
- Respect server hints: use blob cache-control headers and conditional GETs (ETag, Last-Modified).
- Use adaptive heuristics: fall back to lower-resolution uploads when on mobile networks and consider client-side re-encoding if allowed.
- Make moderation explicit: provide clear UI that shows content provenance, reporting flows, and the limits of local filters.
- Design for heterogeneity: plan for servers that implement incomplete or inconsistent features, and add defensive parsing and error handling.
- Consider hybrid indexing: if discovery quality matters, explicitly support optional indexers/caches that users may choose to trust.

## Implications

Microwave’s approach illustrates a middle path: decentralized identity and storage with client-driven UX. It highlights a pressing tradeoff in open social systems: you can gain portability and user control, but some conveniences of vertically integrated platforms — consistent content moderation, global popularity signals, and low-latency CDN-backed streaming — require either broader protocol standards or voluntary cooperation across servers.

For protocol designers, supporting standard ways to advertise CDN-backed blobs, HLS manifests, and consistent metadata (e.g., engagement counts) would help media-heavy clients. For client authors, enabling optional cooperation with ecosystem indexers and making privacy/trust choices explicit to users is pragmatic.

## Conclusion

Microwave demonstrates that a TikTok-like experience is technically possible on top of AT Protocol with a native iOS client, but achieving the performance and recommendation quality users expect from centralized platforms demands compromises. Client-side ranking and aggressive caching can deliver a pleasant local UX, while discovery and consistent moderation remain the hard problems that either require protocol-level conventions or optional cooperative services.

If you’re building similar clients:

- Optimize for resilient playback and caching.
- Use client-side personalization for privacy and responsiveness.
- Offer transparent moderation UI and support for reporting.
- Consider optional indexer cooperation to improve discovery without becoming dependent on a bespoke backend.

Try Microwave on TestFlight and share feedback with the project author (@sinned) — experiments like this surface the practical tradeoffs needed to evolve open social protocols into platforms fit for rich media.

References

- ActivityPub (W3C, 2018).
- AT Protocol / Bluesky (2023).
- Ricci, F., Rokach, L., & Shapira, B. (eds.) (2015). Recommender Systems Handbook.
- Apple Developer (2024), TestFlight and App Distribution Guide.

Original source: Microwave announcement on Hacker News by @sinned (TestFlight: https://testflight.apple.com/join/cVxV1W3g).


## References

- [Show HN: Microwave – Native iOS app for videos on ATproto](https://testflight.apple.com/join/cVxV1W3g) — @sinned on hackernews

- [Bluesky (2023)](https://doi.org/10.59350/tn7kx-3gq89)
- [Ricci et al. (2015)](https://doi.org/10.1007/978-3-319-14944-8_12)
- [Developer (2024)](https://doi.org/10.2172/2335740)