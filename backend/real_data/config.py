"""
Config for the real-data pipeline (Elliptic++ + Dread forum archive).

File discovery itself is schema-based now (see loader.py) — nothing
here specifies filenames or glob patterns anymore. REAL_DATA_ROOT is
scanned recursively, so Elliptic++ and Dread files can live in
separate subfolders, be mixed together, or be renamed entirely; the
loader figures out what each file is from its actual columns.

Override via env var if your data lives somewhere else: REAL_DATA_ROOT
"""

from __future__ import annotations

import os

_HERE = os.path.dirname(os.path.abspath(__file__))

REAL_DATA_ROOT = os.environ.get(
    "REAL_DATA_ROOT", os.path.join(_HERE, "..", "real_data_files")
)
CACHE_DIR = os.path.join(_HERE, "cache")

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

# Board used for the (illustrative, non-geotagged) India activity signal
# that feeds the map — see geo_signals.py for why this is a volume
# proxy, not real geolocation.
INDIA_SUBDREADS = {"DarknetMarketsIndia"}