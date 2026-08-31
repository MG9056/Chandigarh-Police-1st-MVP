"""
Config for the real-data pipeline (Elliptic++ + Dread forum archive).

All paths are directories, not single files, so this works whether you
drop in 1 sample file or the full ~20-file Dread export / full Elliptic++
set — the loaders glob() everything matching the pattern.

Override via env vars if your data lives somewhere else:
    ELLIPTIC_DATA_DIR, DREAD_DATA_DIR
"""

from __future__ import annotations

import os

_HERE = os.path.dirname(os.path.abspath(__file__))

ELLIPTIC_DATA_DIR = os.environ.get(
    "ELLIPTIC_DATA_DIR", os.path.join(_HERE, "..", "real_data_files", "elliptic")
)
DREAD_DATA_DIR = os.environ.get(
    "DREAD_DATA_DIR", os.path.join(_HERE, "..", "real_data_files", "dread")
)
CACHE_DIR = os.path.join(_HERE, "cache")

ELLIPTIC_WALLETS_GLOB = "*wallet*.csv"
ELLIPTIC_EDGES_GLOB = "*edge*.csv"

DREAD_USERS_GLOB = "users-*.parquet"
DREAD_POSTS_GLOB = "posts-*.parquet"
DREAD_COMMENTS_GLOB = "comments-*.parquet"

# Elliptic++ wallets_classes.csv convention (per the dataset's own docs):
#   1 = illicit, 2 = licit, 3 = unknown
ILLICIT_CLASS = 1
LICIT_CLASS = 2
UNKNOWN_CLASS = 3

# --- Graph size caps (force-graph in a browser tab stops being readable
# well before it stops being computable — these keep the default view
# legible; the underlying real dataset is never truncated on disk, only
# the rendered subgraph is).
MAX_ELLIPTIC_NODES = 120
MAX_DREAD_ACCOUNT_NODES = 80
MAX_MARKET_NODES = 20
MAX_TOTAL_LINKS = 600

# --- Correlation confidence (inferred links only — observed links from
# real transactions/replies never carry a confidence score, matching the
# convention already established in graph_adapter.py)
CONFIDENCE_PGP_ALIAS = 0.97       # shared PGP fingerprint or email
CONFIDENCE_WALLET_MENTION = 0.55  # address regex-matched in forum text

BTC_ADDRESS_REGEX = r"\b(?:bc1[a-z0-9]{11,71}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"

# Boards/keywords used for the (illustrative, non-geotagged) India activity
# signal that feeds the map — see geo_signals.py for why this is a volume
# proxy, not real geolocation.
INDIA_SUBDREADS = {"DarknetMarketsIndia"}
CITY_KEYWORDS = {
    "chandigarh": "chandigarh",
    "ludhiana": "ludhiana",
    "amritsar": "amritsar",
    "delhi": "delhi_ncr",
    "new delhi": "delhi_ncr",
    "gurgaon": "delhi_ncr",
    "gurugram": "delhi_ncr",
    "noida": "delhi_ncr",
}
