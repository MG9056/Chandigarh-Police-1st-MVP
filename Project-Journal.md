# DarKnight MVP - Project Journal

## Frontend MVP Built (Summary)
- **Framework & Styling**: Built with Vite React, Tailwind CSS, and Shadcn UI.
- **Branding & UI**: Rebranded as "DarKnight" with a Matrix-style bootup animation featuring a 3D morphing Chandigarh Police logo.
- **Layout**: Implemented a 3-Panel Dashboard layout for general navigation, main metrics, and deep-dive details.
- **Accessibility**: Full localization (English, Hindi, Punjabi) via `react-i18next` and global Light/Dark mode toggling.
- **Key Features Implemented (with Mock Data)**:
  - **Interactive Intelligence Dashboard**: Active investigations, critical alerts, and monitored metrics.
  - **Data Collection Status**: Monitoring status of various darknet/crypto scraper nodes.
  - **Alerts & Suspicious Activity**: Feed consolidating automated alerts and AI pattern detection.
  - **Network Visualization**: Interactive, physics-based 2D network graph for suspects and crypto wallets.
  - **Search & Investigation**: Search bar with mock filtering across aliases, wallets, and keywords.
  - **Reports & Evidence**: Interface for viewing drafted/finalized reports.
  - **Security & Access Control**: Investigator profiles, clearance levels, and audit logs.
  - **Traffic Hotspots**: Map view for geographic activity (never previously logged in this journal, see entry below for how it evolved from mock to real).

---

## Backend Build-Out: Synthetic Intelligence Pipeline (Phase 1)

Before real data existed, the backend was extended with a first "fake but structured" intelligence pipeline, so that entity-resolution and graph logic could be built and tested against a known answer key before real data arrived. None of this was previously logged in this journal.

- **`backend/data/schemas.py` — Pydantic data model.**
  Defines the canonical shape of everything the intelligence pipeline works with: `Entity` (suspect/wallet/market/account), `Observation` (a sighting, optionally geotagged), `Transaction` (money movement between two entities), plus `Region`/`DetailedLocation` for the hotspot map. Every generator, adapter, and future real-data loader is written to produce or consume these exact types. Having one shared schema means the synthetic generator and the eventual real-data loader are interchangeable from the rest of the pipeline's point of view — swapping fake data for real data later shouldn't require touching downstream code.

- **`backend/synthetic_data.py` — deterministic synthetic dataset with planted "ground truth".**
  Generates entities, transactions, and regions with a fixed random seed (so the dataset is identical every run) and deliberately plants known patterns — an "easy" alias pair, a "medium" alias pair, and a "decoy" pair that looks similar but is genuinely two different people. The point is that detection logic (entity resolution, anomaly detection) can be checked against a known answer key instead of just eyeballing whether the output "looks plausible." A `GROUND_TRUTH` dict at the bottom documents every planted pattern in one place.

- **`backend/entity_resolution.py` — username/identifier similarity signal (Workstream A, piece 1 of several).**
  Compares two identifiers using four different deterministic string-similarity metrics (Levenshtein, Jaro-Winkler, shared prefix/suffix, character n-gram overlap) and combines them with `max()` rather than an average, on purpose: the four metrics catch different failure modes (e.g. n-grams catch "abc123" vs "123abc" reordering that the others score near-zero), so averaging would let three correct "no match" signals cancel out the one signal that correctly caught a real match. This module deliberately only answers "how similar do these look" — it's known to misfire on pairs like `john123`/`john124` (different people, high score) and is meant to be combined with other signal types (bio, platform, behavior) later before anything is treated as a confirmed match.

- **`backend/graph_adapter.py` — synthetic Entity/Transaction → frontend graph shape.**
  Converts the synthetic entities and transactions into the `{nodes, links}` JSON shape `NetworkGraph.jsx` already expects. This is the one place that decides **OBSERVED vs INFERRED** edges: an edge backed by an actual `Transaction` (money moved) is OBSERVED; an edge from the planted alias clusters (similarity, not a witnessed event) is INFERRED and carries a `confidence` score. This OBSERVED/INFERRED convention set here is reused later, unchanged, by the real-data graph builder.

- **`backend/geo_signals.py` (top-level, in `backend/`)** — an early, now-superseded version of place-mention scanning for the map. It has since been replaced by `backend/real_data/geo_signals.py` (see below), but the older file is still sitting in the repo and imports (`from . import dread_loader`) that no longer exist elsewhere in `backend/` — it will raise an import error if anything tries to run it. Flagging this as dead code worth deleting rather than a working feature.

- **`backend/requirements.txt` — first pinned dependency list for the backend.** Previously there was no `requirements.txt` at all (per the README's own gap list); this adds `fastapi`, `uvicorn`, `pydantic`, `rapidfuzz` (for entity resolution), and `pandas`/`pyarrow`/`networkx` (for the real-data pipeline below).

---

## Backend Build-Out: Real-Data Pipeline (`backend/real_data/`)

A second, larger backend workstream that replaces the synthetic data with two real, publicly available datasets: **Elliptic++** (a labeled Bitcoin-wallet transaction graph with illicit/licit/unknown classes) and a **Dread forum archive** (a real darknet-forum export with users, posts, and comments). None of this was previously logged in this journal.

- **`backend/real_data/config.py` — pipeline configuration.**
  Central place for the real-data root folder (overridable via `REAL_DATA_ROOT` env var), illicit/licit/unknown class codes from the Elliptic++ docs, graph-size caps (so a browser-rendered force graph stays readable — e.g. max 120 wallet nodes even though the real dataset is far larger), and confidence values for inferred links (0.97 for a shared PGP fingerprint, 0.55 for a wallet address merely mentioned in forum text). Centralizing these numbers means every module tunes off the same values instead of hand-copied constants scattered around.

- **`backend/real_data/loader.py` — schema-based universal file loader (`RealDataLoader`).**
  Points at a folder (or several) containing any mix of Elliptic++ CSVs and Dread parquet files, in any naming scheme, and figures out what each file actually *is* by inspecting its real columns (and, when that's ambiguous, sampling real values) rather than requiring exact filenames. This replaces an earlier, more brittle version that matched on exact filenames like `wallets_classes.csv`, which broke once the dataset's file names varied. A file the loader doesn't recognize is skipped with a logged reason instead of crashing the whole pipeline — one bad file can't take down ingestion of everything else.

- **`backend/real_data/india_gazetteer.py` — reference data for the map.**
  A static lookup of ~100 Indian cities (all state capitals + union territories, plus major cities) with approximate lat/lon, plus an alias table mapping common alternate names (Bombay→Mumbai, Bangalore→Bengaluru, etc.) to the canonical name shown on the map. This is public geographic reference data, not anything derived from either real dataset — it exists purely so forum text can be matched against real place names.

- **`backend/real_data/intelligence.py` — real correlation signals extracted from the Dread archive.**
  Finds entity-resolution edges backed by an actual fact in the data, not a guess: e.g. two forum usernames that share a cryptographic PGP fingerprint or verified email (very high confidence — cryptographically, the same private-key holder controls both), the real reply graph between users, and Bitcoin addresses regex-matched inside forum post/comment text (the bridge that connects the Dread side to the Elliptic++ wallet side). Every function's docstring states exactly what real-world fact the edge represents, continuing the OBSERVED-vs-INFERRED convention from `graph_adapter.py`.

- **`backend/real_data/graph_builder.py` — combines Elliptic++ + Dread into one renderable graph, with disk caching.**
  Picks a real, self-contained illicit-touching cluster of Bitcoin wallets (favoring whole small connected components over a thinned-out slice of the one giant tangled component, which was tried and abandoned because it lost all real cluster structure), merges in Dread accounts/markets from `intelligence.py`, and caches the result to disk for up to 6 hours since rebuilding means re-scanning the full dataset. The cache is versioned (`CACHE_SCHEMA_VERSION`) so that if this function's output shape ever changes, an old cached file is detected as stale and rebuilt automatically instead of silently being served forever in the wrong shape — the journal notes this exact bug already happened once before this safeguard existed.

- **`backend/real_data/geo_signals.py` — real place-mention scan of the Dread archive (replaces the old top-level version).**
  Scans every post and comment in the Dread archive for a mention of any place in the gazetteer and tallies real counts per place, ready to plot as `{name, lat, lon, count}`. Important framing baked into the code and its output: since neither dataset has per-post geolocation, a mention count is an **activity-volume proxy** ("this city's name came up N times"), not proof anyone involved is physically located there — a vendor writing "ships to Mumbai" counts under Mumbai regardless of where they actually are. Also versioned/cached the same way as `graph_builder.py`, and works around a real pandas string-engine bug found during testing (a compiled regex pattern mishandled `\b` word boundaries on non-ASCII text; passing the pattern as a plain string sidesteps it).

- **`backend/main.py` — three new endpoints wired to the above.**
  `/api/network/synthetic` (serves the Phase 1 synthetic graph via `graph_adapter`), `/api/network/real` (serves the real Elliptic++/Dread graph via `real_data/graph_builder`, with a `?refresh=true` param to force a rebuild and a friendly error message if the raw data files aren't present yet), and `/api/geo/activity` (serves the real place-mention counts via `real_data/geo_signals`, same refresh/error pattern). All three return the same shapes the frontend already expected, so no frontend contract changes were needed to switch it over.

---

## Frontend Changes to Consume Real Data

- **`frontend/src/components/views/NetworkGraph.jsx` — real/synthetic data source toggle.**
  The network graph view now defaults to fetching `/api/network/real` and can switch to `/api/network/synthetic`, rather than only ever reading the old `mock_db.json` network data. Degree-based layout forces (hubs behave differently from single-link leaves) and group-based quadrant positioning were added so a much bigger, messier real graph still lays out readably, which wasn't a concern with the small hand-authored mock data.

- **`frontend/src/components/views/TrafficHotspots.jsx` — mock hotspots replaced with a real Leaflet map.**
  This view was never actually documented in this journal despite existing in the original MVP. It has since been rewired from static/mock hotspot data to a real `react-leaflet` map with an India boundary/OSM overlay (`src/assets/india-osm.json`, `indiaBoundary.json`), plotting real place-mention data from `/api/geo/activity`. Marker color/size tiers (critical/high/medium/low) are computed relative to whatever the real data's own max mention count is, not a fixed absolute scale, since that depends entirely on what's actually in the archive.

- **New frontend dependencies added:** `leaflet` + `react-leaflet` (the real map in Traffic Hotspots), `gsap` (drives the pixel-dissolve reveal effect in `PixelTransition.jsx`, used inside the existing bootup animation), `d3-force` (custom force-layout tuning for the bigger real network graph), and `recharts` (charting, added but not yet confirmed wired into a view — worth checking before assuming it's live).

---

## Data Added, Not Yet Wired Up

- **`DATASETS/` folder — three large raw network-traffic CSVs** (`Darknet.CSV`, `MultiTotalDS.csv`, `Binary -2DSCombined.csv`, ~165MB total). These are Tor/darknet vs. regular network-flow classification datasets (per-flow statistical features + a Tor/Non-Tor or traffic-type label). Nothing in `backend/` currently reads, references, or imports these files — they appear to be raw material staged for a future workstream (e.g. network-traffic-based darknet detection) rather than something already integrated. Worth confirming intent before assuming this is "done."

## Housekeeping / Flags Worth a Look

- **`frontend/.env` has live-looking API keys committed to the repo** (`VITE_CARTO_API_KEY`, `VITE_MAPPLS_API_KEY`) for the map tile provider used by Traffic Hotspots. Committing real keys to a repo (even a private one) is generally worth avoiding — rotate/move to a non-committed `.env.local` or secrets manager if these are live.
- **`backend/package.json`** is an essentially empty (`{}`) Node manifest sitting inside the Python backend folder, alongside a matching `package-lock.json`. Looks like a stray `npm init` run in the wrong directory rather than an intentional dependency — safe to delete unless something depends on it.
- **Top-level `backend/geo_signals.py`** (see above) is dead code superseded by `backend/real_data/geo_signals.py` and will error if imported directly (`dread_loader` no longer exists). Candidate for deletion to avoid confusion with the real version.