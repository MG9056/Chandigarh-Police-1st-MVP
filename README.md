# DarKnight — Chandigarh Police Intelligence Dashboard (MVP)

> **Status: Frontend-first mock MVP.** Every number, alert, node, and report you see in this app comes from a static JSON file (`backend/mock_db.json`) served by a thin FastAPI shim. Nothing in this repo actually connects to a darknet marketplace, a forum, or a blockchain node yet. Treat this as a **UI/UX proof of concept** for the real system, not a working intelligence tool.

This README exists because the project was originally built by prompting an AI coding agent (see `AGENTS.md`, `DESIGN.md`, `To-do.md`, `Project-Journal.md`) rather than hand-written from a spec. It documents what actually exists in the codebase today so a human contributor can get productive without re-reading every file.

---

## 1. What this project is

DarKnight (working title, previously "Kala Jaddu") is envisioned as a platform for the Chandigarh Police to aggregate, correlate, and act on intelligence about illicit drug sales across darknet marketplaces, encrypted forums, and blockchain transactions. The full target feature set is defined in `To-do.md`:

1. Multi-Source Data Collection
2. Intelligent Entity Correlation
3. Suspicious Activity Detection
4. Interactive Intelligence Dashboard
5. Network Visualization
6. Automated Alert Generation
7. Search & Investigation Support
8. Reporting & Evidence Management
9. Security & Access Control

**This MVP implements the UI shell and mock API surface for all nine items.** No real data collection, scraping, ML detection, entity resolution, authentication, or report generation logic exists yet — see [Section 6, What's NOT real](#6-whats-not-real-read-this-before-you-demo-it).

---

## 2. Repo layout

```
.
├── AGENTS.md              # Original brief given to the coding agent
├── DESIGN.md               # UI/UX design brief (layout, color, i18n requirements)
├── To-do.md                 # The 9 target features (source of truth for scope)
├── Project-Journal.md       # Agent's running log of what it built and what broke
├── references/              # Reference screenshots used to inspire the UI
│   ├── cdg-logo.png
│   └── light-theme.png
├── backend/
│   ├── main.py               # FastAPI app — 7 endpoints, all reading from mock_db.json
│   └── mock_db.json          # The entire "database" for this MVP
└── frontend/
    ├── src/
    │   ├── App.jsx                    # Top-level layout, nav, theme + language switchers
    │   ├── i18n.js                    # EN/HI/PA translation strings (react-i18next)
    │   ├── components/
    │   │   ├── BootupAnimation.jsx    # Matrix-style boot screen shown on load
    │   │   ├── theme-provider.jsx     # Light/dark mode context (persists to localStorage)
    │   │   └── ui/button.jsx          # shadcn/ui Button primitive
    │   └── components/views/          # One file per left-nav section (see table below)
    ├── public/                        # Logo, favicon, icon sprite
    ├── package.json
    └── vite.config.js
```

---

## 3. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend framework | React 19 + Vite 8 | JS only, no TypeScript |
| Styling | Tailwind CSS v3 + shadcn/ui | **Deliberately downgraded from Tailwind v4** — see `Project-Journal.md` for why |
| Icons | lucide-react | |
| Animation | framer-motion | Used only in `BootupAnimation.jsx` |
| i18n | i18next / react-i18next | English, Hindi, Punjabi — hardcoded string tables in `src/i18n.js`, no external translation service |
| Network graph | react-force-graph-2d | Used in `NetworkGraph.jsx` |
| Routing | react-router-dom is installed but **not used** — navigation is done via `useState` in `App.jsx`, not routes |
| Linting | oxlint | Config in `.oxlintrc.json` |
| Backend framework | FastAPI + Uvicorn | No auth, no DB, no ORM |
| "Database" | A single `mock_db.json` file read from disk on every request | No persistence of writes — there are no write endpoints |

There is **no `requirements.txt` or `pyproject.toml`** in `backend/` yet — see [Section 7](#7-known-gaps--first-things-to-fix).

---

## 4. Running it locally

### Backend

```bash
cd backend
pip install fastapi uvicorn          # no requirements.txt yet — see Section 7
uvicorn main:app --reload --port 8000
```

Verify it's up: `curl http://localhost:8000/` → `{"status": "ok", "message": "Welcome to DarKnight API"}`

### Frontend

```bash
cd frontend
npm install
npm run dev        # Vite dev server, default http://localhost:5173
```

Open the printed localhost URL. The frontend expects the backend at **`http://localhost:8000`** — this is hardcoded (not an env var) in every view component that fetches data. If you run the backend on a different port, the dashboard will just show its loading/empty state.

Other scripts: `npm run build`, `npm run preview`, `npm run lint`.

---

## 5. Feature map — spec → screen → API

| To-do.md feature | Left-nav screen | Component | Backend endpoint(s) |
|---|---|---|---|
| 4. Interactive Intelligence Dashboard | Dashboard | `DashboardOverview.jsx` | `GET /api/dashboard/summary` |
| 1. Multi-Source Data Collection | Data Collection Status | `DataCollectionStatus.jsx` | **None — fully hardcoded array in the component, not wired to the backend at all** |
| 6. Automated Alert Generation + 3. Suspicious Activity Detection | Alerts & Suspicious Activity | `AlertsFeed.jsx` | `GET /api/alerts`, `GET /api/alerts/suspicious` |
| 5. Network Visualization + 2. Intelligent Entity Correlation | Network Visualization | `NetworkGraph.jsx` | `GET /api/network/data` |
| 7. Search & Investigation Support | Search & Investigation | `SearchInvestigation.jsx` | `GET /api/search?q=` (substring match on `identifier` field only) |
| 8. Reporting & Evidence Management | Reports & Evidence | `ReportingEvidence.jsx` | `GET /api/reports` (list only — "Generate New Report" and "PDF" buttons are non-functional) |
| 9. Security & Access Control | Security & Access Control | `AccessControl.jsx` | **None — entirely static markup, no backend, no real session/auth** |

All fetches use plain `fetch()` with no loading/error UI beyond a basic spinner or `console.error`, and no retry logic.

---

## 6. What's NOT real (read this before you demo it)

Because this was vibecoded quickly to prove out the UI, a few things look functional but aren't. Worth knowing so nobody accidentally represents this as production-ready to police leadership:

- **No actual data collection.** Nothing crawls darknet markets, forums, or blockchains. `mock_db.json` is static, hand-written sample data (some timestamps are dated November 2023).
- **No entity correlation logic.** The network graph renders whatever nodes/edges are hardcoded in `mock_db.json` — there's no algorithm linking wallets, aliases, or channels.
- **No anomaly/suspicious-activity detection.** The "AI-driven detection" copy in `AlertsFeed.jsx` is UI text; the underlying data is a fixed list of pre-written events.
- **No authentication or authorization.** `AccessControl.jsx` displays "Clearance Level: Top Secret (Tier 1)" and a "Secure Logout" button, but there is no login flow, no session, no user model, and no role enforcement anywhere in the app or API. `CORSMiddleware` is open to `*` origins ("For dev only" per the code comment).
- **No report generation.** "Generate New Report" and PDF download buttons in `ReportingEvidence.jsx` have no click handlers.
- **Search is a substring match**, not the "advanced search" the copy implies — `q.lower() in r["identifier"].lower()` in `backend/main.py`.
- **The 3-panel layout from `DESIGN.md` isn't fully implemented.** The design brief calls for left (nav) → middle (details) → right (deep-dive) panels. The current `App.jsx` only implements a left nav + a single main content panel; there's no third panel yet.
- **No tests, no CI, no linting gate.** `oxlint` is configured but not wired into any pipeline.
- **No `.env` / environment config.** The API base URL (`http://localhost:8000`) is hardcoded in six different component files rather than centralized.

---

## 7. Known gaps / first things to fix

If you're picking this up to move past MVP, roughly in priority order:

1. **Centralize the API base URL** into a single config/env var (`VITE_API_BASE_URL`) instead of repeating `http://localhost:8000` in every view file.
2. **Add `backend/requirements.txt`** (or a `pyproject.toml`) pinning `fastapi`, `uvicorn`, etc. — currently undocumented.
3. **Decide on real data sources / connectors** for Section 1 (Multi-Source Data Collection) — this is currently the least-implemented feature (not even wired to mock data).
4. **Add authentication** before this touches anything resembling real investigative data — currently zero auth on API or frontend.
5. **Implement the third (right) panel** called for in `DESIGN.md`, or update the design doc if the two-panel layout is the accepted direction going forward.
6. **Replace the in-memory JSON "DB"** with a real datastore once write operations (creating reports, flagging entities, audit logs) are needed.
7. **Add tests** — there are currently none on either frontend or backend.
8. **Wire `oxlint` into CI** so lint issues are caught before merge.
9. **Fill in real translations** — the Hindi/Punjabi strings in `src/i18n.js` cover only nav labels and a handful of headings; most body copy is still English-only inside the JSX.

---

## 8. Design constraints to keep in mind (from `DESIGN.md`)

- Tone must stay professional/clean — explicitly **not** "whimsical or bloated." (The Matrix-style boot animation is a stated exception the design brief allows for flavor, not a green light to add more of that elsewhere.)
- Light **and** dark mode required (implemented via `theme-provider.jsx`, persisted under the `darknight-theme` localStorage key).
- English/Hindi/Punjabi language switching must be **functionally real**, not a dummy toggle (implemented via `i18n.js` — see gap #9 above on translation completeness).
- Alert/status severity should always map to green/yellow/red.
- Colors should be low-eye-strain for long shifts — no large blocks of high-saturation color.
- Reference assets for visual direction live in `references/` (`light-theme.png`, `cdg-logo.png`).

---

## 9. History / provenance

This app was built by an AI coding agent working from `AGENTS.md` + `DESIGN.md` + `To-do.md` as its spec. `Project-Journal.md` is the agent's own log of what it built each phase and the bugs it hit along the way (e.g., a Tailwind v4 → v3 downgrade to fix a shadcn/ui init failure). It's worth skimming once if something in the styling setup looks unusual — the reasoning is documented there rather than in code comments.

The app has been renamed at least once (`Kala Jaddu` → `DarKnight`); grep for both terms if you're hunting for stale references anywhere outside this README.