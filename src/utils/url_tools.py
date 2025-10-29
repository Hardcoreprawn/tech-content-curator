"""URL utilities: normalization and simple tracking-parameter cleanup.

We rely on a lightweight maintained library for core normalization
(url-normalize), and add a tiny helper to drop common tracking params
and fragments.
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from url_normalize import url_normalize

# Common tracking parameters to strip. Keep this conservative.
_TRACKING_PARAMS = {
    "ref",
    "ref_src",
    "ref_source",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
}


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication and comparison.

    Steps:
    - Use url-normalize for RFC-compliant normalization
    - Drop URL fragments
    - Drop common tracking parameters (utm_*, fbclid, gclid, etc.)
    - Sort remaining query params for stability
    """
    # Core normalization
    core = url_normalize(url or "")

    # Split components to clean further
    parts = urlsplit(core)

    # Filter tracking query params conservatively
    query_pairs = parse_qsl(str(parts.query), keep_blank_values=False)
    filtered_pairs = [
        (k, v)
        for (k, v) in query_pairs
        if k.lower() not in _TRACKING_PARAMS
    ]
    # Sort for deterministic ordering
    filtered_pairs.sort()
    query = urlencode(filtered_pairs, doseq=True)

    # Rebuild without fragment and with filtered query
    # Cast to str to satisfy type checker (url_normalize returns str, so parts are str)
    return urlunsplit((str(parts.scheme), str(parts.netloc), str(parts.path), query, ""))
