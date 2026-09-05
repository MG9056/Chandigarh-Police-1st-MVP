# DarKnight — Chandigarh Police Intelligence Platform

> **Status: Functional Backend & Modern React Intelligence Dashboard.**
> Built for the **Chandigarh Police** to detect, correlate, and track illicit drug sales across surface OSINT, encrypted platforms, and blockchain transactions.

---

## 1. Project Overview

DarKnight is an intelligence platform engineered for law enforcement. It aggregates multi-source intelligence, enforces strict security and audit logging, runs automated data collection pipelines, detects entity relationships, and provides actionable insights for law enforcement.

### Key Functional Systems:
1. **Security & Access Control**: Multi-tier RBAC (SUPER ADMIN / DGP down to CONSTABLE), 2FA TOTP, short-lived JWT access tokens, revocable refresh tokens, 15-minute brute-force lockout, forced re-authentication for sensitive actions, and delegated investigation access grants.
2. **Audit Logging & Provenance**: Immutable append-only audit trail and `DataProvenance` / `RawRecord` SHA-256 evidence integrity hashing.
3. **Crawler Pipeline (`specs/crawler-pipeline-prd.md`)**: Source-agnostic crawler architecture supporting search discovery, direct seeds, public blockchain, and public Telegram channels. Features robots.txt caching, rate limiting with hard floor, content cleaning, SHA-256 deduplication, language detection, keyword pre-filtering, LLM relevance classification, spaCy NER & crypto wallet regex candidate extraction, and stable output contract handoff.
4. **Real & Synthetic Intelligence Engines**: Correlation engine extracting cryptographically verified entity links (shared PGP keys, email verification) from public datasets (Elliptic++ Bitcoin transaction graph & Dread darknet archive).
5. **Interactive Dashboard & Traffic Hotspots**: Physics-based 2D network visualization and Leaflet geographic hotspot map for Indian cities based on real activity signals.

---

## 2. Repository Layout

```
.
├── AGENTS.md                    # Agent development instructions
├── Project-Journal.md             # Detailed engineering journal and changelog
├── README.md                      # Project documentation
├── specs/
│   └── crawler-pipeline-prd.md    # PRD for Crawler Pipeline
├── DATASETS/                      # Raw network traffic datasets (staged)
├── backend/
│   ├── main.py                    # FastAPI application entrypoint & router mounts
│   ├── database.py                # SQLAlchemy engine & session management
│   ├── models.py                  # Declarative ORM models & table definitions
│   ├── security.py                # Cryptographic, JWT & TOTP utilities
│   ├── rbac.py                    # RBAC matrix & authorization dependencies
│   ├── audit_service.py           # Append-only security audit log service
│   ├── synthetic_data.py          # Ground-truth synthetic dataset generator
│   ├── entity_resolution.py       # Multi-metric string similarity algorithm
│   ├── graph_adapter.py           # Network graph schema adapter
│   ├── requirements.txt           # Pinned backend dependencies
│   ├── crawler/                   # Crawler Pipeline package
│   │   ├── collectors/            # BaseCollector, DirectHTTP, TorStub, Google CSE, Seed, BTC, Telegram
│   │   ├── policy/                # RobotsChecker (with DB cache) & RateLimiter (delay floor)
│   │   ├── pipeline/              # ContentCleaner, Deduplicator, LanguageDetector, KeywordMatcher, LLMRelevanceClassifier, EntityExtractor
│   │   ├── keywords/              # Watchlist management & initial multi-lingual seed (EN/HI/PA)
│   │   ├── evidence/              # Provenance tagger & SHA-256 raw content hash validator
│   │   ├── orchestration/         # run_crawl pipeline flow & CrawlerScheduler loop
│   │   └── api/routers/           # Sources, Keywords, RawRecords, Activity endpoints
│   ├── real_data/                 # Real dataset loaders & correlation engine
│   │   ├── config.py              # Dataset thresholds & confidence parameters
│   │   ├── loader.py              # Universal file loader for Elliptic++ & Dread
│   │   ├── intelligence.py        # PGP fingerprint & wallet regex correlation
│   │   ├── graph_builder.py       # Renderable network graph builder with caching
│   │   └── geo_signals.py         # India gazetteer mention scanner for hotspot map
│   ├── routers/                   # Core security & governance API routers
│   │   ├── auth_router.py         # Registration, login, 2FA, logout, refresh
│   │   ├── admin_router.py        # User approvals, role assignment, suspension
│   │   ├── reauth_router.py       # Forced re-authentication endpoints
│   │   ├── delegation_router.py    # Investigation access grant management
│   │   ├── audit_router.py        # Audit log query and CSV export
│   │   └── evidence_provenance_router.py # Evidence stream and provenance metadata
│   └── tests/                     # Automated pytest test suites
│       ├── test_phase1_core.py
│       ├── test_phase2_auth_gov.py
│       ├── test_phase3_rbac_reauth.py
│       ├── test_phase4_audit_evidence_provenance.py
│       └── test_crawler_pipeline.py
└── frontend/                      # Vite + React 19 Frontend
    ├── src/
    │   ├── App.jsx                # Layout & view switcher
    │   ├── i18n.js                # Localization (EN/HI/PA)
    │   ├── context/               # AuthContext for session management
    │   └── components/views/      # Dashboard, NetworkGraph, TrafficHotspots, etc.
    └── package.json
```

---

## 3. Technology Stack

| Component | Technology | Description |
|---|---|---|
| Frontend Framework | React 19 + Vite 8 | Modern component UI |
| Frontend Map & Graph | Leaflet, react-force-graph-2d, d3-force | Interactive visualizations |
| Styling & Theme | Tailwind CSS v3 + shadcn/ui | Dark/Light theme support |
| Backend Framework | FastAPI + Uvicorn | High-performance async Python backend |
| Database | SQLAlchemy ORM + SQLite/PostgreSQL | Relational database storage |
| NLP & Extraction | spaCy (`en_core_web_sm`), trafilatura, langdetect | Text extraction, NER & language detection |
| HTTP Transport | httpx | Async HTTP client with backoff retries |
| Testing | pytest | 26 automated unit and integration tests |

---

## 4. Crawler Pipeline API Endpoints

| Endpoint | Method | Required Permission | Description |
|---|---|---|---|
| `/api/sources` | `GET` | `READ` | List crawler sources with last-run summary |
| `/api/sources` | `POST` | `MANAGE_DATA_SOURCES` | Create a new crawl source target |
| `/api/sources/{id}` | `PATCH` | `MANAGE_DATA_SOURCES` | Update source config, interval, or active state |
| `/api/sources/{id}/trigger` | `POST` | `MANAGE_PIPELINES` | Manually trigger a crawler run for a source/case |
| `/api/keywords` | `GET` | `READ` | List active global and case-specific watchlists |
| `/api/keywords` | `POST` | `MANAGE_DATA_SOURCES` | Add a new global keyword term |
| `/api/cases/{case_id}/keywords` | `POST` | `UPDATE` | Add a case-specific keyword override |
| `/api/cases/{case_id}/keywords/{id}` | `DELETE` | `UPDATE` | Remove a case-specific keyword override |
| `/api/raw-records` | `GET` | `READ` | Output contract endpoint for AI mapping (`pending_mapping`, `review_queue`, `discarded`) |
| `/api/crawler/activity` | `GET` | `READ` | Paginated feed of crawler run activity and statistics |

---

## 5. Running & Testing Locally

### Environment Setup

1. **Activate Virtual Environment & Install Dependencies**:
   ```bash
   cd backend
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run Backend Server**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   *Auto-seeds initial Super Admin (`dgp@chandigarhpolice.gov.in` / `AdminPassword123!`) on startup.*

3. **Run Automated Test Suite**:
   ```bash
   .\venv\Scripts\python.exe -m pytest
   ```
   *Executes all 26 automated tests across authentication, RBAC, audit logging, data provenance, and crawler pipeline.*

4. **Run Frontend App**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Open `http://localhost:5173`.

---

## 6. Safety & Demo Mode Safeguards

Per PRD Critical Constraints:
1. **Demo Mode Enforcement (`DemoModeEnforcedError`)**: Hard-coded in `TorStubCollector` and `TorProxyTransport`. Any attempt to make live `.onion` or Tor requests immediately halts with `DemoModeEnforcedError`.
2. **Schema Handoff Contract**: Crawler writes solely to `raw_records` and `crawler_runs`. It never writes directly to fixed entity/observation/transaction tables.
3. **No Stolen Data or Intrusion**: Operates exclusively on legal public web sources, authorized discovery APIs, and synthetic or sanitized OSINT demonstration datasets.
