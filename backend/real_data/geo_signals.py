"""
Neither Elliptic++ nor the Dread archive carries real geolocation —
there's no lat/lon anywhere in either dataset. So instead of faking
precise points, this counts two REAL, auditable things from the text:

  1. How many posts/comments mention a Chandigarh-region city name
     (Chandigarh, Ludhiana, Amritsar, Delhi/NCR variants).
  2. How many posts sit in the `DarknetMarketsIndia` board specifically
     (counted toward Delhi NCR as the largest hub, since the board
     itself isn't city-specific).

This produces a REAL count per region — but it is a volume-of-mentions
proxy, not a geolocation of where any actual person is. A vendor based
in Kolkata saying "ships to Delhi" would be counted under Delhi. The
map should present this as activity intensity, not "we found N people
here." That distinction is on the frontend to preserve in copy/tooltip.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict

import pandas as pd

from . import config, dread_loader

CACHE_PATH = os.path.join(config.CACHE_DIR, "geo_activity.json")
CACHE_TTL_SECONDS = 6 * 60 * 60


def _count_city_mentions(text_series: pd.Series) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    lowered = text_series.dropna().str.lower()
    for keyword, region in config.CITY_KEYWORDS.items():
        counts[region] += int(lowered.str.contains(keyword, regex=False).sum())
    return counts


def build_geo_activity(dread_dir: str = config.DREAD_DATA_DIR) -> dict:
    posts = dread_loader.load_posts(dread_dir)
    comments = dread_loader.load_comments(dread_dir)

    counts = _count_city_mentions(posts.body_text)
    comment_counts = _count_city_mentions(comments.body_text)
    for region, n in comment_counts.items():
        counts[region] = counts.get(region, 0) + n

    india_board_posts = int(posts.subdread.isin(config.INDIA_SUBDREADS).sum())
    counts["delhi_ncr"] = counts.get("delhi_ncr", 0) + india_board_posts

    total = sum(counts.values()) or 1
    return {
        "counts": dict(counts),
        "share": {region: round(n / total, 3) for region, n in counts.items()},
        "india_board_posts": india_board_posts,
        "note": "Real keyword/board mention counts from the Dread archive — an activity-volume proxy, not geolocated data.",
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
    import time as _t

    t0 = _t.time()
    data = build_geo_activity()
    print(f"built in {_t.time() - t0:.1f}s")
    print(json.dumps(data, indent=2))
