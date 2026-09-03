import pytest
import os
import sys
from datetime import datetime, timezone, timedelta

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import engine, Base, SessionLocal
from models import User, RefreshSession, InvestigationAccessGrant, AuditLog, DataProvenance, RoleEnum, AccountStatusEnum
from security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, hash_token,
    create_reauth_token, decode_jwt_token,
    generate_totp_secret, verify_totp_code,
    generate_recovery_codes, verify_and_consume_recovery_code
)

@pytest.fixture(scope="module")
def db_session():
    # Setup in-memory SQLite for testing
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_password_hashing():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_jwt_access_and_reauth_tokens():
    payload = {"sub": "1", "role": RoleEnum.SP}
    token = create_access_token(payload)
    decoded = decode_jwt_token(token)
    assert decoded is not None
    assert decoded["sub"] == "1"
    assert decoded["role"] == RoleEnum.SP
    assert decoded["type"] == "access"

    reauth_token = create_reauth_token(user_id=1)
    decoded_reauth = decode_jwt_token(reauth_token)
    assert decoded_reauth is not None
    assert decoded_reauth["sub"] == "1"
    assert decoded_reauth["type"] == "reauth"

def test_refresh_token_generation():
    raw_token, token_hash = create_refresh_token()
    assert len(raw_token) > 20
    assert hash_token(raw_token) == token_hash

def test_totp_and_recovery_codes():
    secret = generate_totp_secret()
    assert len(secret) == 32

    raw_codes, hashed_codes_json = generate_recovery_codes()
    assert len(raw_codes) == 8
    
    # Verify valid recovery code consumption
    first_code = raw_codes[0]
    valid, updated_json = verify_and_consume_recovery_code(first_code, hashed_codes_json)
    assert valid is True
    
    # Verify same code cannot be reused (one-time single-use constraint)
    valid_retry, _ = verify_and_consume_recovery_code(first_code, updated_json)
    assert valid_retry is False

def test_db_models_creation(db_session):
    # Test User creation
    user = User(
        email="test_inspector@chandigarhpolice.gov.in",
        full_name="Inspector R. Sharma",
        badge_number="CP-8842",
        unit="Cyber Crime Cell",
        password_hash=hash_password("CyberInspector123!"),
        role=RoleEnum.INSPECTOR,
        account_status=AccountStatusEnum.ACTIVE
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.role == RoleEnum.INSPECTOR
    assert user.account_status == AccountStatusEnum.ACTIVE

    # Test RefreshSession creation
    _, token_hash = create_refresh_token()
    session_obj = RefreshSession(
        user_id=user.id,
        refresh_token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        ip_address="192.168.1.10"
    )
    db_session.add(session_obj)

    # Test InvestigationAccessGrant creation with composite index
    grant = InvestigationAccessGrant(
        investigation_id="INV-2026-001",
        user_id=user.id,
        granted_by=1,
        permission="MODIFY"
    )
    db_session.add(grant)

    # Test AuditLog creation
    audit = AuditLog(
        user_id=user.id,
        role=user.role,
        action="LOGIN_SUCCESS",
        result="SUCCESS",
        ip_address="192.168.1.10"
    )
    db_session.add(audit)

    # Test DataProvenance creation
    provenance = DataProvenance(
        source_type="Darknet Forum",
        source_name="Dread Archive",
        source_identifier="post_9921",
        collection_method="Authorized automated collection",
        integrity_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    db_session.add(provenance)

    db_session.commit()

    assert session_obj.id is not None
    assert grant.id is not None
    assert audit.id is not None
    assert provenance.id is not None
