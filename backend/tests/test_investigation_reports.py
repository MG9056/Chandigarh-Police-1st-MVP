"""
test_investigation_reports.py — Comprehensive test suite for Phase 1 Reports & Evidence backend.

Covers:
A. Authenticated + authorized + recently re-authenticated user can generate a report
B. Missing or invalid re-authentication returns 403 REAUTH_REQUIRED
C. Unauthorized user cannot generate report (403 Forbidden)
D. Nonexistent investigation returns 404
E. Generated report is grounded in supplied evidence (contains citations linking to source evidence)
F. Original evidence/source information is not overwritten (immutability preserved)
G. REPORT_GENERATED audit event is created on success
H. Audit metadata does not contain API keys, secrets, passwords, or full raw evidence
I. Missing LLM API key fails gracefully with 503 and records failure audit log
"""

import json
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from database import SessionLocal, init_db
from main import app
from models import (
    AccountStatusEnum,
    AuditLog,
    DataProvenance,
    Investigation,
    InvestigationFinding,
    InvestigationFindingStatus,
    RawRecord,
    Report,
    RoleEnum,
    User,
)
from security import create_access_token, create_reauth_token
from services.ai_service import ai_service

client = TestClient(app)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    init_db()
    session = SessionLocal()
    yield session
    session.close()


def _make_user(db, role: str, unit: str = "Cyber Crime Cell", suffix: str = None) -> User:
    sfx = suffix or uuid.uuid4().hex[:6]
    user = User(
        email=f"report_test_{role.lower().replace(' ', '_').replace('/', '_')}_{sfx}@police.gov",
        full_name=f"Officer {role} {sfx}",
        password_hash="hashed_pass",
        role=role,
        unit=unit,
        account_status=AccountStatusEnum.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_headers(user: User, with_reauth: bool = True) -> dict:
    """Generates authentication headers and cookies for TestClient."""
    access_token = create_access_token(data={"sub": str(user.id), "type": "access"})
    headers = {"Authorization": f"Bearer {access_token}"}
    cookies = {"access_token": access_token}

    if with_reauth:
        reauth_token = create_reauth_token(user.id)
        headers["X-ReAuth-Token"] = reauth_token
        cookies["reauth_token"] = reauth_token

    return {"headers": headers, "cookies": cookies}


def _make_investigation_with_evidence(db, created_by: User, unit: str = "Cyber Crime Cell"):
    """Helper to set up an investigation with 1 raw record, 1 relevant finding, and 1 promoted provenance."""
    inv_id = f"TEST-REP-{uuid.uuid4().hex[:6].upper()}"
    inv = Investigation(
        investigation_id=inv_id,
        title="Drug Trafficking Ring Investigation",
        description="Investigation into illicit narcotics distribution on darknet marketplaces.",
        case_type="Narcotics",
        status="OPEN",
        priority=3,
        created_by_id=created_by.id,
        lead_investigator_id=created_by.id,
        unit=unit,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)

    raw_rec = RawRecord(
        case_id=inv.investigation_id,
        url="http://hydra-market.onion/listing/9842",
        raw_text="Vendor AlphaX offering bulk pharmaceutical shipments to Chandigarh sector 17.",
        cleaned_text="Vendor AlphaX offering bulk pharmaceutical shipments to Chandigarh sector 17.",
        content_hash="sha256_mock_hash_abc123",
        matched_keywords=["bulk", "pharmaceutical", "Chandigarh"],
        relevance_label="high_relevance",
        fetched_at=datetime.now(timezone.utc),
    )
    db.add(raw_rec)
    db.commit()
    db.refresh(raw_rec)

    finding = InvestigationFinding(
        investigation_id=inv.id,
        raw_record_id=str(raw_rec.id),
        review_status=InvestigationFindingStatus.RELEVANT,
        review_notes="Confirmed vendor references target area Sector 17.",
        reviewed_by_id=created_by.id,
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)

    provenance = DataProvenance(
        source_type="Darknet",
        source_name="Hydra Market",
        source_identifier=str(raw_rec.id),
        source_url=raw_rec.url,
        collection_method="Authorized crawler collection",
        investigation_id=inv.investigation_id,
        original_record_reference=str(finding.raw_record_id),
        integrity_hash=raw_rec.content_hash,
        finding_id=finding.id,
        raw_record_id=str(raw_rec.id),
        promoted_by_id=created_by.id,
        promoted_at=datetime.now(timezone.utc),
    )
    db.add(provenance)
    db.commit()
    db.refresh(provenance)

    return inv, finding, provenance, raw_rec


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_generate_report_success(db, monkeypatch):
    """
    Scenario A & E:
    Authenticated, authorized (lead inspector), recently re-authenticated user can generate report.
    Generated report contains evidence grounding citations [EVIDENCE-1].
    """
    inspector = _make_user(db, RoleEnum.INSPECTOR)
    inv, finding, provenance, raw_rec = _make_investigation_with_evidence(db, created_by=inspector)

    # Mock AIService.generate_text to return structured JSON grounded in [EVIDENCE-1]
    mock_response = json.dumps({
        "title": f"Official Intelligence Report: {inv.title}",
        "executive_summary": "Analysis of darknet narcotics vendor AlphaX active in Sector 17.",
        "investigation_overview": "Case focused on localized contraband distribution.",
        "key_findings": [
            {
                "finding": "Vendor AlphaX advertised bulk pharmaceutical shipments destined for Chandigarh.",
                "citations": ["[EVIDENCE-1]"],
                "verification_level": "VERIFIED_EVIDENCE"
            }
        ],
        "evidence_summary": "1 darknet listing analyzed.",
        "entity_suspect_information": [
            {
                "identifier": "AlphaX",
                "role_or_activity": "Vendor / Distributor",
                "citations": ["[EVIDENCE-1]"],
                "notes": "Targeting Sector 17"
            }
        ],
        "timeline": [
            {
                "timestamp": "2026-09-07",
                "event": "Vendor listing discovered on Hydra Market",
                "citations": ["[EVIDENCE-1]"],
                "source": "Hydra Market"
            }
        ],
        "intelligence_assessment": "Recommend physical surveillance in Sector 17 transit hubs.",
        "source_and_evidence_references": [
            {
                "citation": "[EVIDENCE-1]",
                "source_type": "Darknet",
                "source_name": "Hydra Market",
                "description": "Vendor listing 9842"
            }
        ],
        "ai_disclaimer": "AI-assisted synthesis from verified evidence."
    })

    monkeypatch.setattr(ai_service, "generate_text", lambda *args, **kwargs: (mock_response, "gemini-3.6-flash"))

    auth = _auth_headers(inspector, with_reauth=True)
    res = client.post(
        f"/api/investigations/{inv.investigation_id}/reports",
        json={"title": "Custom Test Report Title"},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )

    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["report_id"].startswith(f"REP-{inv.investigation_id}")
    assert data["title"] == "Custom Test Report Title"
    assert data["model_used"] == "gemini-3.6-flash"
    assert "[EVIDENCE-1]" in data["evidence_references"]

    # Verify report is persisted in database
    db_report = db.query(Report).filter(Report.report_id == data["report_id"]).first()
    assert db_report is not None
    assert db_report.investigation_id == inv.investigation_id
    assert db_report.created_by_id == inspector.id


def test_generate_report_missing_reauth_rejected(db):
    """
    Scenario B:
    Request with valid session but WITHOUT recent re-authentication must be rejected with 403 REAUTH_REQUIRED.
    """
    inspector = _make_user(db, RoleEnum.INSPECTOR)
    inv, _, _, _ = _make_investigation_with_evidence(db, created_by=inspector)

    auth = _auth_headers(inspector, with_reauth=False)  # No re-auth cookie/header
    res = client.post(
        f"/api/investigations/{inv.investigation_id}/reports",
        json={},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )

    assert res.status_code == 403
    assert res.json().get("detail") == "REAUTH_REQUIRED"


def test_generate_report_unauthorized_user_rejected(db):
    """
    Scenario C:
    Unauthorized user (Constable or officer from another unit without grant) cannot generate report.
    """
    inspector = _make_user(db, RoleEnum.INSPECTOR, unit="Cyber Crime Cell")
    inv, _, _, _ = _make_investigation_with_evidence(db, created_by=inspector, unit="Cyber Crime Cell")

    # Constable (only has READ permission, no investigation modification access)
    constable = _make_user(db, RoleEnum.CONSTABLE, unit="Cyber Crime Cell")
    auth_constable = _auth_headers(constable, with_reauth=True)

    res = client.post(
        f"/api/investigations/{inv.investigation_id}/reports",
        json={},
        headers=auth_constable["headers"],
        cookies=auth_constable["cookies"],
    )
    assert res.status_code == 403
    assert "permission" in res.json().get("detail", "").lower()

    # Inspector from another unit without assignment or grant
    other_inspector = _make_user(db, RoleEnum.INSPECTOR, unit="Traffic Branch")
    auth_other = _auth_headers(other_inspector, with_reauth=True)

    res_other = client.post(
        f"/api/investigations/{inv.investigation_id}/reports",
        json={},
        headers=auth_other["headers"],
        cookies=auth_other["cookies"],
    )
    assert res_other.status_code == 403


def test_generate_report_nonexistent_investigation(db):
    """
    Scenario D:
    Attempting report generation on a nonexistent investigation ID returns 404.
    """
    dgp = _make_user(db, RoleEnum.SUPER_ADMIN)
    auth = _auth_headers(dgp, with_reauth=True)

    res = client.post(
        "/api/investigations/NON-EXISTENT-CASE-9999/reports",
        json={},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert res.status_code == 404
    assert "not found" in res.json().get("detail", "").lower()


def test_immutability_of_original_evidence(db, monkeypatch):
    """
    Scenario F:
    Generating a report MUST NOT alter, overwrite, or delete original RawRecord,
    InvestigationFinding, or DataProvenance records.
    """
    inspector = _make_user(db, RoleEnum.INSPECTOR)
    inv, finding, provenance, raw_rec = _make_investigation_with_evidence(db, created_by=inspector)

    original_finding_status = finding.review_status
    original_finding_notes = finding.review_notes
    original_raw_text = raw_rec.raw_text
    original_provenance_hash = provenance.integrity_hash

    # Mock LLM
    mock_json = json.dumps({
        "title": "Immutability Verification",
        "executive_summary": "Summary",
        "investigation_overview": "Overview",
        "key_findings": [{"finding": "Finding 1", "citations": ["[EVIDENCE-1]"]}],
        "evidence_summary": "1 item",
        "entity_suspect_information": [],
        "timeline": [],
        "intelligence_assessment": "Assessment",
        "source_and_evidence_references": [],
        "ai_disclaimer": "Disclaimer"
    })
    monkeypatch.setattr(ai_service, "generate_text", lambda *args, **kwargs: (mock_json, "gemini-3.6-flash"))

    auth = _auth_headers(inspector, with_reauth=True)
    res = client.post(
        f"/api/investigations/{inv.investigation_id}/reports",
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert res.status_code == 201

    # Re-query DB objects directly to verify unchanged state
    db.expire_all()
    re_finding = db.query(InvestigationFinding).filter(InvestigationFinding.id == finding.id).first()
    re_provenance = db.query(DataProvenance).filter(DataProvenance.id == provenance.id).first()
    re_raw = db.query(RawRecord).filter(RawRecord.id == raw_rec.id).first()

    assert re_finding.review_status == original_finding_status
    assert re_finding.review_notes == original_finding_notes
    assert re_raw.raw_text == original_raw_text
    assert re_provenance.integrity_hash == original_provenance_hash


def test_audit_event_created_and_sanitized(db, monkeypatch):
    """
    Scenario G & H:
    REPORT_GENERATED audit log is created with SUCCESS.
    Audit metadata does NOT contain API keys, passwords, tokens, or raw evidence dumps.
    """
    dgp = _make_user(db, RoleEnum.SUPER_ADMIN)
    inv, _, _, _ = _make_investigation_with_evidence(db, created_by=dgp)

    mock_json = json.dumps({
        "title": "Audit Test",
        "executive_summary": "Exec summary",
        "investigation_overview": "Overview",
        "key_findings": [{"finding": "Claim", "citations": ["[EVIDENCE-1]"]}],
        "evidence_summary": "Summary",
        "entity_suspect_information": [],
        "timeline": [],
        "intelligence_assessment": "Assessment",
        "source_and_evidence_references": [],
        "ai_disclaimer": "Disclaimer"
    })
    monkeypatch.setattr(ai_service, "generate_text", lambda *args, **kwargs: (mock_json, "gemini-3.6-flash"))

    auth = _auth_headers(dgp, with_reauth=True)
    res = client.post(
        f"/api/investigations/{inv.investigation_id}/reports",
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert res.status_code == 201
    report_id = res.json()["report_id"]

    # Verify audit entry
    audit_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "REPORT_GENERATED",
            AuditLog.resource_id == inv.investigation_id,
            AuditLog.result == "SUCCESS",
        )
        .order_by(AuditLog.timestamp.desc())
        .first()
    )

    assert audit_log is not None
    assert audit_log.user_id == dgp.id
    assert audit_log.role == RoleEnum.SUPER_ADMIN

    meta_str = audit_log.metadata_json or ""
    assert report_id in meta_str
    # Verify strict sanitization: no secrets or evidence bodies in metadata
    assert "LLM_API_KEY" not in meta_str
    assert "api_key" not in meta_str
    assert "password" not in meta_str
    assert "secret" not in meta_str
    assert "bulk pharmaceutical shipments" not in meta_str


def test_missing_llm_api_key_fails_gracefully(db, monkeypatch):
    """
    Scenario I:
    When LLM_API_KEY is not configured, the service fails gracefully:
    - Returns HTTP 503 Service Unavailable with a clean message
    - Logs a REPORT_GENERATED audit event with result="FAILURE"
    - Does not crash with an unhandled 500 error
    """
    inspector = _make_user(db, RoleEnum.INSPECTOR)
    inv, _, _, _ = _make_investigation_with_evidence(db, created_by=inspector)

    # Force AIService.generate_text to raise RuntimeError("LLM_API_KEY_NOT_CONFIGURED")
    def _raise_unconfigured(*args, **kwargs):
        raise RuntimeError("LLM_API_KEY_NOT_CONFIGURED")

    monkeypatch.setattr(ai_service, "generate_text", _raise_unconfigured)

    auth = _auth_headers(inspector, with_reauth=True)
    res = client.post(
        f"/api/investigations/{inv.investigation_id}/reports",
        headers=auth["headers"],
        cookies=auth["cookies"],
    )

    assert res.status_code == 503
    assert "LLM_API_KEY" in res.json().get("detail", "") or "unavailable" in res.json().get("detail", "").lower()

    # Check failure audit entry was created
    fail_audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "REPORT_GENERATED",
            AuditLog.resource_id == inv.investigation_id,
            AuditLog.result == "FAILURE",
        )
        .order_by(AuditLog.timestamp.desc())
        .first()
    )
    assert fail_audit is not None
    assert fail_audit.result == "FAILURE"
    assert "LLM_API_KEY" not in (fail_audit.metadata_json or "")


def test_list_and_get_reports(db, monkeypatch):
    """
    Verifies GET /api/investigations/{investigation_id}/reports and
    GET /api/investigations/{investigation_id}/reports/{report_id}.
    """
    inspector = _make_user(db, RoleEnum.INSPECTOR)
    inv, _, _, _ = _make_investigation_with_evidence(db, created_by=inspector)

    mock_json = json.dumps({
        "title": "List/Get Test Report",
        "executive_summary": "Exec summary text",
        "investigation_overview": "Overview text",
        "key_findings": [{"finding": "Finding 1", "citations": ["[EVIDENCE-1]"]}],
        "evidence_summary": "1 item",
        "entity_suspect_information": [],
        "timeline": [],
        "intelligence_assessment": "Assessment text",
        "source_and_evidence_references": [],
        "ai_disclaimer": "Disclaimer text"
    })
    monkeypatch.setattr(ai_service, "generate_text", lambda *args, **kwargs: (mock_json, "gemini-3.6-flash"))

    auth = _auth_headers(inspector, with_reauth=True)
    create_res = client.post(
        f"/api/investigations/{inv.investigation_id}/reports",
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert create_res.status_code == 201
    report_id = create_res.json()["report_id"]

    # List reports
    list_res = client.get(
        f"/api/investigations/{inv.investigation_id}/reports",
        headers=auth["headers"],
    )
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    report_ids = [r["report_id"] for r in list_data["reports"]]
    assert report_id in report_ids

    # Get specific report
    get_res = client.get(
        f"/api/investigations/{inv.investigation_id}/reports/{report_id}",
        headers=auth["headers"],
    )
    assert get_res.status_code == 200
    report_data = get_res.json()
    assert report_data["report_id"] == report_id
    assert report_data["title"] == "List/Get Test Report"
    assert report_data["structured_data"] is not None
    assert "[EVIDENCE-1]" in report_data["evidence_references"]
