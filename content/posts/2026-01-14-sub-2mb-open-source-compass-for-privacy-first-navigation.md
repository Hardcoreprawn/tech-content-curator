---
action_run_id: '21004859336'
article_quality:
  dimensions:
    citations: 75.0
    code_examples: 0.0
    length: 100.0
    readability: 57.5
    source_citation: 100.0
    structure: 80.0
    tone: 100.0
  overall_score: 66.6
  passed_threshold: false
cover:
  alt: Sub-2MB Open Source Compass for Privacy-first Navigation
  image: https://images.unsplash.com/photo-1626682238005-9db97583f26f?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w4MTYwNTN8MHwxfHNlYXJjaHwxfHxNQkNvbXBhc3MlMjBuYXZpZ2F0aW9uJTIwYXBwfGVufDB8MHx8fDE3Njg0MTQ3MTV8MA&ixlib=rb-4.1.0&q=80&w=1080
  image_source: unsplash
  photographer: Devon Janse van Rensburg
  photographer_url: https://unsplash.com/@huntleytography
date: 2026-01-14T18:16:22+0000
generation_costs:
  content_generation:
  - 0.00231915
  image_generation:
  - 0.0
  title_generation:
  - 0.0007112
generator: General Article Generator
icon: https://images.unsplash.com/photo-1626682238005-9db97583f26f?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w4MTYwNTN8MHwxfHNlYXJjaHwxfHxNQkNvbXBhc3MlMjBuYXZpZ2F0aW9uJTIwYXBwfGVufDB8MHx8fDE3Njg0MTQ3MTV8MA&ixlib=rb-4.1.0&q=80&w=1080
illustrations_count: 0
models_used:
  content: gpt-5-mini
  enrichment: gpt-5-nano
  title: gpt-5-nano
reading_time: 7 min read
sources:
- author: nativeforks
  platform: hackernews
  quality_score: 0.65
  url: https://github.com/CompassMB/MBCompass
summary: Introduction A tiny, fully open-source compass and navigation app under 2
  MB sounds almost nostalgic in an era of hundred-megabyte map apps.
tags:
- open source
- mobile app
- navigation
- geolocation
- small size
title: Sub-2MB Open Source Compass for Privacy-first Navigation
word_count: 1462
---

> **Attribution:** This article was based on content by **@nativeforks** on **GitHub**.  
> Original: https://github.com/CompassMB/MBCompass

## Introduction

A tiny, fully open-source compass and navigation app under 2 MB sounds almost nostalgic in an era of hundred-megabyte map apps. Yet that is exactly what the Hacker News post “Show HN: Tiny FOSS Compass and Navigation App (\<2MB)” points to — MBCompass on GitHub (nativeforks/MBCompass) — a useful prompt to examine how small, privacy-respecting geolocation apps can be designed today (credit: nativeforks, GitHub: https://github.com/CompassMB/MBCompass). This article unpacks the engineering and design choices behind a sub‑2 MB compass/navigation app and explains the trade-offs across sensors, map data, routing, battery, and privacy.

> Background: GNSS stands for Global Navigation Satellite System and refers to satellite constellations such as GPS, Galileo, GLONASS, and BeiDou.

Key Takeaways

- A true tiny app favors on-device sensors for headings and uses on-demand map tiles or online routing to stay under 2 MB.
- Accurate heading requires sensor fusion (magnetometer, accelerometer, gyroscope) plus declination correction and calibration.
- Offline routing and full map bundles typically blow the size budget; hybrid online/offline strategies keep functionality small while preserving privacy and performance.
- OpenStreetMap (OSM) data is a natural fit but must be used in compliance with the ODbL (Open Database License).

## Background

Smartphones determine position primarily through Global Navigation Satellite Systems (GNSS): GPS (United States), Galileo (EU), GLONASS (Russia), and BeiDou (China). These constellations provide pseudorange measurements that a GNSS receiver converts into a latitude/longitude fix. Orientation (heading) is derived from inertial sensors: a magnetometer (compass), accelerometer, and gyroscope. Combining those sensors in a sensor-fusion pipeline yields stable headings and tilt-compensated bearings.

> Background: ODbL (Open Database License) is the database license used by OpenStreetMap data that requires attribution and share-alike for derived databases.

Common map data and packaging formats include raster tiles (PNG/JPEG), vector tiles (Mapbox Vector Tile / MVT), MBTiles (a single-file tile container), GeoJSON (feature collections), GPX (GPS Exchange Format) for tracks, and KML for place data. Each format has trade-offs in size, rendering cost, and licensing.

## Main Content

Designing a sub-2 MB app forces tight decisions at every layer: binary size, third‑party libraries, bundled assets, and offline data. Two main product archetypes make sense within this constraint:

1. Pure compass + minimal location UI. Uses only device sensors to show heading and optionally a simple coordinate readout. Size stays small because no map-rendering libraries or bundled tiles are required.
1. Lean navigation client. Keeps the core small but fetches map tiles and/or routing from a server on demand. This provides richer UX while avoiding large offline datasets.

Sensors and heading accuracy

- Magnetometer: measures the earth’s magnetic field; vulnerable to local magnetic interference.
- Accelerometer: measures linear acceleration; used for tilt compensation so the compass can show correct heading when the device is tilted.
- Gyroscope: measures angular velocity; used to stabilize short-term motion and reduce jitter.

Sensor fusion merges these streams into a stable heading. Lightweight filters such as the Madgwick filter (Madgwick, 2010) are computationally inexpensive and work well on mobile CPUs. Android offers fused rotation vectors through `Sensor.TYPE_ROTATION_VECTOR` and Google Play Services provide a fused location API, while iOS exposes `CMMotionManager` and `CoreLocation` for orientation and GNSS.

Calibration and declination

- Magnetic declination (difference between magnetic north and true north) varies by location. Apply a geomagnetic model (e.g., the World Magnetic Model) to convert magnetic headings to true headings when needed.
- Provide a short calibration UX (figure‑eight motion) and allow manual offset correction for persistent device biases.

GNSS and multi‑constellation benefits

- Using multiple constellations improves fix availability and accuracy in challenging environments.
- On-device GNSS alone is usually sufficient for non-critical navigation, but high-precision or continuity during outages often relies on assisted GNSS or external receivers.

Maps, tiles, and licensing

- Bundling whole-country or regional offline maps will exceed the size budget. Instead:
  - Fetch raster or vector tiles on demand from a tile server (OpenStreetMap tile servers, self-hosted tiles, or third-party providers).
  - Cache a small region locally (MBTiles is a useful container format for cached tiles).
- Vector tiles (MVT) are compact and efficient to render, but client libraries like MapLibre may add tens of megabytes — unacceptable if binary size must remain \<2 MB. A pragmatic pattern is to render simple tiles server-side and download raster tiles, or implement a tiny custom vector renderer limited to basic styles.
- Always follow OSM licensing: data from OpenStreetMap is offered under ODbL and requires attribution and reciprocal sharing for derived databases (OpenStreetMap Foundation, 2012).

Routing strategies under a tight size budget

- Offline routing graphs (even pruned) are large. Routing engines (OSRM, GraphHopper) and preprocessed contraction hierarchies reduce query time but the graph data still consumes tens or hundreds of megabytes for any sizable region.
- Hybrid approach: perform routing on a remote service via a minimal HTTP client. This keeps the app small and leverages powerful servers for routing while caching recent routes for offline reuse.
- For simple turn-by-turn-free experiences, use straight-line guidance, bearing + distance, or follow pre-recorded GPX tracks.

Algorithms: Dijkstra (Dijkstra, 1959) and A\* (Hart et al., 1968) remain foundational for routing. On-device routing for tiny apps is typically constrained to small local graphs (neighborhoods) if implemented.

Resource usage and battery

- GNSS, screen, and radios (cell/Wi‑Fi) are the main battery drains. Minimize GPS duty cycles, use coarse location where appropriate, and offer an explicit low-power mode that samples location more sparsely.
- Sensor sampling and fusion should run at necessary rates only while the app is active or in a foreground navigation session.

Cross‑platform considerations

- Android: fine-grained sensor APIs and easier background operation, but diverse hardware means more calibration variance.
- iOS: consistent hardware and polished APIs (CoreLocation, CoreMotion), but stricter background execution limits and permission flows.
- Cross-platform toolkits (Flutter, React Native) may inflate binary size; for sub‑2 MB targets, favor minimal native implementations.

Security and privacy

- Minimize required permissions (e.g., allow use without location permission if only compass is needed).
- Perform sensitive processing on-device when possible; if routing is done remotely, document what data is sent and consider anonymization.
- Provide offline mode and explicit user controls for caching and telemetry.

## Examples/Applications

1. Backwoods hiker (offline-first compass + GPX): A hiker loads a GPX track on another device, uses the app in pure‑compass + GPX overlay mode, and follows headings and distance without large offline maps. Battery-friendly and privacy-conscious.
1. Urban commuter using on-demand tiles + remote routing: The app stays under 2 MB by fetching raster tiles as needed and hitting a routing endpoint for turn-by-turn directions. Cached tiles for frequent routes reduce data usage.
1. Disaster-response scout: Volunteers use the app for quick headings and coordinates when network infrastructure is compromised. Minimal dependencies make audits and reproduction easier for teams that need to run tools on air-gapped devices.

## Best Practices

- Keep the binary lean: avoid heavy map SDKs, strip symbols, and use compiler-level dead-code elimination (e.g., R8/ProGuard on Android).
- Lazy-load optional features: download routing or advanced rendering modules only when the user requests them.
- Offer clear calibration and heading diagnostics: show magnetometer strength, provide simple calibration flows, and expose a “use true north” toggle.
- Respect user privacy: allow local-only operation and minimize telemetry.
- Use open data responsibly: attribute OSM and comply with ODbL; document how users can contribute corrections (Haklay & Weber, 2008).

## Implications

A tiny FOSS compass/navigation app demonstrates that useful geospatial tooling can be compact, auditable, and privacy-friendly. While feature parity with full map suites is impractical at sub‑2 MB, the right hybrid choices (sensor-first design, on-demand tiles, server-side routing) yield a product that is fast, low-power, and transparent. For communities and developers, small open-source projects make it easier to audit behavior, localize, and integrate into bespoke workflows compared with monolithic commercial map apps.

## Conclusion

MBCompass and similar tiny open-source projects show that practical navigation tools can be compact without sacrificing core utility. The key is to prioritize: use on‑device sensors for heading, offload size‑heavy responsibilities (maps and routing) to on‑demand services or small cached regions, and keep the codebase minimal and auditable. For developers building or evaluating such apps, focus on robust sensor fusion, clear calibration UX, careful tile/routing trade-offs, and strict privacy practices. With those choices, a sub‑2 MB compass/navigation app becomes not just possible, but genuinely useful in the field.

References

- [Dijkstra (1959)](https://doi.org/10.1007/bf02000548). A note on two problems in connexion with graphs.
- Hart, P., Nilsson, N., & Raphael, B. (1968). A formal basis for the heuristic determination of minimum cost paths.
- [Madgwick (2010)](https://doi.org/10.7748/ns2010.08.24.50.43.c7938). An efficient orientation filter for inertial/magnetic sensor arrays.
- Haklay, M., & Weber, P. (2008). OpenStreetMap: User-generated street maps.
- OpenStreetMap [Foundation (2012)](https://doi.org/10.59350/7bbbg-cmj31). Open Database License (ODbL) — license for OpenStreetMap data.

Original project: nativeforks/MBCompass on GitHub (https://github.com/CompassMB/MBCompass), showcased on Hacker News.


## References

- [Show HN: Tiny FOSS Compass and Navigation App (<2MB)](https://github.com/CompassMB/MBCompass) — @nativeforks on GitHub

- [Dijkstra (1959)](https://doi.org/10.1007/bf02000548)
- [Madgwick (2010)](https://doi.org/10.7748/ns2010.08.24.50.43.c7938)
- [Foundation (2012)](https://doi.org/10.59350/7bbbg-cmj31)