"""
Tests for Suspicious Activity Detection and Automated Alert Generation.

Follows existing test patterns:
  - Uses database engine/Base/SessionLocal from database.py
  - Uses TestClient from fastapi.testclient
  - Uses create_access_token for auth headers
  - autouse fixture for DB setup/teardown
"""

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

# Ensure backend is on sys.path (matches existing test convention)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import engine, Base, SessionLocal
from main import app
from models import (
    User, RoleEnum, AccountStatusEnum,
    SuspiciousActivity, SuspiciousActivityStatusEnum,
    Alert, AlertStatusEnum,
)
from security import hash_password, create_access_token
from crawler.models.raw_record import RawRecord
from services.suspicious_activity import detect_suspicious_activity
from services.alert_generation import generate_alert
from services.detection_pipeline import process_raw_records


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_db():
    """Setup fresh DB tables and seed an admin user for each test."""
    os.environ["TESTING"] = "1"
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Seed admin user
    admin = db.query(User).filter(User.email == "detect_test_admin@chandigarhpolice.gov.in").first()
    if not admin:
        admin = User(
            email="detect_test_admin@chandigarhpolice.gov.in",
            full_name="Detection Test Admin",
            password_hash=hash_password("AdminTestPass123!"),
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
    """Create auth headers for the test admin user."""
    db = setup_db
    user = db.query(User).filter(User.email == "detect_test_admin@chandigarhpolice.gov.in").first()
    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    return TestClient(app)


def _make_raw_record(db, **overrides):
    """Helper to create a RawRecord with sensible defaults for testing."""
    defaults = {
        "url": f"http://example.onion/{uuid.uuid4().hex[:8]}",
        "fetched_at": datetime.now(timezone.utc),
        "content_hash": uuid.uuid4().hex,
        "relevance_label": "unrelated",
        "relevance_confidence": 0.5,
        "matched_keywords": [],
        "extracted_candidates": [],
        "status": "pending_mapping",
    }
    defaults.update(overrides)
    record = RawRecord(**defaults)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ── Test 1: Relevant high-confidence record produces suspicious activity ─────

def test_high_confidence_relevant_record_produces_suspicious_activity(setup_db):
    """Rule A: relevant + high confidence → SuspiciousActivity."""
    db = setup_db
    record = _make_raw_record(
        db,
        relevance_label="relevant",
        relevance_confidence=0.92,
        relevance_reasoning="Text contains illicit marketplace indicators.",
        matched_keywords=["vendor", "btc"],
    )

    sa = detect_suspicious_activity(record, db)
    db.commit()

    assert sa is not None
    assert sa.raw_record_id == record.id
    assert float(sa.confidence) >= 0.80
    assert sa.activity_type in ("high_relevance", "combined_signal")
    assert sa.status == SuspiciousActivityStatusEnum.OPEN
    assert sa.description is not None and len(sa.description) > 0


# ── Test 2: Unrelated/low-confidence record does NOT produce suspicious activity ─

def test_low_confidence_unrelated_record_does_not_produce_suspicious_activity(setup_db):
    """Unrelated/low-confidence records should not trigger detection."""
    db = setup_db
    record = _make_raw_record(
        db,
        relevance_label="unrelated",
        relevance_confidence=0.75,
        matched_keywords=[],
        extracted_candidates=[],
    )

    sa = detect_suspicious_activity(record, db)

    assert sa is None

    # Verify nothing was persisted
    count = db.query(SuspiciousActivity).count()
    assert count == 0


# ── Test 3: Suspicious activity contains explainable evidence ────────────────

def test_suspicious_activity_has_explainable_evidence(setup_db):
    """evidence_summary must contain score and reasons array."""
    db = setup_db
    record = _make_raw_record(
        db,
        relevance_label="relevant",
        relevance_confidence=0.92,
        relevance_reasoning="Illicit marketplace signals detected.",
        matched_keywords=["vendor", "btc", "escrow", "stealth"],
        extracted_candidates=[
            {"type": "BITCOIN_ADDRESS", "value": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "confidence": 0.98},
        ],
    )

    sa = detect_suspicious_activity(record, db)
    db.commit()

    assert sa is not None
    evidence = sa.evidence_summary
    assert evidence is not None
    assert "score" in evidence
    assert "reasons" in evidence
    assert isinstance(evidence["reasons"], list)
    assert len(evidence["reasons"]) > 0

    # With multiple rules firing, evidence should have signals breakdown
    assert "signals" in evidence
    assert isinstance(evidence["signals"], list)
    assert len(evidence["signals"]) >= 1


# ── Test 4: High-risk suspicious activity produces an Alert ──────────────────

def test_high_risk_suspicious_activity_produces_alert(setup_db):
    """High-confidence SuspiciousActivity → Alert with appropriate severity."""
    db = setup_db
    record = _make_raw_record(
        db,
        relevance_label="relevant",
        relevance_confidence=0.92,
        matched_keywords=["vendor", "btc", "escrow"],
    )

    sa = detect_suspicious_activity(record, db)
    db.commit()
    assert sa is not None

    alert = generate_alert(sa, db)
    db.commit()

    assert alert is not None
    assert alert.suspicious_activity_id == sa.id
    assert alert.raw_record_id == record.id
    assert alert.severity in ("red", "yellow", "green")
    assert alert.message is not None and len(alert.message) > 0
    assert alert.status == AlertStatusEnum.ACTIVE
    assert alert.dedup_key is not None

    # Verify severity is consistent with confidence
    conf = float(sa.confidence)
    if conf >= 0.85:
        assert alert.severity == "red"
    elif conf >= 0.60:
        assert alert.severity == "yellow"
    else:
        assert alert.severity == "green"


# ── Test 5: Reprocessing same record does NOT create duplicate alerts ────────

def test_reprocessing_same_record_no_duplicate_alerts(setup_db):
    """Deduplication: processing the same record twice → single alert."""
    db = setup_db
    record = _make_raw_record(
        db,
        relevance_label="relevant",
        relevance_confidence=0.92,
        matched_keywords=["vendor", "btc", "escrow"],
    )

    # First pass
    sa1 = detect_suspicious_activity(record, db)
    db.commit()
    assert sa1 is not None
    alert1 = generate_alert(sa1, db)
    db.commit()
    assert alert1 is not None

    # Second pass — should detect existing and skip
    sa2 = detect_suspicious_activity(record, db)
    db.commit()
    assert sa2 is not None  # Returns existing
    assert sa2.id == sa1.id  # Same object

    alert2 = generate_alert(sa2, db)
    db.commit()
    assert alert2 is None  # Deduplicated

    # Verify only one alert exists
    alert_count = db.query(Alert).count()
    assert alert_count == 1


# ── Test 6: GET /api/alerts returns DB-backed alerts ─────────────────────────

def test_get_alerts_endpoint_db_backed(setup_db, auth_headers, client):
    """GET /api/alerts returns DB-backed alerts with correct shape."""
    db = setup_db

    # Create a test record and run detection pipeline
    record = _make_raw_record(
        db,
        relevance_label="relevant",
        relevance_confidence=0.92,
        matched_keywords=["vendor", "btc", "escrow"],
    )
    sa = detect_suspicious_activity(record, db)
    db.commit()
    alert = generate_alert(sa, db)
    db.commit()
    assert alert is not None

    # Hit the endpoint
    response = client.get("/api/alerts", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    # Verify shape matches frontend contract
    first = data[0]
    assert "id" in first
    assert "severity" in first
    assert "message" in first
    assert "timestamp" in first
    assert first["severity"] in ("red", "yellow", "green")


# ── Test 7: GET /api/alerts/suspicious returns DB-backed activities ──────────

def test_get_suspicious_endpoint_db_backed(setup_db, auth_headers, client):
    """GET /api/alerts/suspicious returns DB-backed suspicious activities."""
    db = setup_db

    record = _make_raw_record(
        db,
        relevance_label="relevant",
        relevance_confidence=0.88,
        matched_keywords=["vendor", "escrow", "btc"],
    )
    sa = detect_suspicious_activity(record, db)
    db.commit()
    assert sa is not None

    response = client.get("/api/alerts/suspicious", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    # Verify shape matches frontend contract
    first = data[0]
    assert "id" in first
    assert "type" in first
    assert "description" in first
    assert "confidence" in first
    assert "date" in first


# ── Test 8: Unauthenticated requests are protected ──────────────────────────

def test_unauthenticated_access_protected(client):
    """Both endpoints reject unauthenticated requests."""
    response_alerts = client.get("/api/alerts")
    assert response_alerts.status_code in (401, 403)

    response_suspicious = client.get("/api/alerts/suspicious")
    assert response_suspicious.status_code in (401, 403)


# ── Test 9: Empty DB returns valid empty arrays ──────────────────────────────

def test_empty_db_returns_empty_arrays(setup_db, auth_headers, client):
    """Endpoints return [] when no alerts/suspicious activities exist."""
    response_alerts = client.get("/api/alerts", headers=auth_headers)
    assert response_alerts.status_code == 200
    assert response_alerts.json() == []

    response_suspicious = client.get("/api/alerts/suspicious", headers=auth_headers)
    assert response_suspicious.status_code == 200
    assert response_suspicious.json() == []


# ── Test 10: Detection pipeline processes records end-to-end ─────────────────

def test_detection_pipeline_processes_records(setup_db):
    """process_raw_records() runs detection + alert generation end-to-end."""
    db = setup_db

    # Create a high-risk record
    _make_raw_record(
        db,
        relevance_label="relevant",
        relevance_confidence=0.92,
        matched_keywords=["vendor", "btc", "escrow", "stealth"],
    )

    # Create a benign record
    _make_raw_record(
        db,
        relevance_label="unrelated",
        relevance_confidence=0.30,
        matched_keywords=[],
    )

    summary = process_raw_records(db)

    assert summary["records_processed"] == 2
    assert summary["suspicious_activities_created"] >= 1
    assert summary["alerts_created"] >= 1
    assert summary["errors"] == 0

    # Verify DB state
    sa_count = db.query(SuspiciousActivity).count()
    assert sa_count >= 1
    alert_count = db.query(Alert).count()
    assert alert_count >= 1


# ── Test 11: Keyword-only detection (Rule B) ─────────────────────────────────

def test_keyword_burst_detection(setup_db):
    """Rule B: 3+ keywords without high relevance → keyword_burst detection."""
    db = setup_db
    record = _make_raw_record(
        db,
        relevance_label="medical_legitimate",
        relevance_confidence=0.50,
        matched_keywords=["vendor", "btc", "escrow", "stealth", "wickr"],
    )

    sa = detect_suspicious_activity(record, db)
    db.commit()

    assert sa is not None
    assert sa.activity_type == "keyword_burst"
    assert float(sa.confidence) >= 0.60
