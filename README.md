# DarKnight

## Chandigarh Police Intelligence Platform

DarKnight is a security-focused intelligence and investigation platform built for Chandigarh Police. It brings together authorized public-source collection, synthetic and sanitized intelligence datasets, investigation management, entity correlation, geographic signals, suspicious-activity detection, and evidence provenance in one operational interface.

The project is designed for law-enforcement workflows. It is not an intrusion tool, credential-harvesting system, or unrestricted darknet crawler. The current build operates on legal public sources, mock services, synthetic data, and sanitized datasets. Tor and darknet collection paths are architectural stubs with hard demo-mode enforcement.

> **Project status:** Functional FastAPI backend and React dashboard. The repository contains implemented security, investigation, crawler, provenance, intelligence, and visualization modules, together with automated tests and local demo data.

---

## Contents

1. [Platform Capabilities](#platform-capabilities)
2. [Security and Access Control](#security-and-access-control)
3. [Investigation Management](#investigation-management)
4. [Crawler and Data Collection](#crawler-and-data-collection)
5. [Intelligence and Detection](#intelligence-and-detection)
6. [Evidence and Provenance](#evidence-and-provenance)
7. [Frontend Experience](#frontend-experience)
8. [Architecture](#architecture)
9. [Repository Layout](#repository-layout)
10. [Technology Stack](#technology-stack)
11. [Local Setup](#local-setup)
12. [Configuration](#configuration)
13. [API Surface](#api-surface)
14. [Testing and Validation](#testing-and-validation)
15. [Demo Data and Safety Boundaries](#demo-data-and-safety-boundaries)
16. [Known Limitations](#known-limitations)
17. [Project Documentation](#project-documentation)

---

## Platform Capabilities

DarKnight is composed of the following major systems:

- **Secure identity and access control:** Account approval, role hierarchy, permission checks, session security, multi-factor authentication, sensitive-action re-authentication, and delegated investigation access.
- **Investigation lifecycle:** Create, list, filter, update, assign, close, and audit investigations with status, priority, unit, lead investigator, and closure metadata.
- **Investigation workbench:** Case-scoped sources, keywords, raw intelligence, findings review, evidence promotion, alerts, entity networks, geography, and activity history.
- **Crawler orchestration:** Source registry, scheduled or manual runs, robots policy, rate limiting, fetching, cleaning, deduplication, language detection, relevance filtering, and candidate entity extraction.
- **Intelligence processing:** AI-assisted relevance classification, suspicious-activity detection, alert generation, semantic search, entity resolution, graph construction, and geographic signal extraction.
- **Evidence traceability:** Raw-record provenance, source metadata, collection timestamps, SHA-256 integrity hashes, review decisions, and evidence promotion records.
- **Operational visualizations:** Dashboard metrics, entity relationship graphs, Indian geographic hotspots, traffic analysis, suspect profiles, reports, and data-collection monitoring.
- **Localization:** English, Hindi, and Punjabi UI translations for static interface text. Backend-provided intelligence values are displayed as returned and are not translated.

---

## Security and Access Control

Security is enforced in the FastAPI backend. Frontend controls only improve usability; hiding a button is never treated as authorization.

### Fixed role hierarchy

The platform uses six roles, from highest to lowest authority:

```text
SUPER ADMIN / DGP
        |
       IGP
        |
        SP
        |
    INSPECTOR
        |
   INVESTIGATOR
        |
    CONSTABLE
```

Users cannot assign an equal or higher role than their own. Role assignment and account administration are audited.

### Account registration and approval

- Users can submit registration requests.
- New accounts begin in `PENDING` status and cannot use operational APIs.
- Authorized senior officers can approve, reject, or suspend accounts.
- Approval assigns the role and organizational scope needed by the account.
- Account states are `PENDING`, `ACTIVE`, `SUSPENDED`, and `REJECTED`.
- Authentication and authorization check account status on the backend.

### Permission model

The central permission matrix includes:

| Permission | Purpose |
|---|---|
| `READ` | View authorized platform data and investigations |
| `CREATE` | Create investigations or other permitted resources |
| `UPDATE` | Modify permitted records |
| `DELETE` | Delete resources where the role and endpoint allow it |
| `EXPORT` | Export audit or intelligence data |
| `MANAGE_ACCESS` | Manage investigation access and assignments |
| `MANAGE_USERS` | Approve, suspend, and administer users |
| `MANAGE_DATA_SOURCES` | Create and modify global crawler sources and keywords |
| `MANAGE_PIPELINES` | Trigger and control crawler pipelines |
| `VIEW_AUDIT_LOGS` | View security and activity audit records |

The role matrix is defined centrally in `backend/rbac.py` and protected endpoints use FastAPI dependencies such as `require_permission`.

### Investigation scope rules

- All authenticated roles can currently view all investigations. This broad visibility is intentional for cross-unit intelligence sharing.
- Modification is separately controlled.
- DGP and IGP can modify investigations globally.
- SP and Inspector modification is scoped by unit where applicable.
- A lead investigator can modify their own investigation.
- Explicit active assignments and delegated grants can provide modification access.
- Access grants can expire and can be revoked.
- Assignment and delegation actions are audited.

### Authentication and session security

- Passwords are hashed with BCrypt using cost factor 12.
- Access JWTs expire after approximately 15 minutes.
- Refresh sessions last up to seven days and can be revoked.
- Persistent refresh storage contains a SHA-256 hash, not the plaintext refresh token.
- Logout and suspension can invalidate refresh sessions.
- A short-lived re-authentication token is used for sensitive operations.
- Production deployments must use HTTPS and secure, HttpOnly cookies.
- Secrets and credentials must be supplied through environment variables, never frontend code.

### Two-factor authentication

- TOTP-based 2FA setup and verification are supported.
- Authenticator applications can use the generated `otpauth://` provisioning URI or QR code.
- Eight one-time recovery codes are generated during setup.
- Recovery codes are stored as hashes and are consumed when used.
- Login can require a six-digit TOTP code when 2FA is enabled.

### Brute-force protection

- Failed login attempts are counted per account.
- Accounts can be temporarily locked after repeated failures.
- Lock state and failed-attempt counters are stored with the user account.

### Audit logging

The audit log records security and investigation actions, including:

- User identity, role, timestamp, IP address, user agent, and session context.
- Action, resource type, resource ID, result, and optional metadata.
- Successful, failed, and denied operations.
- Login, logout, approval, suspension, role, access, investigation, evidence, alert, and crawler actions.

Audit records are append-only. The application does not expose update or delete operations for audit entries. Authorized users can query audit records and export them as CSV.

---

## Investigation Management

Investigations are stored in the `investigations` table and use a user-facing case number such as `INV-2026-042`.

### Investigation metadata

Each investigation can contain:

- Unique investigation ID and title.
- Description and case type.
- Lifecycle status: `OPEN`, `ACTIVE`, or `CLOSED`.
- Priority from 1 to 4: Low, Medium, High, Critical.
- Unit or jurisdiction.
- Creator, lead investigator, assigned investigators, and closing officer.
- Creation, update, closure, and closure-reason timestamps and notes.

### Investigation workbench tabs

The investigation detail view provides:

- **Overview:** Case metadata, edit controls, assignments, and lifecycle actions.
- **Sources:** Attach crawler sources to a case, detach them, and trigger case-scoped crawls.
- **Keywords:** Add or remove case-specific keyword overrides while preserving the global watchlist.
- **Intelligence:** Search and review raw records associated with the investigation.
- **Findings:** Filter review decisions and promote relevant findings to evidence.
- **Evidence:** View promoted evidence and integrity/provenance metadata.
- **Alerts:** List, create, filter, and resolve case-scoped alerts.
- **Network:** View entity co-occurrence relationships derived from case intelligence.
- **Geography:** View location signals and hotspot information for the investigation.
- **Activity:** Review the investigation-specific audit timeline.

### Dashboard relationship

The dashboard's **Active Investigations** metric is backed by the `Investigation` table and counts records with `OPEN` or `ACTIVE` status. It links directly to the Investigations section. Suspect totals are separate metrics and are not presented as investigation counts.

---

## Crawler and Data Collection

The crawler is source-agnostic and produces `RawRecord` intermediates. It does not write directly to the platform's final entity, observation, or transaction schema.

### Source registry

Sources have a type, configuration, active state, polling interval, crawl delay, transport type, creator, and run history. Implemented and designed source types include:

| Source type | Current state |
|---|---|
| Google search discovery | Implemented architecture |
| Direct seed URLs | Implemented fallback path |
| Public Bitcoin chain | Supported integration path / dataset workflows |
| Public Telegram | Supported integration path / dataset workflows |
| External API | Design/integration path |
| External database | Design/integration path |
| Tor stub | Architecture stub; hard demo-mode error |

### Collection pipeline

The normal processing flow is:

```text
Source registry
    -> collector and transport
    -> robots.txt policy
    -> per-domain rate limiting
    -> HTTP fetch with retry/backoff
    -> content cleaning
    -> SHA-256 deduplication
    -> language detection
    -> keyword pre-filter
    -> AI relevance classification
    -> candidate entity extraction
    -> provenance validation
    -> RawRecord output
```

### Pipeline controls

- `BaseCollector` provides a shared collector interface.
- Transport is injected so collectors do not hard-code a network implementation.
- `RobotsChecker` caches robots.txt decisions and skips disallowed URLs.
- `RateLimiter` enforces a per-domain delay floor.
- Direct HTTP uses timeouts and bounded retry/backoff behavior.
- Dead or repeatedly failing URLs can be excluded from later runs.
- `trafilatura` extracts useful page text and removes boilerplate.
- Content hashes prevent duplicate downstream processing.
- Language detection tags records for downstream handling.
- Global and case-specific watchlists support English, Hindi, and Punjabi terms.
- Keyword matching runs before the more expensive relevance classifier.
- Low-confidence or ambiguous results are routed to review instead of silently discarded.
- High-confidence unrelated records remain retained with a discarded status and reason.
- spaCy NER and wallet/phone regexes emit confidence-tagged candidates, not confirmed facts.
- Every valid output requires source URL, fetch timestamp, run ID, and content hash.

### Crawler activity and monitoring

The Data Collection Status view provides:

- Source list and active/disabled state.
- Manual trigger and stop controls.
- Global watchlist management.
- Crawler run activity and statistics.
- Raw intelligence records and relevance filtering.
- Last-run outcomes, errors, attempted URLs, skipped robots paths, and produced records.

---

## Intelligence and Detection

### Data domains

The backend models and ingestion workflows support:

- Suspects and aliases.
- Crypto wallets and transactions.
- Darknet listing records from sanitized or synthetic datasets.
- Telegram channels and messages.
- Network traffic flow records.
- Raw crawler records and derived suspicious activities.
- Alerts associated with suspicious activities or raw records.

### Relevance and suspicious activity

The detection pipeline keeps collected data separate from derived analysis:

- `RawRecord` preserves original collected intelligence and provenance.
- Relevance classification stores label, confidence, and reasoning.
- Suspicious activity records describe derived patterns and confidence.
- Alert generation turns actionable detections into deduplicated alerts.
- Statuses support open, acknowledged, resolved, and dismissed workflows where applicable.

### Entity resolution and graph intelligence

- String similarity and alias matching help identify potentially overlapping entities.
- PGP fingerprints, verified email signals, wallet patterns, and other supported identifiers can strengthen correlations.
- Graph adapters normalize entities and relationships for visualization.
- The global and case-scoped network views distinguish observational co-occurrence from confirmed relationships.
- Real-data graph construction supports caching for repeated visualization requests.

### Geographic intelligence

- Location mentions are resolved against an India-focused gazetteer.
- Geographic signals can be viewed globally or within an investigation.
- The Traffic Hotspots view presents location activity on an interactive map.
- Location signals are derived evidence and should be interpreted with their source and confidence context.

### Search and semantic retrieval

- Universal search supports searches across aliases, wallets, listings, and intelligence records.
- Exact and fuzzy search behavior remains available when the semantic index is unavailable.
- Semantic search uses a local multilingual embedding model and writes a separate ignored index at `backend/.semantic_index.json`.
- Building the optional semantic index is done with `python -m semantic_search` from `backend`.

---

## Evidence and Provenance

DarKnight preserves a distinction between source material, derived findings, and promoted evidence.

### Provenance metadata

Provenance records can include:

- Source type and source name.
- Source identifier and URL.
- Authorized collection method.
- Collection timestamp.
- Investigation association.
- Original record reference.
- SHA-256 integrity hash.

### Review-to-evidence workflow

1. A crawler or ingestion process creates a raw record with provenance.
2. Relevance and intelligence review produce a finding decision.
3. Investigators mark a finding as relevant or dismissed.
4. Authorized users promote a relevant finding to evidence.
5. The promotion records who performed it, when it occurred, and which raw record/finding it came from.
6. Evidence can be inspected through the investigation Evidence tab and provenance APIs.

Original intelligence is not silently overwritten by later processing. Derived analysis is stored separately from the collected source record.

---

## Frontend Experience

The React dashboard provides the following navigation surfaces:

- **Dashboard:** Active investigation count, critical alerts, monitored sources, charts, and synchronization status.
- **Investigations:** Global investigation list, filters, case creation, detail view, assignments, and workbench tabs.
- **Traffic Hotspots:** Geographic traffic and activity visualization.
- **Target Profiles:** Suspect profile and risk information.
- **Data Collection Status:** Source, keyword, crawler activity, and raw-record monitoring.
- **Alerts and Suspicious Activity:** Alert feeds and detection-focused views.
- **Network Visualization:** Synthetic and real-data entity graphs.
- **Universal Search:** Cross-domain intelligence lookup.
- **Reports and Evidence:** Structured report and evidence management surface.
- **Security and Access Control:** Account/session status, 2FA access, roles, and administrative controls.

The UI supports:

- Dark and light themes.
- Responsive React components styled with Tailwind CSS and shadcn-inspired primitives.
- English, Hindi, and Punjabi translations for static headings, controls, and explanatory text.
- Backend data rendered without automatic translation so case identifiers, source values, names, statuses, URLs, notes, and evidence remain exact.
- Session refresh handling through the shared API client.

---

## Architecture

```text
React + Vite frontend
        |
        | authenticated API requests
        v
FastAPI application
        |
        +--> Authentication, JWT, 2FA, re-authentication
        +--> RBAC, assignments, delegation, audit logging
        +--> Investigation, alert, evidence, and provenance routers
        +--> Crawler source, keyword, raw-record, and activity routers
        +--> Search, AI, graph, and geography services
        |
        v
SQLAlchemy ORM
        |
        +--> SQLite for local development by default
        +--> PostgreSQL-compatible configuration through DATABASE_URL
```

The crawler emits raw intermediate records. Mapping and enrichment services consume those records and produce derived intelligence without replacing the original collected content.

---

## Repository Layout

```text
.
├── AGENTS.md                         # Repository-specific agent instructions
├── DESIGN.md                         # Frontend/design notes
├── Project-Journal.md                # Feature history, mistakes, and fixes
├── README.md                         # This document
├── specs/                            # Product requirements and security/crawler PRDs
├── audits/                           # PRD and security review notes
├── DATASETS/                         # Staged datasets used by ingestion workflows
├── references/                       # Geographic and other reference data
├── fake_msg_board/                   # Small Flask source used for crawler testing
├── backend/
│   ├── main.py                       # FastAPI application and global endpoints
│   ├── database.py                   # SQLAlchemy engine, sessions, initialization
│   ├── models.py                     # ORM models and domain enums
│   ├── security.py                   # Password, JWT, TOTP, token, and recovery helpers
│   ├── rbac.py                       # Permissions, role matrix, and scope checks
│   ├── audit_service.py              # Append-only audit event service
│   ├── rate_limiter.py               # Request/crawler rate-limiting support
│   ├── entity_resolution.py          # Similarity and identity resolution helpers
│   ├── graph_adapter.py              # Graph output normalization
│   ├── semantic_search.py            # Optional local semantic index
│   ├── synthetic_data.py             # Synthetic data generation
│   ├── routers/                      # Auth, admin, investigation, search, evidence APIs
│   ├── services/                     # AI, alerts, detection, and suspicious activity services
│   ├── crawler/                      # Collectors, pipeline, policy, evidence, orchestration
│   ├── data/                         # Canonical schema and extensions
│   ├── pipelines/                    # Dataset ingestion and database seeding scripts
│   ├── real_data/                    # Dataset loaders, graph, geography, intelligence
│   ├── tests/                        # Pytest suites
│   ├── requirements.txt              # Backend dependencies
│   └── SETUP_NOTES.md                # Environment-specific setup guidance
└── frontend/
    ├── src/App.jsx                   # Main shell, navigation, and view selection
    ├── src/api/                      # API clients
    ├── src/components/               # Views, investigation tabs, auth, and UI primitives
    ├── src/context/                  # Authentication and shared state
    ├── src/i18n.js                   # English, Hindi, and Punjabi translations
    ├── public/                       # Static images and public assets
    ├── package.json                  # Frontend scripts and dependencies
    └── vite.config.js                # Vite configuration
```

---

## Technology Stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | React 19, Vite | Dashboard and investigation workbench |
| UI | Tailwind CSS, Radix primitives, Lucide | Styling and accessible controls |
| Charts | Recharts | Dashboard metrics and distributions |
| Maps | Leaflet, React Leaflet | Geographic views and hotspots |
| Graphs | `react-force-graph-2d`, D3 force | Entity relationship visualization |
| Localization | i18next, react-i18next | English, Hindi, Punjabi static UI text |
| Backend | FastAPI, Uvicorn, Pydantic | Authenticated REST APIs |
| Persistence | SQLAlchemy, SQLite/PostgreSQL | Relational data and ORM models |
| Security | BCrypt, PyJWT, PyOTP | Passwords, sessions, JWTs, TOTP |
| Collection | httpx, trafilatura, langdetect, spaCy | Fetching and text processing |
| Intelligence | sentence-transformers, pandas, NetworkX, RapidFuzz | Search, datasets, graphs, resolution |
| Testing | pytest, HTTPX | Unit and integration coverage |

---

## Local Setup

### Prerequisites

- Windows, macOS, or Linux.
- Python 3.14+ is recommended for the current environment, or the repository's `backend/.venv`.
- Node.js and npm compatible with the frontend toolchain.
- Optional: PostgreSQL for a non-SQLite deployment.

### Backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Use `python -m uvicorn` rather than bare `uvicorn` so the server uses the same interpreter where dependencies were installed.

The API is available at `http://localhost:8000`. FastAPI interactive documentation is available at `/docs` when the server is running.

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

Production build and preview commands:

```powershell
npm run build
npm run preview
```

### Optional fake message board

The `fake_msg_board` service is a small local Flask application for crawler tests. It exposes a human-readable message board and JSON endpoints.

```powershell
cd fake_msg_board
python -m pip install -r requirements.txt
python app.py
```

It runs on `http://localhost:5000` and provides `GET /messages` and `POST /messages`.

---

## Configuration

Use environment variables or a local `.env` file that is excluded from version control. Do not commit secrets.

Important configuration areas include:

| Variable/setting | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy database URL; SQLite is the local default |
| `JWT_SECRET_KEY` | Signing key for access, refresh-related, and re-authentication tokens |
| `GOOGLE_CSE_API_KEY` | Optional authorized search-discovery API credential |
| `GOOGLE_CSE_CX` | Optional Google Custom Search engine ID |
| LLM provider settings | Optional AI relevance and assistant integrations |
| Crawler source settings | Source URLs, polling intervals, delays, and transport mode |

Production requirements:

- Set a strong unique JWT secret.
- Use HTTPS with secure cookies.
- Use a managed PostgreSQL database or secured equivalent.
- Restrict CORS origins to the deployed frontend.
- Store API credentials in a secret manager or protected environment.
- Review logging and access policies before handling operational data.

### Database initialization

On startup, `backend/database.py` creates missing tables and runs lightweight compatibility migrations. Local startup seeds or verifies the development administrative accounts and may create a sample test investigation.

Development seed credentials are documented in the local setup history and must be changed or disabled before any non-development deployment.

### Semantic search index

After the database has records to search:

```powershell
cd backend
python -m semantic_search
```

The first run downloads the local multilingual embedding model. The generated `backend/.semantic_index.json` is ignored by Git. If unavailable, exact and fuzzy search remain available.

---

## API Surface

All operational endpoints require an authenticated user unless explicitly stated otherwise. Backend permissions and investigation scope are checked independently at the endpoint/service layer.

### Authentication and account security

| Route group | Main capabilities |
|---|---|
| `/api/auth/signup` | Submit registration request |
| `/api/auth/login` | Authenticate with password and optional TOTP |
| `/api/auth/logout` | Revoke the active refresh session |
| `/api/auth/refresh` | Issue a new short-lived access token |
| `/api/auth/me` | Return the current user/session view |
| `/api/auth/2fa/setup` | Start TOTP setup |
| `/api/auth/2fa/verify` | Verify and activate TOTP |
| `/api/reauthenticate` | Establish recent authentication for sensitive actions |

### Administration and governance

| Route group | Main capabilities |
|---|---|
| `/api/admin/users` | List users for authorized administration |
| `/api/admin/approve-user` | Approve/reject and assign roles |
| `/api/admin/suspend-user` | Suspend accounts and affect sessions |
| `/api/audit` | Query append-only audit records |
| `/api/audit/export` | Export authorized audit records |
| `/api/delegation/...` | Grant, revoke, and list investigation access |

### Investigations

| Route group | Main capabilities |
|---|---|
| `/api/investigations` | Create, list, filter, update, and close investigations |
| `/api/investigations/{id}/assign` | Assign and remove investigators |
| `/api/investigations/{id}/assignments` | List active/history assignments |
| `/api/investigations/{id}/activity` | Investigation activity timeline |
| `/api/investigations/{id}/entities` | Case-scoped entity graph data |
| `/api/investigations/{id}/geography` | Case-scoped geographic signals |
| `/api/investigations/{id}/sources` | Attach, detach, and trigger case sources |
| `/api/investigations/{id}/keywords` | Manage case keyword overrides |
| `/api/investigations/{id}/intelligence` | List, search, inspect, and review raw intelligence |
| `/api/investigations/{id}/intelligence/findings/list` | List investigation findings |
| `/api/investigations/{id}/evidence` | List and promote evidence |
| `/api/investigations/{id}/alerts` | List, create, and resolve case alerts |

### Collection, search, and intelligence

| Route group | Main capabilities |
|---|---|
| `/api/sources` | Global source registry and source controls |
| `/api/keywords` | Global multilingual watchlist |
| `/api/raw-records` | Raw-record output contract and filtering |
| `/api/crawler/activity` | Paginated crawler activity and run statistics |
| `/api/search/universal` | Cross-domain universal search |
| `/api/suspects` | Suspect list and details |
| `/api/global/entities` | Global entity correlation graph |
| `/api/global/geography` | Global geographic aggregation |
| `/api/dashboard/summary` | Dashboard metrics backed by current database records |
| `/api/evidence` and `/api/provenance` | Evidence stream and provenance metadata |

---

## Testing and Validation

Run the backend tests from the repository root:

```powershell
cd backend
python -m pytest
```

The suites cover areas including:

- Core models and database behavior.
- Authentication, account governance, and session security.
- RBAC, investigation scope, delegation, and re-authentication.
- Audit logging, evidence, and provenance.
- Investigation lifecycle and case-scoped intelligence.
- Crawler collectors, policies, deduplication, relevance routing, and provenance requirements.
- AI assistant and intelligence services where configured.

Frontend production validation:

```powershell
cd frontend
npm run build
```

Frontend linting:

```powershell
npm run lint
```

The build may report non-fatal warnings about large bundles or graph-library chunking. Those warnings do not indicate a failed build.

---

## Demo Data and Safety Boundaries

DarKnight is intentionally constrained for safe development and demonstrations:

- No live `.onion` requests are permitted.
- Tor-related collectors are stubs and raise `DemoModeEnforcedError` for live attempts.
- No credential theft, account bypass, CAPTCHA solving, unauthorized scanning, or exploitation is implemented.
- Do not download or store stolen credentials, private personal data, malware, illicit transaction material, or contraband content.
- Use synthetic data, mock services, legally obtained public data, and sanitized datasets only.
- Crawlers respect robots.txt and enforce a minimum crawl delay.
- Source provenance and integrity metadata are required for collected records.
- `fake_msg_board` is a local test source, not a production intelligence source.

These constraints are code-level expectations, not merely documentation. Any future expansion of collection capabilities must preserve authorization, isolation, provenance, and data-minimization requirements.

---

## Known Limitations

- SQLite is the default local database; production deployments should use a secured PostgreSQL-compatible database.
- Some source types are integration paths or stretch implementations rather than live external integrations.
- Tor support is deliberately not implemented.
- The AI relevance classifier and AI assistant require provider configuration when used beyond local fallback behavior.
- Some dashboard charts and distributions are presentation/demo values rather than complete historical analytics feeds; backend metrics and investigation counts are database-backed where documented.
- Semantic search requires a separately built local embedding index.
- Geographic and graph results are observational signals and must not be treated as confirmed identity or relationship determinations without investigator review.
- The frontend is not a security boundary; all deployment security depends on backend authorization, secure configuration, and HTTPS.

---

## Project Documentation

- [AGENTS.md](AGENTS.md): Repository instructions and project context.
- [DESIGN.md](DESIGN.md): Frontend design guidance.
- [Project-Journal.md](Project-Journal.md): Development history, completed features, mistakes, and fixes.
- [Security and Access Control PRD](specs/Security-Authentication-Access%20Control-PRD.md): Security requirements and threat constraints.
- [Crawler Pipeline PRD](specs/crawler-pipeline-prd.md): Collector, policy, pipeline, provenance, and safety requirements.
- [Crawler Audit](audits/security-access-control-prd-audit.md): Security/access-control audit notes.
- [Backend Setup Notes](backend/SETUP_NOTES.md): Python environment and semantic-search setup guidance.
- [Canonical Schema](backend/data/CANONICAL_SCHEMA.md): Data schema and canonicalization notes.

---

## Development Principles

When extending DarKnight:

1. Enforce authorization in the backend first.
2. Preserve original source records and append derived analysis separately.
3. Add provenance and integrity metadata to collected intelligence.
4. Keep global and investigation-scoped data paths distinct.
5. Keep user-facing translations limited to static interface text; do not mutate backend intelligence values.
6. Respect robots.txt, rate limits, legal authorization, and demo-mode restrictions.
7. Add focused tests for security, scope, provenance, and data-flow changes.
8. Follow the established frontend visual language and update `Project-Journal.md` for meaningful feature work.
