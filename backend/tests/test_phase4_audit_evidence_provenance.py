import pytest
import os
import sys
import hashlib
from datetime import datetime, timezone
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from database import engine, Base, SessionLocal, get_db
from models import User, AuditLog, DataProvenance, RoleEnum, AccountStatusEnum
from security import hash_password
from audit_service import create_audit_log, sanitize_metadata

# Override DB session for testing
def override_get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def setup_senior_officer():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    officer = User(
        email="senior_audit_officer@chandigarhpolice.gov.in",
        full_name="Inspector S. Vault",
        password_hash=hash_password("VaultPassword123!"),
        role=RoleEnum.SUPER_ADMIN,
        account_status=AccountStatusEnum.ACTIVE
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)

    yield officer

    db.close()
    Base.metadata.drop_all(bind=engine)

def test_audit_metadata_sanitization():
    raw_meta = {
        "investigation_id": "INV-2026-001",
        "password": "UnsanitizedPassword123!",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "target_user": "officer@chandigarhpolice.gov.in"
    }
    sanitized_json = sanitize_metadata(raw_meta)
    assert "[REDACTED]" in sanitized_json
    assert "UnsanitizedPassword123!" not in sanitized_json
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." not in sanitized_json

def test_audit_log_query_and_export(setup_senior_officer):
    with TestClient(app) as client:
        # Login
        login_res = client.post("/api/auth/login", json={
            "email": "senior_audit_officer@chandigarhpolice.gov.in",
            "password": "VaultPassword123!"
        })
        assert login_res.status_code == 200
        client.cookies.update(login_res.cookies)

        # Query audit logs without reauth -> 403
        res_no_reauth = client.get("/api/audit-logs")
        assert res_no_reauth.status_code == 403

        # Re-authenticate
        reauth_res = client.post(
            "/api/auth/reauthenticate",
            json={"password": "VaultPassword123!"}
        )
        assert reauth_res.status_code == 200
        client.cookies.update(reauth_res.cookies)

        # Query audit logs with reauth -> SUCCESS
        res_logs = client.get("/api/audit-logs")
        assert res_logs.status_code == 200
        assert isinstance(res_logs.json(), list)

        # Export audit CSV with reauth -> SUCCESS
        res_export = client.get("/api/audit-logs/export")
        assert res_export.status_code == 200
        assert "text/csv" in res_export.headers["content-type"]
        assert "ID,Timestamp" in res_export.text

def test_evidence_download_and_integrity_hash(setup_senior_officer):
    with TestClient(app) as client:
        login_res = client.post("/api/auth/login", json={
            "email": "senior_audit_officer@chandigarhpolice.gov.in",
            "password": "VaultPassword123!"
        })
        assert login_res.status_code == 200
        client.cookies.update(login_res.cookies)
        
        res_evidence = client.get("/api/evidence/EV-9921/download")
        assert res_evidence.status_code == 200
        assert "X-Evidence-Integrity-SHA256" in res_evidence.headers
        
        # Verify content hash matches header
        content_hash = hashlib.sha256(res_evidence.content).hexdigest()
        assert res_evidence.headers["X-Evidence-Integrity-SHA256"] == content_hash

def test_data_provenance_recording(setup_senior_officer):
    with TestClient(app) as client:
        login_res = client.post("/api/auth/login", json={
            "email": "senior_audit_officer@chandigarhpolice.gov.in",
            "password": "VaultPassword123!"
        })
        assert login_res.status_code == 200
        client.cookies.update(login_res.cookies)

        prov_payload = {
            "source_type": "Darknet Forum",
            "source_name": "Dread Market",
            "source_identifier": "listing-88412",
            "source_url": "http://dread4j62qdeao...onion/post/88412",
            "collection_method": "Authorized automated scraper node",
            "investigation_id": "INV-2026-001",
            "raw_content": "Raw listings text describing illicit drug sales"
        }

        res_create = client.post("/api/provenance", json=prov_payload)
        assert res_create.status_code == 201
        data = res_create.json()
        assert data["integrity_hash"] is not None

        # Fetch recorded provenance
        res_get = client.get(f"/api/provenance/{data['provenance_id']}")
        assert res_get.status_code == 200
        assert res_get.json()["source_name"] == "Dread Market"
