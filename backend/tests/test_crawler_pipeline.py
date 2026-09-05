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
    Base.metadata.drop_all(bind=engine)


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
    sample_text = "Vendor John in Chandigarh accepts Bitcoin 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa and Ethereum 0x71C7656EC7ab88b098defB751B7401B5f6d8976F. Contact +919876543210."

    candidates = extractor.extract(sample_text)
    types = [c["type"] for c in candidates]
    values = [c["value"] for c in candidates]

    assert "BITCOIN_ADDRESS" in types
    assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in values
    assert "ETHEREUM_ADDRESS" in types
    assert "0x71C7656EC7ab88b098defB751B7401B5f6d8976F" in values
    assert "PHONE_NUMBER" in types


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

def test_end_to_end_crawl_flow(setup_db):
    async def _inner():
        db = setup_db

        source = Source(
            name="Test Seed Source",
            source_type="DIRECT_SEED",
            config={"seed_urls": ["https://example.com/drugs"]},
            poll_interval_seconds=30,
            crawl_delay_seconds=0.5,
            is_active=True,
        )
        db.add(source)
        db.commit()

        KeywordService.add_global(db, term="heroin", language="en")

        run = await run_crawl(source_id=str(source.id), case_id="CASE-202", db=db)
        assert run.status == "COMPLETED"

        records = db.query(RawRecord).filter(RawRecord.run_id == run.id).all()
        assert isinstance(records, list)

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
            assert records[0]["source"] == "tavily_search_discovery"

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
        async def post(self, url, json=None):
            queries.append(json["query"])

            return {
                "status_code": 200,
                "text": json_module.dumps({
                    "results": [
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

    second_records = asyncio.run(
        collector.fetch(
            source_config,
            transport,
        )
    )

    assert len(second_records) == 1
