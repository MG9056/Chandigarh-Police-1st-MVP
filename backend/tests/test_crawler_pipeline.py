import asyncio
from datetime import datetime, timezone, timedelta
import os
import pytest
from fastapi.testclient import TestClient
import json as json_module
from database import engine, Base, SessionLocal
from main import app
from models import User, RoleEnum, AccountStatusEnum
from security import hash_password, create_access_token
from crawler.collectors.base import DemoModeEnforcedError
from crawler.collectors.tor_stub import TorStubCollector
from crawler.collectors.transport import DirectHTTPTransport, TorProxyTransport
from crawler.collectors.registry import CollectorRegistry
from crawler.collectors.google_discovery import GoogleDiscoveryCollector
from crawler.collectors.direct_seed import DirectSeedCollector
from crawler.policy.robots_checker import RobotsChecker
from crawler.policy.rate_limiter import RateLimiter, MIN_CRAWL_DELAY_SECONDS
from crawler.keywords.service import KeywordService
from crawler.pipeline.cleaner import ContentCleaner
from crawler.pipeline.dedup import Deduplicator
from crawler.pipeline.language import LanguageDetector
from crawler.pipeline.relevance_filter import KeywordMatcher
from crawler.pipeline.relevance_classifier import LLMRelevanceClassifier
from crawler.pipeline.entity_extractor import EntityExtractor
from crawler.evidence.tagging import EvidenceTagger
from crawler.models.source import Source
from crawler.models.crawler_run import CrawlerRun
from crawler.models.raw_record import RawRecord
from crawler.orchestration.flows import run_crawl


@pytest.fixture(autouse=True)
def setup_db():
    os.environ["TESTING"] = "1"
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Seed Admin User if not existing
    admin = db.query(User).filter(User.email == "admin_crawler@chandigarhpolice.gov.in").first()
    if not admin:
        admin = User(
            email="admin_crawler@chandigarhpolice.gov.in",
            full_name="Crawler Admin",
            password_hash=hash_password("AdminPass123!"),
            role=RoleEnum.SUPER_ADMIN,
            account_status=AccountStatusEnum.ACTIVE,
        )
        db.add(admin)
        db.commit()

    yield db

    db.close()


@pytest.fixture
def auth_headers(setup_db):
    db = setup_db
    user = db.query(User).filter(User.email == "admin_crawler@chandigarhpolice.gov.in").first()
    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


# ----------------------------------------------------
# C-01 & Constraint 5: Demo Mode Enforcement & Registry
# ----------------------------------------------------

def test_demo_mode_enforcement():
    async def _inner():
        collector = TorStubCollector()
        with pytest.raises(DemoModeEnforcedError):
            await collector.fetch({}, None)

        transport = TorProxyTransport()
        with pytest.raises(DemoModeEnforcedError):
            await transport.get("http://example.onion")

    asyncio.run(_inner())


def test_collector_registry():
    c1 = CollectorRegistry.get_collector("GOOGLE_SEARCH_DISCOVERY")
    assert isinstance(c1, GoogleDiscoveryCollector)

    c2 = CollectorRegistry.get_collector("DIRECT_SEED")
    assert isinstance(c2, DirectSeedCollector)

    c3 = CollectorRegistry.get_collector("TOR_STUB")
    assert isinstance(c3, TorStubCollector)


# ----------------------------------------------------
# C-02: Keyword & Watchlist Management
# ----------------------------------------------------

def test_keyword_service_and_scoping(setup_db):
    db = setup_db

    # Seed initial global keywords
    kws = KeywordService.get_active_keywords(db)
    assert len(kws) > 0

    # Add global keyword
    kw_global = KeywordService.add_global(db, term="fentanyl_test", language="en")
    assert "fentanyl_test" in KeywordService.get_active_keywords(db)

    # Add case keyword override
    case_id = "CASE-101"
    ck = KeywordService.add_case_keyword(db, case_id=case_id, keyword_id=str(kw_global.id))
    assert "fentanyl_test" in KeywordService.get_active_keywords(db, case_id=case_id)

    # Remove case keyword override
    KeywordService.remove_case_keyword(db, case_id=case_id, keyword_id=str(kw_global.id))
    active_for_case = KeywordService.get_active_keywords(db, case_id=case_id)
    assert "fentanyl_test" not in active_for_case


# ----------------------------------------------------
# C-04: Robots.txt & Rate Limiter Floor
# ----------------------------------------------------

def test_robots_checker_and_rate_limiter(setup_db):
    async def _inner():
        db = setup_db
        checker = RobotsChecker()

        class MockTransport:
            async def get(self, url):
                return {"status_code": 200, "text": "User-agent: *\nAllow: /public\nDisallow: /admin"}

        is_ok = await checker.is_allowed("https://example.com/public", "DarkKnightCrawler/1.0", db, transport=MockTransport())
        assert is_ok is True

        limiter = RateLimiter(default_delay=0.1)
        effective_delay = limiter.get_effective_delay(0.1)
        assert effective_delay >= MIN_CRAWL_DELAY_SECONDS

    asyncio.run(_inner())



# ----------------------------------------------------
# C-06: Content Cleaning, Deduplication & Language
# ----------------------------------------------------

def test_cleaner_dedup_and_language(setup_db):
    db = setup_db

    raw_html = "<html><body><script>alert(1)</script><h1>Heroin Sale</h1><p>Contact for stealth delivery.</p></body></html>"
    cleaned = ContentCleaner.clean(raw_html)
    assert "Heroin Sale" in cleaned

    content_hash = Deduplicator.compute_hash(raw_html)
    assert Deduplicator.is_duplicate(content_hash, db) is False

    lang_en = LanguageDetector.detect("Heroin sale available in Chandigarh")
    assert lang_en == "en"

    lang_hi = LanguageDetector.detect("चरस और अफीम का व्यापार")
    assert lang_hi == "hi"

    lang_pa = LanguageDetector.detect("ਚਿੱਟਾ ਅਤੇ ਅਫ਼ੀਮ")
    assert lang_pa == "pa"


# ----------------------------------------------------
# C-07 & C-08: Pre-Filter & AI Relevance Classifier
# ----------------------------------------------------

def test_prefilter_and_relevance_classification():
    async def _inner():
        text_illicit = "Buy heroin online with stealth shipping and BTC payment."
        matched, is_passed = KeywordMatcher.match(text_illicit, ["heroin", "cocaine"])
        assert is_passed is True
        assert "heroin" in matched

        matched_none, is_passed_none = KeywordMatcher.match("Regular news about weather in Chandigarh.", ["heroin"])
        assert is_passed_none is False
        assert len(matched_none) == 0

        classifier = LLMRelevanceClassifier()
        res = await classifier.classify(text_illicit, matched)
        assert res.label == "relevant"
        assert res.confidence > 0.5
        assert len(res.reasoning) > 0

    asyncio.run(_inner())


# ----------------------------------------------------
# C-09: Entity Extractor (spaCy + Regex)
# ----------------------------------------------------

def test_entity_extractor():
    extractor = EntityExtractor()

    sample_text = (
        "Vendor John in Chandigarh accepts Bitcoin "
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa and Ethereum "
        "0x71C7656EC7ab88b098defB751B7401B5f6d8976F. "
        "Contact +919876543210."
    )

    candidates = extractor.extract(sample_text)

    types = [c["type"] for c in candidates]
    values = [c["value"] for c in candidates]

    assert "BITCOIN_ADDRESS" in types
    assert (
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        in values
    )

    assert "ETHEREUM_ADDRESS" in types
    assert (
        "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
        in values
    )

    assert "PHONE_NUMBER" in types
    assert "+919876543210" in values
def test_entity_extractor_rejects_numeric_false_positives():
    extractor = EntityExtractor()

    text = (
        "Wikipedia statistics: "
        "123.456.7890 "
        "and 12.3456789 "
        "and 2026.09.05. "
        "No phone number is present here."
    )

    candidates = extractor.extract(text)

    phone_values = [
        c["value"]
        for c in candidates
        if c["type"] == "PHONE_NUMBER"
    ]

    assert phone_values == []
def test_entity_extractor_accepts_common_phone_formats():
    extractor = EntityExtractor()

    text = (
        "Contacts: "
        "+91 9876543210, "
        "+91-9876543210, "
        "(202) 555-0123, "
        "+1 202-555-0123."
    )

    candidates = extractor.extract(text)

    phone_values = {
        c["value"]
        for c in candidates
        if c["type"] == "PHONE_NUMBER"
    }

    assert "+91 9876543210" in phone_values or "+91-9876543210" in phone_values
    assert "(202) 555-0123" in phone_values
    assert "+1 202-555-0123" in phone_values

# ----------------------------------------------------
# C-10: Evidence Provenance Validation
# ----------------------------------------------------

def test_evidence_provenance_tagging():
    record_data = {
        "url": "https://example.com/post/1",
        "fetched_at": datetime.now(timezone.utc),
        "raw_text": "Sample raw content",
    }

    tagged = EvidenceTagger.tag_and_validate(record_data, run_id="run-123")
    assert "content_hash" in tagged
    assert tagged["run_id"] == "run-123"

    bad_record = {"fetched_at": datetime.now(timezone.utc), "raw_text": "text"}
    with pytest.raises(ValueError):
        EvidenceTagger.tag_and_validate(bad_record, run_id="run-123")


# ----------------------------------------------------
# C-11 & C-12: End-to-End Orchestration Flow
# ----------------------------------------------------

def test_end_to_end_crawl_flow(setup_db, monkeypatch):
    async def _inner():
        db = setup_db

        # --------------------------------------------------
        # Mock external HTTP boundary
        # --------------------------------------------------

        class MockTransport:
            async def get(self, url):
                if url.endswith("/robots.txt"):
                    return {
                        "status_code": 200,
                        "text": (
                            "User-agent: *\n"
                            "Allow: /"
                        ),
                    }

                return {
                    "status_code": 200,
                    "text": """
                        <html>
                            <head>
                                <title>Test Intelligence</title>
                            </head>
                            <body>
                                <h1>Heroin Vendor Investigation</h1>
                                <p>
                                    A vendor is offering heroin through
                                    Telegram. Contact +91 9876543210.
                                </p>
                            </body>
                        </html>
                    """,
                }

        mock_transport = MockTransport()

        # run_crawl() uses the imported DirectHTTPTransport
        import crawler.orchestration.flows as flows

        original_transport = flows.DirectHTTPTransport
        flows.DirectHTTPTransport = lambda: mock_transport

        # --------------------------------------------------
        # Mock LLM boundary
        # --------------------------------------------------

        class MockLLMResult:
            label = "relevant"
            confidence = 0.95
            reasoning = (
                "The content describes an illicit drug transaction."
            )

            structured_intelligence = {
                "entities": [
                    {
                        "type": "DRUG",
                        "value": "heroin",
                        "role": "substance",
                        "confidence": 0.99,
                    },
                    {
                        "type": "PHONE_NUMBER",
                        "value": "+91 9876543210",
                        "role": "contact",
                        "confidence": 0.90,
                    },
                ],
                "relationships": [
                    {
                        "subject": "Vendor",
                        "relation": "OFFERS",
                        "object": "heroin",
                        "confidence": 0.94,
                    }
                ],
            }

        class MockClassifier:
            async def classify(
                self,
                text,
                matched_keywords,
                candidates=None,
            ):
                assert "heroin" in text.lower()
                assert "heroin" in matched_keywords

                return MockLLMResult()

        original_classifier = flows.LLMRelevanceClassifier
        flows.LLMRelevanceClassifier = MockClassifier

        try:
            # --------------------------------------------------
            # Create source
            # --------------------------------------------------

            source = Source(
                name="E2E Test Source",
                source_type="DIRECT_SEED",
                transport_type="direct",
                config={
                    "seed_urls": [
                        "https://example.com/drugs"
                    ]
                },
                poll_interval_seconds=30,
                crawl_delay_seconds=0,
                is_active=True,
            )

            db.add(source)
            db.commit()
            db.refresh(source)

            # --------------------------------------------------
            # Create active keyword
            # --------------------------------------------------

            KeywordService.add_global(
                db,
                term="heroin",
                language="en",
            )

            db.query(RawRecord).delete()
            db.commit()

            # --------------------------------------------------
            # Run the REAL orchestration pipeline
            # --------------------------------------------------

            run = await run_crawl(
                source_id=str(source.id),
                case_id="CASE-E2E",
                db=db,
            )

            db.refresh(run)

            # --------------------------------------------------
            # Verify crawl execution
            # --------------------------------------------------

            assert run.status == "COMPLETED"
            assert run.urls_attempted > 0
            assert run.records_produced > 0
            assert run.records_relevant > 0

            # --------------------------------------------------
            # Verify database persistence
            # --------------------------------------------------

            records = (
                db.query(RawRecord)
                .filter(RawRecord.run_id == run.id)
                .all()
            )

            assert len(records) == 1

            record = records[0]

            # --------------------------------------------------
            # Verify raw collection
            # --------------------------------------------------

            assert record.url == "https://example.com/drugs"
            assert record.raw_text
            assert "Heroin Vendor Investigation" in record.raw_text

            # --------------------------------------------------
            # Verify cleaning
            # --------------------------------------------------

            assert record.cleaned_text
            assert "Heroin Vendor Investigation" in record.cleaned_text
            assert "<script>" not in record.cleaned_text

            # --------------------------------------------------
            # Verify evidence / provenance
            # --------------------------------------------------

            assert record.content_hash
            assert record.fetched_at
            assert record.run_id == run.id

            # --------------------------------------------------
            # Verify language detection
            # --------------------------------------------------

            assert record.language == "en"

            # --------------------------------------------------
            # Verify keyword pre-filter
            # --------------------------------------------------

            assert "heroin" in record.matched_keywords

            # --------------------------------------------------
            # Verify LLM relevance classification
            # --------------------------------------------------

            assert record.relevance_label == "relevant"
            assert float(record.relevance_confidence) == pytest.approx(0.95)
            assert record.relevance_reasoning

            # --------------------------------------------------
            # Verify entity extraction
            # --------------------------------------------------

            assert record.extracted_candidates is not None

            candidate_values = [
                candidate["value"]
                for candidate in record.extracted_candidates
            ]

            assert "+91 9876543210" in candidate_values

            # --------------------------------------------------
            # Verify structured AI intelligence
            # --------------------------------------------------

            assert record.structured_intelligence is not None

            intelligence = record.structured_intelligence

            assert "entities" in intelligence
            assert "relationships" in intelligence

            assert intelligence["entities"][0]["type"] == "DRUG"
            assert intelligence["entities"][0]["value"] == "heroin"

            assert (
                intelligence["relationships"][0]["relation"]
                == "OFFERS"
            )

            assert (
                intelligence["relationships"][0]["object"]
                == "heroin"
            )

            # --------------------------------------------------
            # Verify final routing
            # --------------------------------------------------

            assert record.status == "pending_mapping"

        finally:
            flows.DirectHTTPTransport = original_transport
            flows.LLMRelevanceClassifier = original_classifier

    asyncio.run(_inner())
# ----------------------------------------------------
# C-13 & C-14: Management API & Activity Feed
# ----------------------------------------------------

def test_crawler_management_api(auth_headers, setup_db):
    client = TestClient(app)

    # 1. Create Source via API
    resp = client.post(
        "/api/sources",
        json={
            "name": "API Test Source",
            "source_type": "DIRECT_SEED",
            "config": {"seed_urls": ["https://example.com"]},
            "poll_interval_seconds": 60,
            "crawl_delay_seconds": 1.0,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    source_id = resp.json()["id"]

    # 2. List Sources
    resp_list = client.get("/api/sources", headers=auth_headers)
    assert resp_list.status_code == 200
    assert len(resp_list.json()) >= 1

    # 3. Trigger Source Run
    resp_trig = client.post(f"/api/sources/{source_id}/trigger?case_id=CASE-999", headers=auth_headers)
    assert resp_trig.status_code == 200

    # 4. Activity Feed
    resp_act = client.get("/api/crawler/activity", headers=auth_headers)
    assert resp_act.status_code == 200
    data_act = resp_act.json()
    assert "items" in data_act
    assert "total" in data_act

    # 5. Raw Records Endpoint
    resp_raw = client.get("/api/raw-records?status=pending_mapping", headers=auth_headers)
    assert resp_raw.status_code == 200
    assert "items" in resp_raw.json()

def test_google_discovery_success():
    async def _inner():
        os.environ["TAVILY_API_KEY"] = "test-key"

        try:
            collector = GoogleDiscoveryCollector()

            class MockTransport:
                def __init__(self):
                    self.post_called = False
                    self.post_url = None
                    self.post_payload = None

                async def post(self, url, json=None):
                    self.post_called = True
                    self.post_url = url
                    self.post_payload = json

                    return {
                        "status_code": 200,
                        "text": (
                            '{"results": ['
                            '{"title": "Test Result", '
                            '"url": "https://example.com/test", '
                            '"content": "Heroin vendor offering stealth shipping."}'
                            ']}'
                        )
                    }

                async def get(self, url):
                    return {
                        "status_code": 200,
                        "text": "Test page content"
                    }

            transport = MockTransport()

            records = await collector.fetch(
                {
                    "keywords": ["heroin", "tramadol"],
                    "seed_urls": []
                },
                transport
            )

            assert transport.post_called is True
            assert transport.post_url == "https://api.tavily.com/search"

            assert transport.post_payload["api_key"] == "test-key"
            assert transport.post_payload["query"] == "heroin tramadol"

            assert len(records) == 1
            assert records[0]["url"] == "https://example.com/test"
            assert "Heroin vendor" in records[0]["raw_text"]
            assert records[0]["source"] == "tavily_recursive_discovery"

        finally:
            os.environ.pop("TAVILY_API_KEY", None)

    asyncio.run(_inner())


def test_google_discovery_tavily_error():
    async def _inner():
        os.environ["TAVILY_API_KEY"] = "invalid-key"

        try:
            collector = GoogleDiscoveryCollector()

            class MockTransport:
                def __init__(self):
                    self.post_called = False

                async def post(self, url, json=None):
                    self.post_called = True

                    return {
                        "status_code": 401,
                        "text": '{"error": "Unauthorized"}'
                    }

                async def get(self, url):
                    raise AssertionError(
                        "Fallback should not run when a Tavily API key is configured."
                    )

            transport = MockTransport()

            records = await collector.fetch(
                {
                    "keywords": ["heroin"],
                    "seed_urls": []
                },
                transport
            )

            assert transport.post_called is True
            assert records == []
            assert collector.requests_used == 1

        finally:
            os.environ.pop("TAVILY_API_KEY", None)

    asyncio.run(_inner())


def test_google_discovery_empty_keywords_and_seeds():
    async def _inner():
        collector = GoogleDiscoveryCollector()

        class MockTransport:
            def __init__(self):
                self.post_called = False
                self.get_called = False

            async def post(self, url, json=None):
                self.post_called = True
                return {
                    "status_code": 200,
                    "text": '{"results": []}'
                }

            async def get(self, url):
                self.get_called = True
                return {
                    "status_code": 200,
                    "text": "Test page"
                }

        transport = MockTransport()

        records = await collector.fetch(
            {
                "keywords": [],
                "seed_urls": []
            },
            transport
        )

        assert records == []
        assert transport.post_called is False
        assert transport.get_called is False

    asyncio.run(_inner())


def test_google_discovery_without_tavily_key():
    async def _inner():
        os.environ.pop("TAVILY_API_KEY", None)

        collector = GoogleDiscoveryCollector()

        class MockTransport:
            def __init__(self):
                self.urls = []

            async def post(self, url, json=None):
                raise AssertionError(
                    "Tavily should not be called without an API key."
                )

            async def get(self, url):
                self.urls.append(url)

                return {
                    "status_code": 200,
                    "text": "<html><body>Heroin information</body></html>"
                }

        transport = MockTransport()

        records = await collector.fetch(
            {
                "keywords": ["heroin"],
                "seed_urls": []
            },
            transport
        )

        assert len(records) == 1
        assert records[0]["url"] == "https://en.wikipedia.org/wiki/Heroin"
        assert records[0]["raw_text"] == (
            "<html><body>Heroin information</body></html>"
        )
        assert records[0]["source"] == "tavily_search_discovery_osint"

        assert transport.urls == [
            "https://en.wikipedia.org/wiki/Heroin"
        ]

    asyncio.run(_inner())

def test_google_discovery_run_crawl_integration(setup_db, monkeypatch):
    async def _inner():
        db = setup_db

        monkeypatch.setenv("TAVILY_API_KEY", "test-key")

        class MockTransport:
            def __init__(self):
                self.post_called = False
                self.post_payload = None

            async def post(self, url, json=None):
                self.post_called = True
                self.post_payload = json

                return {
                    "status_code": 200,
                    "text": (
                        '{"results": ['
                        '{"title": "Test Intelligence", '
                        '"url": "https://example.com/intelligence", '
                        '"content": "Heroin trafficking investigation involving '
                        'a suspicious shipment."}'
                        ']}'
                    )
                }

            async def get(self, url):
                return {
                    "status_code": 200,
                    "text": "<html><body>Test content</body></html>"
                }

        mock_transport = MockTransport()

        import crawler.orchestration.flows as flows

        original_transport = flows.DirectHTTPTransport
        flows.DirectHTTPTransport = lambda: mock_transport

        try:
            source = db.query(Source).filter(
                Source.name == "Google Integration Test"
            ).first()

            if source:
                db.delete(source)
                db.commit()

            source = Source(
    name="Google Integration Test",
    source_type="GOOGLE_SEARCH_DISCOVERY",
    transport_type="direct",
    config={
        "seed_urls": []
    }
)

            db.add(source)
            db.commit()
            db.refresh(source)

            db.query(RawRecord).delete()
            db.commit()

            run = await run_crawl(
                source_id=source.id,
                db=db
            )

            db.refresh(run)

            print("\n=== GOOGLE INTEGRATION DEBUG ===")
            print("Tavily POST called:", mock_transport.post_called)
            print("Tavily payload:", mock_transport.post_payload)
            print("Run status:", run.status)
            print("URLs attempted:", run.urls_attempted)
            print("Records produced:", run.records_produced)
            print("Records relevant:", run.records_relevant)
            print("Error summary:", run.error_summary)
            print("================================\n")

            assert mock_transport.post_called is True
            assert run.status == "COMPLETED"
            assert run.urls_attempted > 0
            assert run.records_produced > 0

        finally:
            flows.DirectHTTPTransport = original_transport

    asyncio.run(_inner())

def test_google_discovery_recursive_queue(monkeypatch):
    monkeypatch.setenv(
        "TAVILY_API_KEY",
        "test-tavily-key",
    )

    collector = GoogleDiscoveryCollector()

    source_config = {
        "keywords": [
            "tramadol",
            "telegram",
            "vendor",
        ],
        "seed_urls": [],
    }

    queries = []

    class MockTransport:
        def __init__(self):
            self.call_count = 0

        async def post(self, url, json=None):
            self.call_count += 1
            queries.append(json["query"])

            if self.call_count == 1:
                results = [
                    {
                        "url": "https://example.com/page1",
                        "title": "Example Tramadol Vendor",
                        "content": (
                            "A vendor offering tramadol "
                            "through Telegram."
                        ),
                    },
                    {
                        "url": "https://example.org/page2",
                        "title": "Example Marketplace",
                        "content": (
                            "Marketplace content involving "
                            "tramadol."
                        ),
                    },
                ]
            else:
                results = [
                    {
                        "url": "https://newsite.com/page3",
                        "title": "New Tramadol Listing",
                        "content": (
                            "New vendor content involving "
                            "tramadol."
                        ),
                    },
                    {
                        "url": "https://othersite.com/page4",
                        "title": "New Telegram Marketplace",
                        "content": (
                            "New marketplace content involving "
                            "Telegram and tramadol."
                        ),
                    },
                ]

            return {
                "status_code": 200,
                "text": json_module.dumps({
                    "results": results
                }),
            }

    transport = MockTransport()

    first_records = asyncio.run(
        collector.fetch(
            source_config,
            transport,
        )
    )

    state = source_config["_discovery_state"]

    assert len(first_records) == 2
    assert len(queries) == 1

    first_query = queries[0]

    assert len(state["seen_urls"]) == 2
    assert len(state["seen_queries"]) == 1
    assert len(state["query_queue"]) > 0

    second_records = asyncio.run(
        collector.fetch(
            source_config,
            transport,
        )
    )

    assert len(second_records) == 2
    assert len(queries) == 2

    second_query = queries[1]

    assert second_query != first_query

def test_google_discovery_revisits_url_after_cooldown(
    monkeypatch,
):
    monkeypatch.setenv(
        "TAVILY_API_KEY",
        "test-tavily-key",
    )

    collector = GoogleDiscoveryCollector()

    source_config = {
        "keywords": [
            "tramadol",
        ],
        "seed_urls": [],
    }

    class MockTransport:
        async def post(self, url, json=None):
            return {
                "status_code": 200,
                "text": json_module.dumps({
                    "results": [
                        {
                            "url": "https://example.com/page1",
                            "title": "Tramadol Page",
                            "content": (
                                "Example tramadol content."
                            ),
                        }
                    ]
                }),
            }

    transport = MockTransport()

    first_records = asyncio.run(
        collector.fetch(
            source_config,
            transport,
        )
    )

    assert len(first_records) == 1

    state = source_config["_discovery_state"]

    old_time = (
        datetime.now(timezone.utc)
        - timedelta(seconds=61)
    )
    
    state["seen_url_times"][
        "https://example.com/page1"
    ] = old_time.isoformat()
    state["domain_last_seen"]["example.com"] = old_time.isoformat()

    second_records = asyncio.run(
        collector.fetch(
            source_config,
            transport,
        )
    )

    assert len(second_records) == 1

def test_google_discovery_domain_exploration_control(
    monkeypatch,
):
    monkeypatch.setenv(
        "TAVILY_API_KEY",
        "test-tavily-key",
    )

    collector = GoogleDiscoveryCollector()

    source_config = {
        "keywords": [
            "tramadol",
            "telegram",
        ],
        "seed_urls": [],
    }

    class MockTransport:
        async def post(self, url, json=None):
            return {
                "status_code": 200,
                "text": json_module.dumps({
                    "results": [
                        {
                            "url": "https://site-a.com/page1",
                            "title": "Site A One",
                            "content": "Tramadol vendor.",
                        },
                        {
                            "url": "https://site-a.com/page2",
                            "title": "Site A Two",
                            "content": "Telegram vendor.",
                        },
                        {
                            "url": "https://site-a.com/page3",
                            "title": "Site A Three",
                            "content": "Another vendor.",
                        },
                        {
                            "url": "https://site-b.com/page1",
                            "title": "Site B One",
                            "content": "Tramadol listing.",
                        },
                    ]
                }),
            }

    transport = MockTransport()

    records = asyncio.run(
    collector.fetch(
        source_config,
        transport,
    )
)

    site_a_records = [
        record
        for record in records
        if "site-a.com" in record["url"]
    ]

    assert len(site_a_records) <= 2
    assert len(records) == 2

    domains = [
        collector._get_domain(record["url"])
        for record in records
    ]
    assert domains.count("site-a.com") == 1
    assert domains.count("site-b.com") == 1

def test_llm_relevance_classifier_empty_text():
    classifier = LLMRelevanceClassifier(
        api_key="test-key",
        model="gemini-3.6-flash",
    )

    result = asyncio.run(
        classifier.classify("")
    )

    assert result.label == "unrelated"
    assert result.confidence == 1.0
    assert result.indicators == []

def test_llm_relevance_classifier_gemini_response(
    monkeypatch,
):
    classifier = LLMRelevanceClassifier(
        api_key="test-key",
        model="gemini-3.6-flash",
    )

    class MockResponse:
        text = json_module.dumps(
        {
    "label": "relevant",
    "confidence": 0.94,
    "reasoning": (
        "The content describes an illicit transaction."
    ),
    "indicators": [
        "vendor",
        "telegram",
    ],
    "entities": [
        {
            "type": "PERSON",
            "value": "John Doe",
            "role": "vendor",
            "confidence": 0.91,
        },
        {
            "type": "DRUG",
            "value": "tramadol",
            "role": "substance",
            "confidence": 0.99,
        },
    ],
    "relationships": [
        {
            "subject": "John Doe",
            "relation": "OFFERS",
            "object": "tramadol",
            "confidence": 0.93,
        },
    ],
})

    class MockModels:
        async def generate_content(
            self,
            model,
            contents,
            config,
        ):
            assert model == "gemini-3.6-flash"
            assert "tramadol" in contents.lower()
            assert "telegram" in contents.lower()

            return MockResponse()

    mock_models = classifier.client.aio.models

    async def mock_generate_content(
        model,
        contents,
        config,
    ):
        assert model == "gemini-3.6-flash"
        assert "tramadol" in contents.lower()
        assert "telegram" in contents.lower()

        return MockResponse()

    monkeypatch.setattr(
        mock_models,
        "generate_content",
        mock_generate_content,
    )
    result = asyncio.run(
    classifier.classify(
        "A vendor offers tramadol through Telegram.",
        ["tramadol", "telegram"],
        [
            {
                "type": "PERSON",
                "value": "John Doe",
                "confidence": 0.85,
            },
            {
                "type": "DRUG",
                "value": "tramadol",
                "confidence": 0.95,
            },
        ],
    )
)

    assert result.label == "relevant"
    assert result.confidence == 0.94
    
    assert result.reasoning == (
        "The content describes an illicit transaction."
    )
    assert "vendor" in result.indicators
    assert result.indicators == [
        "vendor",
        "telegram",
    ]

    assert result.structured_intelligence["entities"][0]["type"] == "PERSON"
    assert result.structured_intelligence["entities"][0]["role"] == "vendor"

    assert result.structured_intelligence["entities"][1]["type"] == "DRUG"
    assert result.structured_intelligence["entities"][1]["value"] == "tramadol"

    assert (
        result.structured_intelligence["relationships"][0]["subject"]
        == "John Doe"
    )

    assert (
        result.structured_intelligence["relationships"][0]["relation"]
        == "OFFERS"
    )

    assert (
        result.structured_intelligence["relationships"][0]["object"]
        == "tramadol"
    )

def test_llm_relevance_classifier_fallback_without_key():
    classifier = LLMRelevanceClassifier(
        api_key="",
        model="gemini-3.6-flash",
    )

    result = asyncio.run(
        classifier.classify(
            "A vendor offers tramadol through Telegram.",
            ["tramadol", "telegram"],
        )
    )

    assert result.label == "relevant"
    assert result.confidence == 0.6
    assert "fallback" in result.reasoning.lower()

def test_llm_receives_extracted_candidates(monkeypatch):
    monkeypatch.setenv(
        "LLM_API_KEY",
        "test-key",
    )
    monkeypatch.setenv(
        "LLM_MODEL",
        "gemini-3.6-flash",
    )

    classifier = LLMRelevanceClassifier(
        api_key="test-key",
        model="gemini-3.6-flash",
    )

    captured = {}

    class MockResponse:
        text = json_module.dumps({
            "label": "relevant",
            "confidence": 0.92,
            "reasoning": "The source indicates illicit drug activity.",
            "indicators": [
                "vendor",
                "telegram",
            ],
            "entities": [
                {
                    "type": "DRUG",
                    "value": "tramadol",
                    "role": "substance",
                    "confidence": 0.98,
                }
            ],
            "relationships": [],
        })

    class MockModels:
        async def generate_content(
            self,
            model,
            contents,
            config,
        ):
            captured["prompt"] = contents
            return MockResponse()

    mock_models = classifier.client.aio.models

    async def mock_generate_content(
        model,
        contents,
        config,
    ):
        captured["prompt"] = contents
        return MockResponse()

    monkeypatch.setattr(
        mock_models,
        "generate_content",
        mock_generate_content,
    )

    candidates = [
        {
            "type": "DRUG",
            "value": "tramadol",
            "confidence": 0.95,
        },
        {
            "type": "PHONE_NUMBER",
            "value": "+91 9876543210",
            "confidence": 0.90,
        },
    ]

    result = asyncio.run(
        classifier.classify(
            "A vendor offers tramadol through Telegram.",
            ["tramadol", "telegram"],
            candidates,
        )
    )

    assert "Machine-extracted candidate entities" in captured["prompt"]
    assert "tramadol" in captured["prompt"]
    assert "+91 9876543210" in captured["prompt"]

    assert result.label == "relevant"
    assert result.confidence == 0.92
    assert result.structured_intelligence["entities"][0]["type"] == "DRUG"

def test_raw_record_stores_structured_intelligence(setup_db):
    raw_record = RawRecord(
        url="https://example.com/test",
        fetched_at=datetime.now(timezone.utc),
        raw_text="Test content",
        cleaned_text="Test content",
        content_hash="test-structured-intelligence-hash",
        language="en",
        matched_keywords=["tramadol"],
        relevance_label="relevant",
        relevance_confidence=0.95,
        relevance_reasoning="Test reasoning.",
        extracted_candidates=[],
        structured_intelligence={
            "entities": [
                {
                    "type": "DRUG",
                    "value": "tramadol",
                    "role": "substance",
                    "confidence": 0.99,
                }
            ],
            "relationships": [
                {
                    "subject": "Vendor A",
                    "relation": "OFFERS",
                    "object": "tramadol",
                    "confidence": 0.91,
                }
            ],
        },
        status="pending_mapping",
    )

    setup_db.add(raw_record)
    setup_db.commit()
    setup_db.refresh(raw_record)

    assert raw_record.structured_intelligence is not None
    assert (
        raw_record.structured_intelligence["entities"][0]["value"]
        == "tramadol"
    )
    assert (
        raw_record.structured_intelligence["relationships"][0]["relation"]
        == "OFFERS"
    )
def test_entity_extractor():
    extractor = EntityExtractor()

    sample_text = (
        "Vendor John in Chandigarh accepts Bitcoin "
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa and Ethereum "
        "0x71C7656EC7ab88b098defB751B7401B5f6d8976F. "
        "Contact +919876543210."
    )

    candidates = extractor.extract(sample_text)

    types = [c["type"] for c in candidates]
    values = [c["value"] for c in candidates]

    # --------------------------------------------------------------
    # Deterministic regex entities
    # --------------------------------------------------------------

    assert "BITCOIN_ADDRESS" in types
    assert (
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        in values
    )

    assert "ETHEREUM_ADDRESS" in types
    assert (
        "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
        in values
    )

    assert "PHONE_NUMBER" in types
    assert "+919876543210" in values

    # --------------------------------------------------------------
    # NER entities (backend-agnostic: spaCy or GLiNER)
    # --------------------------------------------------------------

    assert "PERSON" in types or "ORG" in types
    assert "John" in values or "Chandigarh" in values

    assert "CRYPTOCURRENCY" in types or "BITCOIN_ADDRESS" in types or "ETHEREUM_ADDRESS" in types
    assert "Bitcoin" in values or "BITCOIN_ADDRESS" in types or "ETHEREUM_ADDRESS" in types

    # --------------------------------------------------------------
    # Confidence/source validation
    # --------------------------------------------------------------

    allowed_sources = {"gliner_ner", "spacy_ner", "bitcoin_regex", "ethereum_regex", "phone_regex"}

    for candidate in candidates:
        if candidate["confidence_source"] == "gliner_ner":
            assert candidate["confidence"] is not None
            assert 0.0 <= candidate["confidence"] <= 1.0
        else:
            assert candidate["confidence"] is None

    assert all(
        candidate["confidence_source"] in allowed_sources
        for candidate in candidates
    )
