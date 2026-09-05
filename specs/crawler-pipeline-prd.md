# Dark Knight — Crawler Pipeline PRD
### For AI Agent Execution — Hackathon Build (Normal Web, Darknet-Ready Architecture)

---

## ⛔ CRITICAL CONSTRAINTS — READ FIRST

```
1. All cyber/dark web experimentation must be conducted in isolated VMs/sandboxed
   environments. This applies to any Tor-adjacent code paths, even stubs.

2. Unauthorized scanning, exploitation, intrusion, or attacks on any live
   system/network are strictly prohibited. No exceptions for "research purposes."

3. Actual stolen credentials, PII, illicit transactions, malware, or contraband
   content must NEVER be downloaded, stored, or displayed. If a crawl target
   would require crossing this line, the collector must refuse and log why.

4. Only synthetic, mock, or legally obtained and sanitized OSINT data may be used
   for demonstrations. No live .onion requests, no real darknet marketplace
   access, ever — enforced at the code level, not just documented.

5. The Tor collector is an ARCHITECTURE STUB ONLY. Any attempt to open a real
   Tor/.onion connection must raise `DemoModeEnforcedError` and halt — this is a
   hard error, not a warning, and cannot be disabled via config in this build.

6. No CAPTCHA-solving, no CAPTCHA bypass logic anywhere in this codebase.

7. Every record produced by any collector MUST carry full provenance metadata
   (source URL, fetch timestamp, run ID, content hash) before it is considered
   valid output — a record without provenance is a bug, not a warning.

8. Maintain version-controlled repositories with meaningful development history.

9. The crawler NEVER writes directly into the platform's fixed Entity/
   Observation/Transaction schema. It emits a `RawRecord` intermediate format
   only — schema mapping is owned by a separate AI mapping component (built by
   another team member) and is out of scope for this PRD.
```

---

## Design Philosophy: Darknet-Ready, Not Darknet-Built

This pipeline crawls the **normal, legal, public web** for the hackathon demo. It is deliberately architected so that a future darknet-capable version requires swapping components, not rebuilding the system. This is achieved by:

- A `BaseCollector` interface every source type implements identically, regardless of what it crawls.
- **Transport is injected, not hardcoded.** Every collector receives an HTTP client object at construction time rather than importing `httpx` and configuring it inline. Swapping a plain client for a Tor-proxied SOCKS5 client is a one-line config change, not a rewrite.
- The registry, scheduler, cleaning/dedup, relevance filtering, entity extraction, and evidence-tagging layers are entirely source-agnostic — they operate on `RawRecord` objects and have no knowledge of where the data came from.
- The **only** genuinely new work required to add real Tor support later is: (a) the Tor-proxied transport client, (b) circuit rotation logic, (c) a CAPTCHA human-review queue, (d) a dead-link/mirror monitor tuned for .onion volatility. None of these touch the rest of the pipeline.

This is the answer to give if asked how this becomes a real darknet crawler: the architecture already supports it — only the transport and a couple of Tor-specific modules would need to be added.

---

## Stack

- **Language:** Python 3.11+
- **Framework:** FastAPI (crawler management API)
- **Database:** PostgreSQL
- **Orchestration:** Prefect (falls back to APScheduler if Prefect setup time is tight)
- **HTTP client:** `httpx`
- **HTML → text extraction:** `trafilatura`
- **NLP/Entity extraction:** spaCy
- **Language detection:** `langdetect` or `fasttext`
- **Discovery:** Google Custom Search JSON API
- **AI relevance classification:** LLM API call (Claude/GPT), behind a swappable interface
- **robots.txt parsing:** `urllib.robotparser` (stdlib)
- **Testing:** pytest + httpx `AsyncClient`

---

## Project Structure

```
crawler/
├── collectors/
│   ├── base.py                 # BaseCollector ABC — fetch(source_config) -> RawRecord
│   ├── google_discovery.py     # Google Custom Search based discovery collector
│   ├── direct_seed.py          # Direct URL fetch collector (fallback path)
│   ├── bitcoin.py              # Stretch goal — public blockchain collector
│   ├── telegram.py             # Stretch goal — public channel collector
│   └── tor_stub.py             # Architecture stub only — raises DemoModeEnforcedError
├── policy/
│   ├── robots_checker.py       # robots.txt fetch + cache + allow/deny check
│   └── rate_limiter.py         # Per-domain configurable crawl delay
├── pipeline/
│   ├── cleaner.py              # Boilerplate stripping, main-content extraction
│   ├── dedup.py                # Content-hash based deduplication
│   ├── language.py             # Language detection (+ optional translation)
│   ├── relevance_filter.py     # Keyword pre-filter (cheap, first pass)
│   ├── relevance_classifier.py # RelevanceClassifier interface + LLMRelevanceClassifier impl
│   └── entity_extractor.py     # spaCy NER + regex candidate extraction
├── keywords/
│   ├── models.py                # Keyword, CaseKeyword DB models
│   └── service.py                # Add/remove/list keywords, global + case-scoped
├── evidence/
│   └── tagging.py               # Enforces provenance metadata on every RawRecord
├── orchestration/
│   ├── flows.py                 # Prefect flows, parameterized by (source_type, case_id)
│   └── scheduler.py             # Poll-interval scheduling per source
├── api/
│   └── routers/
│       ├── sources.py           # CRUD + enable/disable + manual trigger
│       ├── keywords.py          # Keyword/watchlist management endpoints
│       └── activity.py          # Paginated crawler activity feed
├── models/
│   ├── source.py                # Source DB model
│   ├── raw_record.py            # RawRecord DB model — the output contract
│   └── crawler_run.py           # CrawlerRun DB model — one row per scheduled/manual run
└── tests/
```

---

## Source Types

```
SOURCE TYPES (this build → future darknet build):

Type                    | Status this build      | Transport
------------------------|-------------------------|---------------------------
GOOGLE_SEARCH_DISCOVERY | Fully built             | Direct HTTPS
DIRECT_SEED             | Fully built (fallback)  | Direct HTTPS
BITCOIN_CHAIN           | Stretch goal            | Direct HTTPS (public API)
TELEGRAM_PUBLIC         | Stretch goal            | Direct HTTPS (Telegram API)
EXTERNAL_API            | Design-only this build  | Direct HTTPS (police-provided)
EXTERNAL_DB             | Design-only this build  | Read-only DB connection
TOR_STUB                | Stub only — hard error  | N/A — DemoModeEnforcedError
```

---

## Database Models

### sources
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
name                TEXT NOT NULL
source_type         TEXT NOT NULL            -- matches Source Types table
config              JSONB NOT NULL           -- query terms, base_url, api params, etc.
poll_interval_seconds INTEGER NOT NULL DEFAULT 60
crawl_delay_seconds  NUMERIC DEFAULT 1.0      -- per-domain adjustable crawl intensity
is_active           BOOLEAN DEFAULT true
transport_type      TEXT DEFAULT 'direct'    -- 'direct' | 'tor_proxy' (future)
created_by          UUID REFERENCES users(id)
created_at          TIMESTAMPTZ DEFAULT now()
```

### keywords
```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
term        TEXT NOT NULL
language    TEXT NOT NULL              -- 'en', 'hi', 'pa', etc.
category    TEXT                       -- e.g. 'substance', 'slang', 'marketplace_term'
is_global   BOOLEAN DEFAULT true
created_by  UUID REFERENCES users(id)
created_at  TIMESTAMPTZ DEFAULT now()
```

### case_keywords
```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
case_id     UUID NOT NULL
keyword_id  UUID REFERENCES keywords(id)
is_active   BOOLEAN DEFAULT true
added_by    UUID REFERENCES users(id)
added_at    TIMESTAMPTZ DEFAULT now()
UNIQUE(case_id, keyword_id)
```

### crawler_runs
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
source_id           UUID REFERENCES sources(id)
case_id             UUID                      -- nullable for non-case-scoped runs
status              TEXT NOT NULL             -- RUNNING | COMPLETED | FAILED
started_at          TIMESTAMPTZ DEFAULT now()
finished_at         TIMESTAMPTZ
urls_attempted      INTEGER DEFAULT 0
urls_skipped_robots INTEGER DEFAULT 0
records_produced    INTEGER DEFAULT 0
records_relevant    INTEGER DEFAULT 0
errors_count        INTEGER DEFAULT 0
error_summary       TEXT
triggered_by        UUID REFERENCES users(id)  -- null if scheduled, not manual
```

### raw_records — the output contract
```sql
id                    UUID PRIMARY KEY DEFAULT gen_random_uuid()
run_id                UUID REFERENCES crawler_runs(id)
source_id             UUID REFERENCES sources(id)
case_id               UUID
url                    TEXT NOT NULL
fetched_at             TIMESTAMPTZ NOT NULL
raw_text               TEXT
cleaned_text           TEXT
content_hash           TEXT NOT NULL           -- SHA-256, evidence integrity
language               TEXT
matched_keywords       JSONB                   -- list of keyword terms matched
relevance_label        TEXT                    -- 'relevant' | 'medical_legitimate' | 'unrelated'
relevance_confidence   NUMERIC
relevance_reasoning    TEXT                    -- LLM's stated reasoning, kept for audit
extracted_candidates   JSONB                   -- [{type, value, confidence}] from spaCy/regex
status                 TEXT NOT NULL DEFAULT 'pending_mapping'
                                              -- pending_mapping | mapped | review_queue | discarded
created_at             TIMESTAMPTZ DEFAULT now()

-- NEVER written directly into Entity/Observation/Transaction — that mapping
-- is owned by a separate AI mapping component consuming this table.
```

### robots_cache
```sql
domain      TEXT PRIMARY KEY
allowed_paths_summary JSONB
checked_at  TIMESTAMPTZ DEFAULT now()
ttl_hours   INTEGER DEFAULT 24
```

---

## Features

---

### C-01 — Source Registry & Collector Interface

**What:** Every crawlable target is a row in `sources`, typed by `source_type`. All collectors implement one shared interface so the scheduler, cleaning, and downstream pipeline never need to know what kind of source produced a record. This is the seam that makes the pipeline "darknet-ready" without being darknet-built.

**Build:**
- `BaseCollector` ABC: `async def fetch(self, source_config: dict, transport: HTTPTransport) -> list[RawRecord]`
- `HTTPTransport` wrapper class injected into every collector at construction — `DirectHTTPTransport` implemented now, `TorProxyTransport` left as an unimplemented stretch stub
- `CollectorRegistry` — maps `source_type` string → collector class, used by the scheduler to instantiate the right collector per source
- `POST /sources`, `GET /sources`, `PATCH /sources/{id}` (enable/disable, edit config) — Super Admin / Supervisor / Investigating Officer per existing RBAC roles

**Test:** Assert every implemented collector conforms to `BaseCollector`. Assert `CollectorRegistry` resolves the correct class for each `source_type`. Assert disabling a source excludes it from the next scheduler pass.

---

### C-02 — Keyword & Watchlist Management

**What:** A global default watchlist (drug-related terms, marketplace terminology, regional slang in Hindi/Punjabi/English) plus per-case overrides so an Investigating Officer can scope a crawl to what their specific investigation cares about, without editing the global list.

**Build:**
- `KeywordService` — `add_global(term, language, category)`, `add_case_keyword(case_id, keyword_id)`, `remove_case_keyword(case_id, keyword_id)`, `get_active_keywords(case_id) -> list[str]` (merges global + case-active, excludes case-deactivated)
- `POST /keywords`, `GET /keywords`, `POST /cases/{case_id}/keywords`, `DELETE /cases/{case_id}/keywords/{keyword_id}`
- Seed script populating an initial global watchlist across English/Hindi/Punjabi

**Test:** Assert `get_active_keywords` correctly merges global + case-scoped and respects `is_active`. Assert non-Investigating-Officer+ roles cannot edit case keywords (per existing permission matrix). Assert removing a case keyword doesn't affect the global list.

---

### C-03 — Google Search Discovery Layer

**What:** Rather than crawling blindly, the pipeline builds search queries from a case's active keywords and uses the Google Custom Search JSON API (official, authorized, ToS-compliant — not scraped SERP HTML) to discover candidate URLs to fetch.

**Build:**
- `GoogleDiscoveryCollector(BaseCollector)` — builds queries from `KeywordService.get_active_keywords(case_id)`, paginates through Custom Search API results, returns candidate URLs + snippets
- Config: `GOOGLE_CSE_API_KEY`, `GOOGLE_CSE_CX` (search engine ID) in env
- Query budget tracking — log remaining daily quota, warn when close to the free-tier limit (100/day) so a live demo doesn't silently run dry
- `DirectSeedCollector(BaseCollector)` — fallback: fetches a fixed list of seed URLs directly, bypassing Search API, for demo resilience if quota is exhausted

**Test:** Assert queries are built only from active keywords for the given case. Assert quota-exceeded response is caught and logged, not raised as an unhandled crash. Assert fallback seed collector works independently of the Search API being available.

---

### C-04 — Robots.txt Policy Check & Crawl Delay

**What:** Before any URL is fetched, the crawler checks whether it's permitted to fetch that path under the target domain's `robots.txt`. Disallowed URLs are skipped and logged, never fetched. A configurable per-domain delay prevents hammering any single site (and protects the Google API quota and demo stability from self-inflicted bans).

**Build:**
- `RobotsChecker` — fetches and parses `robots.txt` via `urllib.robotparser`, caches result in `robots_cache` with a TTL (avoid re-fetching robots.txt on every single URL from the same domain)
- `RateLimiter` — per-domain delay enforcement, default from `source.crawl_delay_seconds`, minimum floor enforced in code (cannot be set to 0 — "adjustable crawl intensity," not "no limits")
- Every fetch attempt passes through `RobotsChecker.is_allowed(url)` before hitting the network

**Test:** Assert disallowed paths are never fetched and are logged with reason `robots_disallowed`. Assert `robots_cache` is used instead of re-fetching within TTL. Assert crawl delay cannot be configured below the enforced floor.

---

### C-05 — Fetch Layer & Dead Link Handling

**What:** The actual HTTP fetch, with retry/backoff and graceful handling of dead or consistently failing URLs — so one bad target doesn't stall or crash a whole crawl run.

**Build:**
- `DirectHTTPTransport` — `httpx.AsyncClient` wrapper, identifiable `User-Agent`, configurable timeout, retry-with-exponential-backoff (max 3 attempts)
- Dead link tracking: increment a fail counter per URL; after N consecutive failures, mark inactive and stop retrying on future runs
- All fetch outcomes (success, timeout, 4xx, 5xx, dead-link-skip) logged to the current `crawler_run`

**Test:** Assert retry occurs on transient failure and stops after max attempts. Assert a URL marked dead is excluded from subsequent runs. Assert a single failed URL does not abort the rest of the run.

---

### C-06 — Content Cleaning, Deduplication & Language Detection

**What:** Raw fetched HTML gets reduced to clean, usable text; duplicate content (same page re-fetched, or the same content mirrored elsewhere) is caught before it wastes downstream processing; non-English content is tagged so it can be handled appropriately.

**Build:**
- `ContentCleaner` — `trafilatura`-based main-content extraction, strips nav/ads/footers
- `Deduplicator` — SHA-256 hash of cleaned content, checked against existing `raw_records.content_hash` before proceeding further in the pipeline
- `LanguageDetector` — tags each record's detected language; translation is a stretch goal, not required for the base demo

**Test:** Assert boilerplate (nav/footer text) is not present in `cleaned_text`. Assert a byte-identical duplicate is detected and skipped before relevance filtering. Assert language detection produces a reasonable tag on known English/Hindi samples.

---

### C-07 — Relevance Pre-Filter (Keyword Matching)

**What:** A cheap, fast first-pass filter — does the cleaned text contain any of the case's active keywords at all? This runs before the more expensive AI classification step, so obviously irrelevant content never reaches the LLM call.

**Build:**
- `KeywordMatcher.match(text, active_keywords) -> list[str]` — returns matched terms
- Records with zero keyword matches are marked `status='discarded'` immediately with reason `no_keyword_match`, skipping the rest of the pipeline (no LLM call spent on it)
- Records with at least one match proceed to C-08 with `matched_keywords` populated

**Test:** Assert a record with no keyword matches never reaches the relevance classifier (mock-assert the classifier is not called). Assert matched terms are correctly recorded on the `raw_record`.

---

### C-08 — AI Relevance Classification Layer

**What:** Keyword matching alone can't distinguish a trafficking discussion from a medical/legitimate mention of the same term (e.g. "fentanyl" appears in both a marketplace post and a pharmacology article). This stage uses an LLM to classify keyword-matched content into relevant / medical-legitimate / unrelated, with confidence and reasoning, before entity extraction runs on it.

**Build:**
- `RelevanceClassifier` interface — `classify(text: str) -> RelevanceResult(label, confidence, reasoning)` — the swappable seam
- `LLMRelevanceClassifier(RelevanceClassifier)` — the implementation used for this build; single structured-output LLM call per keyword-matched record only (not per raw fetch — C-07 already filtered the volume down)
- `TrainedRelevanceClassifier(RelevanceClassifier)` — interface stub only, not implemented this build; documented as the intended swap-in path if a labeled dataset becomes available later
- Routing logic: `relevant` → proceed to entity extraction; `medical_legitimate` / `unrelated`, low confidence → `status='review_queue'` (never silently deleted); high-confidence `unrelated` → `status='discarded'` but retained in DB, not purged

**Test:** Assert the classifier interface can be swapped via config without touching pipeline code (test with a mock second implementation). Assert low-confidence results are routed to `review_queue`, not auto-discarded. Assert `relevance_reasoning` is always populated and stored for audit.

---

### C-09 — Entity Extraction

**What:** Runs only on content that passed relevance classification as relevant. Extracts candidate entities — names, locations, organizations via spaCy NER, plus wallet-address-shaped strings and phone numbers via regex — as unconfirmed candidates, not final schema objects.

**Build:**
- `EntityExtractor.extract(text) -> list[Candidate(type, value, confidence)]`
- spaCy pipeline (`en_core_web_sm` or larger if time allows) for NER
- Regex patterns for BTC/ETH-shaped wallet addresses, phone number formats
- Output written to `raw_records.extracted_candidates` — explicitly candidates, confidence-tagged, not asserted as fact

**Test:** Assert known entity types are extracted from sample text with reasonable recall. Assert wallet-address regex matches valid formats and rejects obviously malformed strings. Assert extraction only runs on `relevance_label='relevant'` records.

---

### C-10 — Evidence Metadata & Provenance Tagging

**What:** Every `raw_record`, regardless of source or outcome, carries the metadata needed to trace it back to its origin for court proceedings: exact source URL, fetch timestamp, which crawler run produced it, and a content hash proving what was actually collected. This is enforced, not optional.

**Build:**
- `EvidenceTagger` — validation step run before any `raw_record` is persisted; rejects/errors if `url`, `fetched_at`, `run_id`, or `content_hash` is missing
- `content_hash` computed via SHA-256 over the raw fetched bytes, before any cleaning — proves what was actually retrieved, matching the artifact-hashing pattern already used in the Security & Access Control module
- Applied uniformly across every collector via a shared post-fetch hook, not re-implemented per collector

**Test:** Assert a `RawRecord` missing any required provenance field fails validation and is never persisted. Assert `content_hash` is computed over raw content, not cleaned content (so it reflects exactly what was fetched).

---

### C-11 — RawRecord Output Contract & Handoff

**What:** The crawler's final output is a stable, source-agnostic `RawRecord` — it does not write into the platform's fixed `Entity` / `Observation` / `Transaction` schema. A separate AI-driven schema-mapping component (owned by another team member) consumes `raw_records` and performs that mapping.

**Build:**
- `raw_records` table is the contract boundary — documented schema, versioned, additive-only changes going forward
- `GET /raw-records?status=pending_mapping` — read endpoint the mapping component polls or subscribes to
- No write path anywhere in this codebase touches `entities`, `observations`, or `transactions` tables

**Test:** Assert no code path in the crawler package imports or writes to `Entity`/`Observation`/`Transaction` models. Assert `GET /raw-records` correctly filters by status.

---

### C-12 — Multi-Instance Orchestration

**What:** Crawls run as scheduled or manually-triggered flows, each parameterized by `(source, case_id)` so that different investigations don't share keyword scope or cross-contaminate results, and multiple cases can be actively crawled concurrently.

**Build:**
- Prefect flow `run_crawl(source_id, case_id)` — resolves the right collector via `CollectorRegistry`, pulls active keywords for `case_id`, runs fetch → clean → dedup → relevance filter → classify → extract → tag, writes `raw_records`
- Scheduler triggers flows per `source.poll_interval_seconds`, one flow instance per active `(source, case)` pairing
- Manual trigger via API creates a flow run outside the schedule, tagged `triggered_by`

**Test:** Assert two concurrent flow runs for different cases don't leak keyword scope into each other's queries. Assert a manually triggered run is correctly tagged and doesn't duplicate a concurrently scheduled run for the same source/case.

---

### C-13 — Crawler Management API

**What:** The control surface for the Data Collection Status module — list sources, see their state, trigger runs manually, enable/disable.

**Build:**
- `GET /sources` — list with last-run status summary per source
- `POST /sources/{id}/trigger` — manual run trigger
- `PATCH /sources/{id}` — enable/disable, edit poll interval / crawl delay
- Role-gated per existing permission matrix (Data Collection Status module: SuperAdmin RW, Supervisor R, Data Engineer RW)

**Test:** Assert `POST /sources/{id}/trigger` creates a new `crawler_run` row. Assert disabled sources report correctly in `GET /sources` and are excluded from the scheduler.

---

### C-14 — Crawler Activity Feed

**What:** A paginated, filterable feed of recent crawler activity — what ran, when, how many records, how many were skipped and why — powering a live-updating section in the Data Collection Status UI (replacing the currently hardcoded frontend array).

**Build:**
- `GET /crawler/activity?page=&page_size=&source_id=&case_id=` — returns `crawler_runs` newest-first, joined with source name, with counts (`urls_attempted`, `urls_skipped_robots`, `records_produced`, `records_relevant`, `errors_count`)
- Default page size sane for UI (e.g. 20), max enforced server-side to prevent unbounded queries

**Test:** Assert pagination returns correct page boundaries and total count. Assert filtering by `case_id` only returns that case's runs. Assert response ordering is newest-first.

---

## Out of Scope / Stretch Goals (This Build)

```
- Tor/.onion live collector       — stub only, DemoModeEnforcedError enforced,
                                     not to be implemented this build
- CAPTCHA queue                    — not built; no CAPTCHA-solving/bypass logic
- Bitcoin blockchain collector     — stretch goal if time remains, public-data
                                     only, no additional legal risk
- Telegram public channel scraper — stretch goal if time remains
- Translation of non-English text — language detection only is required;
                                     translation is a nice-to-have
- TrainedRelevanceClassifier       — interface defined, not implemented;
                                     LLM classifier is the build target
- EXTERNAL_API / EXTERNAL_DB       — designed at the schema/interface level
  collectors (police-provided)     only; not required for hackathon demo
```

---

## Global Testing Rules

```
1. pytest is the only test runner
2. Use pytest-asyncio for async tests, httpx AsyncClient for API requests
3. Every collector test must cover: success case, robots.txt-disallowed case,
   dead-link case, and empty-result case
4. LLM-dependent tests (C-08) must mock the LLM call — no live API calls in CI
5. No test may assume the Google Custom Search API is reachable — mock it
6. Evidence metadata tests (C-10) must assert rejection on missing fields,
   not just presence on the happy path
7. Any endpoint that triggers a crawl must have a test asserting the correct
   crawler_run row is created with the right case_id/source_id
```

---

## Environment Variables (.env.example)

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/darknight

# Google Custom Search
GOOGLE_CSE_API_KEY=change-this
GOOGLE_CSE_CX=change-this
GOOGLE_CSE_DAILY_QUOTA=100

# LLM Relevance Classifier
LLM_API_KEY=change-this
LLM_MODEL=change-this
RELEVANCE_CLASSIFIER_IMPL=llm          # llm | trained (trained not implemented yet)

# Crawl behavior
DEFAULT_CRAWL_DELAY_SECONDS=1.5
MIN_CRAWL_DELAY_SECONDS=0.5            # hard floor — cannot be configured to 0
DEFAULT_USER_AGENT=DarkKnightCrawler/1.0 (+contact info)
DEAD_LINK_FAILURE_THRESHOLD=5

# Orchestration
PREFECT_API_URL=http://localhost:4200/api

# Safety
DEMO_MODE_ENFORCED=true                # hard-coded true in this build, not
                                        # overridable via env in code
```

---

## Build Order (Sequential)

```
1. DB models → sources, keywords, case_keywords, crawler_runs, raw_records,
   robots_cache
2. C-01 Source Registry & Collector Interface (BaseCollector, transport
   injection, tor_stub raising DemoModeEnforcedError)
3. C-04 Robots.txt Policy Check & Crawl Delay
4. C-05 Fetch Layer & Dead Link Handling
5. C-03 Google Search Discovery Layer (+ DirectSeedCollector fallback)
6. C-06 Content Cleaning, Deduplication & Language Detection
7. C-02 Keyword & Watchlist Management
8. C-07 Relevance Pre-Filter (Keyword Matching)
9. C-08 AI Relevance Classification Layer (LLMRelevanceClassifier)
10. C-09 Entity Extraction
11. C-10 Evidence Metadata & Provenance Tagging
12. C-11 RawRecord Output Contract & Handoff (coordinate schema with the
    AI-mapping team member before this step)
13. C-12 Multi-Instance Orchestration (Prefect flows)
14. C-13 Crawler Management API
15. C-14 Crawler Activity Feed
```
