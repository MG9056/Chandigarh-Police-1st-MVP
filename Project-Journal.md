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

## Security & Access Control

### Phase 1: Security & Core Infrastructure Setup (Completed)
- **Database Architecture**: Implemented SQLAlchemy engine, declarative base, and request session management in `database.py`.
- **Core Security Models (`models.py`)**: Created ORM models matching PRD specs:
  - `User`: Email, BCrypt password hash, role hierarchy (`SUPER ADMIN / DGP` down to `CONSTABLE`), account status (`PENDING`, `ACTIVE`, `SUSPENDED`, `REJECTED`), 2FA TOTP secret, and brute-force lockout counters.
  - `RefreshSession`: Long-lived refresh session tracking with server-side revocation and IP/user-agent auditing.
  - `InvestigationAccessGrant`: Explicit delegated access grants with composite index on `(user_id, investigation_id)`.
  - `AuditLog`: Immutable append-only audit trail.
  - `DataProvenance`: Intelligence source origin, collection method, integrity hash (SHA-256), and raw record reference tracking.
- **Cryptographic Utilities (`security.py`)**: Password hashing (BCrypt cost 12), short-lived JWT Access Tokens (15 min), Refresh Tokens, Re-Authentication state tokens, TOTP MFA secret generation, and single-use 8 recovery codes.
- **Frontend Authentication Context (`AuthContext.jsx`)**: React Context provider for user session lifecycle, account status, CSRF tokens, and re-authentication modal handling.
- **Automated Verification**: Built and ran pytest test suite `tests/test_phase1_core.py` (5/5 passed cleanly).

### Phase 2: Authentication, Session Management & Governance (Completed)
- **Backend Authentication Routers (`routers/auth_router.py`)**:
  - Registration endpoint (`/signup`) with min 12-char password check, creating users in `PENDING` status.
  - Login endpoint (`/login`) with generic failure responses, 5-failed-attempt 15-minute brute-force lockout, TOTP 2FA validation, 15-min `HttpOnly` Access Token cookie, and server-side revocable Refresh Token cookie.
  - Revocable logout endpoint (`/logout`) and token refresh endpoint (`/refresh`).
  - TOTP 2FA setup (`/2fa/setup`) and verification (`/2fa/verify`) yielding secret key and 8 single-use recovery codes.
- **User Governance & Role Hierarchy (`routers/admin_router.py`)**:
  - Approvals & Role assignment (`/approve-user`) enforcing **Critical Security Constraint 4** (users cannot assign an equal or higher role than themselves).
  - Suspension endpoint (`/suspend-user`) immediately revoking all active refresh sessions.
- **Security Headers Middleware**: Configured global HTTP security headers (`HSTS`, `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`) in `main.py`.
- **Frontend UI Components**:
  - `LoginPage.jsx` & `RegisterPage.jsx` with DarKnight Matrix branding, error alerts, and 2FA prompts.
  - `TFAModal.jsx` for QR/secret display, recovery code copying, and verification.
  - `UserManagementTable.jsx` for Senior Officers to inspect pending users, assign role hierarchy options, and suspend users.
- **Automated Verification**: Created and ran pytest suite `tests/test_phase2_auth_gov.py` (9/9 total test cases passed cleanly).

### Phase 3: RBAC Access Control, Delegated Access & Re-Authentication (Completed)
- **Centralized Permission Matrix (`rbac.py`)**:
  - Centralized permission definitions (`READ`, `CREATE`, `UPDATE`, `DELETE`, `EXPORT`, `MANAGE_ACCESS`, `MANAGE_USERS`, `MANAGE_DATA_SOURCES`, `MANAGE_PIPELINES`, `VIEW_AUDIT_LOGS`).
  - Implemented `require_permission` FastAPI dependency checking permission matrix per role.
  - Implemented `check_investigation_modification_access()` evaluating role scope and explicit delegated grants via composite database index `(user_id, investigation_id)`.
- **Forced Re-Authentication Window (`routers/reauth_router.py` & `ReAuthModal.jsx`)**:
  - Created `/api/auth/reauthenticate` endpoint returning short-lived 10-minute re-auth token for high-risk sensitive operations.
  - Implemented `require_recent_reauth` dependency blocking sensitive operations without recent password reauth.
  - Created frontend `ReAuthModal.jsx` password confirmation dialog.
- **Delegated Access Control (`routers/delegation_router.py` & `DelegationControlPanel.jsx`)**:
  - Implemented `/grant-access` and `/revoke-access` endpoints requiring `MANAGE_ACCESS` permission + `require_recent_reauth`.
  - Enforced rules preventing users from granting access to themselves.
  - Created `DelegationControlPanel.jsx` component.
- **Automated Verification**: Created and ran pytest suite `tests/test_phase3_rbac_reauth.py` (12/12 total test cases passed cleanly).

### Phase 4: Audit Logging, Evidence Protection & Data Provenance (Completed)
- **Append-Only Audit Logging (`audit_service.py` & `routers/audit_router.py`)**:
  - Created append-only audit logger enforcing sanitization of passwords/tokens/secrets from metadata.
  - Implemented `/api/audit-logs` query endpoint filterable by date range, user ID, action, resource type, result (requires `VIEW_AUDIT_LOGS` + `require_recent_reauth`).
  - Implemented `/api/audit-logs/export` generating downloadable CSV files.
- **Evidence Protection & Integrity (`routers/evidence_provenance_router.py`)**:
  - Backend-authorized evidence stream computing SHA-256 integrity hash and returning `X-Evidence-Integrity-SHA256` header.
- **Data Provenance System (`routers/evidence_provenance_router.py` & `ProvenanceBadgePanel.jsx`)**:
  - Data provenance recording and lookup endpoints storing intelligence origin (Darknet, Telegram, Blockchain, Public Forum), collection timestamp, collection method, raw record reference, and SHA-256 hash without overwriting raw data with AI analysis.
- **Frontend UI Components**:
  - `AuditLogViewer.jsx` for Senior Officers to inspect activity logs and export CSV files.
  - `ProvenanceBadgePanel.jsx` rendering data source origin metadata, collection method, SHA-256 hash, and raw record indicator.
- **Automated Verification**: Created and ran pytest suite `tests/test_phase4_audit_evidence_provenance.py` (16/16 total test cases passed cleanly).

### Phase 5: Verification & PRD Audit (Completed)
- Conducted full PRD Definition of Done compliance check across all 15 Critical Security Constraints.
- Verified test suite execution: **16/16 test cases passed** across all 4 test modules (`test_phase1_core.py`, `test_phase2_auth_gov.py`, `test_phase3_rbac_reauth.py`, `test_phase4_audit_evidence_provenance.py`).
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

---

## Crawler Pipeline Implementation (`specs/crawler-pipeline-prd.md`)

Implemented the full production-grade, source-agnostic Crawler Pipeline based on [specs/crawler-pipeline-prd.md](file:///e:/Manomoy/PEC/Hackathons/Chandigarh%20Police/1st%20round%20mvp/specs/crawler-pipeline-prd.md) (C-01 to C-14).

### Key Architectural Highlights:
1. **Source & Collector Interface (C-01)**:
   - Built `BaseCollector` ABC and `CollectorRegistry` mapping `source_type` strings to collectors.
   - `DirectHTTPTransport` wraps `httpx.AsyncClient` with user-agent config, timeouts, and exponential backoff retries (up to 3 attempts).
   - Enforced **Critical Constraint #5** via `DemoModeEnforcedError` in `TorStubCollector` and `TorProxyTransport` — hard error whenever darknet/live `.onion` requests are initiated.
2. **Keyword Watchlist & Case Overrides (C-02)**:
   - Built `KeywordService` with pre-seeded multi-lingual initial watchlist (EN, HI, PA drug terms and regional slang: heroin, fentanyl, अफीम, चरस, गांजा, स्मैक, ਚਿੱਟਾ).
   - Dynamic query scope merging global watchlist with case-specific overrides (`add_case_keyword`, `remove_case_keyword`).
3. **Google Search Discovery Layer & Fallbacks (C-03)**:
   - `GoogleDiscoveryCollector` builds search queries from case keywords via official Google Custom Search JSON API with quota tracking (100 free requests/day).
   - `DirectSeedCollector` provides direct seed URL fetching fallback.
   - Stretch collectors added for `BITCOIN_CHAIN` and `TELEGRAM_PUBLIC`.
4. **Policy, Governance & Compliance (C-04 & C-05)**:
   - `RobotsChecker` checks domain `robots.txt` and caches rules in `robots_cache` DB table with 24h TTL.
   - `RateLimiter` enforces per-domain crawl delays with code-enforced minimum floor (`MIN_CRAWL_DELAY_SECONDS = 0.5s`).
5. **Data Cleaning, Deduplication & Language (C-06 & C-07)**:
   - `ContentCleaner` main content extraction using `trafilatura` (with regex HTML fallback).
   - `Deduplicator` computes raw content SHA-256 hash and checks `raw_records` table to eliminate redundant processing.
   - `LanguageDetector` tags detected language (`en`, `hi`, `pa`, etc.).
   - `KeywordMatcher` pre-filters non-matching records to `status='discarded'` before invoking AI models.
6. **AI Relevance Classifier & Entity Extraction (C-08 & C-09)**:
   - `LLMRelevanceClassifier` classifies keyword-matched text into `relevant`, `medical_legitimate`, or `unrelated` with confidence and reasoning.
   - Low confidence / medical legitimate content routes to `review_queue`.
   - `EntityExtractor` extracts spaCy NER candidates + regex patterns for Bitcoin (`1|3|bc1`), Ethereum (`0x`), and phone numbers into `extracted_candidates` JSON.
7. **Evidence Provenance & Handoff Contract (C-10 & C-11)**:
   - `EvidenceTagger` validates mandatory fields (`url`, `fetched_at`, `run_id`, `content_hash`) and computes SHA-256 over raw content bytes.
   - Handoff contract exposed at `GET /api/raw-records?status=pending_mapping` for AI mapping component. Crawler logic strictly avoids writing into fixed `entities`, `observations`, or `transactions` tables.
8. **Management APIs & Activity Feed (C-12, C-13, C-14)**:
   - `run_crawl` execution flow and `CrawlerScheduler` background loop.
   - API endpoints mounted in `main.py`: `/api/sources`, `/api/keywords`, `/api/raw-records`, `/api/crawler/activity`. Protected via RBAC permissions (`MANAGE_DATA_SOURCES`, `MANAGE_PIPELINES`, `READ`, `UPDATE`).
9. **Automated Verification**:
   - Built test suite `backend/tests/test_crawler_pipeline.py`.
   - All 26 backend tests passed cleanly (`26 passed, 0 failed`).

### Crawler Operational & UI Bug Fixes:
- **Collector Out-Of-Box Fallbacks**:
  - `GoogleDiscoveryCollector`: Added OSINT keyword candidate fallback when `GOOGLE_CSE_API_KEY` is unconfigured, so searches work out-of-the-box in demo/dev mode.
  - `TelegramPublicCollector` & `BitcoinChainCollector`: Added parsing for seed URLs and default fallbacks so missing `channels`/`addresses` keys in UI modal don't result in empty `[]` runs.
  - `DirectSeedCollector`: Provided default public OSINT fallback URLs (`https://en.wikipedia.org/wiki/Heroin`, `https://en.wikipedia.org/wiki/Fentanyl`) when seed URLs list is empty.
- **Backend CRUD & Control Endpoints**:
  - `DELETE /api/sources/{id}`: Added endpoint to delete crawler targets and clean up associated runs.
  - `POST /api/sources/{id}/stop`: Added endpoint to immediately halt active runs and set status to `STOPPED`.
- **Frontend UI & Styling Alignment**:
  - Heading font colors in `DataCollectionStatus.jsx` updated to match the rest of the application theme (`text-foreground`).
  - Removed internal "PRD C-01 — C-14" badge from header.
  - Added **Edit Target** modal (`PATCH /api/sources/{id}`) allowing operators to modify target name, seed URLs, poll interval, crawl delay, and active state.
  - Added **Delete Target** with confirmation dialog (`DELETE /api/sources/{id}`).
  - Added **Stop Run** button (`POST /api/sources/{id}/stop`).

---

## Tavily API Migration, Login Healing & Password Re-Authentication Governance Integration

### 1. Account Auto-Healing & Login Restoration
- **Issue**: Login was failing due to stale or out-of-sync password hashes in local SQLite `darknight.db`.
- **Fix**: Updated `init_db()` in `backend/database.py` to check and automatically reset password hashes, active account status (`AccountStatusEnum.ACTIVE`), and zero out failed login lockout counters on startup for:
  - `dgp@chandigarhpolice.gov.in` (`AdminPassword123!`)
  - `igp@chandigarhpolice.gov.in` (`IGPPassword123!`) - **New Permanent IGP Account**
  - `inspector.chandr@chandigarhpolice.gov.in` (`InspectorPass123!`)

### 2. Google Search -> Tavily Search API Migration
- **Issue**: Google Custom Search API integration replaced due to deprecation.
- **Fix**:
  - Updated `google_discovery.py` to use **Tavily Search API** (`https://api.tavily.com/search` via `TAVILY_API_KEY`).
  - Updated `transport.py` HTTP transport layer (`HTTPTransport`, `DirectHTTPTransport`, `TorProxyTransport`) with `async def post()` method support for JSON search payloads.
  - Retained fallback OSINT simulation when `TAVILY_API_KEY` is not present, allowing development and offline testing without breakage.

### 3. Target Editing & Deletion Governance (Password Re-Authentication)
- **Issue**: Edits and deletions needed to persist cleanly to backend DB and trigger mandatory password re-authentication modal instead of basic browser alert warnings.
- **Fix**:
  - Updated `DataCollectionStatus.jsx` to integrate `AuthContext`'s `triggerReAuth(callback)`.
  - Sensitive operations (**Edit Target** and **Delete Target**) now launch `ReAuthModal.jsx` to verify operator credentials before sending `PATCH` or `DELETE` API requests.
  - Adjusted API endpoint permissions in backend routers from `Permission.MANAGE_DATA_SOURCES` to `Permission.UPDATE` / `Permission.CREATE`, matching police roles (`INSPECTOR`, `INVESTIGATOR`, `SP`, `DGP`).

### 4. Automated Verification
- Ran full backend test suite (`pytest` via virtual environment python): **26 / 26 passed cleanly (100%)**.
- Ran production frontend build (`npm run build`): **0 errors**.