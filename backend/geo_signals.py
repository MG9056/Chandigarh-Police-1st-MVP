"""
Scans every post and comment in the Dread archive for a mention of any
place in india_gazetteer.PLACES (or one of its ALIASES — "Bangalore",
"Bombay", etc.), tallies real counts per place, and returns them ready
to plot: {name, lat, lon, count}.

This replaces the earlier "4 hardcoded cities" version. There's no
per-post geolocation in either dataset, so a mention count is still an
activity-volume proxy, not proof anyone involved is physically in that
city — that framing has to stay on the frontend (a vendor writing
"ships to Mumbai" gets counted under Mumbai regardless of where they
actually are).
"""

from __future__ import annotations

import json
import os
import re
import time

import pandas as pd

from . import config, dread_loader
from .india_gazetteer import ALIASES, PLACES

CACHE_PATH = os.path.join(config.CACHE_DIR, "geo_activity.json")
CACHE_TTL_SECONDS = 6 * 60 * 60

# Every recognizable name (canonical + aliases), longest first so e.g.
# "New Delhi" matches before the bare "Delhi" inside it — findall()
# won't double-count the substring once the longer span is consumed.
_ALL_TERMS = sorted(
    {p.lower() for p in PLACES} | set(ALIASES.keys()),
    key=len,
    reverse=True,
)
_PLACE_PATTERN = r"\b(" + "|".join(re.escape(t) for t in _ALL_TERMS) + r")\b"


def _canonical(name: str) -> str:
    lower = name.lower()
    if lower in ALIASES:
        return ALIASES[lower]
    for p in PLACES:
        if p.lower() == lower:
            return p
    return name  # shouldn't happen — every regex term maps to one of the two above


def extract_place_mentions(text_series: pd.Series) -> dict[str, int]:
    """
    Vectorized scan of a text column for any gazetteer place name.
    Returns {canonical_place_name: mention_count}. Every count here
    traces back to an actual substring found in actual post/comment
    text — nothing estimated.

    IMPORTANT: pandas' newer default PyArrow-backed string dtype uses a
    different regex engine under `.str.contains`/`.str.findall` when
    given a *compiled* `re.Pattern`, and it disagrees with Python's own
    `re` on \\b word-boundary handling for non-ASCII text (verified: a
    compiled pattern flagged "leh" as present in Hungarian-language
    posts where a plain `re.search` finds nothing). Passing the pattern
    as a plain string with `flags=` — and forcing `object` dtype first —
    sidesteps that engine entirely and matches standard `re` semantics.
    Do not swap this back to a compiled pattern without re-verifying
    against a non-English sample; this dataset has plenty of it.
    """
    counts: dict[str, int] = {}
    found = text_series.dropna().astype(object).str.findall(_PLACE_PATTERN, flags=re.IGNORECASE)
    for matches in found:
        if not matches:
            continue
        for m in matches:
            canon = _canonical(m)
            counts[canon] = counts.get(canon, 0) + 1
    return counts


def build_geo_activity(dread_dir: str = config.DREAD_DATA_DIR) -> dict:
    posts = dread_loader.load_posts(dread_dir)
    comments = dread_loader.load_comments(dread_dir)

    post_counts = extract_place_mentions(posts.body_text)
    comment_counts = extract_place_mentions(comments.body_text)

    combined: dict[str, int] = dict(post_counts)
    for place, n in comment_counts.items():
        combined[place] = combined.get(place, 0) + n

    india_board_posts = int(posts.subdread.isin(config.INDIA_SUBDREADS).sum())

    places = [
        {"name": name, "lat": PLACES[name][0], "lon": PLACES[name][1], "count": count}
        for name, count in combined.items()
        if count > 0
    ]
    places.sort(key=lambda p: p["count"], reverse=True)

    return {
        "places": places,
        "total_mentions": sum(p["count"] for p in places),
        "distinct_places_mentioned": len(places),
        "india_board_posts": india_board_posts,
        "note": (
            "Real place-name mention counts scanned from the full Dread archive "
            "(post + comment text) — an activity-volume proxy, not geolocated data. "
            "A place is counted whenever its name appears in text, regardless of "
            "who's actually located there."
        ),
    }


def get_cached_or_build_geo(force: bool = False) -> dict:
    if not force and os.path.exists(CACHE_PATH):
        age = time.time() - os.path.getmtime(CACHE_PATH)
        if age < CACHE_TTL_SECONDS:
            with open(CACHE_PATH) as f:
                return json.load(f)

    data = build_geo_activity()
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f)
    return data


if __name__ == "__main__":
    t0 = time.time()
    data = build_geo_activity()
    print(f"built in {time.time() - t0:.1f}s")
    print("distinct places mentioned:", data["distinct_places_mentioned"])
    print("total mentions:", data["total_mentions"])
    print("india_board_posts:", data["india_board_posts"])
    print("top 15:")
    for p in data["places"][:15]:
        print(f"  {p['name']:20s} {p['count']}")
